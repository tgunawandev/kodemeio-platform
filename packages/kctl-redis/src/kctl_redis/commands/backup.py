"""Backup commands for kctl-redis (via SSH/SCP)."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

import typer

from kctl_lib.ssh import scp_download, scp_upload, ssh_run
from kctl_redis.core.callbacks import AppContext
from kctl_redis.core.config import ServiceConfig, resolve_connection

app = typer.Typer(help="Redis backup operations via SSH.", no_args_is_help=True)


def _resolve_ssh_config(app_ctx: AppContext) -> ServiceConfig:
    """Resolve connection config with all CLI overrides applied."""
    return resolve_connection(
        profile_name=app_ctx.profile,
        host_override=app_ctx.host_override,
        port_override=app_ctx.port_override,
        user_override=app_ctx.user_override,
        password_override=app_ctx.password_override,
        db_override=app_ctx.db_override,
    )


@app.command()
def dump(
    ctx: typer.Context,
    output_path: Annotated[str, typer.Option("--output", "-o", help="Local output path")] = "",
) -> None:
    """Trigger BGSAVE and download the RDB file."""
    app_ctx: AppContext = ctx.obj
    out = app_ctx.output
    c = app_ctx.client

    out.info("Triggering BGSAVE...")
    c.execute("BGSAVE")

    deadline = time.monotonic() + 300
    while True:
        persist = c.info("persistence")
        if not persist.get("rdb_bgsave_in_progress", 0):
            break
        if time.monotonic() >= deadline:
            out.error("BGSAVE timed out after 300 seconds")
            raise typer.Exit(1)
        time.sleep(1)

    status = c.info("persistence").get("rdb_last_bgsave_status", "?")
    if status != "ok":
        out.error(f"BGSAVE failed: {status}")
        raise typer.Exit(1)

    if not output_path:
        timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M%S")
        output_path = f"dump-{timestamp}.rdb"

    cfg = _resolve_ssh_config(app_ctx)
    remote_path = "/data/dump.rdb"

    out.info(f"Downloading RDB from {cfg.ssh_host}...")
    try:
        scp_download(
            cfg.ssh_host,
            remote_path,
            output_path,
            user=cfg.ssh_user,
            port=cfg.ssh_port,
            ssh_key=cfg.ssh_key,
        )
    except Exception as e:
        out.error(f"SCP failed: {e}")
        raise typer.Exit(1) from e

    out.success(f"Backup saved to {output_path}")
    app_ctx.close()


@app.command()
def restore(
    ctx: typer.Context,
    file_path: Annotated[str, typer.Argument(help="Local RDB file to upload")],
) -> None:
    """Upload an RDB file to the server."""
    app_ctx: AppContext = ctx.obj
    out = app_ctx.output

    local = Path(file_path)
    if not local.exists():
        out.error(f"File not found: {file_path}")
        raise typer.Exit(1)

    cfg = _resolve_ssh_config(app_ctx)
    remote_path = "/data/dump.rdb"

    typer.confirm("This will overwrite the remote dump.rdb. Redis must be restarted to load it. Continue?", abort=True)

    out.info(f"Uploading {file_path} to {cfg.ssh_host}...")
    try:
        scp_upload(
            cfg.ssh_host,
            str(local),
            remote_path,
            user=cfg.ssh_user,
            port=cfg.ssh_port,
            ssh_key=cfg.ssh_key,
        )
    except Exception as e:
        out.error(f"SCP failed: {e}")
        raise typer.Exit(1) from e

    out.success(f"Uploaded {file_path}. Restart Redis to load the restored data.")
    app_ctx.close()


@app.command(name="list")
def list_backups(
    ctx: typer.Context,
    remote_dir: Annotated[str, typer.Option(help="Remote backup directory")] = "/backups",
) -> None:
    """List backup files on the remote server."""
    app_ctx: AppContext = ctx.obj
    out = app_ctx.output

    cfg = _resolve_ssh_config(app_ctx)

    result = ssh_run(
        cfg.ssh_host,
        f"ls -lhtr {remote_dir}/*.rdb 2>/dev/null || echo '(no backups found)'",
        user=cfg.ssh_user,
        port=cfg.ssh_port,
        ssh_key=cfg.ssh_key,
    )
    if not result.ok:
        out.error(f"SSH failed: {result.stderr}")
        raise typer.Exit(1)

    out.text(result.stdout)
    app_ctx.close()
