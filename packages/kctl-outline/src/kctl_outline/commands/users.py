"""User management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_outline.core.callbacks import AppContext

app = typer.Typer(help="User management.")


@app.command("list")
def list_(
    ctx: typer.Context,
    offset: Annotated[int, typer.Option(help="Pagination offset")] = 0,
    limit: Annotated[int, typer.Option(help="Results per page")] = 25,
    filter_: Annotated[str | None, typer.Option("--filter", help="Filter: all, active, invited, suspended")] = None,
) -> None:
    """List users."""
    c: AppContext = ctx.obj
    data: dict = {"offset": offset, "limit": limit}
    if filter_:
        data["filter"] = filter_

    result = c.client.post("users.list", data=data)
    users = result.get("data", [])
    pagination = result.get("pagination", {})

    rows = [
        [
            u.get("id", "")[:8],
            u.get("name", ""),
            u.get("email", ""),
            u.get("role", ""),
            "yes" if not u.get("isSuspended") else "[red]suspended[/red]",
            (u.get("lastActiveAt") or "never")[:10],
        ]
        for u in users
    ]

    total = pagination.get("total", len(users))
    c.output.table(
        f"Users ({total} total)",
        [("ID", "cyan"), ("Name", "green"), ("Email", ""), ("Role", ""), ("Active", ""), ("Last Active", "dim")],
        rows,
        data_for_json=users,
    )


@app.command()
def get(
    ctx: typer.Context,
    user_id: Annotated[str, typer.Argument(help="User ID")],
) -> None:
    """Get user details."""
    c: AppContext = ctx.obj
    result = c.client.post("users.info", data={"id": user_id})
    user = result.get("data", {})

    c.output.detail(
        f"User: {user.get('name', '')}",
        [
            (
                "Identity",
                [
                    ("ID", user.get("id", "")),
                    ("Name", user.get("name", "")),
                    ("Email", user.get("email", "")),
                    ("Role", user.get("role", "")),
                ],
            ),
            (
                "Status",
                [
                    ("Suspended", str(user.get("isSuspended", False))),
                    ("Admin", str(user.get("isAdmin", False))),
                    ("Viewer", str(user.get("isViewer", False))),
                    ("Last Active", user.get("lastActiveAt", "never")),
                ],
            ),
            (
                "Dates",
                [
                    ("Created", user.get("createdAt", "")),
                ],
            ),
        ],
        data_for_json=user,
    )


@app.command()
def invite(
    ctx: typer.Context,
    email: Annotated[str, typer.Argument(help="Email address")],
    name: Annotated[str, typer.Option("--name", help="Display name")] = "",
    role: Annotated[str, typer.Option("--role", help="Role: admin, member, viewer")] = "member",
) -> None:
    """Invite a user by email."""
    c: AppContext = ctx.obj
    invites = [{"email": email, "name": name or email.split("@")[0], "role": role}]
    result = c.client.post("users.invite", data={"invites": invites})
    sent = result.get("data", {}).get("sent", [])

    if sent:
        c.output.success(f"Invitation sent to {email}")
    else:
        c.output.warn("Invitation may not have been sent (user may already exist)")


@app.command()
def update(
    ctx: typer.Context,
    user_id: Annotated[str, typer.Argument(help="User ID")],
    name: Annotated[str | None, typer.Option("--name", help="New display name")] = None,
    role: Annotated[str | None, typer.Option("--role", help="New role: admin, member, viewer")] = None,
) -> None:
    """Update a user."""
    c: AppContext = ctx.obj
    data: dict = {"id": user_id}
    if name:
        data["name"] = name
    if role:
        data["role"] = role

    result = c.client.post("users.update", data=data)
    user = result.get("data", {})
    c.output.success(f"User updated: {user.get('name', user_id)}")


@app.command()
def activate(
    ctx: typer.Context,
    user_id: Annotated[str, typer.Argument(help="User ID")],
) -> None:
    """Activate (unsuspend) a user."""
    c: AppContext = ctx.obj
    c.client.post("users.activate", data={"id": user_id})
    c.output.success(f"User {user_id} activated")


@app.command()
def deactivate(
    ctx: typer.Context,
    user_id: Annotated[str, typer.Argument(help="User ID")],
) -> None:
    """Deactivate (suspend) a user."""
    c: AppContext = ctx.obj
    c.client.post("users.suspend", data={"id": user_id})
    c.output.success(f"User {user_id} suspended")
