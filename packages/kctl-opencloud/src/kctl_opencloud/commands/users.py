"""User management commands for kctl-opencloud."""

from __future__ import annotations

from typing import Annotated, Any

import typer

from kctl_opencloud.core.callbacks import AppContext

app = typer.Typer(help="User management.")


@app.command("list")
def list_(
    ctx: typer.Context,
    search: Annotated[str | None, typer.Option("--search", "-s", help="Search by name or email")] = None,
) -> None:
    """List all users."""
    c: AppContext = ctx.obj
    params: dict[str, Any] = {}
    if search:
        params["$search"] = search

    users = c.client.get_all("users", params=params)

    rows = []
    for u in users:
        rows.append(
            [
                u.get("id", ""),
                u.get("displayName", "-"),
                u.get("mail", "-"),
                "active" if u.get("accountEnabled", True) else "disabled",
            ]
        )

    c.output.table(
        "Users",
        [("ID", "cyan"), ("Name", "green"), ("Email", "white"), ("Status", "yellow")],
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
    user = c.client.get(f"users/{user_id}")

    sections = [
        (
            "User",
            [
                ("ID", user.get("id", "")),
                ("Display Name", user.get("displayName", "-")),
                ("Email", user.get("mail", "-")),
                ("Username", user.get("onPremisesSamAccountName", "-")),
                ("Enabled", str(user.get("accountEnabled", True))),
            ],
        ),
    ]
    c.output.detail("User Details", sections, data_for_json=user)


@app.command()
def create(
    ctx: typer.Context,
    email: Annotated[str, typer.Argument(help="User email address")],
    name: Annotated[str | None, typer.Option("--name", "-n", help="Display name")] = None,
    password: Annotated[str | None, typer.Option("--password", help="Initial password")] = None,
) -> None:
    """Create a new user."""
    c: AppContext = ctx.obj
    display_name = name or email.split("@")[0]
    username = email.split("@")[0]

    user_data: dict[str, Any] = {
        "displayName": display_name,
        "mail": email,
        "onPremisesSamAccountName": username,
        "accountEnabled": True,
    }
    if password:
        user_data["passwordProfile"] = {"password": password}

    user = c.client.post("users", data=user_data)
    c.output.success(f"User created: {user.get('displayName', email)}")


@app.command()
def update(
    ctx: typer.Context,
    user_id: Annotated[str, typer.Argument(help="User ID")],
    name: Annotated[str | None, typer.Option("--name", "-n", help="Display name")] = None,
    email: Annotated[str | None, typer.Option("--email", help="Email address")] = None,
    enabled: Annotated[bool | None, typer.Option("--enabled/--disabled", help="Account status")] = None,
) -> None:
    """Update a user."""
    c: AppContext = ctx.obj
    patch_data: dict[str, Any] = {}
    if name is not None:
        patch_data["displayName"] = name
    if email is not None:
        patch_data["mail"] = email
    if enabled is not None:
        patch_data["accountEnabled"] = enabled

    if not patch_data:
        c.output.warn("No changes specified")
        return

    c.client.patch(f"users/{user_id}", data=patch_data)
    c.output.success(f"User {user_id} updated")


@app.command()
def delete(
    ctx: typer.Context,
    user_id: Annotated[str, typer.Argument(help="User ID")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Delete a user."""
    c: AppContext = ctx.obj
    if not force:
        typer.confirm(f"Delete user {user_id}?", abort=True)

    c.client.delete(f"users/{user_id}")
    c.output.success(f"User {user_id} deleted")
