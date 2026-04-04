"""Mail queue management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_mailcow.core.callbacks import AppContext

app = typer.Typer(help="Manage mail queue.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List mail queue entries."""
    c: AppContext = ctx.obj
    data = c.client.mc_get("mailq/all")
    items = data if isinstance(data, list) else []

    if not items:
        c.output.info("Mail queue is empty")
        if c.json_mode:
            c.output.raw_json([])
        return

    rows = []
    for q in items:
        rows.append(
            [
                q.get("queue_id", ""),
                q.get("sender", ""),
                q.get("recipients", ""),
                q.get("arrival_time", ""),
                q.get("message_size", ""),
            ]
        )

    c.output.table(
        "Mail Queue",
        [("Queue ID", "cyan"), ("Sender", ""), ("Recipients", ""), ("Arrival Time", ""), ("Size", "")],
        rows,
        data_for_json=items,
    )


@app.command()
def flush(
    ctx: typer.Context,
    queue_id: Annotated[str, typer.Argument(help="Queue ID to flush, or 'all'")] = "all",
) -> None:
    """Flush (retry) queued messages."""
    c: AppContext = ctx.obj
    if queue_id == "all":
        result = c.client.mc_edit("mailq", {"action": "flush", "items": ["all"]})
    else:
        result = c.client.mc_edit("mailq", {"action": "flush", "items": [queue_id]})

    c.output.success(f"Queue flush requested: {queue_id}")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def delete(
    ctx: typer.Context,
    queue_id: Annotated[str, typer.Argument(help="Queue ID to delete, or 'all'")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete queued messages."""
    c: AppContext = ctx.obj
    if not force:
        if not typer.confirm(f"Delete queue entry '{queue_id}'?"):
            raise typer.Exit(0)

    if queue_id == "all":
        result = c.client.mc_edit("mailq", {"action": "super_delete", "items": ["all"]})
    else:
        result = c.client.mc_edit("mailq", {"action": "super_delete", "items": [queue_id]})

    c.output.success(f"Queue entry deleted: {queue_id}")
    if c.json_mode:
        c.output.raw_json(result)
