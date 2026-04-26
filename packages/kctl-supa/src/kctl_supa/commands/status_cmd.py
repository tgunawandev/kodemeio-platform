"""Container status commands for kctl-supa.

Show service container status.
"""

from __future__ import annotations

from typing import Annotated

import typer
from rich import print as rprint
from rich.table import Table

from kctl_supa.core.callbacks import AppContext
from kctl_supa.core.docker import DockerOps
from kctl_supa.core.exceptions import DockerError

app = typer.Typer(help="Show service container status.")


def _get_docker(actx: AppContext) -> DockerOps:
    return DockerOps(actx.config)


@app.command(name="all")
def all_containers(ctx: typer.Context) -> None:
    """Show all container states."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        docker = _get_docker(actx)
        containers = docker.container_status()
        docker.close()
    except DockerError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc

    if not containers:
        out.warn("No containers found.")
        return

    table = Table(title="Container Status", show_header=True, header_style="bold cyan")
    table.add_column("Name", style="cyan")
    table.add_column("State")
    table.add_column("Status")
    table.add_column("Uptime")

    for c in containers:
        name = c.get("Names", c.get("Name", ""))
        state = c.get("State", "")
        status = c.get("Status", "")
        uptime = c.get("RunningFor", c.get("CreatedAt", ""))

        state_fmt = f"[green]{state}[/green]" if state == "running" else f"[red]{state}[/red]"
        table.add_row(name, state_fmt, status, uptime)

    rprint(table)


@app.command()
def service(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Service/container name")],
) -> None:
    """Show specific service detail."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        docker = _get_docker(actx)
        full_name = docker.resolve_container(name)
        result = docker.exec(f"docker inspect {full_name}")
        docker.close()
    except DockerError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc

    typer.echo(result)
