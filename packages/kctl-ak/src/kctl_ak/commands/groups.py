"""Group management commands."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import typer
import yaml

from kctl_ak.core.callbacks import AppContext
from kctl_ak.core.config import resolve_group_structure_path
from kctl_ak.core.resolve import resolve_group, resolve_user

app = typer.Typer(help="Group management and hierarchy.")


@app.command("list")
def list_(
    ctx: typer.Context,
    page: Annotated[int, typer.Option(help="Page number")] = 1,
) -> None:
    """List all groups."""
    c: AppContext = ctx.obj
    data = c.client.get("core/groups/", params={"page": page, "page_size": 50})
    groups = data.get("results", [])
    pagination = data.get("pagination", {})

    rows = [
        [
            g.get("pk", ""),
            g.get("name", ""),
            g.get("parent_name", "") or "",
            str(len(g.get("users", []))),
            "yes" if g.get("is_superuser") else "no",
        ]
        for g in groups
    ]

    c.output.table(
        f"Groups (page {pagination.get('current', page)}/{pagination.get('total_pages', 1)})",
        [("ID", "dim"), ("Name", "green"), ("Parent", ""), ("Members", "cyan"), ("Superuser", "")],
        rows,
        data_for_json=groups,
    )


@app.command()
def get(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="Group ID, UUID, or name")],
) -> None:
    """Get detailed group info."""
    c: AppContext = ctx.obj
    pk = resolve_group(c.client, identifier)
    group = c.client.get(f"core/groups/{pk}/")

    members = [f"{u.get('username', '')} ({u.get('email', '')})" for u in group.get("users_obj", [])]

    c.output.detail(
        f"Group: {group.get('name', '')}",
        [
            (
                "Details",
                [
                    ("ID", group.get("pk", "")),
                    ("Name", group.get("name", "")),
                    ("Parent", group.get("parent_name", "") or "(root)"),
                    ("Superuser", str(group.get("is_superuser", False))),
                ],
            ),
            ("Members", [(str(i + 1), m) for i, m in enumerate(members)] if members else [("(none)", "")]),
            (
                "Attributes",
                [(k, str(v)) for k, v in group.get("attributes", {}).items()]
                if group.get("attributes")
                else [("(none)", "")],
            ),
        ],
        data_for_json=group,
    )


@app.command()
def tree(ctx: typer.Context) -> None:
    """Display group hierarchy as a tree."""
    c: AppContext = ctx.obj
    all_groups = c.client.get_all("core/groups/")

    by_parent: dict[str | None, list[dict]] = {}
    for g in all_groups:
        parent = g.get("parent")
        by_parent.setdefault(parent, []).append(g)

    def build_nodes(parent_pk: str | None) -> list[dict]:
        children = sorted(by_parent.get(parent_pk, []), key=lambda g: g.get("name", ""))
        nodes = []
        for g in children:
            member_count = len(g.get("users", []))
            info = f"{member_count} members"
            if g.get("is_superuser"):
                info += ", superuser"
            nodes.append(
                {
                    "name": g["name"],
                    "info": info,
                    "children": build_nodes(g["pk"]),
                }
            )
        return nodes

    root_nodes = build_nodes(None)
    c.output.tree("Group Hierarchy", root_nodes, data_for_json=all_groups)


@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Group name")],
    parent: Annotated[str | None, typer.Option(help="Parent group name or ID")] = None,
    superuser: Annotated[bool, typer.Option("--superuser", help="Grant superuser to group")] = False,
) -> None:
    """Create a new group."""
    c: AppContext = ctx.obj
    group_data: dict = {
        "name": name,
        "is_superuser": superuser,
    }
    if parent:
        group_data["parent"] = resolve_group(c.client, parent)

    group = c.client.post("core/groups/", data=group_data)
    c.output.success(f"Group created: {group.get('name', name)} (ID: {group.get('pk', '')})")


@app.command()
def update(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="Group ID, UUID, or name")],
    field: Annotated[str, typer.Argument(help="Field to update (name, is_superuser, parent)")],
    value: Annotated[str, typer.Argument(help="New value")],
) -> None:
    """Update a group field."""
    c: AppContext = ctx.obj
    pk = resolve_group(c.client, identifier)

    update_value: str | bool = value
    if field == "is_superuser":
        update_value = value.lower() in ("true", "1", "yes")
    elif field == "parent":
        update_value = resolve_group(c.client, value) if value else None

    c.client.patch(f"core/groups/{pk}/", data={field: update_value})
    c.output.success(f"Group {pk}: {field} = {value}")


@app.command()
def delete(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="Group ID, UUID, or name")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete a group."""
    c: AppContext = ctx.obj
    pk = resolve_group(c.client, identifier)

    if not force:
        group = c.client.get(f"core/groups/{pk}/")
        confirm = typer.confirm(f"Delete group {group.get('name', pk)}?")
        if not confirm:
            raise typer.Abort()

    c.client.delete(f"core/groups/{pk}/")
    c.output.success(f"Group {pk} deleted")


