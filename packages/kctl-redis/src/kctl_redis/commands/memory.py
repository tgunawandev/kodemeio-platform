"""Memory analysis commands for kctl-redis."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_redis.core.callbacks import AppContext

app = typer.Typer(help="Redis memory analysis.", no_args_is_help=True)


@app.command()
def stats(ctx: typer.Context) -> None:
    """Show memory statistics."""
    app_ctx: AppContext = ctx.obj
    out = app_ctx.output
    c = app_ctx.client

    mem = c.info("memory")
    if app_ctx.json_mode:
        out.json(mem)
    else:
        rows = [
            {"metric": "used_memory_human", "value": mem.get("used_memory_human", "?")},
            {"metric": "used_memory_peak_human", "value": mem.get("used_memory_peak_human", "?")},
            {"metric": "used_memory_rss_human", "value": mem.get("used_memory_rss_human", "?")},
            {"metric": "maxmemory_human", "value": mem.get("maxmemory_human", "?")},
            {"metric": "maxmemory_policy", "value": mem.get("maxmemory_policy", "?")},
            {"metric": "mem_fragmentation_ratio", "value": str(mem.get("mem_fragmentation_ratio", "?"))},
            {"metric": "mem_allocator", "value": mem.get("mem_allocator", "?")},
        ]
        out.table(rows, columns=["metric", "value"], title="Memory Statistics")

    app_ctx.close()


@app.command(name="big-keys")
def big_keys(
    ctx: typer.Context,
    count: Annotated[int, typer.Option(help="Number of keys to scan per batch")] = 100,
    limit: Annotated[int, typer.Option(help="Max big keys to report")] = 20,
) -> None:
    """Find largest keys by memory usage."""
    app_ctx: AppContext = ctx.obj
    out = app_ctx.output
    r = app_ctx.client.r

    big: list[dict[str, object]] = []
    cursor = 0
    scanned = 0

    while True:
        cursor, keys = r.scan(cursor=cursor, count=count)
        for key in keys:
            usage = r.memory_usage(key)
            if usage is not None:
                big.append({"key": key, "bytes": usage, "type": r.type(key)})
        scanned += len(keys)
        if cursor == 0 or scanned >= 10000:
            break

    big.sort(key=lambda x: x["bytes"], reverse=True)  # type: ignore[arg-type]
    big = big[:limit]

    if app_ctx.json_mode:
        out.json({"big_keys": big})
    else:
        rows = [{"key": k["key"], "type": k["type"], "bytes": k["bytes"]} for k in big]
        out.table(rows, columns=["key", "type", "bytes"], title=f"Top {limit} Keys by Memory")

    app_ctx.close()


@app.command()
def eviction(ctx: typer.Context) -> None:
    """Show eviction policy and stats."""
    app_ctx: AppContext = ctx.obj
    out = app_ctx.output
    c = app_ctx.client

    mem = c.info("memory")
    stats_info = c.info("stats")

    if app_ctx.json_mode:
        out.json(
            {
                "maxmemory_policy": mem.get("maxmemory_policy", "?"),
                "maxmemory_human": mem.get("maxmemory_human", "?"),
                "evicted_keys": stats_info.get("evicted_keys", 0),
            }
        )
    else:
        out.kv("Policy", mem.get("maxmemory_policy", "?"))
        out.kv("Max memory", mem.get("maxmemory_human", "?"))
        out.kv("Evicted keys", str(stats_info.get("evicted_keys", 0)))

    app_ctx.close()


@app.command()
def fragmentation(ctx: typer.Context) -> None:
    """Show memory fragmentation and recommendation."""
    app_ctx: AppContext = ctx.obj
    out = app_ctx.output
    c = app_ctx.client

    mem = c.info("memory")
    ratio = mem.get("mem_fragmentation_ratio", 0)

    if app_ctx.json_mode:
        out.json({"fragmentation_ratio": ratio, "used_memory_rss": mem.get("used_memory_rss", 0)})
    else:
        out.kv("Fragmentation ratio", f"{ratio}")
        out.kv("RSS", mem.get("used_memory_rss_human", "?"))
        if isinstance(ratio, (int, float)) and ratio >= 1.5:
            out.warn("High fragmentation detected. Consider: kctl-redis maintenance defrag")
        elif isinstance(ratio, (int, float)) and ratio < 1.0:
            out.warn("Ratio < 1.0 indicates Redis needs more memory than available")
        else:
            out.success("Fragmentation is within normal range")

    app_ctx.close()
