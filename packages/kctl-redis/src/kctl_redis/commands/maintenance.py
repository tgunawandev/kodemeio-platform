"""Maintenance commands for kctl-redis."""

from __future__ import annotations

import typer

from kctl_redis.core.callbacks import AppContext

app = typer.Typer(help="Redis maintenance operations.", no_args_is_help=True)


@app.command(name="memory-purge")
def memory_purge(ctx: typer.Context) -> None:
    """Release memory back to the OS."""
    app_ctx: AppContext = ctx.obj
    out = app_ctx.output
    c = app_ctx.client

    c.execute("MEMORY", "PURGE")
    out.success("Memory purge complete")
    app_ctx.close()


@app.command()
def defrag(ctx: typer.Context) -> None:
    """Check and enable active defragmentation."""
    app_ctx: AppContext = ctx.obj
    out = app_ctx.output
    c = app_ctx.client

    mem = c.info("memory")
    frag = mem.get("mem_fragmentation_ratio", 0)
    out.kv("Fragmentation ratio", f"{frag}")

    config = c.r.config_get("activedefrag")
    enabled = config.get("activedefrag", "no")

    if enabled == "yes":
        out.info("Active defragmentation is already enabled")
    else:
        out.info("Active defragmentation is disabled. Enabling...")
        c.r.config_set("activedefrag", "yes")
        out.success("Active defragmentation enabled")

    app_ctx.close()


@app.command(name="config-rewrite")
def config_rewrite(ctx: typer.Context) -> None:
    """Persist runtime configuration to redis.conf."""
    app_ctx: AppContext = ctx.obj
    out = app_ctx.output
    c = app_ctx.client

    c.execute("CONFIG", "REWRITE")
    out.success("Configuration rewritten to disk")
    app_ctx.close()
