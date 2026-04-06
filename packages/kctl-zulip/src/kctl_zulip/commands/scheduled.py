"""Scheduled messages commands."""

from __future__ import annotations

import json
from typing import Annotated, Optional

import typer

from kctl_zulip.core.callbacks import AppContext

app = typer.Typer(help="Scheduled messages.")


@app.command("list")
def list_(
    ctx: typer.Context,
) -> None:
    """List scheduled messages."""
    c: AppContext = ctx.obj
    data = c.client.get("scheduled_messages")
    messages = data.get("scheduled_messages", [])

    rows = []
    for m in messages:
        mid = str(m.get("scheduled_message_id", ""))
        msg_type = m.get("type", "")
        to = str(m.get("to", ""))
        topic = m.get("topic", "") or ""
        content = (m.get("content", "") or "")[:50]
        deliver_at = str(m.get("scheduled_delivery_timestamp", ""))
        rows.append([mid, msg_type, to, topic, content, deliver_at])

    c.output.table(
        f"Scheduled Messages ({len(messages)})",
        [("ID", "cyan"), ("Type", ""), ("To", "green"), ("Topic", ""), ("Content", ""), ("Deliver At", "dim")],
        rows,
        data_for_json=messages,
    )


@app.command()
def create(
    ctx: typer.Context,
    content: Annotated[str, typer.Option("--content", "-c", help="Message content")],
    deliver_at: Annotated[int, typer.Option("--deliver-at", help="Unix timestamp for delivery")],
    to: Annotated[str, typer.Option("--to", help="Stream name or comma-separated user IDs/emails")],
    topic: Annotated[Optional[str], typer.Option("--topic", "-t", help="Topic (required for stream messages)")] = None,
    msg_type: Annotated[str, typer.Option("--type", help="Message type: stream or direct")] = "stream",
) -> None:
    """Create a scheduled message."""
    c: AppContext = ctx.obj

    payload: dict = {
        "type": msg_type,
        "content": content,
        "scheduled_delivery_timestamp": str(deliver_at),
    }

    if msg_type == "stream":
        payload["to"] = to
        if topic:
            payload["topic"] = topic
    else:
        # Direct message: parse comma-separated IDs
        recipients = []
        for r in to.split(","):
            r = r.strip()
            try:
                recipients.append(int(r))
            except ValueError:
                recipients.append(r)
        payload["to"] = json.dumps(recipients)

    result = c.client.post("scheduled_messages", data=payload)
    msg_id = result.get("scheduled_message_id", "")
    c.output.success(f"Scheduled message created (ID: {msg_id})")


@app.command()
def update(
    ctx: typer.Context,
    msg_id: Annotated[int, typer.Argument(help="Scheduled message ID")],
    content: Annotated[Optional[str], typer.Option("--content", "-c", help="New content")] = None,
    deliver_at: Annotated[Optional[int], typer.Option("--deliver-at", help="New delivery timestamp")] = None,
    topic: Annotated[Optional[str], typer.Option("--topic", "-t", help="New topic")] = None,
) -> None:
    """Update a scheduled message."""
    c: AppContext = ctx.obj

    payload: dict = {}
    if content is not None:
        payload["content"] = content
    if deliver_at is not None:
        payload["scheduled_delivery_timestamp"] = str(deliver_at)
    if topic is not None:
        payload["topic"] = topic

    if not payload:
        c.output.warn("No fields to update")
        return

    c.client.patch(f"scheduled_messages/{msg_id}", data=payload)
    c.output.success(f"Scheduled message {msg_id} updated")


@app.command()
def delete(
    ctx: typer.Context,
    msg_id: Annotated[int, typer.Argument(help="Scheduled message ID")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete a scheduled message."""
    c: AppContext = ctx.obj

    if not force:
        if not typer.confirm(f"Delete scheduled message {msg_id}?"):
            raise typer.Abort()

    c.client.delete(f"scheduled_messages/{msg_id}")
    c.output.success(f"Scheduled message {msg_id} deleted")
