"""Playwright E2E testing and screenshot commands."""

from __future__ import annotations

import signal
import subprocess
from typing import Annotated

import typer

from kctl_react.core.callbacks import AppContext
from kctl_react.core.runner import run

app = typer.Typer(help="E2E testing and screenshots via Playwright.")


@app.command()
def screenshots(
    ctx: typer.Context,
    app_name: Annotated[str | None, typer.Argument(help="App name (omit for all)")] = None,
) -> None:
    """Capture screenshots of all app pages using Playwright.

    Uses the existing capture-fast.sh script if available,
    or falls back to a basic Playwright screenshot approach.
    """
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    if app_name:
        actx.validate_app(app_name)

    # Try existing script first
    script = root / "scripts" / "screenshots" / "capture-fast.sh"
    if script.exists():
        out.info(f"Running screenshot capture{f' for {app_name}' if app_name else ''}...")
        cmd = ["bash", str(script)]
        if app_name:
            cmd.append(app_name)
        try:
            run(cmd, cwd=root, capture=False, timeout=300)
            out.success("Screenshots captured")
        except Exception as e:
            out.error(f"Screenshot capture failed: {e}")
            raise typer.Exit(1) from None
    else:
        # Fallback: use pnpm screenshots script
        out.info("Using pnpm screenshots script...")
        cmd = ["pnpm", f"screenshots{f':{app_name}' if app_name else ''}"]
        try:
            run(cmd, cwd=root, capture=False, timeout=300)
            out.success("Screenshots captured")
        except Exception as e:
            out.error(f"Screenshot capture failed: {e}")
            raise typer.Exit(1) from None

    # Show screenshot directory
    screenshots_dir = root / "docs" / "screenshots"
    if screenshots_dir.is_dir():
        count = len(list(screenshots_dir.rglob("*.png")))
        out.info(f"Screenshots: {count} file(s) in docs/screenshots/")


@app.command()
def test(
    ctx: typer.Context,
    app_name: Annotated[str | None, typer.Argument(help="App name (omit for all)")] = None,
    headed: Annotated[bool, typer.Option("--headed", help="Run with visible browser.")] = False,
    ui: Annotated[bool, typer.Option("--ui", help="Open Playwright UI mode.")] = False,
) -> None:
    """Run Playwright E2E tests.

    Examples:
      kctl-react e2e test              # Run all E2E tests
      kctl-react e2e test sfa --headed # Run SFA tests with visible browser
      kctl-react e2e test --ui         # Open Playwright UI mode
    """
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    if app_name:
        actx.validate_app(app_name)

    # Find e2e test directory
    e2e_dir = root / "e2e"
    if not e2e_dir.is_dir():
        e2e_dir = root / "tests" / "e2e"

    cmd = ["pnpm", "exec", "playwright", "test"]
    if app_name:
        cmd.append(f"--grep={app_name}")
    if headed:
        cmd.append("--headed")
    if ui:
        cmd = ["pnpm", "exec", "playwright", "test", "--ui"]

    out.info(f"Running E2E tests{f' for {app_name}' if app_name else ''}...")

    try:
        proc = subprocess.Popen(cmd, cwd=root)
        proc.wait()
        if proc.returncode == 0:
            out.success("E2E tests passed")
        else:
            out.error("E2E tests failed")
            raise typer.Exit(1)
    except KeyboardInterrupt:
        proc.send_signal(signal.SIGINT)
        proc.wait()


@app.command()
def report(ctx: typer.Context) -> None:
    """Open Playwright HTML test report."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    out.info("Opening Playwright report...")
    try:
        proc = subprocess.Popen(
            ["pnpm", "exec", "playwright", "show-report"],
            cwd=root,
        )
        proc.wait()
    except KeyboardInterrupt:
        proc.send_signal(signal.SIGINT)
        proc.wait()
    except Exception as e:
        out.error(f"Failed to open report: {e}")