@app.command("add-user")
def add_user(
    ctx: typer.Context,
    group: Annotated[str, typer.Argument(help="Group name or ID")],
    user: Annotated[str, typer.Argument(help="User ID, username, or email")],
) -> None:
    """Add a user to a group."""
    c: AppContext = ctx.obj
    gid = resolve_group(c.client, group)
    uid = resolve_user(c.client, user)
    c.client.post(f"core/groups/{gid}/add_user/", data={"pk": uid})
    c.output.success(f"User {uid} added to group {group}")


@app.command("remove-user")
def remove_user(
    ctx: typer.Context,
    group: Annotated[str, typer.Argument(help="Group name or ID")],
    user: Annotated[str, typer.Argument(help="User ID, username, or email")],
) -> None:
    """Remove a user from a group."""
    c: AppContext = ctx.obj
    gid = resolve_group(c.client, group)
    uid = resolve_user(c.client, user)
    c.client.post(f"core/groups/{gid}/remove_user/", data={"pk": uid})
    c.output.success(f"User {uid} removed from group {group}")


@app.command()
def members(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="Group ID, UUID, or name")],
) -> None:
    """List members of a group."""
    c: AppContext = ctx.obj
    pk = resolve_group(c.client, identifier)
    group = c.client.get(f"core/groups/{pk}/")
    users = group.get("users_obj", [])

    rows = [
        [str(u.get("pk", "")), u.get("username", ""), u.get("email", ""), "yes" if u.get("is_active") else "no"]
        for u in users
    ]

    c.output.table(
        f"Members of {group.get('name', identifier)}",
        [("ID", "cyan"), ("Username", "green"), ("Email", ""), ("Active", "")],
        rows,
        data_for_json=users,
    )


def _compute_sync_plan(
    desired: list[dict],
    existing: list[dict],
) -> dict[str, list[dict]]:
    """Compare desired groups (from YAML) with existing groups (from API).

    Returns ``{"create": [...], "update": [...], "prune": [...]}``.
    This is a pure function with NO side effects.
    """
    existing_by_name: dict[str, dict] = {g["name"]: g for g in existing}
    desired_names: set[str] = set()

    create: list[dict] = []
    update: list[dict] = []

    for g in desired:
        name = g.get("name", "")
        if not name:
            continue
        desired_names.add(name)

        ex = existing_by_name.get(name)
        if ex is None:
            create.append(g)
            continue

        # Detect changes
        changes: dict = {}

        # is_superuser
        desired_su = g.get("is_superuser", False)
        if desired_su != ex.get("is_superuser", False):
            changes["is_superuser"] = desired_su

        # parent (compare by name)
        desired_parent = g.get("parent")  # name string or None
        existing_parent = ex.get("parent_name") or None
        if desired_parent != existing_parent:
            changes["parent"] = desired_parent

        # description (stored in attributes.description)
        desired_desc = g.get("description", "")
        existing_desc = ex.get("attributes", {}).get("description", "")
        if desired_desc != existing_desc:
            changes["description"] = desired_desc

        if changes:
            update.append({"name": name, "pk": ex["pk"], "changes": changes})

    # Prune: existing groups with ak- prefix not in desired set
    prune: list[dict] = []
    for ex in existing:
        name = ex.get("name", "")
        if name.startswith("ak-") and name not in desired_names:
            prune.append({"name": name, "pk": ex["pk"]})

    return {"create": create, "update": update, "prune": prune}


