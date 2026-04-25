"""Stack deployment operation commands for kctl-supa."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from kctl_supa.core.callbacks import AppContext
from kctl_supa.core.docker import DockerOps
from kctl_supa.core.exceptions import DockerError

app = typer.Typer(help="Stack deployment operations.")

_COMPOSE_PATH = "/app/terakidz-supabase/docker-compose.prod.yml"


def _get_docker(actx: AppContext) -> DockerOps:
    return DockerOps(actx.config)


@app.command()
def up(ctx: typer.Context) -> None:
    """Bring the stack up with docker compose."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info("Starting stack...")
    try:
        docker = _get_docker(actx)
        result = docker.exec(f"docker compose -f {_COMPOSE_PATH} up -d")
        docker.close()
    except DockerError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc

    typer.echo(result)
    out.success("Stack is up")


@app.command()
def down(ctx: typer.Context) -> None:
    """Bring the stack down with docker compose."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info("Stopping stack...")
    try:
        docker = _get_docker(actx)
        result = docker.exec(f"docker compose -f {_COMPOSE_PATH} down")
        docker.close()
    except DockerError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc

    typer.echo(result)
    out.success("Stack is down")


@app.command()
def restart(
    ctx: typer.Context,
    service: Annotated[Optional[str], typer.Argument(help="Service name to restart (omit for all)")] = None,
) -> None:
    """Restart a service or the entire stack."""
    actx: AppContext = ctx.obj
    out = actx.output

    target = service or "all services"
    out.info(f"Restarting {target}...")
    try:
        docker = _get_docker(actx)
        svc_arg = service or ""
        result = docker.exec(f"docker compose -f {_COMPOSE_PATH} restart {svc_arg}".strip())
        docker.close()
    except DockerError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc

    typer.echo(result)
    out.success(f"Restarted {target}")


@app.command()
def pull(ctx: typer.Context) -> None:
    """Pull latest images for the stack."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info("Pulling latest images...")
    try:
        docker = _get_docker(actx)
        result = docker.exec(f"docker compose -f {_COMPOSE_PATH} pull")
        docker.close()
    except DockerError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc

    typer.echo(result)
    out.success("Images pulled")


@app.command()
def redeploy(ctx: typer.Context) -> None:
    """Pull latest images then bring the stack up."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info("Pulling latest images...")
    try:
        docker = _get_docker(actx)
        pull_result = docker.exec(f"docker compose -f {_COMPOSE_PATH} pull")
        typer.echo(pull_result)

        out.info("Starting stack...")
        up_result = docker.exec(f"docker compose -f {_COMPOSE_PATH} up -d")
        docker.close()
        typer.echo(up_result)
    except DockerError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc

    out.success("Redeploy complete")
