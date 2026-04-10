"""Group management commands."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from kctl_outline.core.callbacks import AppContext

app = typer.Typer(help="Group management.")


@app.command("list")
def list_(
    ctx: typer.Context,
    offset: Annotated[int, typer.Option(help="Pagination offset")] = 0,
    limit: Annotated[int, typer.Option(help="Results per page")] = 25,
) -> None:
    """List all groups."""
    c: AppContext = ctx.obj
    result = c.client.post("groups.list", data={"offset": offset, "limit": limit})
    groups = result.get("data", {}).get("groups", [])
    group_memberships = result.get("data", {}).get("groupMemberships", [])

    # Build member count map
    member_counts: dict[str, int] = {}
    for gm in group_memberships:
        gid = gm.get("groupId", "")
        member_counts[gid] = member_counts.get(gid, 0) + 1

    rows = [
        [
            g.get("id", "")[:8],
            g.get("name", ""),
            str(g.get("memberCount", member_counts.get(g.get("id", ""), 0))),
            (g.get("updatedAt") or "")[:10],
        ]
        for g in groups
    ]

    c.output.table(
        f"Groups ({len(groups)})",
        [("ID", "cyan"), ("Name", "green"), ("Members", ""), ("Updated", "dim")],
        rows,
        data_for_json=groups,
    )


@app.command()
def get(
    ctx: typer.Context,
    group_id: Annotated[str, typer.Argument(help="Group ID")],
) -> None:
    """Get group details."""
    c: AppContext = ctx.obj
    result = c.client.post("groups.info", data={"id": group_id})
    group = result.get("data", {})

    c.output.detail(
        f"Group: {group.get('name', '')}",
        [
            ("Details", [
                ("ID", group.get("id", "")),
                ("Name", group.get("name", "")),
                ("Member Count", str(group.get("memberCount", 0))),
            ]),
            ("Dates", [
                ("Created", group.get("createdAt", "")),
                ("Updated", group.get("updatedAt", "")),
            ]),
        ],
        data_for_json=group,
    )


@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Group name")],
) -> None:
    """Create a new group."""
    c: AppContext = ctx.obj
    result = c.client.post("groups.create", data={"name": name})
    group = result.get("data", {})
    c.output.success(f"Group created: {group.get('name', name)} (ID: {group.get('id', '')})")


@app.command()
def update(
    ctx: typer.Context,
    group_id: Annotated[str, typer.Argument(help="Group ID")],
    name: Annotated[str, typer.Option("--name", help="New group name")] = "",
) -> None:
    """Update a group."""
    c: AppContext = ctx.obj
    data: dict = {"id": group_id}
    if name:
        data["name"] = name

    result = c.client.post("groups.update", data=data)
    group = result.get("data", {})
    c.output.success(f"Group updated: {group.get('name', group_id)}")


@app.command()
def delete(
    ctx: typer.Context,
    group_id: Annotated[str, typer.Argument(help="Group ID")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete a group."""
    c: AppContext = ctx.obj

    if not force:
        info = c.client.post("groups.info", data={"id": group_id})
        group = info.get("data", {})
        if not typer.confirm(f"Delete group '{group.get('name', group_id)}'?"):
            raise typer.Abort()

    c.client.post("groups.delete", data={"id": group_id})
    c.output.success(f"Group {group_id} deleted")


@app.command("add-user")
def add_user(
    ctx: typer.Context,
    group_id: Annotated[str, typer.Argument(help="Group ID")],
    user_id: Annotated[str, typer.Argument(help="User ID")],
) -> None:
    """Add a user to a group."""
    c: AppContext = ctx.obj
    c.client.post("groups.add_user", data={"id": group_id, "userId": user_id})
    c.output.success(f"User {user_id} added to group {group_id}")


@app.command("remove-user")
def remove_user(
    ctx: typer.Context,
    group_id: Annotated[str, typer.Argument(help="Group ID")],
    user_id: Annotated[str, typer.Argument(help="User ID")],
) -> None:
    """Remove a user from a group."""
    c: AppContext = ctx.obj
    c.client.post("groups.remove_user", data={"id": group_id, "userId": user_id})
    c.output.success(f"User {user_id} removed from group {group_id}")
