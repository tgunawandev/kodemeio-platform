"""Docker container management."""

from __future__ import annotations

from typing import Annotated

import typer
from kctl_lib.docker import DockerManager

from kctl_react.core.callbacks import AppContext

app = typer.Typer(help="Docker container management.")


def _get_manager(actx: AppContext, app_name: str | None = None) -> DockerManager:
    compose = (
        actx.project_root / f"docker-compose.prod.{app_name}.yml"
        if app_name
        else actx.project_root / "docker-compose.yml"
    )
    if not compose.exists():
        compose = actx.project_root / "docker-compose.prod.yml"
    return DockerManager(compose_file=compose, project_name=app_name or "kodemeio-react")


@app.command()
def ps(ctx: typer.Context) -> None:
    """List running containers."""
    actx: AppContext = ctx.obj
    out = actx.output
    mgr = _get_manager(actx)
    containers = mgr.ps()
    if not containers:
        out.info("No running containers")
        return
    rows = [[c.get("Name", ""), c.get("State", ""), c.get("Status", "")] for c in containers]
    out.table("Containers", [("Name", "cyan"), ("State", "green"), ("Status", "dim")], rows, data_for_json=containers)


@app.command()
def logs(
    ctx: typer.Context,
    service: Annotated[str | None, typer.Argument(help="Service name")] = None,
    tail: Annotated[int, typer.Option("--tail", help="Lines")] = 100,
) -> None:
    """Stream container logs."""
    actx: AppContext = ctx.obj
    mgr = _get_manager(actx)
    mgr.logs(service=service, tail=tail)


@app.command()
def restart(ctx: typer.Context, service: Annotated[str, typer.Argument(help="Service name")]) -> None:
    """Restart a container."""
    actx: AppContext = ctx.obj
    out = actx.output
    mgr = _get_manager(actx)
    mgr.restart(service)
    out.success(f"Restarted {service}")


@app.command("image-size")
def image_size(ctx: typer.Context) -> None:
    """Show Docker image sizes."""
    actx: AppContext = ctx.obj
    out = actx.output
    mgr = _get_manager(actx)
    images = mgr.image_size()
    if not images:
        out.info("No images found")
        return
    rows = [[i.get("Repository", ""), i.get("Tag", ""), i.get("Size", "")] for i in images]
    out.table("Images", [("Repository", "cyan"), ("Tag", "dim"), ("Size", "")], rows, data_for_json=images)
