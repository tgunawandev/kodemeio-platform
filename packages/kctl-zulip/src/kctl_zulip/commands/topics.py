"""Topic management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_zulip.core.callbacks import AppContext
from kctl_zulip.commands.streams import _resolve_stream_id

app = typer.Typer(help="Topic management.")


@app.command("list")
def list_(
    ctx: typer.Context,
    stream: Annotated[str, typer.Option("--stream", "-s", help="Stream name or ID")],
) -> None:
    """List topics in a stream."""
    c: AppContext = ctx.obj
    stream_id = _resolve_stream_id(c.client, stream)

    data = c.client.get(f"users/me/{stream_id}/topics")
    topics = data.get("topics", [])

    rows = [
        [
            t.get("name", ""),
            str(t.get("max_id", "")),
        ]
        for t in topics
    ]

    c.output.table(
        f"Topics in stream {stream} ({len(topics)})",
        [("Topic", "green"), ("Latest Message ID", "dim")],
        rows,
        data_for_json=topics,
    )
