"""kctl-claude env — environment management."""

from __future__ import annotations

import subprocess

import typer
from kctl_common.exceptions import CommandError

from kctl_claude.core.callbacks import AppContext
from kctl_claude.core.runner import run_script

app = typer.Typer(help="Environment file management.")


@app.command()
def generate(ctx: typer.Context) -> None:
    """Interactive .env generator."""
    actx: AppContext = ctx.obj
    out = actx.output
    script = _get_script(actx, "generate-env.sh")
    try:
        run_script(script, capture=False)
        out.success(".env file generated")
    except CommandError as e:
        out.error(f"Command failed (exit {e.returncode}): {e.stderr}")
        raise typer.Exit(code=1) from None


@app.command()
def check(ctx: typer.Context) -> None:
    """Validate .env file."""
    actx: AppContext = ctx.obj
    out = actx.output
    script = _get_script(actx, "generate-env.sh")
    try:
        run_script(script, args=["--check"], capture=False)
        out.success(".env validation passed")
    except CommandError as e:
        out.error(f".env validation failed (exit {e.returncode})")
        raise typer.Exit(code=1) from None


@app.command()
def deploy(ctx: typer.Context) -> None:
    """Deploy .env to Hetzner server."""
    actx: AppContext = ctx.obj
    out = actx.output
    repo = actx.repo_dir
    if not repo:
        out.error("Repo not found.")
        raise typer.Exit(code=1)
    import os

    host = os.environ.get("HETZNER_SSH", "root@dokploy.kodeme.io")
    env_file = repo / ".env"
    if not env_file.is_file():
        env_file = repo / ".env.prod"
    if not env_file.is_file():
        out.error("No .env or .env.prod found")
        raise typer.Exit(code=1)
    out.info(f"Deploying {env_file.name} -> {host}:/opt/kodemeio-claude/.env")
    result = subprocess.run(
        ["scp", str(env_file), f"{host}:/opt/kodemeio-claude/.env"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        out.error(f"SCP failed (exit {result.returncode}): {result.stderr.strip()}")
        raise typer.Exit(code=1)
    out.success(f"Deployed {env_file.name} to {host}")


def _get_script(actx: AppContext, name: str):  # noqa: ANN202
    repo = actx.repo_dir
    if not repo:
        actx.output.error("Repo not found.")
        raise typer.Exit(code=1)
    script = repo / "scripts" / name
    if not script.is_file():
        actx.output.error(f"Script not found: {script}")
        raise typer.Exit(code=1)
    return script
