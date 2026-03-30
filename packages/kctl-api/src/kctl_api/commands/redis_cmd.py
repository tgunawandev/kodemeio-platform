"""Redis management commands for kctl-api.

Inspect keys, get/delete values, and view server info.
"""

from __future__ import annotations

import asyncio
from typing import Annotated

import typer

from kctl_api.core.callbacks import AppContext

app = typer.Typer(name="redis", help="Redis management — info, keys, get, delete, stats.", no_args_is_help=True)


# ---------------------------------------------------------------------------
# info
# ---------------------------------------------------------------------------
@app.command()
def info(ctx: typer.Context) -> None:
    """Show Redis server info via async PING + INFO."""
    actx: AppContext = ctx.obj
    out = actx.output

    redis_url = actx.redis_url
    if not redis_url:
        out.error("No redis_url configured.")
        raise typer.Exit(1)

    async def _run() -> dict:
        from kctl_api.core.redis import close_redis, get_redis

        try:
            client = get_redis(redis_url)
            info_data = await client.info()
            return dict(info_data) if info_data else {}
        finally:
            await close_redis()

    try:
        data = asyncio.run(_run())
    except ImportError as e:
        out.error(str(e))
        raise typer.Exit(1) from None
    except Exception as e:
        out.error(f"Redis error: {e}")
        raise typer.Exit(1) from None

    # Show key metrics
    sections = [
        (
            "Server",
            [
                ("Version", str(data.get("redis_version", ""))),
                ("Uptime (seconds)", str(data.get("uptime_in_seconds", ""))),
                ("Connected Clients", str(data.get("connected_clients", ""))),
                ("Used Memory", str(data.get("used_memory_human", ""))),
                (
                    "Total Keys",
                    str(
                        sum(
                            data.get(f"db{i}", {}).get("keys", 0)
                            for i in range(16)
                            if isinstance(data.get(f"db{i}"), dict)
                        )
                    ),
                ),
            ],
        ),
    ]

    out.detail(title="Redis Info", sections=sections, data_for_json=data)


