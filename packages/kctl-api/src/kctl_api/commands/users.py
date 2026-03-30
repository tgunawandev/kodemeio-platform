"""User management commands for kctl-api.

CRUD operations on users, role and tier assignment.
"""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_api.core.callbacks import AppContext
from kctl_api.core.exceptions import APIError, AuthenticationError
from kctl_api.core.exceptions import ConnectionError as KctlConnectionError
from kctl_api.core.resolve import resolve_user, resolve_user_id
from kctl_api.core.utils import role_color, tier_color

app = typer.Typer(
    name="users", help="User management — list, create, update, delete, roles, tiers.", no_args_is_help=True
)


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------
@app.command(name="list")
def list_users(
    ctx: typer.Context,
    page: Annotated[int, typer.Option("--page", "-p", help="Page number.")] = 1,
    per_page: Annotated[int, typer.Option("--per-page", "-n", help="Items per page.")] = 20,
    search: Annotated[str | None, typer.Option("--search", "-s", help="Search by name or email.")] = None,
) -> None:
    """List users with pagination and optional search."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        params: dict[str, str | int] = {"page": page, "per_page": per_page}
        if search:
            params["search"] = search
        data = actx.client.get("/api/v1/users", params=params)
    except AuthenticationError as e:
        out.error(f"Auth failed: {e}")
        raise typer.Exit(1) from None
    except KctlConnectionError as e:
        out.error(f"Connection failed: {e}")
        raise typer.Exit(1) from None
    except APIError as e:
        out.error(f"API error: {e.detail}")
        raise typer.Exit(1) from None

    items = data.get("items", []) if isinstance(data, dict) else []
    total = data.get("total", len(items)) if isinstance(data, dict) else len(items)

    rows: list[list[str]] = []
    for u in items:
        rows.append(
            [
                str(u.get("id", "")),
                u.get("email", ""),
                u.get("name", u.get("full_name", "")),
                role_color(u.get("role", "")),
                tier_color(u.get("tier", "")),
                "[green]yes[/green]" if u.get("is_active") else "[red]no[/red]",
            ]
        )

    out.table(
        title=f"Users (page {page}, {total} total)",
        columns=[
            ("ID", "bold"),
            ("Email", ""),
            ("Name", ""),
            ("Role", ""),
            ("Tier", ""),
            ("Active", ""),
        ],
        rows=rows,
        data_for_json=items,
    )


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------
@app.command()
def get(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="User ID or email.")],
) -> None:
    """Get detailed user information by ID or email."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        user = resolve_user(actx.client, identifier)
    except typer.Exit:
        raise
    except (AuthenticationError, KctlConnectionError, APIError) as e:
        out.error(str(e))
        raise typer.Exit(1) from None

    role = user.get("role", "unknown")
    tier = user.get("tier", "unknown")

    out.detail(
        title=f"User: {user.get('email', identifier)}",
        sections=[
            (
                "Identity",
                [
                    ("ID", str(user.get("id", ""))),
                    ("Email", user.get("email", "")),
                    ("Name", user.get("name", user.get("full_name", ""))),
                ],
            ),
            (
                "Access",
                [
                    ("Role", role_color(role)),
                    ("Tier", tier_color(tier)),
                    ("Active", str(user.get("is_active", ""))),
                ],
            ),
            (
                "Timestamps",
                [
                    ("Created", str(user.get("created_at", ""))),
                    ("Updated", str(user.get("updated_at", ""))),
                ],
            ),
        ],
        data_for_json=user,
    )


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------
@app.command()
def create(
    ctx: typer.Context,
    email: Annotated[str, typer.Option("--email", "-e", help="User email.")],
    name: Annotated[str, typer.Option("--name", "-n", help="User full name.")],
    password: Annotated[
        str | None, typer.Option("--password", help="Password (prompted if omitted).", hide_input=True)
    ] = None,
) -> None:
    """Create a new user via POST /api/v1/auth/register."""
    actx: AppContext = ctx.obj
    out = actx.output

    if not password:
        password = typer.prompt("Password", hide_input=True)

    try:
        result = actx.client.post(
            "/api/v1/auth/register",
            json={"email": email, "name": name, "password": password},
        )
    except AuthenticationError as e:
        out.error(f"Auth failed: {e}")
        raise typer.Exit(1) from None
    except KctlConnectionError as e:
        out.error(f"Connection failed: {e}")
        raise typer.Exit(1) from None
    except APIError as e:
        out.error(f"API error: {e.detail}")
        raise typer.Exit(1) from None

    out.success(f"User created: {email}")
    if actx.json_mode:
        out.raw_json(result)


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------
@app.command()
def update(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="User ID or email.")],
    name: Annotated[str | None, typer.Option("--name", "-n", help="New name.")] = None,
    email: Annotated[str | None, typer.Option("--email", "-e", help="New email.")] = None,
) -> None:
    """Update user fields via PATCH /api/v1/users/{id}."""
    actx: AppContext = ctx.obj
    out = actx.output

    user_id = resolve_user_id(actx.client, identifier)
    payload: dict[str, str] = {}
    if name:
        payload["name"] = name
    if email:
        payload["email"] = email

    if not payload:
        out.warn("No fields to update. Use --name or --email.")
        raise typer.Exit(0)

    try:
        result = actx.client.patch(f"/api/v1/users/{user_id}", json=payload)
    except (AuthenticationError, KctlConnectionError, APIError) as e:
        out.error(str(e))
        raise typer.Exit(1) from None

    out.success(f"User {user_id} updated.")
    if actx.json_mode:
        out.raw_json(result)


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------
@app.command()
def delete(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="User ID or email.")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation.")] = False,
) -> None:
    """Soft-delete a user via DELETE /api/v1/users/{id}."""
    actx: AppContext = ctx.obj
    out = actx.output

    user_id = resolve_user_id(actx.client, identifier)

    if not force:
        confirm = typer.confirm(f"Delete user {identifier} (id={user_id})?", default=False)
        if not confirm:
            out.info("Cancelled.")
            raise typer.Exit(0)

    try:
        result = actx.client.delete(f"/api/v1/users/{user_id}")
    except (AuthenticationError, KctlConnectionError, APIError) as e:
        out.error(str(e))
        raise typer.Exit(1) from None

    out.success(f"User {user_id} deleted.")
    if actx.json_mode:
        out.raw_json(result)


