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
def test(
    ctx: typer.Context,
    app_name: Annotated[str | None, typer.Argument(help="App name (omit for all)")] = None,
    headed: Annotated[bool, typer.Option("--headed", help="Run with visible browser.")] = False,
    ui: Annotated[bool, typer.Option("--ui", help="Open Playwright UI mode.")] = False,
    shared_only: Annotated[bool, typer.Option("--shared", help="Run only shared tests.")] = False,
    debug: Annotated[bool, typer.Option("--debug", help="Run with Playwright debug mode.")] = False,
    screenshots: Annotated[bool, typer.Option("--screenshots", help="Capture screenshots for every test.")] = False,
    video: Annotated[bool, typer.Option("--video", help="Record video for every test.")] = False,
    mobile: Annotated[bool, typer.Option("--mobile", help="Run with mobile viewport (iPhone 14).")] = False,
    grep: Annotated[str | None, typer.Option("--grep", "-g", help="Filter tests by title pattern.")] = None,
    api_only: Annotated[bool, typer.Option("--api", help="Run only API CRUD tests.")] = False,
    pages_only: Annotated[bool, typer.Option("--pages", help="Run only page screenshot tests.")] = False,
) -> None:
    """Run Playwright E2E tests.

    Uses multi-project config with --project flag for per-app targeting.

    Examples:
      kctl-react e2e test              # Run all E2E tests
      kctl-react e2e test sfa          # Run SFA tests (shared + app-specific)
      kctl-react e2e test sfa --headed # Run SFA tests with visible browser
      kctl-react e2e test sfa --shared # Run only shared tests for SFA
      kctl-react e2e test hrm --screenshots  # Run with screenshots
      kctl-react e2e test hrm --video        # Run with video recording
      kctl-react e2e test hrm --mobile       # Run with mobile viewport
      kctl-react e2e test hrm --mobile --screenshots  # Mobile + screenshots
      kctl-react e2e test hrm --api          # Run only API CRUD tests
      kctl-react e2e test hrm --pages        # Run only page screenshot tests
      kctl-react e2e test hrm --grep "Leave" # Run tests matching "Leave"
      kctl-react e2e test --ui         # Open Playwright UI mode
    """
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    if app_name:
        actx.validate_app(app_name)

    e2e_dir = root / "e2e"
    if not e2e_dir.is_dir():
        out.error("e2e/ directory not found")
        raise typer.Exit(1) from None

    cmd = ["npx", "playwright", "test"]

    # File filter must come before --project
    if api_only and app_name:
        cmd.append(f"tests/apps/{app_name}/api-crud.spec.ts")
    elif pages_only and app_name:
        app_pages = e2e_dir / "tests" / "apps" / app_name / "all-pages.spec.ts"
        if app_pages.exists():
            cmd.append(f"tests/apps/{app_name}/all-pages.spec.ts")
        else:
            # Use generic factory (auto-generates from app-registry)
            cmd.append("factories/all-pages.factory.ts")
    elif shared_only:
        cmd.append("tests/shared/")

    # Build project name: "hrm" or "hrm-mobile"
    project_name = app_name
    if app_name and mobile:
        project_name = f"{app_name}-mobile"
    elif mobile and not app_name:
        out.error("--mobile requires an app name (e.g. kctl-react e2e test hrm --mobile)")
        raise typer.Exit(1) from None

    if project_name:
        cmd.extend(["--project", project_name])

    if headed:
        cmd.append("--headed")
    if ui:
        cmd.append("--ui")
    if debug:
        cmd.append("--debug")
    if grep:
        cmd.extend(["--grep", grep])

    env: dict[str, str] = {}
    if app_name:
        env["E2E_APPS"] = app_name
    if screenshots:
        env["E2E_SCREENSHOTS"] = "on"
    if video:
        env["E2E_VIDEO"] = "on"

    viewport = "mobile" if mobile else "desktop"
    flags = []
    if screenshots:
        flags.append("screenshots")
    if video:
        flags.append("video")
    if api_only:
        flags.append("API only")
    if pages_only:
        flags.append("pages only")
    if grep:
        flags.append(f'grep="{grep}"')
    flags_str = f"  ({', '.join(flags)})" if flags else ""
    out.info(f"Running E2E tests{f' for {app_name}' if app_name else ' (all apps)'} [{viewport}]{flags_str}...")

    try:
        import os

        run_env = {**os.environ, **(env or {})}
        proc = subprocess.Popen(cmd, cwd=e2e_dir, env=run_env)
        proc.wait()
        if proc.returncode == 0:
            out.success("E2E tests passed")
            if screenshots or video:
                results_dir = root / "e2e" / "screenshots"
                if results_dir.is_dir():
                    parts = []
                    if screenshots:
                        pngs = list(results_dir.rglob("*.png"))
                        parts.append(f"Screenshots: {len(pngs)} file(s)")
                    if video:
                        videos = list(results_dir.rglob("*.webm"))
                        parts.append(f"Videos: {len(videos)} file(s)")
                    out.info(f"{', '.join(parts)} in e2e/screenshots/")
        else:
            out.error("E2E tests failed")
            raise typer.Exit(1)
    except KeyboardInterrupt:
        proc.send_signal(signal.SIGINT)
        proc.wait()


