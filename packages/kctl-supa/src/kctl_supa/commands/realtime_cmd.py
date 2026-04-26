"""Realtime service management commands for kctl-supa."""

from __future__ import annotations

import typer

from kctl_supa.core.callbacks import AppContext
from kctl_supa.core.docker import DockerOps
from kctl_supa.core.exceptions import DockerError

app = typer.Typer(help="Realtime service management.")


def _get_docker(actx: AppContext) -> DockerOps:
    return DockerOps(actx.config)


@app.command()
def status(ctx: typer.Context) -> None:
    """Show realtime service health."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        docker = _get_docker(actx)
        result = docker.docker_exec(
            "realtime",
            "bash -c '(echo > /dev/tcp/localhost/4000) 2>/dev/null && echo healthy || echo unhealthy'",
        )
        docker.close()
    except DockerError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc

    typer.echo(result)


@app.command()
def channels(ctx: typer.Context) -> None:
    """List active realtime channels."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        docker = _get_docker(actx)
        result = docker.psql("SELECT * FROM _realtime.extensions LIMIT 50")
        docker.close()
    except DockerError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc

    typer.echo(result)


@app.command()
def connections(ctx: typer.Context) -> None:
    """Current WebSocket connection count."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        docker = _get_docker(actx)
        result = docker.psql(
            "SELECT count(*) AS active_connections FROM pg_stat_activity "
            "WHERE application_name LIKE '%realtime%' OR application_name LIKE '%Realtime%'",
        )
        docker.close()
    except DockerError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc

    typer.echo(result)
