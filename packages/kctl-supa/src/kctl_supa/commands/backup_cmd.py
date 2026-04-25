"""Database backup commands for kctl-supa.

Database backup operations.
"""

from __future__ import annotations

import shlex
from typing import Annotated

import typer

from kctl_supa.core.callbacks import AppContext
from kctl_supa.core.docker import DockerOps
from kctl_supa.core.exceptions import DockerError

app = typer.Typer(help="Database backup operations.")

_SCHEMA_SCRIPT_MAP = {
    "all": "dump-supabase",
    "auth": "dump-auth",
    "storage": "dump-storage",
    "public": "dump-public",
}


def _get_docker(actx: AppContext) -> DockerOps:
    return DockerOps(actx.config)


@app.command()
def create(
    ctx: typer.Context,
    schema: Annotated[
        str,
        typer.Option(
            "--schema",
            help="Schema to backup: public|auth|storage|all",
        ),
    ] = "all",
) -> None:
    """Run database backup."""
    actx: AppContext = ctx.obj
    out = actx.output

    script = _SCHEMA_SCRIPT_MAP.get(schema)
    if script is None:
        out.error(f"Unknown schema '{schema}'. Valid options: {', '.join(_SCHEMA_SCRIPT_MAP)}")
        raise typer.Exit(1)

    out.info(f"Running backup for schema: {schema}")
    try:
        docker = _get_docker(actx)
        result = docker.docker_exec("db", f"/scripts/backup.sh {script}")
        docker.close()
    except DockerError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc

    typer.echo(result)
    out.success("Backup complete")


@app.command(name="list")
def list_backups(ctx: typer.Context) -> None:
    """List available backups."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        docker = _get_docker(actx)
        result = docker.docker_exec("db", "/scripts/backup.sh list")
        docker.close()
    except DockerError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc

    typer.echo(result)


@app.command()
def restore(
    ctx: typer.Context,
    file: Annotated[str, typer.Argument(help="Backup file to restore")],
) -> None:
    """Restore from a backup file."""
    actx: AppContext = ctx.obj
    out = actx.output

    if not typer.confirm(f"Restore from '{file}'? This will overwrite existing data."):
        raise typer.Exit(0)

    out.info(f"Restoring from: {file}")
    try:
        docker = _get_docker(actx)
        safe_file = shlex.quote(file)
        result = docker.docker_exec("db", f"/scripts/backup.sh restore postgres {safe_file}")
        docker.close()
    except DockerError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc

    typer.echo(result)
    out.success("Restore complete")


@app.command()
def verify(
    ctx: typer.Context,
    file: Annotated[str, typer.Argument(help="Backup file to verify")],
) -> None:
    """Verify a backup file."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info(f"Verifying: {file}")
    try:
        docker = _get_docker(actx)
        safe_file = shlex.quote(file)
        result = docker.docker_exec("db", f"/scripts/backup.sh verify {safe_file}")
        docker.close()
    except DockerError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc

    typer.echo(result)
