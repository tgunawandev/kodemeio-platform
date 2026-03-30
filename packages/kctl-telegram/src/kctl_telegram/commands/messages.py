"""Message management commands.

Send, broadcast, schedule, and manage Telegram messages.
"""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_telegram.core.callbacks import AppContext

app = typer.Typer(help="Send and manage messages.")


@app.command()
def send(
    ctx: typer.Context,
    chat_id: Annotated[str, typer.Option("--chat-id", help="Target chat ID.")],
    text: Annotated[str, typer.Option("--text", help="Message text to send.")],
    bot_id: Annotated[int | None, typer.Option("--bot-id", help="Bot ID to send from.")] = None,
    parse_mode: Annotated[
        str | None, typer.Option("--parse-mode", help="Parse mode: HTML, Markdown, MarkdownV2")
    ] = None,
) -> None:
    """Send a message to a specific chat."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    payload: dict = {
        "chat_id": chat_id,
        "text": text,
    }
    if bot_id is not None:
        payload["bot_id"] = bot_id
    if parse_mode:
        payload["parse_mode"] = parse_mode

    result = c.post("messages/send", json=payload)

    out.success("Message sent")
    out.kv("Chat ID", chat_id)
    if result.get("message_id"):
        out.kv("Message ID", str(result["message_id"]))

    if actx.output.json_mode:
        out.raw_json(result)


@app.command()
def broadcast(
    ctx: typer.Context,
    text: Annotated[str, typer.Option("--text", help="Message text to broadcast.")],
    bot_id: Annotated[int | None, typer.Option("--bot-id", help="Bot ID to send from.")] = None,
    parse_mode: Annotated[
        str | None, typer.Option("--parse-mode", help="Parse mode: HTML, Markdown, MarkdownV2.")
    ] = None,
) -> None:
    """Broadcast a message to all groups."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    payload: dict = {"text": text}
    if bot_id is not None:
        payload["bot_id"] = bot_id
    if parse_mode:
        payload["parse_mode"] = parse_mode

    result = c.post("messages/broadcast", json=payload)

    sent_count = result.get("sent_count", result.get("count", 0))
    out.success(f"Broadcast sent to {sent_count} group(s)")

    if actx.output.json_mode:
        out.raw_json(result)


@app.command()
def schedule(
    ctx: typer.Context,
    text: Annotated[str, typer.Option("--text", help="Message text to schedule.")],
    target_id: Annotated[str, typer.Option("--target-id", help="Target chat/group ID.")],
    at: Annotated[str, typer.Option("--at", help="ISO 8601 datetime for delivery (e.g. 2026-03-27T10:00:00Z).")],
    bot_id: Annotated[int | None, typer.Option("--bot-id", help="Bot ID to send from.")] = None,
) -> None:
    """Schedule a message for later delivery."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    payload: dict = {
        "text": text,
        "target_id": target_id,
        "scheduled_at": at,
    }
    if bot_id is not None:
        payload["bot_id"] = bot_id

    result = c.post("messages/schedule", json=payload)

    out.success(f"Message scheduled for {at}")
    if result.get("id"):
        out.kv("Schedule ID", str(result["id"]))
    out.kv("Target", target_id)

    if actx.output.json_mode:
        out.raw_json(result)


@app.command()
def scheduled(ctx: typer.Context) -> None:
    """List scheduled messages."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    data = c.get("messages/scheduled")
    messages = data.get("results", []) if isinstance(data, dict) else data if isinstance(data, list) else []

    if not messages:
        out.warn("No scheduled messages found.")
        return

    rows: list[list[str]] = []
    json_data: list[dict] = []

    for msg in messages:
        msg_id = str(msg.get("id", ""))
        target = str(msg.get("target_id", msg.get("chat_id", "")))
        text = msg.get("text", "")
        if len(text) > 50:
            text = text[:47] + "..."
        scheduled_at = msg.get("scheduled_at", "")
        status = msg.get("status", "pending")

        rows.append([msg_id, target, text, scheduled_at, status])
        json_data.append(msg)

    out.table(
        "Scheduled Messages",
        [("ID", "cyan"), ("Target", ""), ("Text", ""), ("Scheduled At", ""), ("Status", "")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def cancel(
    ctx: typer.Context,
    message_id: Annotated[int, typer.Argument(help="Scheduled message ID to cancel")],
) -> None:
    """Cancel a scheduled message."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    c.delete(f"messages/scheduled/{message_id}")
    out.success(f"Scheduled message {message_id} cancelled")
