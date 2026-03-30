"""Test runner commands for kctl-api.

Run pytest for specific apps or the entire workspace.
"""

from __future__ import annotations

import subprocess
from typing import Annotated

import typer

from kctl_api.core.callbacks import AppContext
from kctl_api.core.utils import find_project_root

app = typer.Typer(name="test", help="Test runner — run, coverage, watch.", no_args_is_help=True)


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------
@app.command()
def run(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name or 'all'.")] = "all",
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Verbose output.")] = False,
    marker: Annotated[str | None, typer.Option("--marker", "-m", help="Pytest marker expression.")] = None,
    keyword: Annotated[str | None, typer.Option("--keyword", "-k", help="Pytest keyword expression.")] = None,
) -> None:
    """Run tests via scripts/test."""
    actx: AppContext = ctx.obj
    out = actx.output

    root = find_project_root()
    cmd = [str(root / "scripts" / "test"), app_name]
    if verbose:
        cmd.append("-v")
    if marker:
        cmd.extend(["-m", marker])
    if keyword:
        cmd.extend(["-k", keyword])

    out.info(f"Running tests for: {app_name}")
    result = subprocess.run(cmd, cwd=str(root), capture_output=False)
    if result.returncode != 0:
        out.error("Tests failed.")
        raise typer.Exit(result.returncode)
    out.success("Tests passed.")


# ---------------------------------------------------------------------------
# coverage
# ---------------------------------------------------------------------------
@app.command()
def coverage(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name or 'all'.")] = "all",
) -> None:
    """Run tests with coverage report via scripts/test --cov."""
    actx: AppContext = ctx.obj
    out = actx.output

    root = find_project_root()
    cmd = [str(root / "scripts" / "test"), app_name, "--cov"]

    out.info(f"Running tests with coverage for: {app_name}")
    result = subprocess.run(cmd, cwd=str(root), capture_output=False)
    if result.returncode != 0:
        out.error("Tests failed.")
        raise typer.Exit(result.returncode)
    out.success("Coverage report generated.")


# ---------------------------------------------------------------------------
# watch
# ---------------------------------------------------------------------------
@app.command()
def watch(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name or 'all'.")] = "all",
) -> None:
    """Run tests in watch mode (requires pytest-watch)."""
    actx: AppContext = ctx.obj
    out = actx.output

    root = find_project_root()

    out.info(f"Starting test watcher for: {app_name}")
    app_dir = root / "apps" / app_name if app_name != "all" else root
    cmd = ["ptw", "--", str(app_dir)]
    try:
        subprocess.run(cmd, cwd=str(root), capture_output=False)
    except FileNotFoundError:
        out.error("pytest-watch (ptw) not found. Install with: uv pip install pytest-watch")
        raise typer.Exit(1) from None
