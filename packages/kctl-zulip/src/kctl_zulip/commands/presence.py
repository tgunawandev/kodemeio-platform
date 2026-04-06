"""User presence and status commands."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from kctl_zulip.core.callbacks import AppContext

app = typer.Typer(help="User presence and status.")


@app.command("list")
def list_(
    ctx: typer.Context,
) -> None:
    """List all users' presence status."""
    c: AppContext = ctx.obj
    data = c.client.get("realm/presence")
    presences = data.get("presences", {})

    rows = []
    for email, info in presences.items():
        aggregated = info.get("aggregated", {})
        status = aggregated.get("status", "unknown")
        timestamp = str(aggregated.get("timestamp", ""))
        rows.append([email, status, timestamp])

    rows.sort(key=lambda r: r[1])

    c.output.table(
        f"User Presence ({len(rows)})",
        [("User", "cyan"), ("Status", "green"), ("Timestamp", "dim")],
        rows,
        data_for_json=presences,
    )


@app.command()
def get(
    ctx: typer.Context,
    user_id_or_email: Annotated[str, typer.Argument(help="User ID or email")],
) -> None:
    """Get a specific user's presence status."""
    c: AppContext = ctx.obj
    data = c.client.get(f"users/{user_id_or_email}/presence")
    presence = data.get("presence", {})

    aggregated = presence.get("aggregated", {})
    sections = [
        (
            "Presence",
            [
                ("User", user_id_or_email),
                ("Status", aggregated.get("status", "unknown")),
                ("Timestamp", str(aggregated.get("timestamp", ""))),
                ("Client", aggregated.get("client", "")),
            ],
        ),
    ]

    # Show per-client details
    client_items = []
    for client, info in presence.items():
        if client != "aggregated":
            client_items.append((client, f"{info.get('status', '')} (ts: {info.get('timestamp', '')})"))
    if client_items:
        sections.append(("Clients", client_items))

    c.output.detail(f"Presence: {user_id_or_email}", sections, data_for_json=data)


@app.command("set-status")
def set_status(
    ctx: typer.Context,
    text: Annotated[Optional[str], typer.Option("--text", "-t", help="Status text")] = None,
    emoji: Annotated[Optional[str], typer.Option("--emoji", "-e", help="Status emoji name")] = None,
) -> None:
    """Set your status message and emoji."""
    c: AppContext = ctx.obj

    payload: dict = {}
    if text is not None:
        payload["status_text"] = text
    if emoji is not None:
        payload["emoji_name"] = emoji

    if not payload:
        c.output.warn("Specify --text and/or --emoji to set status")
        return

    # Zulip expects away field
    payload.setdefault("away", False)

    c.client.post("users/me/status", data=payload)
    c.output.success("Status updated")
