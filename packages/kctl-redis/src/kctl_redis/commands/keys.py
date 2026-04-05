"""Key inspection and management commands for kctl-redis."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_redis.core.callbacks import AppContext

app = typer.Typer(help="Redis key management.", no_args_is_help=True)


@app.command()
def scan(
    ctx: typer.Context,
    pattern: Annotated[str, typer.Option(help="Key pattern")] = "*",
    count: Annotated[int, typer.Option(help="Hint for scan batch size")] = 100,
    key_type: Annotated[
        str | None, typer.Option("--type", help="Filter by type (string, list, set, zset, hash, stream)")
    ] = None,
    limit: Annotated[int, typer.Option(help="Max keys to return")] = 100,
) -> None:
    """Scan keys matching a pattern."""
    app_ctx: AppContext = ctx.obj
    out = app_ctx.output
    r = app_ctx.client.r

    keys: list[str] = []
    cursor = 0
    while len(keys) < limit:
        if key_type:
            cursor, batch = r.scan(cursor=cursor, match=pattern, count=count, _type=key_type)
        else:
            cursor, batch = r.scan(cursor=cursor, match=pattern, count=count)
        keys.extend(batch)
        if cursor == 0:
            break

    keys = keys[:limit]

    if app_ctx.json_mode:
        out.json({"pattern": pattern, "count": len(keys), "keys": keys})
    else:
        out.info(f"Found {len(keys)} keys matching '{pattern}'")
        rows = [{"key": k} for k in keys]
        if rows:
            out.table(rows, columns=["key"])

    app_ctx.close()


@app.command()
def get(
    ctx: typer.Context,
    key: Annotated[str, typer.Argument(help="Key name")],
) -> None:
    """Get value of a key (auto-detects type)."""
    app_ctx: AppContext = ctx.obj
    out = app_ctx.output
    r = app_ctx.client.r

    key_type = r.type(key)
    if key_type == "none":
        out.error(f"Key '{key}' does not exist")
        raise typer.Exit(1)

    if key_type == "string":
        value = r.get(key)
    elif key_type == "hash":
        value = r.hgetall(key)
    elif key_type == "list":
        value = r.lrange(key, 0, -1)
    elif key_type == "set":
        value = list(r.smembers(key))
    elif key_type == "zset":
        value = r.zrange(key, 0, -1, withscores=True)
    elif key_type == "stream":
        value = r.xrange(key, count=50)
    else:
        value = f"(unsupported type: {key_type})"

    if app_ctx.json_mode:
        out.json({"key": key, "type": key_type, "value": value})
    else:
        out.kv("Key", key)
        out.kv("Type", key_type)
        if isinstance(value, dict):
            for k, v in value.items():
                out.kv(f"  {k}", str(v))
        elif isinstance(value, list):
            for item in value:
                out.text(f"  {item}")
        else:
            out.kv("Value", str(value))

    app_ctx.close()


@app.command(name="type")
def type_cmd(
    ctx: typer.Context,
    key: Annotated[str, typer.Argument(help="Key name")],
) -> None:
    """Show key type and encoding."""
    app_ctx: AppContext = ctx.obj
    out = app_ctx.output
    r = app_ctx.client.r

    key_type = r.type(key)
    encoding = r.object("encoding", key) if key_type != "none" else None

    if app_ctx.json_mode:
        out.json({"key": key, "type": key_type, "encoding": encoding})
    else:
        out.kv("Type", key_type)
        out.kv("Encoding", str(encoding or "N/A"))

    app_ctx.close()


@app.command()
def ttl(
    ctx: typer.Context,
    key: Annotated[str, typer.Argument(help="Key name")],
    precise: Annotated[bool, typer.Option("--ms", help="Show TTL in milliseconds")] = False,
) -> None:
    """Show time-to-live for a key."""
    app_ctx: AppContext = ctx.obj
    out = app_ctx.output
    r = app_ctx.client.r

    if precise:
        val = r.pttl(key)
        unit = "ms"
    else:
        val = r.ttl(key)
        unit = "s"

    if val == -2:
        out.error(f"Key '{key}' does not exist")
    elif val == -1:
        out.text("No expiry set (persistent)")
    else:
        out.text(f"TTL: {val}{unit}")

    app_ctx.close()


@app.command()
def delete(
    ctx: typer.Context,
    key: Annotated[str, typer.Argument(help="Key name")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Delete a key."""
    app_ctx: AppContext = ctx.obj
    out = app_ctx.output
    r = app_ctx.client.r

    if not r.exists(key):
        out.error(f"Key '{key}' does not exist")
        raise typer.Exit(1)

    if not force:
        typer.confirm(f"Delete key '{key}'?", abort=True)

    r.delete(key)
    out.success(f"Deleted key '{key}'")
    app_ctx.close()


@app.command(name="memory-usage")
def memory_usage(
    ctx: typer.Context,
    key: Annotated[str, typer.Argument(help="Key name")],
) -> None:
    """Show memory usage of a key."""
    app_ctx: AppContext = ctx.obj
    out = app_ctx.output
    r = app_ctx.client.r

    usage = r.memory_usage(key)
    if usage is None:
        out.error(f"Key '{key}' does not exist")
        raise typer.Exit(1)

    if app_ctx.json_mode:
        out.json({"key": key, "memory_bytes": usage})
    else:
        out.kv("Memory", f"{usage} bytes")

    app_ctx.close()


@app.command()
def rename(
    ctx: typer.Context,
    old_key: Annotated[str, typer.Argument(help="Current key name")],
    new_key: Annotated[str, typer.Argument(help="New key name")],
) -> None:
    """Rename a key."""
    app_ctx: AppContext = ctx.obj
    out = app_ctx.output
    r = app_ctx.client.r

    if not r.exists(old_key):
        out.error(f"Key '{old_key}' does not exist")
        raise typer.Exit(1)

    if r.exists(new_key):
        typer.confirm(f"Key '{new_key}' already exists. Overwrite?", abort=True)

    r.rename(old_key, new_key)
    out.success(f"Renamed '{old_key}' -> '{new_key}'")
    app_ctx.close()
