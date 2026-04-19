"""kctl-odoo roles — declarative role management.

See kodemeio-docs/superpowers/specs/2026-04-19-role-standardization-design.md
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.roles import (
    RoleDbState,
    SyncAction,
    load_roles_file,
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
    roles = client.execute("res.users.role", "search_read", [], ["id", "name", "implied_ids"])
    if not roles:
        console.print("[yellow]No roles configured in this DB.[/yellow]")
        return

    table = Table(title=f"Roles ({len(roles)})")
    table.add_column("ID", justify="right")
    table.add_column("Name")
    table.add_column("Groups", justify="right")
    table.add_column("Users", justify="right")

    for role in roles:
        lines = client.execute(
            "res.users.role.line",
            "search_read",
            [("role_id", "=", role["id"])],
            ["user_id"],
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
    roles = client.execute(
        "res.users.role",
        "search_read",
        [("name", "=", name)],
        ["id", "name", "implied_ids"],
    )
    if not roles:
        console.print(f"[red]Role '{name}' not found.[/red]")
        raise typer.Exit(1)

    role = roles[0]
    console.print(f"[bold]Role:[/bold] {role['name']} (id={role['id']})")

    if role["implied_ids"]:
        groups = client.execute("res.groups", "read", role["implied_ids"], ["name", "full_name"])
        group_table = Table(title="Groups")
        group_table.add_column("ID", justify="right")
        group_table.add_column("Full Name")
        for g in groups:
            group_table.add_row(str(g["id"]), g.get("full_name") or g["name"])
        console.print(group_table)
    else:
        console.print("[dim]No groups.[/dim]")

    user_lines = client.execute(
        "res.users.role.line",
        "search_read",
        [("role_id", "=", role["id"])],
        ["user_id"],
    )
    if user_lines:
        users_str = ", ".join(line["user_id"][1] for line in user_lines if line.get("user_id"))
        console.print(f"[bold]Users ({len(user_lines)}):[/bold] {users_str}")
    else:
        console.print("[dim]No users assigned.[/dim]")


def _fetch_db_state(client, requested_xmlids: list[str]) -> RoleDbState:
    """Snapshot current DB roles + resolve xml_ids."""
    roles = client.execute("res.users.role", "search_read", [], ["id", "name", "implied_ids"])
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
            new_id = client.execute(
                "res.users.role",
                "create",
                {"name": a.role_name, "implied_ids": [(6, 0, a.desired_group_ids)]},
            )
            console.print(f"[green]+ created role '{a.role_name}' (id={new_id})[/green]")
        elif a.action == "update":
            client.execute(
                "res.users.role",
                "write",
                [a.existing_role_id],
                {"implied_ids": [(6, 0, a.desired_group_ids)]},
            )
            console.print(f"[yellow]~ updated role '{a.role_name}' (id={a.existing_role_id})[/yellow]")
        elif a.action == "delete":
            client.execute("res.users.role", "unlink", [a.existing_role_id])
            console.print(f"[red]- deleted role '{a.role_name}' (id={a.existing_role_id})[/red]")


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
        return

    if actions:
        _apply_plan(client, actions)
        console.print("[green]Sync complete.[/green]")
