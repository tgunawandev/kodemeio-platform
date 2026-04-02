"""User and access management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_dokploy.core.callbacks import AppContext

app = typer.Typer(help="Manage Dokploy users and access.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all users."""
    c: AppContext = ctx.obj
    users = c.client.get("/user.all")
    if not isinstance(users, list):
        users = []
    rows = []
    for u in users:
        uid = u.get("userId", u.get("id", ""))
        email = u.get("email", "")
        role = u.get("rol", u.get("role", "unknown"))
        status = u.get("status", u.get("isActive", "active"))
        created = u.get("createdAt", "-")
        rows.append([uid, email, role, str(status), str(created)])
    c.output.table(
        "Users",
        [("ID", "dim"), ("Email", "cyan"), ("Role", ""), ("Status", ""), ("Created", "dim")],
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
    data = c.client.get("/user.one", params={"userId": user_id})
    if not isinstance(data, dict):
        c.output.error(f"User '{user_id}' not found")
        raise typer.Exit(1)
    sections = [
        (
            "User",
            [
                ("ID", data.get("userId", data.get("id", ""))),
                ("Email", data.get("email", "")),
                ("Role", data.get("rol", data.get("role", "unknown"))),
                ("Status", str(data.get("status", data.get("isActive", "active")))),
                ("Created", data.get("createdAt", "-")),
            ],
        ),
    ]
    c.output.detail(f"User: {data.get('email', '')}", sections, data_for_json=data)


@app.command()
def create(
    ctx: typer.Context,
    email: Annotated[str, typer.Option("--email", "-e", help="User email")],
    password: Annotated[str, typer.Option("--password", help="User password", prompt=True, hide_input=True)],
    role: Annotated[str, typer.Option("--role", "-r", help="User role (admin, user)")] = "user",
) -> None:
    """Create a new user."""
    c: AppContext = ctx.obj
    payload: dict = {
        "email": email,
        "password": password,
        "rol": role,
    }
    result = c.client.post("/user.create", json=payload)
    uid = result.get("userId", result.get("id", "")) if isinstance(result, dict) else ""
    c.output.success(f"User '{email}' created: {uid}")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def update(
    ctx: typer.Context,
    user_id: Annotated[str, typer.Argument(help="User ID")],
    role: Annotated[str | None, typer.Option("--role", "-r", help="New role")] = None,
    email: Annotated[str | None, typer.Option("--email", "-e", help="New email")] = None,
    password: Annotated[str | None, typer.Option("--password", help="New password")] = None,
) -> None:
    """Update a user."""
    c: AppContext = ctx.obj
    payload: dict = {"userId": user_id}
    if role is not None:
        payload["rol"] = role
    if email is not None:
        payload["email"] = email
    if password is not None:
        payload["password"] = password
    if len(payload) == 1:
        c.output.error("No update options provided. Use --role, --email, or --password.")
        raise typer.Exit(1)
    result = c.client.post("/user.update", json=payload)
    c.output.success(f"User '{user_id}' updated")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def remove(
    ctx: typer.Context,
    user_id: Annotated[str, typer.Argument(help="User ID to remove")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Remove a user (destructive)."""
    c: AppContext = ctx.obj
    if not force:
        typer.confirm(f"Remove user '{user_id}'? This cannot be undone.", abort=True)
    result = c.client.post("/user.remove", json={"userId": user_id})
    c.output.success(f"User '{user_id}' removed")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def permissions(
    ctx: typer.Context,
    user_id: Annotated[str, typer.Argument(help="User ID")],
) -> None:
    """Show user permissions and project access."""
    c: AppContext = ctx.obj
    data = c.client.get("/user.one", params={"userId": user_id})
    if not isinstance(data, dict):
        c.output.error(f"User '{user_id}' not found")
        raise typer.Exit(1)
    role = data.get("rol", data.get("role", "unknown"))
    email = data.get("email", "")
    perms = data.get("permissions", [])
    projects = data.get("projects", [])
    sections = [
        (
            "User",
            [
                ("ID", data.get("userId", data.get("id", ""))),
                ("Email", email),
                ("Role", role),
            ],
        ),
    ]
    if perms:
        perm_items = [
            (p.get("name", p.get("permission", str(i))), str(p.get("granted", True))) for i, p in enumerate(perms)
        ]
        sections.append(("Permissions", perm_items))
    if projects:
        proj_items = [
            (p.get("name", p.get("projectName", str(i))), p.get("projectId", "-")) for i, p in enumerate(projects)
        ]
        sections.append(("Projects", proj_items))
    if not perms and not projects:
        sections.append(("Access", [("Info", f"Role '{role}' — no explicit permission entries")]))
    c.output.detail(f"Permissions: {email}", sections, data_for_json=data)
