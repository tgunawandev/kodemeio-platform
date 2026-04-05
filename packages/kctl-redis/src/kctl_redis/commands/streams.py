"""Redis Streams commands for kctl-redis."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_redis.core.callbacks import AppContext

app = typer.Typer(help="Redis Streams operations.", no_args_is_help=True)


@app.command()
def info(
    ctx: typer.Context,
    key: Annotated[str, typer.Argument(help="Stream key")],
) -> None:
    """Show stream information."""
    app_ctx: AppContext = ctx.obj
    out = app_ctx.output
    r = app_ctx.client.r

    try:
        data = r.xinfo_stream(key)
    except Exception as e:
        out.error(f"Failed to get stream info: {e}")
        raise typer.Exit(1)

    if app_ctx.json_mode:
        out.json(data)
    else:
        out.kv("Length", str(data.get("length", "?")))
        out.kv("Groups", str(data.get("groups", "?")))
        out.kv("First entry", str(data.get("first-entry", "?")))
        out.kv("Last entry", str(data.get("last-entry", "?")))

    app_ctx.close()


@app.command()
def groups(
    ctx: typer.Context,
    key: Annotated[str, typer.Argument(help="Stream key")],
) -> None:
    """Show consumer groups for a stream."""
    app_ctx: AppContext = ctx.obj
    out = app_ctx.output
    r = app_ctx.client.r

    try:
        data = r.xinfo_groups(key)
    except Exception as e:
        out.error(f"Failed to get groups: {e}")
        raise typer.Exit(1)

    if app_ctx.json_mode:
        out.json({"groups": data})
    else:
        rows = [
            {
                "name": g.get("name", "?"),
                "consumers": g.get("consumers", 0),
                "pending": g.get("pending", 0),
                "last_delivered_id": g.get("last-delivered-id", "?"),
            }
            for g in data
        ]
        if rows:
            out.table(rows, columns=["name", "consumers", "pending", "last_delivered_id"], title="Consumer Groups")
        else:
            out.info("No consumer groups")

    app_ctx.close()


@app.command()
def consumers(
    ctx: typer.Context,
    key: Annotated[str, typer.Argument(help="Stream key")],
    group: Annotated[str, typer.Argument(help="Consumer group name")],
) -> None:
    """Show consumers in a group."""
    app_ctx: AppContext = ctx.obj
    out = app_ctx.output
    r = app_ctx.client.r

    try:
        data = r.xinfo_consumers(key, group)
    except Exception as e:
        out.error(f"Failed to get consumers: {e}")
        raise typer.Exit(1)

    if app_ctx.json_mode:
        out.json({"consumers": data})
    else:
        rows = [
            {
                "name": c.get("name", "?"),
                "pending": c.get("pending", 0),
                "idle": c.get("idle", 0),
            }
            for c in data
        ]
        if rows:
            out.table(rows, columns=["name", "pending", "idle"], title="Consumers")
        else:
            out.info("No consumers")

    app_ctx.close()


@app.command()
def pending(
    ctx: typer.Context,
    key: Annotated[str, typer.Argument(help="Stream key")],
    group: Annotated[str, typer.Argument(help="Consumer group name")],
    count: Annotated[int, typer.Option(help="Number of pending entries")] = 20,
) -> None:
    """Show pending messages for a consumer group."""
    app_ctx: AppContext = ctx.obj
    out = app_ctx.output
    r = app_ctx.client.r

    try:
        summary = r.xpending(key, group)
    except Exception as e:
        out.error(f"Failed to get pending: {e}")
        raise typer.Exit(1)

    if app_ctx.json_mode:
        out.json({"pending_summary": summary})
    else:
        out.kv("Pending count", str(summary.get("pending", 0)))
        out.kv("Min ID", str(summary.get("min", "?")))
        out.kv("Max ID", str(summary.get("max", "?")))
        consumers_data = summary.get("consumers", [])
        if consumers_data:
            rows = [{"consumer": c["name"], "pending": c["pending"]} for c in consumers_data]
            out.table(rows, columns=["consumer", "pending"], title="Pending per Consumer")

    app_ctx.close()


@app.command()
def trim(
    ctx: typer.Context,
    key: Annotated[str, typer.Argument(help="Stream key")],
    maxlen: Annotated[int | None, typer.Option(help="Trim to max length")] = None,
    minid: Annotated[str | None, typer.Option(help="Trim entries older than ID")] = None,
    approximate: Annotated[bool, typer.Option("--approx", help="Use approximate trimming")] = True,
) -> None:
    """Trim a stream."""
    app_ctx: AppContext = ctx.obj
    out = app_ctx.output
    r = app_ctx.client.r

    if maxlen is None and minid is None:
        out.error("Specify --maxlen or --minid")
        raise typer.Exit(1)

    if maxlen is not None:
        trimmed = r.xtrim(key, maxlen=maxlen, approximate=approximate)
    else:
        trimmed = r.xtrim(key, minid=minid, approximate=approximate)

    out.success(f"Trimmed {trimmed} entries from '{key}'")
    app_ctx.close()
