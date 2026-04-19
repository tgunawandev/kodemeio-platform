"""kctl-odoo roles — declarative role management.

See kodemeio-docs/superpowers/specs/2026-04-19-role-standardization-design.md
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.roles import (
    RoleDbState,
    RolesFile,
    SyncAction,
    load_ignored_file,
    load_roles_file,
    plan_menu_visibility,
    plan_sync,
    resolve_role_groups,
    resolve_xmlids,
)

app = typer.Typer(help="Declarative role management via install/roles.yaml")
console = Console()


def _get_client(ctx: typer.Context):
    """Return the Odoo client from typer context (indirection for test mocking)."""
    app_ctx: AppContext = ctx.obj
    return app_ctx.client


@app.command("list")
def list_cmd(ctx: typer.Context) -> None:
    """List roles currently in the DB with user counts."""
    client = _get_client(ctx)
    roles = client.search_read("res.users.role", [], fields=["id", "name", "implied_ids"])
    if not roles:
        console.print("[yellow]No roles configured in this DB.[/yellow]")
        return

    table = Table(title=f"Roles ({len(roles)})")
    table.add_column("ID", justify="right")
    table.add_column("Name")
    table.add_column("Groups", justify="right")
    table.add_column("Users", justify="right")

    for role in roles:
        lines = client.search_read(
            "res.users.role.line",
            [("role_id", "=", role["id"])],
            fields=["user_id"],
        )
        table.add_row(
            str(role["id"]),
            role["name"],
            str(len(role["implied_ids"])),
            str(len(lines)),
        )
    console.print(table)


@app.command("show")
def show_cmd(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Role name (case-sensitive)"),
) -> None:
    """Show role detail: groups, implied groups, assigned users."""
    client = _get_client(ctx)
    roles = client.search_read(
        "res.users.role",
        [("name", "=", name)],
        fields=["id", "name", "implied_ids"],
    )
    if not roles:
        console.print(f"[red]Role '{name}' not found.[/red]")
        raise typer.Exit(1)

    role = roles[0]
    console.print(f"[bold]Role:[/bold] {role['name']} (id={role['id']})")

    if role["implied_ids"]:
        groups = client.read("res.groups", role["implied_ids"], fields=["name", "full_name"])
        group_table = Table(title="Groups")
        group_table.add_column("ID", justify="right")
        group_table.add_column("Full Name")
        for g in groups:
            group_table.add_row(str(g["id"]), g.get("full_name") or g["name"])
        console.print(group_table)
    else:
        console.print("[dim]No groups.[/dim]")

    user_lines = client.search_read(
        "res.users.role.line",
        [("role_id", "=", role["id"])],
        fields=["user_id"],
    )
    if user_lines:
        users_str = ", ".join(line["user_id"][1] for line in user_lines if line.get("user_id"))
        console.print(f"[bold]Users ({len(user_lines)}):[/bold] {users_str}")
    else:
        console.print("[dim]No users assigned.[/dim]")

    # Hidden menus via base_menu_visibility_restriction — look up the role's
    # backing group, then find top-level menus where that group appears in
    # excluded_group_ids.
    group_id: int | None = None
    role_record_full = client.read("res.users.role", [role["id"]], fields=["group_id"])
    if role_record_full and role_record_full[0].get("group_id"):
        gid_field = role_record_full[0]["group_id"]
        group_id = gid_field[0] if isinstance(gid_field, list) else gid_field

    if group_id:
        hidden_menus = client.search_read(
            "ir.ui.menu",
            [("parent_id", "=", False), ("excluded_group_ids", "in", [group_id])],
            fields=["name"],
        )
        if hidden_menus:
            menus_str = ", ".join(m["name"] for m in hidden_menus)
            console.print(f"[bold]Hidden menus ({len(hidden_menus)}):[/bold] {menus_str}")


def _fetch_db_state(client, requested_xmlids: list[str]) -> RoleDbState:
    """Snapshot current DB roles + resolve xml_ids."""
    roles = client.search_read("res.users.role", [], fields=["id", "name", "implied_ids"])
    roles_by_name = {r["name"]: {"id": r["id"], "implied_ids": r["implied_ids"]} for r in roles}
    resolved, _missing = resolve_xmlids(client, requested_xmlids)
    return RoleDbState(roles_by_name=roles_by_name, xmlid_to_group_id=resolved)


def _print_plan(actions: list[SyncAction]) -> None:
    if not actions:
        console.print("[green]Nothing to do — DB matches YAML.[/green]")
        return
    table = Table(title=f"Sync plan ({len(actions)} actions)")
    table.add_column("Action", style="bold")
    table.add_column("Role")
    table.add_column("Groups", justify="right")
    table.add_column("Missing xml_ids")
    for a in actions:
        action_style = {"create": "green", "update": "yellow", "delete": "red"}.get(a.action, "")
        table.add_row(
            f"[{action_style}]{a.action}[/{action_style}]",
            a.role_name or "<unknown>",
            str(len(a.desired_group_ids)),
            ", ".join(a.missing_xmlids) or "-",
        )
    console.print(table)


def _apply_plan(client, actions: list[SyncAction]) -> None:
    for a in actions:
        if a.action == "create":
            new_id = client.create(
                "res.users.role",
                {"name": a.role_name, "implied_ids": [(6, 0, a.desired_group_ids)]},
            )
            console.print(f"[green]+ created role '{a.role_name}' (id={new_id})[/green]")
        elif a.action == "update":
            client.write(
                "res.users.role",
                [a.existing_role_id],
                {"implied_ids": [(6, 0, a.desired_group_ids)]},
            )
            console.print(f"[yellow]~ updated role '{a.role_name}' (id={a.existing_role_id})[/yellow]")
        elif a.action == "delete":
            client.unlink("res.users.role", [a.existing_role_id])
            console.print(f"[red]- deleted role '{a.role_name}' (id={a.existing_role_id})[/red]")


def _sync_menu_visibility(client, rf: RolesFile, prune: bool, dry_run: bool) -> None:
    """Apply `hide_menus` declarations via ir.ui.menu.excluded_group_ids.

    No-op when no role declares `hide_menus` — so existing tests that
    don't exercise this feature don't need fresh mock setups.
    """
    roles_with_hides = [rid for rid, spec in rf.roles.items() if spec.hide_menus]
    if not roles_with_hides:
        return

    # Fetch backing groups for roles that declared hide_menus.
    wanted_names = [rf.roles[rid].name for rid in roles_with_hides]
    db_roles = client.search_read(
        "res.users.role",
        [("name", "in", wanted_names)],
        fields=["id", "name", "group_id"],
    )
    name_to_role_id = {spec.name: rid for rid, spec in rf.roles.items()}
    role_backing_groups: dict[str, int] = {}
    for r in db_roles:
        rid = name_to_role_id.get(r["name"])
        gid_field = r.get("group_id")
        if rid and gid_field:
            role_backing_groups[rid] = gid_field[0] if isinstance(gid_field, list) else gid_field

    missing_roles = [rid for rid in roles_with_hides if rid not in role_backing_groups]
    if missing_roles:
        console.print(
            "[yellow]⚠ hide_menus: role(s) missing on DB or without backing group (run role sync first):[/yellow]"
        )
        for rid in missing_roles:
            console.print(f"  - {rid} ({rf.roles[rid].name})")

    # Fetch top-level menus.
    menus = client.search_read(
        "ir.ui.menu",
        [("parent_id", "=", False)],
        fields=["id", "name", "excluded_group_ids"],
    )
    menu_ids_by_name: dict[str, int] = {m["name"]: m["id"] for m in menus}
    current_exclusions: dict[int, set[int]] = {m["id"]: set(m.get("excluded_group_ids") or []) for m in menus}

    # Warn on unknown menu names up-front.
    unknown: set[str] = set()
    for spec in rf.roles.values():
        for name in spec.hide_menus:
            if name not in menu_ids_by_name:
                unknown.add(name)
    if unknown:
        console.print("[yellow]⚠ hide_menus references unknown top-level menus (skipped):[/yellow]")
        for name in sorted(unknown):
            console.print(f"  - {name}")

    actions = plan_menu_visibility(
        rf,
        role_backing_groups,
        menu_ids_by_name,
        current_exclusions,
        prune=prune,
    )
    if not actions:
        console.print("[dim]Menu visibility: nothing to do.[/dim]")
        return

    table = Table(title=f"Menu visibility plan ({len(actions)} actions)")
    table.add_column("Action", style="bold")
    table.add_column("Role")
    table.add_column("Menu")
    for a in actions:
        style = "green" if a.action == "add" else "red"
        sym = "+" if a.action == "add" else "-"
        table.add_row(f"[{style}]{sym} hide[/{style}]", a.role_id, a.menu_name)
    console.print(table)

    if dry_run:
        return

    # Apply — batch per-menu writes, so one client.write per menu.
    writes_by_menu: dict[int, list[tuple[int, int]]] = {}
    for a in actions:
        writes_by_menu.setdefault(a.menu_id, []).append((4 if a.action == "add" else 3, a.group_id))
    for mid, ops in writes_by_menu.items():
        client.write(
            "ir.ui.menu",
            [mid],
            {"excluded_group_ids": [(cmd, gid) for cmd, gid in ops]},
        )
    console.print(f"[green]Menu visibility: applied {len(actions)} change(s).[/green]")


@app.command("sync")
def sync_cmd(
    ctx: typer.Context,
    file: Annotated[
        Path,
        typer.Option(
            "--file",
            "-f",
            help="Path to roles.yaml (default: install/roles.yaml relative to cwd)",
        ),
    ] = Path("install/roles.yaml"),
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show plan without applying")] = False,
    prune: Annotated[bool, typer.Option("--prune", help="Also delete DB roles missing from YAML")] = False,
    strict: Annotated[bool, typer.Option("--strict", help="Fail if any xml_id is missing")] = False,
) -> None:
    """Apply install/roles.yaml to the DB idempotently."""
    if not file.exists():
        console.print(f"[red]File not found: {file}[/red]")
        raise typer.Exit(1)

    rf = load_roles_file(file)
    all_xmlids: list[str] = []
    for role_id in rf.roles:
        all_xmlids.extend(resolve_role_groups(rf, role_id))
    all_xmlids = list(dict.fromkeys(all_xmlids))

    client = _get_client(ctx)
    db_state = _fetch_db_state(client, all_xmlids)

    missing = [x for x in all_xmlids if x not in db_state.xmlid_to_group_id]
    if missing:
        console.print(f"[yellow]⚠ {len(missing)} xml_id(s) not installed on this DB — skipped:[/yellow]")
        for x in missing:
            console.print(f"  - {x}")
        if strict:
            console.print("[red]--strict given; aborting.[/red]")
            raise typer.Exit(2)

    actions = plan_sync(rf, db_state, prune=prune)
    _print_plan(actions)

    if dry_run:
        console.print("[dim]--dry-run: no changes applied.[/dim]")
        _sync_menu_visibility(client, rf, prune=prune, dry_run=True)
        return

    if actions:
        _apply_plan(client, actions)
        console.print("[green]Sync complete.[/green]")

    _sync_menu_visibility(client, rf, prune=prune, dry_run=False)


@app.command("diff")
def diff_cmd(
    ctx: typer.Context,
    file: Annotated[
        Path,
        typer.Option(
            "--file",
            "-f",
            help="Path to roles.yaml (default: install/roles.yaml relative to cwd)",
        ),
    ] = Path("install/roles.yaml"),
) -> None:
    """Compare live DB roles vs. YAML (drift detection)."""
    rf = load_roles_file(file)
    all_xmlids: list[str] = []
    for role_id in rf.roles:
        all_xmlids.extend(resolve_role_groups(rf, role_id))
    all_xmlids = list(dict.fromkeys(all_xmlids))

    client = _get_client(ctx)
    db_state = _fetch_db_state(client, all_xmlids)
    actions = plan_sync(rf, db_state, prune=False)

    if not actions:
        console.print("[green]No drift — DB matches YAML.[/green]")
        return
    console.print(f"[yellow]{len(actions)} drift(s) detected:[/yellow]")
    _print_plan(actions)


@app.command("audit")
def audit_cmd(
    ctx: typer.Context,
    file: Annotated[
        Path,
        typer.Option(
            "--file",
            "-f",
            help="Path to roles.yaml (default: install/roles.yaml relative to cwd)",
        ),
    ] = Path("install/roles.yaml"),
    ignored_file: Annotated[
        Path,
        typer.Option(
            "--ignored-file",
            help="Path to roles.ignored.yaml",
        ),
    ] = Path("install/roles.ignored.yaml"),
    suggest: Annotated[
        bool,
        typer.Option("--suggest", help="Print heuristic role mappings for orphans"),
    ] = False,
    strict: Annotated[
        bool,
        typer.Option("--strict", help="Exit non-zero on any findings"),
    ] = False,
) -> None:
    """Report orphan groups, dead xml_id references, and drift."""
    rf = load_roles_file(file)
    ignored = load_ignored_file(ignored_file)

    all_xmlids: list[str] = []
    for role_id in rf.roles:
        all_xmlids.extend(resolve_role_groups(rf, role_id))
    all_xmlids = list(dict.fromkeys(all_xmlids))

    client = _get_client(ctx)

    all_groups = client.search_read("res.groups", [], fields=["id", "full_name"])
    group_xmlid_by_id: dict[int, str] = {}
    all_ids = [g["id"] for g in all_groups]
    if all_ids:
        data_rows = client.search_read(
            "ir.model.data",
            [("model", "=", "res.groups"), ("res_id", "in", all_ids)],
            fields=["module", "name", "res_id"],
        )
        for row in data_rows:
            group_xmlid_by_id[row["res_id"]] = f"{row['module']}.{row['name']}"

    yaml_xmlids = set(all_xmlids)
    ignored_set = set(ignored.ignored)
    orphan: list[tuple[str, str]] = []
    for g in all_groups:
        xid = group_xmlid_by_id.get(g["id"])
        if xid is None:
            continue
        if xid in yaml_xmlids or xid in ignored_set:
            continue
        orphan.append((xid, g.get("full_name") or ""))

    _resolved, dead_refs = resolve_xmlids(client, all_xmlids)

    findings = 0
    if orphan:
        findings += len(orphan)
        table = Table(title=f"Orphan groups ({len(orphan)}) — not in any role, not ignored")
        table.add_column("xml_id")
        table.add_column("Full name")
        if suggest:
            table.add_column("Suggested role")
        for xid, full_name in orphan:
            row = [xid, full_name]
            if suggest:
                row.append(_suggest_role(xid))
            table.add_row(*row)
        console.print(table)

    if dead_refs:
        findings += len(dead_refs)
        console.print(f"[red]{len(dead_refs)} xml_id(s) in roles.yaml not installed:[/red]")
        for x in dead_refs:
            console.print(f"  - {x}")

    if findings == 0:
        console.print("[green]Audit clean.[/green]")

    if strict and findings > 0:
        raise typer.Exit(1)


def _suggest_role(xmlid: str) -> str:
    """Heuristic — map an orphan xml_id to a likely role."""
    m = xmlid.split(".", 1)[0]
    name_lc = xmlid.lower()
    is_manager = "manager" in name_lc or "administrator" in name_lc
    tier = "Manager" if is_manager else "User"
    mapping = [
        (("base.group_system", "base.group_erp_manager", "base.group_no_one"), "System Administrator"),
        (("account", "account_"), f"Finance {tier}"),
        (("sale", "crm"), f"Sales {tier}"),
        (("purchase",), f"Purchase {tier}"),
        (("stock", "delivery", "inventory"), f"Warehouse {tier}"),
        (("mrp",), f"Manufacturing {tier}"),
        (("quality",), "Quality Inspector"),
        (("hr", "payroll"), f"HR {tier}"),
        (("point_of_sale", "pos"), f"Branch {tier}"),
    ]
    for prefixes, role in mapping:
        if xmlid in prefixes or any(m.startswith(p) for p in prefixes):
            return role
    return "? (manual review)"


def _resolve_user(client, login: str) -> int:
    users = client.search_read("res.users", [("login", "=", login)], fields=["id", "login"])
    if not users:
        raise typer.BadParameter(f"User with login '{login}' not found.")
    return users[0]["id"]


def _resolve_roles(client, role_names: list[str]) -> list[int]:
    if not role_names:
        return []
    roles = client.search_read(
        "res.users.role",
        [("name", "in", role_names)],
        fields=["id", "name"],
    )
    found = {r["name"]: r["id"] for r in roles}
    missing = [n for n in role_names if n not in found]
    if missing:
        raise typer.BadParameter(f"Role(s) not found: {', '.join(missing)}")
    return [found[n] for n in role_names]


def _resolve_ous(client, ou_codes: list[str]) -> list[int]:
    if not ou_codes:
        return []
    if ou_codes == ["*"]:
        ous = client.search_read("operating.unit", [], fields=["id"])
        return [o["id"] for o in ous]
    ous = client.search_read(
        "operating.unit",
        [("code", "in", ou_codes)],
        fields=["id", "code"],
    )
    found = {o["code"]: o["id"] for o in ous}
    missing = [c for c in ou_codes if c not in found]
    if missing:
        raise typer.BadParameter(f"Operating unit code(s) not found: {', '.join(missing)}")
    return [found[c] for c in ou_codes]


@app.command("assign")
def assign_cmd(
    ctx: typer.Context,
    login: Annotated[str, typer.Argument(help="User login")],
    roles: Annotated[
        list[str] | None,
        typer.Argument(help="One or more role names (use quotes for names with spaces)"),
    ] = None,
    ous: Annotated[
        str,
        typer.Option("--ous", help="Comma-separated OU codes (use '*' for all)"),
    ] = "",
    clear: Annotated[
        bool,
        typer.Option("--clear", help="Remove ALL roles + OUs from user"),
    ] = False,
) -> None:
    """Assign role(s) + OU(s) to a user (or clear)."""
    client = _get_client(ctx)
    uid = _resolve_user(client, login)

    payload: dict[str, Any] = {}
    if clear:
        payload["role_line_ids"] = [(5, 0, 0)]
        payload["assigned_operating_unit_ids"] = [(5, 0, 0)]
        payload["default_operating_unit_id"] = False
    else:
        if not roles:
            raise typer.BadParameter("Pass role name(s) or use --clear.")
        role_ids = _resolve_roles(client, roles)
        payload["role_line_ids"] = [(5, 0, 0)] + [(0, 0, {"role_id": rid}) for rid in role_ids]
        if ous:
            ou_codes = [c.strip() for c in ous.split(",") if c.strip()]
            ou_ids = _resolve_ous(client, ou_codes)
            payload["assigned_operating_unit_ids"] = [(6, 0, ou_ids)]
            if ou_ids:
                payload["default_operating_unit_id"] = ou_ids[0]

    client.write("res.users", [uid], payload)
    console.print(f"[green]Assigned roles={roles or '[]'}, ous={ous or '[]'} to {login}[/green]")


@app.command("apply")
def apply_cmd(
    ctx: typer.Context,
    csv_file: Annotated[
        Path,
        typer.Argument(
            help="CSV with columns: login, roles (pipe-separated), ous (comma-separated, quote when multiple)"
        ),
    ],
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
) -> None:
    """Bulk-assign from a CSV."""
    client = _get_client(ctx)
    rows: list[dict[str, str]] = []
    with csv_file.open() as fh:
        reader = csv.DictReader(line for line in fh if not line.lstrip().startswith("#"))
        for row in reader:
            rows.append(row)

    table = Table(title=f"Apply plan ({len(rows)} rows)")
    table.add_column("login")
    table.add_column("roles")
    table.add_column("ous")
    for r in rows:
        table.add_row(r.get("login", ""), r.get("roles", ""), r.get("ous", ""))
    console.print(table)

    if dry_run:
        console.print("[dim]--dry-run: no writes.[/dim]")
        return

    for r in rows:
        login = r["login"]
        roles_list = [s.strip() for s in r.get("roles", "").split("|") if s.strip()]
        ou_raw = r.get("ous", "")
        ou_codes = [c.strip() for c in ou_raw.split(",") if c.strip()] if ou_raw else []
        uid = _resolve_user(client, login)
        role_ids = _resolve_roles(client, roles_list)
        ou_ids = _resolve_ous(client, ou_codes)
        payload: dict[str, Any] = {
            "role_line_ids": [(5, 0, 0)] + [(0, 0, {"role_id": rid}) for rid in role_ids],
            "assigned_operating_unit_ids": [(6, 0, ou_ids)],
        }
        if ou_ids:
            payload["default_operating_unit_id"] = ou_ids[0]
        client.write("res.users", [uid], payload)
        console.print(f"[green]✓ {login}[/green]")
