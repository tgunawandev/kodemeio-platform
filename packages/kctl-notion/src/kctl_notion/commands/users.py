"""Users command group -- workspace user management."""

from __future__ import annotations

from typing import Any

import typer

from kctl_notion.core.callbacks import AppContext

app = typer.Typer(help="Workspace user management.")


def _format_user_type(user: dict[str, Any]) -> str:
    """Format user type (person or bot)."""
    user_type = user.get("type", "unknown")
    if user_type == "bot":
        owner = user.get("bot", {}).get("owner", {})
        owner_type = owner.get("type", "")
        return f"bot ({owner_type})"
    return user_type


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List workspace members and bots."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.get_client()

    try:
        all_users: list[dict[str, Any]] = []
        cursor: str | None = None

        while True:
            result = client.list_users(start_cursor=cursor)
            users = result.get("results", [])
            all_users.extend(users)
            if not result.get("has_more"):
                break
            cursor = result.get("next_cursor")
            if not cursor:
                break

        if out.json_mode:
            out.raw_json({"users": all_users, "count": len(all_users)})
            return

        if not all_users:
            out.warn("No users found")
            return

        rows: list[list[str]] = []
        for user in all_users:
            user_id = user.get("id", "")[:8]
            name = user.get("name", "(unnamed)")
            user_type = _format_user_type(user)
            email = ""
            if user.get("type") == "person":
                email = user.get("person", {}).get("email", "")
            rows.append([user_id, name, user_type, email])

        out.table(
            f"Users ({len(all_users)})",
            [("ID", "cyan"), ("Name", "white"), ("Type", "green"), ("Email", "yellow")],
            rows,
        )
    finally:
        actx.close()


@app.command()
def me(ctx: typer.Context) -> None:
    """Show current bot/integration user."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.get_client()

    try:
        user = client.get_me()

        if out.json_mode:
            out.raw_json(user)
            return

        name = user.get("name", "Unknown")
        user_type = user.get("type", "unknown")
        user_id = user.get("id", "")
        bot_info = user.get("bot", {})
        workspace = bot_info.get("workspace_name", "N/A") if bot_info else "N/A"

        sections = [
            (
                "Bot Info",
                [
                    ("ID", user_id),
                    ("Name", name),
                    ("Type", user_type),
                    ("Workspace", workspace),
                ],
            ),
        ]
        out.detail("Current User", sections)
    finally:
        actx.close()
