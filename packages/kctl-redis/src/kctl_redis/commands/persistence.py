"""Persistence management commands for kctl-redis."""

from __future__ import annotations

from datetime import datetime, timezone

import typer

from kctl_redis.core.callbacks import AppContext

app = typer.Typer(help="Redis persistence management.", no_args_is_help=True)


@app.command(name="rdb-status")
def rdb_status(ctx: typer.Context) -> None:
    """Show RDB persistence status."""
    app_ctx: AppContext = ctx.obj
    out = app_ctx.output
    c = app_ctx.client

    persist = c.info("persistence")
    last_save = persist.get("rdb_last_save_time", 0)
    last_save_dt = datetime.fromtimestamp(last_save, tz=timezone.utc).isoformat() if last_save else "never"

    if app_ctx.json_mode:
        out.json(
            {
                "rdb_last_save_time": last_save,
                "rdb_last_save_iso": last_save_dt,
                "rdb_last_bgsave_status": persist.get("rdb_last_bgsave_status", "?"),
                "rdb_changes_since_last_save": persist.get("rdb_changes_since_last_save", 0),
                "rdb_bgsave_in_progress": persist.get("rdb_bgsave_in_progress", 0),
            }
        )
    else:
        out.kv("Last save", last_save_dt)
        out.kv("Last BGSAVE status", persist.get("rdb_last_bgsave_status", "?"))
        out.kv("Changes since last save", str(persist.get("rdb_changes_since_last_save", 0)))
        out.kv("BGSAVE in progress", str(persist.get("rdb_bgsave_in_progress", 0)))

    app_ctx.close()


@app.command(name="aof-status")
def aof_status(ctx: typer.Context) -> None:
    """Show AOF persistence status."""
    app_ctx: AppContext = ctx.obj
    out = app_ctx.output
    c = app_ctx.client

    persist = c.info("persistence")
    if app_ctx.json_mode:
        out.json(
            {
                "aof_enabled": persist.get("aof_enabled", 0),
                "aof_rewrite_in_progress": persist.get("aof_rewrite_in_progress", 0),
                "aof_last_rewrite_status": persist.get("aof_last_bgrewrite_status", "?"),
                "aof_current_size": persist.get("aof_current_size", 0),
                "aof_base_size": persist.get("aof_base_size", 0),
            }
        )
    else:
        out.kv("AOF enabled", "yes" if persist.get("aof_enabled", 0) else "no")
        out.kv("Rewrite in progress", str(persist.get("aof_rewrite_in_progress", 0)))
        out.kv("Last rewrite status", persist.get("aof_last_bgrewrite_status", "?"))
        out.kv("Current AOF size", str(persist.get("aof_current_size", 0)))
        out.kv("Base AOF size", str(persist.get("aof_base_size", 0)))

    app_ctx.close()


@app.command()
def bgsave(ctx: typer.Context) -> None:
    """Trigger a background RDB save."""
    app_ctx: AppContext = ctx.obj
    out = app_ctx.output
    c = app_ctx.client

    c.execute("BGSAVE")
    out.success("BGSAVE initiated")
    app_ctx.close()


@app.command()
def bgrewriteaof(ctx: typer.Context) -> None:
    """Trigger AOF rewrite."""
    app_ctx: AppContext = ctx.obj
    out = app_ctx.output
    c = app_ctx.client

    c.execute("BGREWRITEAOF")
    out.success("BGREWRITEAOF initiated")
    app_ctx.close()
