"""Announce command -- send announcements to streams."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_zulip.core.callbacks import AppContext

app = typer.Typer(help="Send announcements.")


@app.command("send")
def send(
    ctx: typer.Context,
    message: Annotated[str, typer.Argument(help="Announcement message content")],
    stream: Annotated[str, typer.Option("--stream", "-s", help="Target stream name")],
    topic: Annotated[str, typer.Option("--topic", "-t", help="Topic name")] = "Announcement",
) -> None:
    """Send an announcement to a stream topic."""
    c: AppContext = ctx.obj

    result = c.client.post(
        "messages",
        data={
            "type": "stream",
            "to": stream,
            "topic": topic,
            "content": message,
        },
    )

    msg_id = result.get("id", "")
    c.output.success(f"Announcement sent to #{stream} > {topic} (ID: {msg_id})")
