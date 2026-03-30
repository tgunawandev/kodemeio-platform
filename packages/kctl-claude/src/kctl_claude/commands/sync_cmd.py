"""kctl-claude sync — config sync between local and repo."""

from __future__ import annotations

import typer
from kctl_common.exceptions import CommandError

from kctl_claude.core.callbacks import AppContext
from kctl_claude.core.runner import run_script

app = typer.Typer(help="Sync config between local ~/.claude and repo.")


@app.command()
def push(ctx: typer.Context) -> None:
    """Sync local config -> repo (for Docker deployment)."""
    actx: AppContext = ctx.obj
    out = actx.output
    repo = actx.repo_dir
    if not repo:
        out.error("Repo not found. Run from inside kodemeio-claude or set up paths.")
        raise typer.Exit(code=1)
    script = repo / "scripts" / "sync-config.sh"
    try:
        run_script(script, capture=False)
        out.success("Config pushed to repo")
    except CommandError as e:
        out.error(f"Command failed (exit {e.returncode}): {e.stderr}")
        raise typer.Exit(code=1) from None


@app.command()
def pull(ctx: typer.Context) -> None:
    """Sync repo config -> local (update local environment)."""
    actx: AppContext = ctx.obj
    out = actx.output
    repo = actx.repo_dir
    if not repo:
        out.error("Repo not found.")
        raise typer.Exit(code=1)
    script = repo / "scripts" / "setup-local.sh"
    try:
        run_script(script, args=["--sync"], capture=False)
        out.success("Config pulled from repo")
    except CommandError as e:
        out.error(f"Command failed (exit {e.returncode}): {e.stderr}")
        raise typer.Exit(code=1) from None


@app.command()
def diff(ctx: typer.Context) -> None:
    """Preview what push would change (dry-run)."""
    actx: AppContext = ctx.obj
    out = actx.output
    repo = actx.repo_dir
    if not repo:
        out.error("Repo not found.")
        raise typer.Exit(code=1)
    script = repo / "scripts" / "sync-config.sh"
    try:
        run_script(script, args=["--dry-run"], capture=False)
        out.success("Diff complete")
    except CommandError as e:
        out.error(f"Command failed (exit {e.returncode}): {e.stderr}")
        raise typer.Exit(code=1) from None


@app.command()
def secrets(ctx: typer.Context) -> None:
    """Deploy kctl credentials to Hetzner."""
    actx: AppContext = ctx.obj
    out = actx.output
    repo = actx.repo_dir
    if not repo:
        out.error("Repo not found.")
        raise typer.Exit(code=1)
    script = repo / "scripts" / "sync-secrets.sh"
    try:
        run_script(script, capture=False)
        out.success("Secrets deployed to Hetzner")
    except CommandError as e:
        out.error(f"Command failed (exit {e.returncode}): {e.stderr}")
        raise typer.Exit(code=1) from None
