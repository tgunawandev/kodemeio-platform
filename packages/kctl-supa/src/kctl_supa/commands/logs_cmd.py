"""Service log management commands for kctl-supa."""

from __future__ import annotations

import shlex
from typing import Annotated, Optional

import typer

from kctl_supa.core.callbacks import AppContext
from kctl_supa.core.docker import DockerOps
from kctl_supa.core.exceptions import DockerError

app = typer.Typer(help="Service log management.")


def _get_docker(actx: AppContext) -> DockerOps:
    return DockerOps(actx.config)


@app.command()
def tail(
    ctx: typer.Context,
    service: Annotated[Optional[str], typer.Argument(help="Service name (e.g. kong, db, auth)")] = None,
    lines: Annotated[int, typer.Option("--lines", "-n", help="Number of lines to show")] = 100,
) -> None:
    """Show recent logs for a service or all services."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        docker = _get_docker(actx)
        if service:
            result = docker.logs(service, tail=lines)
        else:
            cfg = actx.config
            prefix = cfg.container_prefix
            if prefix:
                result = docker.exec(
                    f"docker compose -f /app/terakidz-supabase/docker-compose.prod.yml logs --tail {lines}"
                )
            else:
                result = docker.exec(f"docker compose logs --tail {lines}")
        docker.close()
    except DockerError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc

    typer.echo(result)


@app.command()
def search(
    ctx: typer.Context,
    pattern: Annotated[str, typer.Argument(help="Pattern to search for in logs")],
    service: Annotated[Optional[str], typer.Argument(help="Service name to search (optional)")] = None,
) -> None:
    """Search for a pattern in service logs."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        docker = _get_docker(actx)
        cfg = actx.config
        prefix = cfg.container_prefix

        if service:
            container = f"{prefix}-{service}" if prefix else service
            safe_pattern = shlex.quote(pattern)
            result = docker.exec(f"docker logs {container} 2>&1 | grep -i {safe_pattern} || true")
        else:
            safe_pattern = shlex.quote(pattern)
            result = docker.exec(
                f"docker compose -f /app/terakidz-supabase/docker-compose.prod.yml logs 2>&1 | grep -i {safe_pattern} || true"
            )
        docker.close()
    except DockerError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc

    if result:
        typer.echo(result)
    else:
        out.info(f"No matches found for pattern: {pattern}")


@app.command()
def follow(
    ctx: typer.Context,
    service: Annotated[Optional[str], typer.Argument(help="Service name to follow (optional)")] = None,
) -> None:
    """Stream logs in real time (shows command to run)."""
    actx: AppContext = ctx.obj
    out = actx.output

    cfg = actx.config
    prefix = cfg.container_prefix

    if service:
        container = f"{prefix}-{service}" if prefix else service
        cmd = f"docker logs -f {container}"
    else:
        cmd = "docker compose -f /app/terakidz-supabase/docker-compose.prod.yml logs -f"

    out.info("Run the following command on the remote host to stream logs:")
    typer.echo(f"  {cmd}")
