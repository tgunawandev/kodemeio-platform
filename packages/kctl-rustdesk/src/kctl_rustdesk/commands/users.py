"""User management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_rustdesk.core.callbacks import AppContext

app = typer.Typer(help="Manage RustDesk users.")


@app.command("list")
def list_(
    ctx: typer.Context,
    active: Annotated[bool, typer.Option("--active", help="Only active users")] = False,
) -> None:
    """List all users."""
    c: AppContext = ctx.obj
    ex = c.executor

    where = "WHERE status = 1" if active else ""
    sql = f"SELECT name, email, is_admin, created_at, status FROM user {where} ORDER BY name;"

    rows_data = ex.query_db(sql)
    rows = [
        [
            r.get("name", ""),
            r.get("email", ""),
            "yes" if r.get("is_admin") == "1" else "",
            r.get("status", ""),
            r.get("created_at", ""),
        ]
        for r in rows_data
    ]

    c.output.table(
        "Users" + (" (active)" if active else ""),
        [("Name", "cyan"), ("Email", ""), ("Admin", "green"), ("Status", ""), ("Created", "dim")],
        rows,
        data_for_json=rows_data,
    )


@app.command("get")
def get(
    ctx: typer.Context,
    username: Annotated[str, typer.Argument(help="Username")],
) -> None:
    """Get details for a specific user."""
    c: AppContext = ctx.obj
    ex = c.executor

    users = ex.query_db(f"SELECT * FROM user WHERE name = '{username}';")
    if not users:
        c.output.error(f"User not found: {username}")
        raise typer.Exit(1)

    user = users[0]
    peer_count = ex.query_db_scalar(
        f"SELECT count(*) FROM peer WHERE user_id = (SELECT rowid FROM user WHERE name = '{username}');"
    )

    sections = [
        ("User Details", [(k, str(v)) for k, v in user.items()] + [("Peers", peer_count)]),
    ]
    data = dict(user)
    data["peer_count"] = int(peer_count) if peer_count.isdigit() else 0
    c.output.detail(f"User: {username}", sections, data_for_json=data)


@app.command()
def count(ctx: typer.Context) -> None:
    """Count users."""
    c: AppContext = ctx.obj
    ex = c.executor

    total = ex.query_db_scalar("SELECT count(*) FROM user;")
    active = ex.query_db_scalar("SELECT count(*) FROM user WHERE status = 1;")
    admins = ex.query_db_scalar("SELECT count(*) FROM user WHERE is_admin = 1;")

    sections = [("User Count", [("Total", total), ("Active", active), ("Admins", admins)])]
    c.output.detail(
        "User Count",
        sections,
        data_for_json={
            "total": int(total),
            "active": int(active),
            "admins": int(admins),
        },
    )


@app.command()
def groups(ctx: typer.Context) -> None:
    """List user groups."""
    c: AppContext = ctx.obj
    rows_data = c.executor.query_db("SELECT * FROM grp ORDER BY name;")
    rows = [[r.get("name", ""), r.get("note", ""), r.get("created_at", "")] for r in rows_data]

    c.output.table(
        "Groups",
        [("Name", "cyan"), ("Note", ""), ("Created", "dim")],
        rows,
        data_for_json=rows_data,
    )


@app.command()
def export(ctx: typer.Context) -> None:
    """Export all users as JSON."""
    c: AppContext = ctx.obj
    rows = c.executor.query_db("SELECT * FROM user ORDER BY name;")
    c.output.raw_json(rows)
