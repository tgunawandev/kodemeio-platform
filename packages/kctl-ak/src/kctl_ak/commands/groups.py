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


@app.command()
def sync(
    ctx: typer.Context,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview changes without applying")] = True,
    file: Annotated[Path | None, typer.Option(help="Path to group-structure.yaml")] = None,
) -> None:
    """Sync groups from group-structure.yaml."""
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

    existing = c.client.get_all("core/groups/")
    existing_names = {g["name"] for g in existing}

    to_create: list[dict] = []
    already_exist: list[str] = []

    for g in desired_groups:
        name = g.get("name", "")
        if not name:
            continue
        if name in existing_names:
            already_exist.append(name)
        else:
            to_create.append(g)

    c.output.header("Group Sync")
    c.output.info(f"Source: {gs_path}")
    c.output.info(f"Desired: {len(desired_groups)} | Existing: {len(already_exist)} | To create: {len(to_create)}")

    if not to_create:
        c.output.success("All groups already exist")
        return

    for g in to_create:
        name = g["name"]
        if dry_run:
            c.output.info(f"[dry-run] Would create: {name}")
        else:
            try:
                c.client.post(
                    "core/groups/",
                    data={
                        "name": name,
                        "is_superuser": g.get("is_superuser", False),
                    },
                )
                c.output.success(f"Created: {name}")
            except Exception as e:
                c.output.error(f"Failed to create {name}: {e}")

    if dry_run:
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
