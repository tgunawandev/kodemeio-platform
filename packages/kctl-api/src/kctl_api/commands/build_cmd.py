"""Build commands for kctl-api.

Build Docker images for development and production.
"""

from __future__ import annotations

import subprocess
from typing import Annotated

import typer

from kctl_api.core.callbacks import AppContext
from kctl_api.core.utils import find_project_root

app = typer.Typer(name="build", help="Docker image builds — dev, prod, all.", no_args_is_help=True)


# ---------------------------------------------------------------------------
# dev
# ---------------------------------------------------------------------------
@app.command()
def dev(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name or 'all'.")] = "all",
) -> None:
    """Build development Docker image(s) via scripts/build --dev."""
    actx: AppContext = ctx.obj
    out = actx.output

    root = find_project_root()
    cmd = [str(root / "scripts" / "build"), app_name, "--dev"]

    out.info(f"Building dev image: {app_name}")
    result = subprocess.run(cmd, cwd=str(root), capture_output=False)
    if result.returncode != 0:
        out.error("Build failed.")
        raise typer.Exit(result.returncode)
    out.success(f"Dev build complete: {app_name}")


# ---------------------------------------------------------------------------
# prod
# ---------------------------------------------------------------------------
@app.command()
def prod(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name or 'all'.")] = "all",
) -> None:
    """Build production Docker image(s) via scripts/build."""
    actx: AppContext = ctx.obj
    out = actx.output

    root = find_project_root()
    cmd = [str(root / "scripts" / "build"), app_name]

    out.info(f"Building prod image: {app_name}")
    result = subprocess.run(cmd, cwd=str(root), capture_output=False)
    if result.returncode != 0:
        out.error("Build failed.")
        raise typer.Exit(result.returncode)
    out.success(f"Prod build complete: {app_name}")


# ---------------------------------------------------------------------------
# all
# ---------------------------------------------------------------------------
@app.command(name="all")
def build_all(
    ctx: typer.Context,
    dev_mode: Annotated[bool, typer.Option("--dev", help="Build in dev mode.")] = False,
) -> None:
    """Build all Docker images via scripts/build all."""
    actx: AppContext = ctx.obj
    out = actx.output

    root = find_project_root()
    cmd = [str(root / "scripts" / "build"), "all"]
    if dev_mode:
        cmd.append("--dev")

    out.info("Building all images ...")
    result = subprocess.run(cmd, cwd=str(root), capture_output=False)
    if result.returncode != 0:
        out.error("Build failed.")
        raise typer.Exit(result.returncode)
    out.success("All builds complete.")
