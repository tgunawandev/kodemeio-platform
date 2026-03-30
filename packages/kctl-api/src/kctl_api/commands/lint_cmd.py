"""Linting commands for kctl-api.

Run ruff and mypy checks via project scripts.
"""

from __future__ import annotations

import subprocess

import typer

from kctl_api.core.callbacks import AppContext
from kctl_api.core.utils import find_project_root

app = typer.Typer(name="lint", help="Linting — check, fix, strict.", no_args_is_help=True)


# ---------------------------------------------------------------------------
# check
# ---------------------------------------------------------------------------
@app.command()
def check(ctx: typer.Context) -> None:
    """Run ruff check + mypy via scripts/lint."""
    actx: AppContext = ctx.obj
    out = actx.output

    root = find_project_root()
    cmd = [str(root / "scripts" / "lint")]

    out.info("Running lint checks ...")
    result = subprocess.run(cmd, cwd=str(root), capture_output=False)
    if result.returncode != 0:
        out.error("Lint checks failed.")
        raise typer.Exit(result.returncode)
    out.success("Lint checks passed.")


# ---------------------------------------------------------------------------
# fix
# ---------------------------------------------------------------------------
@app.command()
def fix(ctx: typer.Context) -> None:
    """Run ruff check --fix to auto-fix lint issues."""
    actx: AppContext = ctx.obj
    out = actx.output

    root = find_project_root()

    out.info("Auto-fixing lint issues ...")
    result = subprocess.run(
        ["ruff", "check", "--fix", "."],
        cwd=str(root),
        capture_output=False,
    )
    if result.returncode != 0:
        out.warn("Some issues could not be auto-fixed.")
    else:
        out.success("All auto-fixable issues resolved.")


# ---------------------------------------------------------------------------
# strict
# ---------------------------------------------------------------------------
@app.command()
def strict(ctx: typer.Context) -> None:
    """Run mypy in strict mode."""
    actx: AppContext = ctx.obj
    out = actx.output

    root = find_project_root()

    out.info("Running mypy strict ...")
    result = subprocess.run(
        ["mypy", "--strict", "."],
        cwd=str(root),
        capture_output=False,
    )
    if result.returncode != 0:
        out.error("Strict type checking failed.")
        raise typer.Exit(result.returncode)
    out.success("Strict type checking passed.")
