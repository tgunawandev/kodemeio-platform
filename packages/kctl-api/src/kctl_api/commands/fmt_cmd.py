"""Formatting commands for kctl-api.

Run ruff format via project scripts.
"""

from __future__ import annotations

import subprocess

import typer

from kctl_api.core.callbacks import AppContext
from kctl_api.core.utils import find_project_root

app = typer.Typer(name="fmt", help="Code formatting — run, check.", no_args_is_help=True)


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------
@app.command()
def run(ctx: typer.Context) -> None:
    """Format code via scripts/fmt."""
    actx: AppContext = ctx.obj
    out = actx.output

    root = find_project_root()
    cmd = [str(root / "scripts" / "fmt")]

    out.info("Formatting code ...")
    result = subprocess.run(cmd, cwd=str(root), capture_output=False)
    if result.returncode != 0:
        out.error("Formatting failed.")
        raise typer.Exit(result.returncode)
    out.success("Code formatted.")


# ---------------------------------------------------------------------------
# check
# ---------------------------------------------------------------------------
@app.command()
def check(ctx: typer.Context) -> None:
    """Check formatting without modifying files (ruff format --check)."""
    actx: AppContext = ctx.obj
    out = actx.output

    root = find_project_root()

    out.info("Checking code formatting ...")
    result = subprocess.run(
        ["ruff", "format", "--check", "."],
        cwd=str(root),
        capture_output=False,
    )
    if result.returncode != 0:
        out.error("Code is not properly formatted. Run: kctl-api fmt run")
        raise typer.Exit(result.returncode)
    out.success("Code is properly formatted.")
