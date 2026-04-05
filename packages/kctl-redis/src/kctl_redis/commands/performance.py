"""Performance monitoring commands for kctl-redis."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_redis.core.callbacks import AppContext

app = typer.Typer(help="Redis performance monitoring.", no_args_is_help=True)


@app.command()
def slowlog(
    ctx: typer.Context,
    count: Annotated[int, typer.Option(help="Number of entries")] = 20,
) -> None:
    """Show slow log entries."""
    app_ctx: AppContext = ctx.obj
    out = app_ctx.output
    r = app_ctx.client.r

    entries = r.slowlog_get(count)
    if app_ctx.json_mode:
        out.json({"entries": [{"id": e["id"], "duration_us": e["duration"], "command": e["command"]} for e in entries]})
    else:
        rows = [
            {
                "id": e.get("id", "?"),
                "duration_us": e.get("duration", "?"),
                "command": " ".join(str(c) for c in e.get("command", [])),
            }
            for e in entries
        ]
        if rows:
            out.table(rows, columns=["id", "duration_us", "command"], title="Slow Log")
        else:
            out.info("No slow log entries")

    app_ctx.close()


@app.command()
def latency(ctx: typer.Context) -> None:
    """Show latency monitoring data."""
    app_ctx: AppContext = ctx.obj
    out = app_ctx.output
    c = app_ctx.client

    result = c.execute("LATENCY", "LATEST")

    if app_ctx.json_mode:
        out.json({"latency": result})
    else:
        if not result:
            out.info("No latency events recorded. Enable with: CONFIG SET latency-monitor-threshold 100")
        elif isinstance(result, list):
            for entry in result:
                if isinstance(entry, list) and len(entry) >= 4:
                    out.kv(str(entry[0]), f"latest={entry[2]}ms, max={entry[3]}ms")
                else:
                    out.text(str(entry))

    app_ctx.close()


@app.command(name="hit-ratio")
def hit_ratio(ctx: typer.Context) -> None:
    """Show keyspace hit ratio."""
    app_ctx: AppContext = ctx.obj
    out = app_ctx.output
    c = app_ctx.client

    stats = c.info("stats")
    hits = stats.get("keyspace_hits", 0)
    misses = stats.get("keyspace_misses", 0)
    total = hits + misses
    ratio = (hits / total * 100) if total > 0 else 0.0

    if app_ctx.json_mode:
        out.json({"hits": hits, "misses": misses, "total": total, "ratio": round(ratio, 2)})
    else:
        out.kv("Hits", str(hits))
        out.kv("Misses", str(misses))
        out.kv("Total", str(total))
        out.kv("Hit ratio", f"{ratio:.1f}%")

        if total > 100 and ratio < 50:
            out.warn("Low hit ratio — check eviction policy and key patterns")

    app_ctx.close()


@app.command(name="ops-sec")
def ops_sec(ctx: typer.Context) -> None:
    """Show current operations per second."""
    app_ctx: AppContext = ctx.obj
    out = app_ctx.output
    c = app_ctx.client

    stats = c.info("stats")
    ops = stats.get("instantaneous_ops_per_sec", 0)
    total_commands = stats.get("total_commands_processed", 0)

    if app_ctx.json_mode:
        out.json({"ops_per_sec": ops, "total_commands": total_commands})
    else:
        out.kv("Ops/sec", str(ops))
        out.kv("Total commands", str(total_commands))

    app_ctx.close()
