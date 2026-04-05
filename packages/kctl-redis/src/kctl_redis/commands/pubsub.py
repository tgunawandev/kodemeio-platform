"""Pub/Sub commands for kctl-redis."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_redis.core.callbacks import AppContext

app = typer.Typer(help="Redis Pub/Sub operations.", no_args_is_help=True)


@app.command()
def channels(
    ctx: typer.Context,
    pattern: Annotated[str, typer.Option(help="Channel pattern")] = "*",
) -> None:
    """List active Pub/Sub channels."""
    app_ctx: AppContext = ctx.obj
    out = app_ctx.output
    r = app_ctx.client.r

    chans = r.pubsub_channels(pattern)
    if app_ctx.json_mode:
        out.json({"channels": chans})
    else:
        if chans:
            rows = [{"channel": c} for c in chans]
            out.table(rows, columns=["channel"], title="Active Channels")
        else:
            out.info("No active channels")

    app_ctx.close()


@app.command()
def numsub(
    ctx: typer.Context,
    channel_names: Annotated[list[str], typer.Argument(help="Channel names")],
) -> None:
    """Show subscriber counts for channels."""
    app_ctx: AppContext = ctx.obj
    out = app_ctx.output
    r = app_ctx.client.r

    result = r.pubsub_numsub(*channel_names)
    if app_ctx.json_mode:
        out.json({"channels": {k: v for k, v in result.items()}})
    else:
        rows = [{"channel": k, "subscribers": v} for k, v in result.items()]
        out.table(rows, columns=["channel", "subscribers"], title="Subscriber Counts")

    app_ctx.close()


@app.command()
def publish(
    ctx: typer.Context,
    channel: Annotated[str, typer.Argument(help="Channel name")],
    message: Annotated[str, typer.Argument(help="Message to publish")],
) -> None:
    """Publish a message to a channel."""
    app_ctx: AppContext = ctx.obj
    out = app_ctx.output
    r = app_ctx.client.r

    receivers = r.publish(channel, message)
    out.success(f"Published to '{channel}', received by {receivers} subscriber(s)")
    app_ctx.close()