# ---------------------------------------------------------------------------
# keys
# ---------------------------------------------------------------------------
@app.command()
def keys(
    ctx: typer.Context,
    pattern: Annotated[str, typer.Argument(help="Key pattern (e.g. 'myapp:*').")] = "*",
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max keys to return.")] = 50,
) -> None:
    """List Redis keys matching a pattern via async SCAN."""
    actx: AppContext = ctx.obj
    out = actx.output

    redis_url = actx.redis_url
    if not redis_url:
        out.error("No redis_url configured.")
        raise typer.Exit(1)

    async def _run() -> list[str]:
        from kctl_api.core.redis import close_redis, get_redis

        try:
            client = get_redis(redis_url)
            result: list[str] = []
            async for key in client.scan_iter(match=pattern, count=100):
                result.append(key)
                if len(result) >= limit:
                    break
            return result
        finally:
            await close_redis()

    try:
        found_keys = asyncio.run(_run())
    except ImportError as e:
        out.error(str(e))
        raise typer.Exit(1) from None
    except Exception as e:
        out.error(f"Redis error: {e}")
        raise typer.Exit(1) from None

    rows = [[k] for k in found_keys]

    out.table(
        title=f"Redis Keys ({len(found_keys)} matching '{pattern}')",
        columns=[("Key", "")],
        rows=rows,
        data_for_json=[{"key": k} for k in found_keys],
    )


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------
@app.command(name="get")
def get_key(
    ctx: typer.Context,
    key: Annotated[str, typer.Argument(help="Redis key to retrieve.")],
) -> None:
    """Get a Redis key value."""
    actx: AppContext = ctx.obj
    out = actx.output

    redis_url = actx.redis_url
    if not redis_url:
        out.error("No redis_url configured.")
        raise typer.Exit(1)

    async def _run() -> str | None:
        from kctl_api.core.redis import close_redis, get_redis

        try:
            client = get_redis(redis_url)
            return await client.get(key)
        finally:
            await close_redis()

    try:
        value = asyncio.run(_run())
    except Exception as e:
        out.error(f"Redis error: {e}")
        raise typer.Exit(1) from None

    if value is None:
        out.info(f"Key not found: {key}")
        return

    if actx.json_mode:
        out.raw_json({"key": key, "value": value})
    else:
        out.text(f"{key} = {value}")


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------
@app.command()
def delete(
    ctx: typer.Context,
    key: Annotated[str, typer.Argument(help="Redis key to delete.")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation.")] = False,
) -> None:
    """Delete a Redis key."""
    actx: AppContext = ctx.obj
    out = actx.output

    redis_url = actx.redis_url
    if not redis_url:
        out.error("No redis_url configured.")
        raise typer.Exit(1)

    if not force:
        confirm = typer.confirm(f"Delete Redis key '{key}'?", default=False)
        if not confirm:
            out.info("Cancelled.")
            raise typer.Exit(0)

    async def _run() -> int:
        from kctl_api.core.redis import close_redis, get_redis

        try:
            client = get_redis(redis_url)
            return await client.delete(key)
        finally:
            await close_redis()

    try:
        deleted = asyncio.run(_run())
    except Exception as e:
        out.error(f"Redis error: {e}")
        raise typer.Exit(1) from None

    if deleted:
        out.success(f"Key '{key}' deleted.")
    else:
        out.info(f"Key '{key}' did not exist.")

    if actx.json_mode:
        out.raw_json({"key": key, "deleted": deleted})


# ---------------------------------------------------------------------------
# flush
# ---------------------------------------------------------------------------
@app.command()
def flush(
    ctx: typer.Context,
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation.")] = False,
) -> None:
    """Flush the current Redis database (FLUSHDB)."""
    actx: AppContext = ctx.obj
    out = actx.output

    redis_url = actx.redis_url
    if not redis_url:
        out.error("No redis_url configured.")
        raise typer.Exit(1)

    if not force:
        confirm = typer.confirm("Flush the entire Redis database?", default=False)
        if not confirm:
            out.info("Cancelled.")
            raise typer.Exit(0)

    async def _run() -> bool:
        from kctl_api.core.redis import close_redis, get_redis

        try:
            client = get_redis(redis_url)
            return await client.flushdb()
        finally:
            await close_redis()

    try:
        asyncio.run(_run())
    except Exception as e:
        out.error(f"Redis error: {e}")
        raise typer.Exit(1) from None

    out.success("Redis database flushed.")


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------
@app.command()
def stats(ctx: typer.Context) -> None:
    """Show Redis memory and key statistics."""
    actx: AppContext = ctx.obj
    out = actx.output

    redis_url = actx.redis_url
    if not redis_url:
        out.error("No redis_url configured.")
        raise typer.Exit(1)

    async def _run() -> dict:
        from kctl_api.core.redis import close_redis, get_redis

        try:
            client = get_redis(redis_url)
            info_data = await client.info("memory")
            dbsize = await client.dbsize()
            result = dict(info_data) if info_data else {}
            result["dbsize"] = dbsize
            return result
        finally:
            await close_redis()

    try:
        data = asyncio.run(_run())
    except Exception as e:
        out.error(f"Redis error: {e}")
        raise typer.Exit(1) from None

    out.detail(
        title="Redis Stats",
        sections=[
            (
                "Memory",
                [
                    ("Used Memory", str(data.get("used_memory_human", ""))),
                    ("Peak Memory", str(data.get("used_memory_peak_human", ""))),
                    ("Total Keys", str(data.get("dbsize", ""))),
                ],
            ),
        ],
        data_for_json=data,
    )


# ---------------------------------------------------------------------------
# monitor
# ---------------------------------------------------------------------------
@app.command()
def monitor(
    ctx: typer.Context,
    duration: Annotated[int, typer.Option("--duration", help="Monitor duration in seconds.")] = 10,
) -> None:
    """Real-time Redis MONITOR — show commands as they execute."""
    actx: AppContext = ctx.obj
    out = actx.output

    redis_url = actx.redis_url
    if not redis_url:
        out.error("No redis_url configured.")
        raise typer.Exit(1)

    out.info(f"Redis MONITOR — capturing commands for {duration}s (Ctrl+C to stop) ...")
    out.warn("MONITOR can impact Redis performance. Use in dev/staging only.")

    async def _run() -> list[str]:
        import time

        from kctl_api.core.redis import close_redis, get_redis

        try:
            client = get_redis(redis_url)
            commands: list[str] = []
            deadline = time.monotonic() + duration

            # Use raw pubsub monitor via execute_command
            # Note: redis-py doesn't have a native monitor context; use raw approach
            monitor_client = client.monitor()  # type: ignore[attr-defined]
            async with monitor_client as m:
                while time.monotonic() < deadline:
                    try:
                        command = await asyncio.wait_for(m.next_command(), timeout=1.0)
                        line = f"[{command.get('time', '')}] {command.get('command', '')}"
                        commands.append(line)
                        typer.echo(f"  {line}")
                    except TimeoutError:
                        continue
                    except Exception:
                        break
            return commands
        finally:
            await close_redis()

    try:
        commands = asyncio.run(_run())
        out.success(f"Captured {len(commands)} commands.")
    except AttributeError:
        out.warn("MONITOR not available via this client version.")
        out.info("Use: redis-cli MONITOR (direct Redis CLI)")
    except Exception as e:
        out.error(f"Redis error: {e}")
        raise typer.Exit(1) from None


# ---------------------------------------------------------------------------
# memory
# ---------------------------------------------------------------------------
@app.command()
def memory(ctx: typer.Context) -> None:
    """Show memory usage per key prefix."""
    actx: AppContext = ctx.obj
    out = actx.output

    redis_url = actx.redis_url
    if not redis_url:
        out.error("No redis_url configured.")
        raise typer.Exit(1)

    async def _run() -> dict[str, dict]:
        from kctl_api.core.redis import close_redis, get_redis

        try:
            client = get_redis(redis_url)
            prefix_stats: dict[str, dict] = {}
            count = 0

            async for key in client.scan_iter(match="*", count=500):
                count += 1
                if count > 5000:
                    break
                # Extract prefix (up to first : or first 20 chars)
                key_str = str(key)
                prefix = key_str.split(":")[0] if ":" in key_str else key_str[:20]

                try:
                    mem = await client.memory_usage(key)  # type: ignore[attr-defined]
                    if mem:
                        if prefix not in prefix_stats:
                            prefix_stats[prefix] = {"count": 0, "bytes": 0}
                        prefix_stats[prefix]["count"] += 1
                        prefix_stats[prefix]["bytes"] += mem
                except Exception:
                    if prefix not in prefix_stats:
                        prefix_stats[prefix] = {"count": 0, "bytes": 0}
                    prefix_stats[prefix]["count"] += 1

            return prefix_stats
        finally:
            await close_redis()

    try:
        stats = asyncio.run(_run())
    except Exception as e:
        out.error(f"Redis error: {e}")
        raise typer.Exit(1) from None

    if not stats:
        out.info("No keys found.")
        return

    sorted_stats = sorted(stats.items(), key=lambda x: -x[1].get("bytes", 0))

    rows = [
        [
            prefix,
            str(data["count"]),
            f"{round(data.get('bytes', 0) / 1024, 1)} KB" if data.get("bytes") else "N/A",
        ]
        for prefix, data in sorted_stats
    ]
    out.table(
        title="Redis Memory by Prefix",
        columns=[("Prefix", "bold"), ("Keys", ""), ("Memory", "")],
        rows=rows,
        data_for_json=[{"prefix": p, **d} for p, d in sorted_stats],
    )


# ---------------------------------------------------------------------------
# pubsub
# ---------------------------------------------------------------------------
@app.command()
def pubsub(ctx: typer.Context) -> None:
    """Show active Pub/Sub channels and subscriber counts."""
    actx: AppContext = ctx.obj
    out = actx.output

    redis_url = actx.redis_url
    if not redis_url:
        out.error("No redis_url configured.")
        raise typer.Exit(1)

    async def _run() -> dict:
        from kctl_api.core.redis import close_redis, get_redis

        try:
            client = get_redis(redis_url)
            channels = await client.pubsub_channels()
            numsub = await client.pubsub_numsub(*channels) if channels else {}
            numpat = await client.pubsub_numpat()
            return {
                "channels": [str(c) for c in channels],
                "subscribers": {str(k): v for k, v in numsub.items()} if isinstance(numsub, dict) else {},
                "pattern_subscriptions": numpat,
            }
        finally:
            await close_redis()

    try:
        data = asyncio.run(_run())
    except Exception as e:
        out.error(f"Redis error: {e}")
        raise typer.Exit(1) from None

    channels = data.get("channels", [])
    subscribers = data.get("subscribers", {})

    if not channels:
        out.info("No active Pub/Sub channels.")
        out.text(f"  Pattern subscriptions: {data.get('pattern_subscriptions', 0)}")
        return

    rows = [[ch, str(subscribers.get(ch, 0))] for ch in channels]
    out.table(
        title=f"Active Pub/Sub Channels ({len(channels)})",
        columns=[("Channel", "bold"), ("Subscribers", "")],
        rows=rows,
        data_for_json=data,
    )
    out.info(f"Pattern subscriptions: {data.get('pattern_subscriptions', 0)}")


# ---------------------------------------------------------------------------
# expire-audit
# ---------------------------------------------------------------------------
@app.command(name="expire-audit")
def expire_audit(
    ctx: typer.Context,
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max keys to check.")] = 200,
) -> None:
    """Find keys without TTL (potential memory leaks)."""
    actx: AppContext = ctx.obj
    out = actx.output

    redis_url = actx.redis_url
    if not redis_url:
        out.error("No redis_url configured.")
        raise typer.Exit(1)

    async def _run() -> tuple[list[str], int]:
        from kctl_api.core.redis import close_redis, get_redis

        try:
            client = get_redis(redis_url)
            no_ttl: list[str] = []
            total = 0

            async for key in client.scan_iter(match="*", count=100):
                total += 1
                if total > limit:
                    break
                ttl = await client.ttl(key)
                if ttl == -1:  # -1 means no TTL, -2 means key doesn't exist
                    no_ttl.append(str(key))

            return no_ttl, total
        finally:
            await close_redis()

    try:
        no_ttl_keys, total_checked = asyncio.run(_run())
    except Exception as e:
        out.error(f"Redis error: {e}")
        raise typer.Exit(1) from None

    out.info(f"Checked {total_checked} keys — {len(no_ttl_keys)} without TTL.")

    if not no_ttl_keys:
        out.success("All sampled keys have TTL set.")
        return

    rows = [[k] for k in no_ttl_keys[:50]]
    out.table(
        title=f"Keys Without TTL ({len(no_ttl_keys)} found)",
        columns=[("Key", "yellow")],
        rows=rows,
        data_for_json=[{"key": k} for k in no_ttl_keys],
    )
    out.warn(f"{len(no_ttl_keys)} keys without TTL may cause unbounded memory growth.")


# ---------------------------------------------------------------------------
# keys-by-prefix
# ---------------------------------------------------------------------------
@app.command(name="keys-by-prefix")
def keys_by_prefix(
    ctx: typer.Context,
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max keys to scan.")] = 1000,
) -> None:
    """Group Redis keys by prefix (up to first colon)."""
    actx: AppContext = ctx.obj
    out = actx.output

    redis_url = actx.redis_url
    if not redis_url:
        out.error("No redis_url configured.")
        raise typer.Exit(1)

    async def _run() -> dict[str, int]:
        from kctl_api.core.redis import close_redis, get_redis

        try:
            client = get_redis(redis_url)
            prefix_counts: dict[str, int] = {}
            count = 0

            async for key in client.scan_iter(match="*", count=100):
                count += 1
                if count > limit:
                    break
                key_str = str(key)
                prefix = key_str.split(":")[0] if ":" in key_str else f"(no prefix) {key_str[:20]}"
                prefix_counts[prefix] = prefix_counts.get(prefix, 0) + 1

            return prefix_counts
        finally:
            await close_redis()

    try:
        prefix_counts = asyncio.run(_run())
    except Exception as e:
        out.error(f"Redis error: {e}")
        raise typer.Exit(1) from None

    if not prefix_counts:
        out.info("No keys found.")
        return

    sorted_prefixes = sorted(prefix_counts.items(), key=lambda x: -x[1])

    rows = [[prefix, str(count), "#" * min(count, 30)] for prefix, count in sorted_prefixes]
    out.table(
        title=f"Keys by Prefix (sampled {limit})",
        columns=[("Prefix", "bold"), ("Count", ""), ("Bar", "green")],
        rows=rows,
        data_for_json=[{"prefix": p, "count": c} for p, c in sorted_prefixes],
    )
