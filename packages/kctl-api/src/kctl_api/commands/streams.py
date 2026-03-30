"""Redis Streams management commands for kctl-api.

List, read, trim, and manage dead-letter queues.
"""

from __future__ import annotations

import asyncio
from typing import Annotated

import typer

from kctl_api.core.callbacks import AppContext

app = typer.Typer(name="streams", help="Redis Streams — list, read, trim, dead-letter.", no_args_is_help=True)


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------
@app.command(name="list")
def list_streams(ctx: typer.Context) -> None:
    """List all Redis Streams via SCAN for stream-type keys."""
    actx: AppContext = ctx.obj
    out = actx.output

    redis_url = actx.redis_url
    if not redis_url:
        out.error("No redis_url configured.")
        raise typer.Exit(1)

    async def _run() -> list[dict]:
        from kctl_api.core.redis import close_redis, get_redis

        try:
            client = get_redis(redis_url)
            streams: list[dict] = []
            async for key in client.scan_iter(match="*", count=200):
                key_type = await client.type(key)
                if key_type == "stream":
                    length = await client.xlen(key)
                    streams.append({"name": key, "length": length})
            return streams
        finally:
            await close_redis()

    try:
        streams = asyncio.run(_run())
    except ImportError as e:
        out.error(str(e))
        raise typer.Exit(1) from None
    except Exception as e:
        out.error(f"Redis error: {e}")
        raise typer.Exit(1) from None

    rows = [[s["name"], str(s["length"])] for s in streams]

    out.table(
        title=f"Redis Streams ({len(streams)})",
        columns=[("Stream", "bold"), ("Length", "")],
        rows=rows,
        data_for_json=streams,
    )


# ---------------------------------------------------------------------------
# read
# ---------------------------------------------------------------------------
@app.command()
def read(
    ctx: typer.Context,
    stream_name: Annotated[str, typer.Argument(help="Stream name to read from.")],
    count: Annotated[int, typer.Option("--count", "-n", help="Number of messages to read.")] = 10,
    start: Annotated[str, typer.Option("--start", help="Start ID (default: oldest).")] = "0-0",
) -> None:
    """Read messages from a Redis Stream via XRANGE."""
    actx: AppContext = ctx.obj
    out = actx.output

    redis_url = actx.redis_url
    if not redis_url:
        out.error("No redis_url configured.")
        raise typer.Exit(1)

    async def _run() -> list[dict]:
        from kctl_api.core.redis import close_redis, get_redis

        try:
            client = get_redis(redis_url)
            messages = await client.xrange(stream_name, min=start, count=count)
            return [{"id": msg_id, "data": data} for msg_id, data in messages]
        finally:
            await close_redis()

    try:
        messages = asyncio.run(_run())
    except Exception as e:
        out.error(f"Redis error: {e}")
        raise typer.Exit(1) from None

    if actx.json_mode:
        out.raw_json(messages)
    else:
        for msg in messages:
            out.text(f"[bold]{msg['id']}[/bold]")
            for k, v in msg["data"].items():
                out.kv(f"  {k}", str(v))
        out.info(f"{len(messages)} message(s) read from '{stream_name}'.")


# ---------------------------------------------------------------------------
# trim
# ---------------------------------------------------------------------------
@app.command()
def trim(
    ctx: typer.Context,
    stream_name: Annotated[str, typer.Argument(help="Stream name to trim.")],
    maxlen: Annotated[int, typer.Option("--maxlen", "-n", help="Maximum stream length after trim.")] = 1000,
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation.")] = False,
) -> None:
    """Trim a Redis Stream to a maximum length via XTRIM."""
    actx: AppContext = ctx.obj
    out = actx.output

    redis_url = actx.redis_url
    if not redis_url:
        out.error("No redis_url configured.")
        raise typer.Exit(1)

    if not force:
        confirm = typer.confirm(f"Trim stream '{stream_name}' to maxlen={maxlen}?", default=False)
        if not confirm:
            out.info("Cancelled.")
            raise typer.Exit(0)

    async def _run() -> int:
        from kctl_api.core.redis import close_redis, get_redis

        try:
            client = get_redis(redis_url)
            return await client.xtrim(stream_name, maxlen=maxlen)
        finally:
            await close_redis()

    try:
        trimmed = asyncio.run(_run())
    except Exception as e:
        out.error(f"Redis error: {e}")
        raise typer.Exit(1) from None

    out.success(f"Trimmed {trimmed} message(s) from '{stream_name}'.")
    if actx.json_mode:
        out.raw_json({"stream": stream_name, "trimmed": trimmed, "maxlen": maxlen})


