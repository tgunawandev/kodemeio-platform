"""User info commands."""

from __future__ import annotations

import typer

from kctl_linear.core.callbacks import AppContext
from kctl_linear.core.client import USERS_LIST_QUERY

app = typer.Typer(help="User information.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all workspace members."""
    actx: AppContext = ctx.obj
    out = actx.output

    data = actx.client.query(USERS_LIST_QUERY)
    users = data.get("users", {}).get("nodes", [])

    if out.json_mode:
        out.raw_json(users)
        return

    if not users:
        out.info("No users found")
        return

    rows = [
        [
            u.get("name", ""),
            u.get("email", ""),
            "Yes" if u.get("admin") else "No",
            "Yes" if u.get("active", True) else "No",
        ]
        for u in users
    ]
    out.table(
        f"Users ({len(users)})",
        [("Name", "cyan"), ("Email", "white"), ("Admin", "yellow"), ("Active", "green")],
        rows,
    )


@app.command()
def me(ctx: typer.Context) -> None:
    """Show current authenticated user."""
    actx: AppContext = ctx.obj
    out = actx.output

    viewer = actx.client.viewer()

    if out.json_mode:
        out.raw_json(viewer)
        return

    sections = [
        (
            "Current User",
            [
                ("Name", viewer.get("name", "")),
                ("Email", viewer.get("email", "")),
                ("Admin", str(viewer.get("admin", False))),
                ("Active", str(viewer.get("active", True))),
            ],
        ),
    ]
    out.detail("Me", sections)
