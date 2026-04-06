"""User management commands."""

from __future__ import annotations

import json
from typing import Annotated, Optional

import typer

from kctl_zulip.core.callbacks import AppContext

app = typer.Typer(help="User management.")


@app.command("list")
def list_(
    ctx: typer.Context,
    include_deactivated: Annotated[bool, typer.Option("--include-deactivated", help="Include deactivated users")] = False,
) -> None:
    """List all users."""
    c: AppContext = ctx.obj

    if include_deactivated:
        data = c.client.get("users", params={"include_custom_profile_fields": "false"})
    else:
        data = c.client.get("users", params={"include_custom_profile_fields": "false"})

    members = data.get("members", [])
    if not include_deactivated:
        members = [m for m in members if m.get("is_active", True)]

    rows = [
        [
            str(m["user_id"]),
            m.get("email", ""),
            m.get("full_name", ""),
            m.get("role", 400).__class__.__name__ != "int" and str(m.get("role", "")) or _role_name(m.get("role", 400)),
            "yes" if m.get("is_active", True) else "no",
            "yes" if m.get("is_bot", False) else "no",
        ]
        for m in members
    ]

    c.output.table(
        f"Users ({len(members)})",
        [("ID", "cyan"), ("Email", ""), ("Name", "green"), ("Role", ""), ("Active", ""), ("Bot", "dim")],
        rows,
        data_for_json=members,
    )


def _role_name(role: int) -> str:
    return {100: "owner", 200: "admin", 300: "moderator", 400: "member", 600: "guest"}.get(role, str(role))


def _role_id(role_str: str) -> int:
    return {"owner": 100, "admin": 200, "moderator": 300, "member": 400, "guest": 600}.get(role_str.lower(), 400)


@app.command()
def get(
    ctx: typer.Context,
    user_id: Annotated[int, typer.Argument(help="User ID")],
) -> None:
    """Get detailed user info."""
    c: AppContext = ctx.obj
    data = c.client.get(f"users/{user_id}")
    user = data.get("user", {})

    c.output.detail(
        f"User: {user.get('full_name', '')}",
        [
            ("Identity", [
                ("ID", str(user.get("user_id", ""))),
                ("Email", user.get("email", "")),
                ("Name", user.get("full_name", "")),
                ("Delivery Email", user.get("delivery_email", "")),
            ]),
            ("Status", [
                ("Role", _role_name(user.get("role", 400))),
                ("Active", str(user.get("is_active", True))),
                ("Bot", str(user.get("is_bot", False))),
                ("Bot Type", str(user.get("bot_type", "")) if user.get("is_bot") else "N/A"),
                ("Timezone", user.get("timezone", "")),
                ("Date Joined", user.get("date_joined", "")),
            ]),
        ],
        data_for_json=user,
    )


@app.command()
def create(
    ctx: typer.Context,
    email: Annotated[str, typer.Argument(help="User email address")],
    full_name: Annotated[str, typer.Option("--name", help="Full display name")],
    password: Annotated[str, typer.Option("--password", help="User password")],
    role: Annotated[str, typer.Option("--role", help="Role: owner/admin/moderator/member/guest")] = "member",
) -> None:
    """Create a new user."""
    c: AppContext = ctx.obj

    result = c.client.post("users", data={
        "email": email,
        "password": password,
        "full_name": full_name,
        "role": str(_role_id(role)),
    })

    user_id = result.get("user_id", "")
    c.output.detail(
        "User Created",
        [("Details", [
            ("ID", str(user_id)),
            ("Email", email),
            ("Name", full_name),
            ("Role", role),
        ])],
        data_for_json=result,
    )


@app.command()
def update(
    ctx: typer.Context,
    user_id: Annotated[int, typer.Argument(help="User ID")],
    full_name: Annotated[Optional[str], typer.Option("--name", help="New display name")] = None,
    role: Annotated[Optional[str], typer.Option("--role", help="New role")] = None,
) -> None:
    """Update a user."""
    c: AppContext = ctx.obj
    payload: dict = {}
    if full_name is not None:
        payload["full_name"] = full_name
    if role is not None:
        payload["role"] = str(_role_id(role))

    if not payload:
        c.output.warn("No fields to update")
        return

    c.client.patch(f"users/{user_id}", data=payload)
    c.output.success(f"User {user_id} updated")


@app.command()
def deactivate(
    ctx: typer.Context,
    user_id: Annotated[int, typer.Argument(help="User ID")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Deactivate a user."""
    c: AppContext = ctx.obj

    if not force:
        data = c.client.get(f"users/{user_id}")
        user = data.get("user", {})
        if not typer.confirm(f"Deactivate user {user.get('full_name', user_id)}?"):
            raise typer.Abort()

    c.client.delete(f"users/{user_id}")
    c.output.success(f"User {user_id} deactivated")


@app.command()
def reactivate(
    ctx: typer.Context,
    user_id: Annotated[int, typer.Argument(help="User ID")],
) -> None:
    """Reactivate a deactivated user."""
    c: AppContext = ctx.obj
    c.client.post(f"users/{user_id}/reactivate")
    c.output.success(f"User {user_id} reactivated")
