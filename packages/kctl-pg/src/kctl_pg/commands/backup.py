"""Backup and restore commands via SSH."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Annotated

import typer

from kctl_lib.ssh import _build_ssh_base, ssh_run
from kctl_pg.core.callbacks import AppContext
from kctl_pg.core.config import resolve_connection

app = typer.Typer(help="Backup and restore databases via SSH.")


def _get_container_name(config) -> str:
    """Get the PostgreSQL Docker container name on the remote host."""
    result = ssh_run(
        config.ssh_host,
        "docker ps --format '{{.Names}}' | grep -i postgres | head -1",
        user=config.ssh_user,
        port=config.ssh_port,
        ssh_key=config.ssh_key,
        timeout=30,
    )
    name = result.stdout.strip()
    if not name:
        return "kodemeio-postgres"
    return name


@app.command()
def dump(
    ctx: typer.Context,
    database: Annotated[str, typer.Argument(help="Database name to dump")],
    output: Annotated[
        str | None, typer.Option("--output", "-o", help="Local output path (default: ./<db>_<date>.dump)")
    ] = None,
    format_: Annotated[
        str, typer.Option("--format", "-F", help="Dump format: custom (c), plain (p), directory (d)")
    ] = "c",
) -> None:
    """Dump a database via SSH + pg_dump.

    Runs pg_dump inside the Docker container and streams the result back.

    Examples:
      kctl-pg backup dump odoo
      kctl-pg backup dump odoo -o /tmp/odoo.dump
      kctl-pg backup dump odoo --format p -o /tmp/odoo.sql
    """
    actx: AppContext = ctx.obj
    out = actx.output

    config = resolve_connection(profile_name=actx.profile)
    container = _get_container_name(config)

    if output is None:
        import datetime

        date_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        ext = ".sql" if format_ == "p" else ".dump"
        output = f"{database}_{date_str}{ext}"

    out.info(f"Dumping '{database}' from {config.ssh_host} (container: {container})...")

    remote_cmd = f"docker exec {container} pg_dump -U {config.user} -F {format_} {database}"
    ssh = _build_ssh_base(config.ssh_host, config.ssh_user, config.ssh_port, config.ssh_key)
    ssh.append(remote_cmd)

    with open(output, "wb") as f:
        proc = subprocess.run(ssh, stdout=f, stderr=subprocess.PIPE, timeout=3600)

    if proc.returncode != 0:
        stderr = proc.stderr.decode().strip()
        out.error(f"pg_dump failed: {stderr}")
        raise typer.Exit(1)

    file_size = Path(output).stat().st_size
    size_mb = file_size / (1024 * 1024)
    out.success(f"Dump saved to {output} ({size_mb:.1f} MB)")


@app.command()
def restore(
    ctx: typer.Context,
    database: Annotated[str, typer.Argument(help="Target database name")],
    input_file: Annotated[str, typer.Option("--input", "-i", help="Dump file path")],
    create: Annotated[bool, typer.Option("--create", help="Create database before restore")] = False,
    clean: Annotated[bool, typer.Option("--clean", help="Drop objects before restore")] = False,
) -> None:
    """Restore a database from a dump file via SSH.

    Streams the dump file to pg_restore inside the Docker container.

    Examples:
      kctl-pg backup restore odoo_new -i odoo.dump --create
      kctl-pg backup restore odoo -i odoo.dump --clean
    """
    actx: AppContext = ctx.obj
    out = actx.output

    config = resolve_connection(profile_name=actx.profile)
    container = _get_container_name(config)

    input_path = Path(input_file)
    if not input_path.exists():
        out.error(f"File not found: {input_file}")
        raise typer.Exit(1)

    if create:
        out.info(f"Creating database '{database}'...")
        create_cmd = f"docker exec {container} createdb -U {config.user} {database}"
        result = ssh_run(
            config.ssh_host,
            create_cmd,
            user=config.ssh_user,
            port=config.ssh_port,
            ssh_key=config.ssh_key,
            timeout=30,
        )
        if not result.ok and "already exists" not in result.stderr:
            out.error(f"createdb failed: {result.stderr}")
            raise typer.Exit(1)

    out.info(f"Restoring '{database}' from {input_file}...")

    restore_opts = f"-U {config.user} -d {database}"
    if clean:
        restore_opts += " --clean"

    remote_cmd = f"docker exec -i {container} pg_restore {restore_opts}"
    ssh = _build_ssh_base(config.ssh_host, config.ssh_user, config.ssh_port, config.ssh_key)
    ssh.append(remote_cmd)

    with open(input_file, "rb") as f:
        proc = subprocess.run(ssh, stdin=f, stderr=subprocess.PIPE, timeout=3600)

    if proc.returncode != 0:
        stderr = proc.stderr.decode().strip()
        # pg_restore returns 1 for warnings (non-fatal), only fail on exit code > 1
        if proc.returncode > 1:
            out.error(f"pg_restore failed (exit {proc.returncode}): {stderr}")
            raise typer.Exit(1)
        if stderr:
            out.warn(f"pg_restore warnings: {stderr[:200]}")

    out.success(f"Database '{database}' restored from {input_file}")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List recent backups on the remote server."""
    actx: AppContext = ctx.obj
    out = actx.output

    config = resolve_connection(profile_name=actx.profile)
    container = _get_container_name(config)

    # Check for pgBackRest backups
    remote_cmd = f"docker exec {container} sh -c 'command -v pgbackrest >/dev/null 2>&1 && pgbackrest info --output=json || echo null'"
    result = ssh_run(
        config.ssh_host,
        remote_cmd,
        user=config.ssh_user,
        port=config.ssh_port,
        ssh_key=config.ssh_key,
        timeout=30,
    )

    if result.ok and result.stdout != "null":
        out.info("pgBackRest backups:")
        out.text(result.stdout)
    else:
        out.info("No pgBackRest configured. Use 'kctl-pg backup dump' for manual backups.")
