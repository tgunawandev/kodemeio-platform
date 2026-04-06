"""User group management commands."""

from __future__ import annotations

import json
from typing import Annotated, Optional

import typer

from kctl_zulip.core.callbacks import AppContext

app = typer.Typer(help="User group management.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all user groups."""
    c: AppContext = ctx.obj
    data = c.client.get("user_groups")
    groups = data.get("user_groups", data.get("direct_subgroups", []))

    rows = [
        [
            str(g.get("id", "")),
            g.get("name", ""),
            g.get("description", ""),
            str(len(g.get("members", []))),
            "yes" if g.get("is_system_group", False) else "no",
        ]
        for g in groups
    ]

    c.output.table(
        f"User Groups ({len(groups)})",
        [("ID", "cyan"), ("Name", "green"), ("Description", ""), ("Members", ""), ("System", "dim")],
        rows,
        data_for_json=groups,
    )


@app.command()
def get(
    ctx: typer.Context,
    group_id: Annotated[int, typer.Argument(help="Group ID")],
) -> None:
    """Get detailed group info."""
    c: AppContext = ctx.obj

    # Fetch all groups and find by ID
    data = c.client.get("user_groups")
    groups = data.get("user_groups", [])
    group = next((g for g in groups if g.get("id") == group_id), None)

    if not group:
        c.output.error(f"Group {group_id} not found")
        raise typer.Exit(1)

    members = group.get("members", [])

    c.output.detail(
        f"Group: {group.get('name', '')}",
        [
            ("Details", [
                ("ID", str(group.get("id", ""))),
                ("Name", group.get("name", "")),
                ("Description", group.get("description", "")),
                ("System Group", str(group.get("is_system_group", False))),
            ]),
            ("Members", [
                ("Count", str(len(members))),
                ("Member IDs", ", ".join(str(m) for m in members[:20]) if members else "(none)"),
            ]),
        ],
        data_for_json=group,
    )


@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Group name")],
    description: Annotated[str, typer.Option("--description", "-d", help="Group description")] = "",
    members: Annotated[Optional[str], typer.Option("--members", help="Comma-separated user IDs")] = None,
) -> None:
    """Create a new user group."""
    c: AppContext = ctx.obj

    member_ids = []
    if members:
        member_ids = [int(m.strip()) for m in members.split(",") if m.strip()]

    c.client.post("user_groups/create", data={
        "name": name,
        "description": description,
        "members": json.dumps(member_ids),
    })

    c.output.success(f"Group '{name}' created")


@app.command()
def update(
    ctx: typer.Context,
    group_id: Annotated[int, typer.Argument(help="Group ID")],
    name: Annotated[Optional[str], typer.Option("--name", help="New name")] = None,
    description: Annotated[Optional[str], typer.Option("--description", "-d", help="New description")] = None,
) -> None:
    """Update a user group."""
    c: AppContext = ctx.obj

    payload: dict = {}
    if name is not None:
        payload["name"] = name
    if description is not None:
        payload["description"] = description

    if not payload:
        c.output.warn("No fields to update")
        return

    c.client.patch(f"user_groups/{group_id}", data=payload)
    c.output.success(f"Group {group_id} updated")


@app.command()
def delete(
    ctx: typer.Context,
    group_id: Annotated[int, typer.Argument(help="Group ID")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete a user group."""
    c: AppContext = ctx.obj

    if not force:
        if not typer.confirm(f"Delete group {group_id}?"):
            raise typer.Abort()

    c.client.delete(f"user_groups/{group_id}")
    c.output.success(f"Group {group_id} deleted")


@app.command("add-member")
def add_member(
    ctx: typer.Context,
    group_id: Annotated[int, typer.Argument(help="Group ID")],
    user_ids: Annotated[str, typer.Argument(help="Comma-separated user IDs to add")],
) -> None:
    """Add members to a user group."""
    c: AppContext = ctx.obj

    ids = [int(uid.strip()) for uid in user_ids.split(",") if uid.strip()]
    c.client.post(f"user_groups/{group_id}/members", data={
        "add": json.dumps(ids),
    })
    c.output.success(f"Added {len(ids)} member(s) to group {group_id}")


@app.command("remove-member")
def remove_member(
    ctx: typer.Context,
    group_id: Annotated[int, typer.Argument(help="Group ID")],
    user_ids: Annotated[str, typer.Argument(help="Comma-separated user IDs to remove")],
) -> None:
    """Remove members from a user group."""
    c: AppContext = ctx.obj

    ids = [int(uid.strip()) for uid in user_ids.split(",") if uid.strip()]
    c.client.post(f"user_groups/{group_id}/members", data={
        "delete": json.dumps(ids),
    })
    c.output.success(f"Removed {len(ids)} member(s) from group {group_id}")
