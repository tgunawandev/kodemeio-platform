"""Backup commands for kctl-redis (via SSH/SCP)."""

from __future__ import annotations

import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

import typer

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
    ssh_key_path = str(Path(cfg.ssh_key).expanduser())
    remote_path = "/data/dump.rdb"
    scp_target = f"{cfg.ssh_user}@{cfg.ssh_host}:{remote_path}"

    scp_cmd = [
        "scp",
        "-i",
        ssh_key_path,
        "-P",
        str(cfg.ssh_port),
        "-o",
        "StrictHostKeyChecking=accept-new",
        scp_target,
        output_path,
    ]

    out.info(f"Downloading RDB from {cfg.ssh_host}...")
    result = subprocess.run(scp_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        out.error(f"SCP failed: {result.stderr}")
        raise typer.Exit(1)

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
    ssh_key_path = str(Path(cfg.ssh_key).expanduser())
    remote_path = "/data/dump.rdb"
    scp_target = f"{cfg.ssh_user}@{cfg.ssh_host}:{remote_path}"

    typer.confirm("This will overwrite the remote dump.rdb. Redis must be restarted to load it. Continue?", abort=True)

    scp_cmd = [
        "scp",
        "-i",
        ssh_key_path,
        "-P",
        str(cfg.ssh_port),
        "-o",
        "StrictHostKeyChecking=accept-new",
        str(local),
        scp_target,
    ]

    out.info(f"Uploading {file_path} to {cfg.ssh_host}...")
    result = subprocess.run(scp_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        out.error(f"SCP failed: {result.stderr}")
        raise typer.Exit(1)

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
    ssh_key_path = str(Path(cfg.ssh_key).expanduser())

    ssh_cmd = [
        "ssh",
        "-i",
        ssh_key_path,
        "-p",
        str(cfg.ssh_port),
        "-o",
        "StrictHostKeyChecking=accept-new",
        f"{cfg.ssh_user}@{cfg.ssh_host}",
        f"ls -lhtr {remote_dir}/*.rdb 2>/dev/null || echo '(no backups found)'",
    ]

    result = subprocess.run(ssh_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        out.error(f"SSH failed: {result.stderr}")
        raise typer.Exit(1)

    out.text(result.stdout.strip())
    app_ctx.close()