# ---------------------------------------------------------------------------
# dead-letter
# ---------------------------------------------------------------------------
@app.command(name="dead-letter")
def dead_letter(
    ctx: typer.Context,
    stream_name: Annotated[str, typer.Argument(help="Dead-letter stream name.")] = "dead-letter",
    count: Annotated[int, typer.Option("--count", "-n", help="Number of messages to read.")] = 20,
) -> None:
    """Read messages from the dead-letter stream."""
    actx: AppContext = ctx.obj
    out = actx.output

    redis_url = actx.redis_url
    if not redis_url:
        out.error("No redis_url configured.")
        raise typer.Exit(1)

    async def _run() -> list[dict]:
        from kctl_api.core.redis import close_redis, get_redis

        try:
            client = get_redis(redis_url)
            messages = await client.xrange(stream_name, count=count)
            return [{"id": msg_id, "data": data} for msg_id, data in messages]
        finally:
            await close_redis()

    try:
        messages = asyncio.run(_run())
    except Exception as e:
        out.error(f"Redis error: {e}")
        raise typer.Exit(1) from None

    if not messages:
        out.info("Dead-letter stream is empty.")
        if actx.json_mode:
            out.raw_json([])
        return

    if actx.json_mode:
        out.raw_json(messages)
    else:
        for msg in messages:
            out.text(f"[bold red]{msg['id']}[/bold red]")
            for k, v in msg["data"].items():
                out.kv(f"  {k}", str(v))
        out.warn(f"{len(messages)} dead-letter message(s).")


# ---------------------------------------------------------------------------
# replay
# ---------------------------------------------------------------------------
@app.command()
def replay(
    ctx: typer.Context,
    source_stream: Annotated[str, typer.Argument(help="Source stream (dead-letter).")],
    target_stream: Annotated[str, typer.Argument(help="Target stream to replay to.")],
    count: Annotated[int, typer.Option("--count", "-n", help="Number of messages to replay.")] = 10,
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation.")] = False,
) -> None:
    """Replay messages from one stream to another via XRANGE + XADD."""
    actx: AppContext = ctx.obj
    out = actx.output

    redis_url = actx.redis_url
    if not redis_url:
        out.error("No redis_url configured.")
        raise typer.Exit(1)

    if not force:
        confirm = typer.confirm(f"Replay {count} messages from '{source_stream}' to '{target_stream}'?", default=False)
        if not confirm:
            out.info("Cancelled.")
            raise typer.Exit(0)

    async def _run() -> int:
        from kctl_api.core.redis import close_redis, get_redis

        try:
            client = get_redis(redis_url)
            messages = await client.xrange(source_stream, count=count)
            replayed = 0
            for _msg_id, data in messages:
                await client.xadd(target_stream, data)
                replayed += 1
            return replayed
        finally:
            await close_redis()

    try:
        replayed = asyncio.run(_run())
    except Exception as e:
        out.error(f"Redis error: {e}")
        raise typer.Exit(1) from None

    out.success(f"Replayed {replayed} message(s) from '{source_stream}' to '{target_stream}'.")
    if actx.json_mode:
        out.raw_json({"source": source_stream, "target": target_stream, "replayed": replayed})


# ---------------------------------------------------------------------------
# consumers
# ---------------------------------------------------------------------------
@app.command()
def consumers(
    ctx: typer.Context,
    stream_name: Annotated[str, typer.Argument(help="Stream name.")],
    group: Annotated[str, typer.Argument(help="Consumer group name.")],
) -> None:
    """List consumers in a consumer group via XINFO CONSUMERS."""
    actx: AppContext = ctx.obj
    out = actx.output

    redis_url = actx.redis_url
    if not redis_url:
        out.error("No redis_url configured.")
        raise typer.Exit(1)

    async def _run() -> list[dict]:
        from kctl_api.core.redis import close_redis, get_redis

        try:
            client = get_redis(redis_url)
            info = await client.xinfo_consumers(stream_name, group)
            return [dict(c) for c in info] if info else []
        finally:
            await close_redis()

    try:
        consumer_list = asyncio.run(_run())
    except Exception as e:
        out.error(f"Redis error: {e}")
        raise typer.Exit(1) from None

    rows = [
        [
            str(c.get("name", "")),
            str(c.get("pending", 0)),
            str(c.get("idle", 0)),
        ]
        for c in consumer_list
    ]

    out.table(
        title=f"Consumers: {stream_name} / {group}",
        columns=[
            ("Consumer", "bold"),
            ("Pending", ""),
            ("Idle (ms)", ""),
        ],
        rows=rows,
        data_for_json=consumer_list,
    )
