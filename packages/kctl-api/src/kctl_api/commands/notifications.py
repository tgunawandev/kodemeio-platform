"""Notification commands for kctl-api.

Send messages via Mattermost, Telegram, broadcast, and test.
"""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_api.core.callbacks import AppContext
from kctl_api.core.exceptions import APIError, AuthenticationError
from kctl_api.core.exceptions import ConnectionError as KctlConnectionError

app = typer.Typer(
    name="notifications", help="Send notifications — Mattermost, Telegram, broadcast.", no_args_is_help=True
)


# ---------------------------------------------------------------------------
# mattermost
# ---------------------------------------------------------------------------
@app.command()
def mattermost(
    ctx: typer.Context,
    message: Annotated[str, typer.Argument(help="Message text to send.")],
    channel: Annotated[str, typer.Option("--channel", "-c", help="Channel ID or name.")] = "",
) -> None:
    """Send a Mattermost notification via POST /api/v1/notifications/mattermost."""
    actx: AppContext = ctx.obj
    out = actx.output

    payload: dict = {"message": message}
    if channel:
        payload["channel"] = channel

    try:
        result = actx.client.post("/api/v1/notifications/mattermost", json=payload)
    except (AuthenticationError, KctlConnectionError, APIError) as e:
        out.error(str(e))
        raise typer.Exit(1) from None

    out.success("Mattermost notification sent.")
    if actx.json_mode:
        out.raw_json(result)


# ---------------------------------------------------------------------------
# telegram
# ---------------------------------------------------------------------------
@app.command()
def telegram(
    ctx: typer.Context,
    message: Annotated[str, typer.Argument(help="Message text to send.")],
    chat_id: Annotated[str, typer.Option("--chat-id", "-c", help="Telegram chat ID.")] = "",
) -> None:
    """Send a Telegram notification via POST /api/v1/notifications/telegram."""
    actx: AppContext = ctx.obj
    out = actx.output

    payload: dict = {"message": message}
    if chat_id:
        payload["chat_id"] = chat_id

    try:
        result = actx.client.post("/api/v1/notifications/telegram", json=payload)
    except (AuthenticationError, KctlConnectionError, APIError) as e:
        out.error(str(e))
        raise typer.Exit(1) from None

    out.success("Telegram notification sent.")
    if actx.json_mode:
        out.raw_json(result)


# ---------------------------------------------------------------------------
# broadcast
# ---------------------------------------------------------------------------
@app.command()
def broadcast(
    ctx: typer.Context,
    message: Annotated[str, typer.Argument(help="Broadcast message.")],
    channel_type: Annotated[str, typer.Option("--type", "-t", help="Channel type: all, mattermost, telegram.")] = "all",
) -> None:
    """Broadcast a message to all notification channels via POST /api/v1/notifications/broadcast."""
    actx: AppContext = ctx.obj
    out = actx.output

    payload: dict = {"message": message, "channel_type": channel_type}

    try:
        result = actx.client.post("/api/v1/notifications/broadcast", json=payload)
    except (AuthenticationError, KctlConnectionError, APIError) as e:
        out.error(str(e))
        raise typer.Exit(1) from None

    out.success(f"Broadcast sent ({channel_type}).")
    if actx.json_mode:
        out.raw_json(result)


# ---------------------------------------------------------------------------
# test
# ---------------------------------------------------------------------------
@app.command(name="test")
def test_notification(
    ctx: typer.Context,
    channel_type: Annotated[
        str, typer.Option("--type", "-t", help="Channel type: mattermost, telegram.")
    ] = "mattermost",
) -> None:
    """Send a test notification to verify configuration.

    Sends a test message via the broadcast endpoint.
    """
    actx: AppContext = ctx.obj
    out = actx.output

    test_msg = f"[kctl-api] Test notification via {channel_type}"
    try:
        result = actx.client.post(
            "/api/v1/notifications/broadcast",
            json={"message": test_msg, "channel_type": channel_type},
        )
    except (AuthenticationError, KctlConnectionError, APIError) as e:
        out.error(str(e))
        raise typer.Exit(1) from None

    out.success(f"Test notification sent via {channel_type}.")
    if actx.json_mode:
        out.raw_json(result)
