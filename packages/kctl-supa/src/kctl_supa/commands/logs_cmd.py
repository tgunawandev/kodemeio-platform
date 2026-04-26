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
            services = ["kong", "auth", "rest", "realtime", "storage", "functions", "db", "analytics", "meta"]
            parts = []
            for svc in services:
                try:
                    svc_log = docker.logs(svc, tail=lines // len(services) or 5)
                    parts.append(f"=== {svc} ===\n{svc_log}")
                except DockerError:
                    parts.append(f"=== {svc} === (no logs)")
            result = "\n".join(parts)
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

        if service:
            container = docker.resolve_container(service)
            safe_pattern = shlex.quote(pattern)
            result = docker.exec(f"docker logs {container} 2>&1 | grep -i {safe_pattern} || true")
        else:
            safe_pattern = shlex.quote(pattern)
            parts = []
            for svc in ["kong", "auth", "rest", "realtime", "storage", "functions", "db"]:
                try:
                    svc_container = docker.resolve_container(svc)
                    svc_log = docker.exec(f"docker logs {svc_container} 2>&1 | grep -i {safe_pattern} || true")
                    if svc_log.strip():
                        parts.append(f"=== {svc} ===\n{svc_log}")
                except DockerError:
                    pass
            result = "\n".join(parts)
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

    docker = _get_docker(actx)
    svc_name = service or "auth"
    container = docker.resolve_container(svc_name)
    docker.close()

    cmd = f"docker logs -f {container}"
    out.info("Run the following command on the remote host to stream logs:")
    typer.echo(f"  {cmd}")
