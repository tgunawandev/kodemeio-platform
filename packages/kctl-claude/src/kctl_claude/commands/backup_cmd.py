"""kctl-claude backup — runtime volume backup/restore."""

from __future__ import annotations

import subprocess
from typing import Annotated

import typer
from kctl_common.exceptions import CommandError

from kctl_claude.core.callbacks import AppContext
from kctl_claude.core.runner import run_script

app = typer.Typer(help="Backup and restore Claude Code runtime.")


@app.command("create")
def create_backup(ctx: typer.Context) -> None:
    """Backup container runtime volume."""
    actx: AppContext = ctx.obj
    out = actx.output
    repo = actx.repo_dir
    if not repo:
        out.error("Repo not found.")
        raise typer.Exit(code=1)
    script = repo / "scripts" / "backup-runtime.sh"
    try:
        run_script(script, capture=False)
        out.success("Backup created")
    except CommandError as e:
        out.error(f"Backup failed (exit {e.returncode}): {e.stderr}")
        raise typer.Exit(code=1) from None


@app.command()
def restore(
    ctx: typer.Context,
    backup_dir: Annotated[str, typer.Argument(help="Path to backup directory")],
) -> None:
    """Restore runtime from backup."""
    actx: AppContext = ctx.obj
    out = actx.output
    out.info(f"Restoring from {backup_dir}...")
    result = subprocess.run(
        ["docker", "cp", f"{backup_dir}/.", "kodemeio-claude:/home/dev/.claude/"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        out.success("Restore complete")
    else:
        out.error(f"Restore failed (exit {result.returncode}): {result.stderr.strip()}")
        raise typer.Exit(code=1)
