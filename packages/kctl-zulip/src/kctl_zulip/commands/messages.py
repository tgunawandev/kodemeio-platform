"""Message management commands."""

from __future__ import annotations

import json
from typing import Annotated, Optional

import typer

from kctl_zulip.core.callbacks import AppContext

app = typer.Typer(help="Message management.")


@app.command("list")
def list_(
    ctx: typer.Context,
    stream: Annotated[Optional[str], typer.Option("--stream", "-s", help="Stream name")] = None,
    topic: Annotated[Optional[str], typer.Option("--topic", "-t", help="Topic name")] = None,
    num_before: Annotated[int, typer.Option("--before", help="Number of messages before anchor")] = 20,
    num_after: Annotated[int, typer.Option("--after", help="Number of messages after anchor")] = 0,
    anchor: Annotated[str, typer.Option("--anchor", help="Message anchor (newest, oldest, or message ID)")] = "newest",
) -> None:
    """List messages from a stream/topic or DMs."""
    c: AppContext = ctx.obj

    narrow: list[dict] = []
    if stream:
        narrow.append({"operator": "channel", "operand": stream})
    if topic:
        narrow.append({"operator": "topic", "operand": topic})

    params: dict = {
        "anchor": anchor,
        "num_before": str(num_before),
        "num_after": str(num_after),
        "narrow": json.dumps(narrow) if narrow else "[]",
    }

    data = c.client.get("messages", params=params)
    messages = data.get("messages", [])

    rows = []
    for m in messages:
        recipient = m.get("display_recipient", "")
        if not isinstance(recipient, str):
            recipient = "(DM)"
        # Strip HTML tags for display
        import re
        content_raw = re.sub(r"<[^>]+>", "", m.get("content", "")).strip()
        if len(content_raw) > 60:
            content_raw = content_raw[:60] + "..."
        rows.append([
            str(m.get("id", "")),
            str(m.get("sender_full_name", "")),
            str(recipient),
            str(m.get("subject", "")),
            content_raw,
            str(m.get("timestamp", "")),
        ])

    title = "Messages"
    if stream:
        title += f" in #{stream}"
    if topic:
        title += f" > {topic}"

    c.output.table(
        f"{title} ({len(messages)})",
        [("ID", "cyan"), ("Sender", "green"), ("Stream", ""), ("Topic", ""), ("Content", ""), ("Time", "dim")],
        rows,
        data_for_json=messages,
    )


@app.command()
def send(
    ctx: typer.Context,
    content: Annotated[str, typer.Argument(help="Message content")],
    stream: Annotated[Optional[str], typer.Option("--stream", "-s", help="Stream name (for channel messages)")] = None,
    topic: Annotated[Optional[str], typer.Option("--topic", "-t", help="Topic name (required for channel messages)")] = None,
    to: Annotated[Optional[str], typer.Option("--to", help="Comma-separated user IDs or emails (for direct messages)")] = None,
) -> None:
    """Send a message to a stream/topic or as a direct message."""
    c: AppContext = ctx.obj

    if stream:
        if not topic:
            c.output.error("--topic is required for channel messages")
            raise typer.Exit(1)
        payload = {
            "type": "stream",
            "to": stream,
            "topic": topic,
            "content": content,
        }
    elif to:
        recipients = []
        for r in to.split(","):
            r = r.strip()
            try:
                recipients.append(int(r))
            except ValueError:
                recipients.append(r)
        payload = {
            "type": "direct",
            "to": json.dumps(recipients),
            "content": content,
        }
    else:
        c.output.error("Specify --stream (with --topic) or --to for direct messages")
        raise typer.Exit(1)

    result = c.client.post("messages", data=payload)
    msg_id = result.get("id", "")
    c.output.success(f"Message sent (ID: {msg_id})")


@app.command()
def update(
    ctx: typer.Context,
    message_id: Annotated[int, typer.Argument(help="Message ID")],
    content: Annotated[Optional[str], typer.Option("--content", "-c", help="New content")] = None,
    topic: Annotated[Optional[str], typer.Option("--topic", "-t", help="New topic")] = None,
) -> None:
    """Update a message's content or topic."""
    c: AppContext = ctx.obj

    payload: dict = {}
    if content is not None:
        payload["content"] = content
    if topic is not None:
        payload["topic"] = topic

    if not payload:
        c.output.warn("No fields to update")
        return

    c.client.patch(f"messages/{message_id}", data=payload)
    c.output.success(f"Message {message_id} updated")


@app.command()
def delete(
    ctx: typer.Context,
    message_id: Annotated[int, typer.Argument(help="Message ID")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete a message."""
    c: AppContext = ctx.obj

    if not force:
        if not typer.confirm(f"Delete message {message_id}?"):
            raise typer.Abort()

    c.client.delete(f"messages/{message_id}")
    c.output.success(f"Message {message_id} deleted")
