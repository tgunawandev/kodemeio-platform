"""Self-test command — runs the built-in test suite."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Annotated

import typer

app = typer.Typer(help="Run built-in test suite.")


@app.command("run")
def run(
    ctx: typer.Context,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Verbose test output")] = False,
    smoke: Annotated[bool, typer.Option("--smoke", help="Run smoke tests (requires live API)")] = False,
    coverage: Annotated[bool, typer.Option("--coverage", help="Run with coverage report")] = False,
) -> None:
    """Run the kctl-cloudflare test suite.

    By default runs unit tests only. Use --smoke to include integration tests
    that require a live Cloudflare API connection.

    Examples:
        kctl-cloudflare selftest run
        kctl-cloudflare selftest run -v
        kctl-cloudflare selftest run --smoke
        kctl-cloudflare selftest run --coverage
    """
    # Resolve tests directory relative to package
    pkg_dir = Path(__file__).resolve().parents[3]
    tests_dir = pkg_dir / "tests"

    if not tests_dir.is_dir():
        # Try project root (development mode)
        project_root = Path(__file__).resolve().parents[4]
        tests_dir = project_root / "tests"

    if not tests_dir.is_dir():
        typer.echo("Test directory not found. Ensure tests/ exists in the project.", err=True)
        raise typer.Exit(1)

    cmd = [sys.executable, "-m", "pytest", str(tests_dir)]

    if verbose:
        cmd.append("-v")

    if not smoke:
        cmd.extend(["-m", "not smoke"])

    if coverage:
        cmd.extend(["--cov=kctl_cloudflare", "--cov-report=term-missing"])

    cmd.extend(["--tb=short", "-q"])

    sys.exit(subprocess.call(cmd))  # noqa: S603
