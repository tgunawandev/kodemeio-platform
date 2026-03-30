"""Development server commands for kctl-api.

Start, stop, rebuild, and manage the dev environment.
"""

from __future__ import annotations

import subprocess
from typing import Annotated

import typer

from kctl_api.core.callbacks import AppContext
from kctl_api.core.utils import find_project_root

app = typer.Typer(name="dev", help="Development environment — up, down, rebuild, logs.", no_args_is_help=True)


# ---------------------------------------------------------------------------
# up
# ---------------------------------------------------------------------------
@app.command()
def up(
    ctx: typer.Context,
    build: Annotated[bool, typer.Option("--build", help="Rebuild images before starting.")] = False,
    odoo_mm: Annotated[bool, typer.Option("--odoo-mm", help="Include Odoo-MM.")] = False,
    plane_mm: Annotated[bool, typer.Option("--plane-mm", help="Include Plane-MM.")] = False,
    all_services: Annotated[bool, typer.Option("--all", help="Include all optional services.")] = False,
) -> None:
    """Start the development stack via scripts/dev."""
    actx: AppContext = ctx.obj
    out = actx.output

    root = find_project_root()
    cmd = [str(root / "scripts" / "dev")]
    if build:
        cmd.append("--build")
    if odoo_mm:
        cmd.append("--odoo-mm")
    if plane_mm:
        cmd.append("--plane-mm")
    if all_services:
        cmd.append("--all")

    out.info("Starting dev environment ...")
    result = subprocess.run(cmd, cwd=str(root), capture_output=False)
    if result.returncode != 0:
        out.error("Failed to start dev environment.")
        raise typer.Exit(result.returncode)


# ---------------------------------------------------------------------------
# down
# ---------------------------------------------------------------------------
@app.command()
def down(ctx: typer.Context) -> None:
    """Stop the development stack."""
    actx: AppContext = ctx.obj
    out = actx.output

    root = find_project_root()
    cmd = ["docker", "compose", "-f", str(root / "docker-compose.yml"), "down"]

    out.info("Stopping dev environment ...")
    result = subprocess.run(cmd, capture_output=False)
    if result.returncode != 0:
        out.error("Failed to stop dev environment.")
        raise typer.Exit(result.returncode)
    out.success("Dev environment stopped.")


# ---------------------------------------------------------------------------
# rebuild
# ---------------------------------------------------------------------------
@app.command()
def rebuild(
    ctx: typer.Context,
    service: Annotated[str | None, typer.Argument(help="Service name (all if omitted).")] = None,
) -> None:
    """Rebuild and restart docker compose services."""
    actx: AppContext = ctx.obj
    out = actx.output

    root = find_project_root()
    cmd = ["docker", "compose", "-f", str(root / "docker-compose.yml"), "up", "--build", "-d"]
    if service:
        cmd.append(service)

    out.info(f"Rebuilding {service if service else 'all services'} ...")
    result = subprocess.run(cmd, capture_output=False)
    if result.returncode != 0:
        out.error("Rebuild failed.")
        raise typer.Exit(result.returncode)
    out.success("Rebuild complete.")


# ---------------------------------------------------------------------------
# logs
# ---------------------------------------------------------------------------
@app.command()
def logs(
    ctx: typer.Context,
    service: Annotated[str | None, typer.Argument(help="Service name (all if omitted).")] = None,
    follow: Annotated[bool, typer.Option("--follow", "-f", help="Follow log output.")] = False,
    tail: Annotated[int, typer.Option("--tail", "-n", help="Number of lines.")] = 100,
) -> None:
    """View docker compose logs."""
    root = find_project_root()
    cmd = ["docker", "compose", "-f", str(root / "docker-compose.yml"), "logs", "--tail", str(tail)]
    if follow:
        cmd.append("--follow")
    if service:
        cmd.append(service)
    subprocess.run(cmd, capture_output=False)


# ---------------------------------------------------------------------------
# attach
# ---------------------------------------------------------------------------
@app.command()
def attach(
    ctx: typer.Context,
    service: Annotated[str, typer.Argument(help="Service name to attach to.")],
) -> None:
    """Attach to a running container's shell."""
    actx: AppContext = ctx.obj
    out = actx.output

    root = find_project_root()
    cmd = ["docker", "compose", "-f", str(root / "docker-compose.yml"), "exec", service, "/bin/sh"]

    out.info(f"Attaching to {service} ...")
    result = subprocess.run(cmd, capture_output=False)
    if result.returncode != 0:
        out.error(f"Failed to attach to {service}.")
        raise typer.Exit(result.returncode)
