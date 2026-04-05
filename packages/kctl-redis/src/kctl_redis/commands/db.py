"""Database management commands for kctl-redis."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_redis.core.callbacks import AppContext

app = typer.Typer(help="Redis database operations.", no_args_is_help=True)


@app.command(name="list")
def list_dbs(ctx: typer.Context) -> None:
    """List databases with key counts."""
    app_ctx: AppContext = ctx.obj
    out = app_ctx.output
    c = app_ctx.client

    keyspace = c.info("keyspace")
    rows = []
    for db_name, stats in sorted(keyspace.items()):
        if isinstance(stats, dict):
            rows.append(
                {
                    "db": db_name,
                    "keys": stats.get("keys", 0),
                    "expires": stats.get("expires", 0),
                    "avg_ttl": stats.get("avg_ttl", 0),
                }
            )

    if not rows:
        out.info("No databases with keys")
    elif app_ctx.json_mode:
        out.json({"databases": rows})
    else:
        out.table(rows, columns=["db", "keys", "expires", "avg_ttl"], title="Databases")

    app_ctx.close()


@app.command()
def size(ctx: typer.Context) -> None:
    """Show key count for current database."""
    app_ctx: AppContext = ctx.obj
    out = app_ctx.output
    r = app_ctx.client.r

    count = r.dbsize()
    if app_ctx.json_mode:
        out.json({"dbsize": count})
    else:
        out.text(f"Keys in current database: {count}")

    app_ctx.close()


@app.command()
def flush(
    ctx: typer.Context,
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
    async_mode: Annotated[bool, typer.Option("--async", help="Flush asynchronously")] = False,
) -> None:
    """Flush current database (delete all keys)."""
    app_ctx: AppContext = ctx.obj
    out = app_ctx.output
    r = app_ctx.client.r

    if not force:
        count = r.dbsize()
        typer.confirm(f"Flush current database ({count} keys)? This cannot be undone", abort=True)

    r.flushdb(asynchronous=async_mode)
    out.success("Database flushed")
    app_ctx.close()


@app.command()
def swap(
    ctx: typer.Context,
    db1: Annotated[int, typer.Argument(help="First database number")],
    db2: Annotated[int, typer.Argument(help="Second database number")],
) -> None:
    """Swap two databases."""
    app_ctx: AppContext = ctx.obj
    out = app_ctx.output
    c = app_ctx.client

    c.execute("SWAPDB", str(db1), str(db2))
    out.success(f"Swapped db{db1} <-> db{db2}")
    app_ctx.close()