@app.command(name="list")
def list_tests(
    ctx: typer.Context,
    app_name: Annotated[str | None, typer.Argument(help="App name (omit for all)")] = None,
) -> None:
    """List all discovered E2E tests.

    Examples:
      kctl-react e2e list          # List all tests
      kctl-react e2e list sfa      # List SFA tests only
    """
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    if app_name:
        actx.validate_app(app_name)

    e2e_dir = root / "e2e"
    if not e2e_dir.is_dir():
        out.error("e2e/ directory not found")
        raise typer.Exit(1) from None

    cmd = ["npx", "playwright", "test", "--list"]
    env: dict[str, str] | None = None

    if app_name:
        cmd.extend(["--project", app_name])
        env = {"E2E_APPS": app_name}

    try:
        run(cmd, cwd=e2e_dir, capture=False, timeout=30, env=env)
    except Exception as e:
        out.error(f"Failed to list tests: {e}")
        raise typer.Exit(1) from None


@app.command()
def report(ctx: typer.Context) -> None:
    """Open Playwright HTML test report."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    e2e_dir = root / "e2e"
    if not e2e_dir.is_dir():
        out.error("e2e/ directory not found")
        raise typer.Exit(1) from None

    out.info("Opening Playwright report...")
    try:
        proc = subprocess.Popen(
            ["npx", "playwright", "show-report"],
            cwd=e2e_dir,
        )
        proc.wait()
    except KeyboardInterrupt:
        proc.send_signal(signal.SIGINT)
        proc.wait()
    except Exception as e:
        out.error(f"Failed to open report: {e}")


@app.command()
def discover(
    ctx: typer.Context,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview without writing.")] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
) -> None:
    """Auto-discover app configs and regenerate e2e/app-registry.ts.

    Scans apps/spa/*/src/ for ports, token keys, routes, and nav items.
    Run this after adding new pages, routes, or nav items.

    Examples:
      kctl-react e2e discover            # Regenerate registry
      kctl-react e2e discover --dry-run  # Preview changes
      kctl-react e2e discover --json     # Output as JSON
    """
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    script = root / "e2e" / "scripts" / "discover.mjs"
    if not script.exists():
        out.error("e2e/scripts/discover.mjs not found")
        raise typer.Exit(1) from None

    cmd = ["node", str(script)]
    if dry_run:
        cmd.append("--dry-run")
    if json_output:
        cmd.append("--json")

    out.info("Discovering app configs from source files...")
    try:
        run(cmd, cwd=root, capture=False, timeout=30)
    except Exception as e:
        out.error(f"Discovery failed: {e}")
        raise typer.Exit(1) from None


@app.command()
def install(ctx: typer.Context) -> None:
    """Install Playwright browsers (chromium).

    Examples:
      kctl-react e2e install
    """
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    e2e_dir = root / "e2e"
    if not e2e_dir.is_dir():
        out.error("e2e/ directory not found")
        raise typer.Exit(1) from None

    out.info("Installing Playwright browsers...")
    try:
        run(
            ["npx", "playwright", "install", "--with-deps", "chromium"],
            cwd=e2e_dir,
            capture=False,
            timeout=120,
        )
        out.success("Playwright browsers installed")
    except Exception as e:
        out.error(f"Failed to install browsers: {e}")
        raise typer.Exit(1) from None


@app.command()
def screenshots(
    ctx: typer.Context,
    app_name: Annotated[str | None, typer.Argument(help="App name (omit for all)")] = None,
    mobile: Annotated[bool, typer.Option("--mobile", help="Use mobile viewport (default).")] = True,
    desktop: Annotated[bool, typer.Option("--desktop", help="Use desktop viewport.")] = False,
) -> None:
    """Capture screenshots of all app pages via Playwright.

    Runs the all-pages.factory.ts test which saves timestamped screenshots
    to e2e/screenshots/{app}/{viewport}/{YYYYMMDD-HHMMSS}/.

    Examples:
      kctl-react e2e screenshots           # All apps, mobile viewport
      kctl-react e2e screenshots sfa       # SFA only
      kctl-react e2e screenshots --desktop # Desktop viewport
    """
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    if app_name:
        actx.validate_app(app_name)

    e2e_dir = root / "e2e"
    if not e2e_dir.is_dir():
        out.error("e2e/ directory not found")
        raise typer.Exit(1) from None

    # Determine viewport: --desktop overrides default mobile
    use_mobile = not desktop

    # Build playwright command — delegates to all-pages.factory.ts
    cmd = ["npx", "playwright", "test", "factories/all-pages.factory.ts"]

    if app_name:
        project_name = f"{app_name}-mobile" if use_mobile else app_name
        cmd.extend(["--project", project_name])

    viewport_label = "mobile" if use_mobile else "desktop"
    out.info(f"Capturing screenshots{f' for {app_name}' if app_name else ' (all apps)'} [{viewport_label}]...")

    import os

    env = {**os.environ}
    if app_name:
        env["E2E_APPS"] = app_name

    try:
        proc = subprocess.Popen(cmd, cwd=e2e_dir, env=env)
        proc.wait()
        if proc.returncode == 0:
            out.success("Screenshots captured")
        else:
            out.error("Screenshot capture failed (Playwright exited with errors)")
            raise typer.Exit(1)
    except KeyboardInterrupt:
        proc.send_signal(signal.SIGINT)
        proc.wait()

    # Show screenshot directory
    screenshots_dir = root / "e2e" / "screenshots"
    if screenshots_dir.is_dir():
        count = len(list(screenshots_dir.rglob("*.png")))
        out.info(f"Screenshots: {count} file(s) in e2e/screenshots/")