@app.command()
def sync(
    ctx: typer.Context,
    dry_run: Annotated[bool, typer.Option("--dry-run/--no-dry-run", help="Preview changes without applying")] = True,
    prune: Annotated[bool, typer.Option("--prune", help="Delete ak-* groups not in YAML")] = False,
    file: Annotated[Path | None, typer.Option(help="Path to group-structure.yaml")] = None,
) -> None:
    """Sync groups from group-structure.yaml (3-phase: create/update/prune)."""
    c: AppContext = ctx.obj

    if file:
        gs_path = file
    else:
        gs_path = resolve_group_structure_path()
        if gs_path is None:
            c.output.error("group-structure.yaml not found. Use --file to specify path.")
            raise typer.Exit(1)

    with open(gs_path) as f:
        structure = yaml.safe_load(f) or {}

    desired_groups = structure.get("groups", [])
    if not desired_groups:
        c.output.warn("No groups defined in structure file")
        return

    # --- Initial plan ---
    existing = c.client.get_all("core/groups/")
    plan = _compute_sync_plan(desired_groups, existing)

    c.output.header("Group Sync")
    c.output.info(f"Source: {gs_path}")
    c.output.info(
        f"Desired: {len(desired_groups)} | "
        f"Create: {len(plan['create'])} | "
        f"Update: {len(plan['update'])} | "
        f"Prune: {len(plan['prune'])}"
    )

    # ---- Phase 1: CREATE (no parents yet) ----
    if plan["create"]:
        c.output.header("Phase 1: Create")
        for g in plan["create"]:
            name = g["name"]
            if dry_run:
                c.output.info(f"[create] {name}")
            else:
                try:
                    data: dict = {
                        "name": name,
                        "is_superuser": g.get("is_superuser", False),
                    }
                    desc = g.get("description", "")
                    if desc:
                        data["attributes"] = {"description": desc}
                    c.client.post("core/groups/", data=data)
                    c.output.success(f"[create] {name}")
                except Exception as e:
                    c.output.error(f"[create] Failed {name}: {e}")

    # ---- Reload + recompute after creates (to get PKs) ----
    if plan["create"] and not dry_run:
        existing = c.client.get_all("core/groups/")
        plan = _compute_sync_plan(desired_groups, existing)

    # ---- Phase 2: UPDATE (parent, is_superuser, description) ----
    if plan["update"]:
        c.output.header("Phase 2: Update")
        existing_by_name = {g["name"]: g for g in existing}
        for entry in plan["update"]:
            name = entry["name"]
            pk = entry["pk"]
            changes = entry["changes"]
            if dry_run:
                c.output.info(f"[update] {name}: {changes}")
            else:
                try:
                    patch_data: dict = {}
                    if "is_superuser" in changes:
                        patch_data["is_superuser"] = changes["is_superuser"]
                    if "parent" in changes:
                        parent_name = changes["parent"]
                        if parent_name and parent_name in existing_by_name:
                            patch_data["parent"] = existing_by_name[parent_name]["pk"]
                        else:
                            patch_data["parent"] = None
                    if "description" in changes:
                        patch_data["attributes"] = {"description": changes["description"]}
                    c.client.patch(f"core/groups/{pk}/", data=patch_data)
                    c.output.success(f"[update] {name}")
                except Exception as e:
                    c.output.error(f"[update] Failed {name}: {e}")

    # ---- Phase 3: PRUNE (only with --prune flag) ----
    if plan["prune"] and prune:
        c.output.header("Phase 3: Prune")
        for entry in plan["prune"]:
            name = entry["name"]
            pk = entry["pk"]
            if dry_run:
                c.output.info(f"[prune] {name}")
            else:
                try:
                    c.client.delete(f"core/groups/{pk}/")
                    c.output.success(f"[prune] {name}")
                except Exception as e:
                    c.output.error(f"[prune] Failed {name}: {e}")
    elif plan["prune"] and not prune:
        c.output.warn(f"{len(plan['prune'])} stale ak-* group(s) found. Use --prune to remove them.")

    # ---- Summary ----
    no_changes = not plan["create"] and not plan["update"] and (not plan["prune"] or not prune)
    if no_changes and not plan["prune"]:
        c.output.success("All groups in sync")

    if dry_run and (plan["create"] or plan["update"] or (plan["prune"] and prune)):
        c.output.warn("Dry-run mode. Use --no-dry-run to apply changes.")


@app.command("export")
def export_(
    ctx: typer.Context,
    format: Annotated[str, typer.Option("--format", help="Output format: json or yaml")] = "json",
) -> None:
    """Export all groups."""
    c: AppContext = ctx.obj
    groups = c.client.get_all("core/groups/")

    if format == "yaml":
        export_data = {
            "groups": [
                {
                    "name": g.get("name", ""),
                    "is_superuser": g.get("is_superuser", False),
                    "parent": g.get("parent_name") or None,
                }
                for g in groups
            ]
        }
        yaml.dump(export_data, sys.stdout, default_flow_style=False, sort_keys=False)
    else:
        c.output.raw_json(groups)
