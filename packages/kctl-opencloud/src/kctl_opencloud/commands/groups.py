"""Group management commands for kctl-opencloud."""

from __future__ import annotations

from typing import Annotated, Any

import typer

from kctl_opencloud.core.callbacks import AppContext

app = typer.Typer(help="Group management.")


@app.command("list")
def list_(
    ctx: typer.Context,
    search: Annotated[str | None, typer.Option("--search", "-s", help="Search by name")] = None,
) -> None:
    """List all groups."""
    c: AppContext = ctx.obj
    params: dict[str, Any] = {}
    if search:
        params["$search"] = search

    groups = c.client.get_all("groups", params=params)

    rows = []
    for g in groups:
        members = g.get("members", [])
        rows.append(
            [
                g.get("id", ""),
                g.get("displayName", "-"),
                str(len(members)) if members else "0",
            ]
        )

    c.output.table(
        "Groups",
        [("ID", "cyan"), ("Name", "green"), ("Members", "yellow")],
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
    group = c.client.get(f"groups/{group_id}")

    members = group.get("members", [])
    sections = [
        (
            "Group",
            [
                ("ID", group.get("id", "")),
                ("Name", group.get("displayName", "-")),
                ("Members", str(len(members))),
            ],
        ),
    ]
    c.output.detail("Group Details", sections, data_for_json=group)


@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Group display name")],
) -> None:
    """Create a new group."""
    c: AppContext = ctx.obj
    group = c.client.post("groups", data={"displayName": name})
    c.output.success(f"Group created: {group.get('displayName', name)}")


@app.command()
def update(
    ctx: typer.Context,
    group_id: Annotated[str, typer.Argument(help="Group ID")],
    name: Annotated[str, typer.Option("--name", "-n", help="New display name")],
) -> None:
    """Update a group."""
    c: AppContext = ctx.obj
    c.client.patch(f"groups/{group_id}", data={"displayName": name})
    c.output.success(f"Group {group_id} updated")


@app.command()
def delete(
    ctx: typer.Context,
    group_id: Annotated[str, typer.Argument(help="Group ID")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Delete a group."""
    c: AppContext = ctx.obj
    if not force:
        typer.confirm(f"Delete group {group_id}?", abort=True)
    c.client.delete(f"groups/{group_id}")
    c.output.success(f"Group {group_id} deleted")


@app.command("add-member")
def add_member(
    ctx: typer.Context,
    group_id: Annotated[str, typer.Argument(help="Group ID")],
    user_id: Annotated[str, typer.Argument(help="User ID to add")],
) -> None:
    """Add a member to a group."""
    c: AppContext = ctx.obj
    c.client.post(
        f"groups/{group_id}/members/$ref",
        data={"@odata.id": f"{c.client.api_base_url}/users/{user_id}"},
    )
    c.output.success(f"User {user_id} added to group {group_id}")


@app.command("remove-member")
def remove_member(
    ctx: typer.Context,
    group_id: Annotated[str, typer.Argument(help="Group ID")],
    user_id: Annotated[str, typer.Argument(help="User ID to remove")],
) -> None:
    """Remove a member from a group."""
    c: AppContext = ctx.obj
    c.client.delete(f"groups/{group_id}/members/{user_id}/$ref")
    c.output.success(f"User {user_id} removed from group {group_id}")
