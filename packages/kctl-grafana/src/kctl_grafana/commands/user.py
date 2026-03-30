"""User management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_grafana.core.callbacks import AppContext

app = typer.Typer(help="Organization user management.")


@app.command("list")
def list_users(ctx: typer.Context) -> None:
    """List organization users."""
    c: AppContext = ctx.obj
    out = c.output
    client = c.client

    users = client.get("/org/users")

    rows: list[list[str]] = []
    for u in users:
        user_id = str(u.get("userId", ""))
        login = u.get("login", "")
        email = u.get("email", "")
        role = u.get("role", "")
        last_seen = u.get("lastSeenAt", "")
        rows.append([user_id, login, email, role, last_seen])

    out.table(
        f"Organization Users ({len(users)})",
        [("ID", "cyan"), ("Login", ""), ("Email", ""), ("Role", ""), ("Last Seen", "dim")],
        rows,
        data_for_json=users,
    )


@app.command("add")
def add_user(
    ctx: typer.Context,
    email: Annotated[str, typer.Argument(help="User email address")],
    role: Annotated[str, typer.Option("--role", "-r", help="Role: Viewer, Editor, Admin")] = "Viewer",
) -> None:
    """Add a user to the organization."""
    c: AppContext = ctx.obj
    out = c.output
    client = c.client

    valid_roles = {"Viewer", "Editor", "Admin"}
    if role not in valid_roles:
        out.error(f"Invalid role: {role}. Must be one of: {', '.join(valid_roles)}")
        raise typer.Exit(1)

    payload = {
        "loginOrEmail": email,
        "role": role,
    }

    result = client.post("/org/users", json_body=payload)
    out.success(f"User '{email}' added as {role} (message: {result.get('message', 'ok')})")