# ---------------------------------------------------------------------------
# set-role
# ---------------------------------------------------------------------------
@app.command(name="set-role")
def set_role(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="User ID or email.")],
    role: Annotated[str, typer.Argument(help="Role: user or admin.")],
) -> None:
    """Set user role via PATCH /api/v1/users/{id}."""
    actx: AppContext = ctx.obj
    out = actx.output

    if role not in ("user", "admin"):
        out.error(f"Invalid role '{role}'. Must be 'user' or 'admin'.")
        raise typer.Exit(1)

    user_id = resolve_user_id(actx.client, identifier)

    try:
        result = actx.client.patch(f"/api/v1/users/{user_id}", json={"role": role})
    except (AuthenticationError, KctlConnectionError, APIError) as e:
        out.error(str(e))
        raise typer.Exit(1) from None

    out.success(f"User {user_id} role set to {role}.")
    if actx.json_mode:
        out.raw_json(result)


# ---------------------------------------------------------------------------
# set-tier
# ---------------------------------------------------------------------------
@app.command(name="set-tier")
def set_tier(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="User ID or email.")],
    tier: Annotated[str, typer.Argument(help="Tier: free, user, premium, admin.")],
) -> None:
    """Set user tier via PATCH /api/v1/users/{id}."""
    actx: AppContext = ctx.obj
    out = actx.output

    valid_tiers = ("free", "user", "premium", "admin")
    if tier not in valid_tiers:
        out.error(f"Invalid tier '{tier}'. Must be one of: {', '.join(valid_tiers)}")
        raise typer.Exit(1)

    user_id = resolve_user_id(actx.client, identifier)

    try:
        result = actx.client.patch(f"/api/v1/users/{user_id}", json={"tier": tier})
    except (AuthenticationError, KctlConnectionError, APIError) as e:
        out.error(str(e))
        raise typer.Exit(1) from None

    out.success(f"User {user_id} tier set to {tier}.")
    if actx.json_mode:
        out.raw_json(result)
