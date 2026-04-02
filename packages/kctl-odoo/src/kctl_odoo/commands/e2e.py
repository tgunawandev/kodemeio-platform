"""Playwright E2E testing for Odoo web UI."""

from __future__ import annotations

import signal
import subprocess
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.config import resolve_connection

app = typer.Typer(help="E2E browser testing via Playwright.")
console = Console()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

E2E_DIR_NAME = "e2e"


def _find_e2e_dir() -> Path:
    """Locate the e2e/ directory relative to the kctl-odoo package root."""
    # Walk up from this file to find the package root (has pyproject.toml)
    cur = Path(__file__).resolve().parent.parent.parent.parent  # commands -> kctl_odoo -> src -> kctl-odoo
    e2e = cur / E2E_DIR_NAME
    if e2e.is_dir():
        return e2e

    # Also try CWD
    cwd_e2e = Path.cwd() / E2E_DIR_NAME
    if cwd_e2e.is_dir():
        return cwd_e2e

    return cur / E2E_DIR_NAME  # return expected path for error messages


def _resolve_odoo_url(ctx: typer.Context) -> str:
    """Get the Odoo base URL from the active profile."""
    actx: AppContext = ctx.obj
    url, _db, _user, _key = resolve_connection(
        profile_name=actx.profile,
        url_override=actx.url_override,
    )
    return url


def _build_env(ctx: typer.Context, extra: dict[str, str] | None = None) -> dict[str, str]:
    """Build environment dict with Odoo connection info for Playwright tests."""
    import os

    actx: AppContext = ctx.obj
    url, database, username, api_key = resolve_connection(
        profile_name=actx.profile,
        url_override=actx.url_override,
        api_key_override=actx.api_key_override,
        database_override=actx.database_override,
        username_override=actx.username_override,
    )

    env = {**os.environ}
    if url:
        env["ODOO_URL"] = url
    if database:
        env["ODOO_DATABASE"] = database
    if username:
        env["ODOO_USERNAME"] = username
    if api_key:
        env["ODOO_API_KEY"] = api_key
    if extra:
        env.update(extra)
    return env


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command()
def test(
    ctx: typer.Context,
    scenario: Annotated[str | None, typer.Argument(help="Scenario name (omit for all)")] = None,
    headed: Annotated[bool, typer.Option("--headed", help="Run with visible browser.")] = False,
    ui: Annotated[bool, typer.Option("--ui", help="Open Playwright UI mode.")] = False,
    debug: Annotated[bool, typer.Option("--debug", help="Run with Playwright debug mode.")] = False,
    screenshots: Annotated[bool, typer.Option("--screenshots", help="Capture screenshots for every test.")] = False,
    video: Annotated[bool, typer.Option("--video", help="Record video for every test.")] = False,
    mobile: Annotated[bool, typer.Option("--mobile", help="Run with mobile viewport.")] = False,
    smoke: Annotated[bool, typer.Option("--smoke", help="Run only smoke tests (visit all menus).")] = False,
    module: Annotated[str | None, typer.Option("--module", "-m", help="Filter by Odoo module.")] = None,
    grep: Annotated[str | None, typer.Option("--grep", "-g", help="Filter tests by title pattern.")] = None,
) -> None:
    """Run Playwright E2E tests against an Odoo instance.

    Uses the active kctl-odoo profile for connection details (URL, database,
    credentials). Tests run from the e2e/ directory inside kctl-odoo.

    Examples:
      kctl-odoo e2e test                    # Run all E2E tests
      kctl-odoo e2e test login              # Run login scenario only
      kctl-odoo e2e test --smoke            # Smoke test: visit all menus
      kctl-odoo e2e test --module sale      # Run tests for sale module
      kctl-odoo e2e test --headed           # Run with visible browser
      kctl-odoo e2e test --mobile           # Run with mobile viewport
      kctl-odoo e2e test --screenshots      # Capture screenshots
      kctl-odoo e2e test --grep "Invoice"   # Filter by test title
      kctl-odoo e2e test --ui              # Open Playwright UI mode
    """
    e2e_dir = _find_e2e_dir()
    if not e2e_dir.is_dir():
        console.print(f"[red]ERROR[/red] e2e/ directory not found at {e2e_dir}")
        console.print("  Run [bold]kctl-odoo e2e install[/bold] to set up E2E testing.")
        raise typer.Exit(1)

    cmd = ["npx", "playwright", "test"]

    # File/directory filters
    if smoke:
        cmd.append("tests/smoke/")
    elif scenario:
        cmd.append(f"tests/scenarios/{scenario}")

    # Project selection (viewport)
    if mobile:
        cmd.extend(["--project", "mobile"])
    else:
        cmd.extend(["--project", "desktop"])

    if headed:
        cmd.append("--headed")
    if ui:
        cmd.append("--ui")
    if debug:
        cmd.append("--debug")
    if grep:
        cmd.extend(["--grep", grep])

    extra_env: dict[str, str] = {}
    if module:
        extra_env["ODOO_E2E_MODULE"] = module
    if screenshots:
        extra_env["ODOO_E2E_SCREENSHOTS"] = "on"
    if video:
        extra_env["ODOO_E2E_VIDEO"] = "on"

    # Build info line
    flags = []
    if smoke:
        flags.append("smoke")
    if module:
        flags.append(f"module={module}")
    if screenshots:
        flags.append("screenshots")
    if video:
        flags.append("video")
    if mobile:
        flags.append("mobile")
    flags_str = f"  ({', '.join(flags)})" if flags else ""

    target = f" scenario={scenario}" if scenario else " (all)"
    console.print(f"[blue]INFO[/blue] Running E2E tests{target}{flags_str}...")

    env = _build_env(ctx, extra_env)

    try:
        proc = subprocess.Popen(cmd, cwd=e2e_dir, env=env)
        proc.wait()
        if proc.returncode == 0:
            console.print("[green]OK[/green] E2E tests passed")
            # Report screenshots/videos if captured
            if screenshots or video:
                results_dir = e2e_dir / "test-results"
                if results_dir.is_dir():
                    parts = []
                    if screenshots:
                        pngs = list(results_dir.rglob("*.png"))
                        parts.append(f"Screenshots: {len(pngs)}")
                    if video:
                        videos = list(results_dir.rglob("*.webm"))
                        parts.append(f"Videos: {len(videos)}")
                    console.print(f"[blue]INFO[/blue] {', '.join(parts)} in e2e/test-results/")
        else:
            console.print("[red]FAIL[/red] E2E tests failed")
            raise typer.Exit(1)
    except FileNotFoundError:
        console.print("[red]ERROR[/red] npx not found. Install Node.js and run [bold]kctl-odoo e2e install[/bold].")
        raise typer.Exit(1) from None
    except KeyboardInterrupt:
        proc.send_signal(signal.SIGINT)
        proc.wait()


@app.command(name="list")
def list_tests(
    ctx: typer.Context,
    scenario: Annotated[str | None, typer.Argument(help="Scenario name (omit for all)")] = None,
) -> None:
    """List all discovered E2E tests.

    Examples:
      kctl-odoo e2e list              # List all tests
      kctl-odoo e2e list login        # List login scenario tests
    """
    e2e_dir = _find_e2e_dir()
    if not e2e_dir.is_dir():
        console.print(f"[red]ERROR[/red] e2e/ directory not found at {e2e_dir}")
        raise typer.Exit(1)

    cmd = ["npx", "playwright", "test", "--list"]
    if scenario:
        cmd.append(f"tests/scenarios/{scenario}")

    env = _build_env(ctx)

    try:
        subprocess.run(cmd, cwd=e2e_dir, env=env, check=False)
    except FileNotFoundError:
        console.print("[red]ERROR[/red] npx not found.")
        raise typer.Exit(1) from None


@app.command()
def report(ctx: typer.Context) -> None:
    """Open Playwright HTML test report.

    Examples:
      kctl-odoo e2e report
    """
    e2e_dir = _find_e2e_dir()
    if not e2e_dir.is_dir():
        console.print(f"[red]ERROR[/red] e2e/ directory not found at {e2e_dir}")
        raise typer.Exit(1)

    console.print("[blue]INFO[/blue] Opening Playwright report...")
    try:
        proc = subprocess.Popen(
            ["npx", "playwright", "show-report"],
            cwd=e2e_dir,
        )
        proc.wait()
    except KeyboardInterrupt:
        proc.send_signal(signal.SIGINT)
        proc.wait()
    except FileNotFoundError:
        console.print("[red]ERROR[/red] npx not found.")
        raise typer.Exit(1) from None


@app.command()
def install(ctx: typer.Context) -> None:
    """Install Playwright browsers and dependencies.

    Sets up the e2e/ project: installs npm packages and Playwright browsers.

    Examples:
      kctl-odoo e2e install
    """
    e2e_dir = _find_e2e_dir()
    if not e2e_dir.is_dir():
        console.print(f"[red]ERROR[/red] e2e/ directory not found at {e2e_dir}")
        console.print("  Expected at: {e2e_dir}")
        raise typer.Exit(1)

    # Step 1: npm install
    pkg_json = e2e_dir / "package.json"
    if pkg_json.exists():
        console.print("[blue]INFO[/blue] Installing npm dependencies...")
        try:
            subprocess.run(["npm", "install"], cwd=e2e_dir, check=True, timeout=120)
        except subprocess.CalledProcessError:
            console.print("[red]ERROR[/red] npm install failed")
            raise typer.Exit(1) from None
        except FileNotFoundError:
            console.print("[red]ERROR[/red] npm not found. Install Node.js first.")
            raise typer.Exit(1) from None

    # Step 2: install browsers
    console.print("[blue]INFO[/blue] Installing Playwright browsers (chromium)...")
    try:
        subprocess.run(
            ["npx", "playwright", "install", "--with-deps", "chromium"],
            cwd=e2e_dir,
            check=True,
            timeout=180,
        )
        console.print("[green]OK[/green] Playwright browsers installed")
    except subprocess.CalledProcessError:
        console.print("[red]ERROR[/red] Failed to install Playwright browsers")
        raise typer.Exit(1) from None
    except FileNotFoundError:
        console.print("[red]ERROR[/red] npx not found.")
        raise typer.Exit(1) from None


@app.command()
def screenshots(
    ctx: typer.Context,
    module: Annotated[str | None, typer.Option("--module", "-m", help="Filter by Odoo module.")] = None,
    output: Annotated[str, typer.Option("--output", "-o", help="Output directory.")] = "screenshots",
) -> None:
    """Capture screenshots of all accessible Odoo menu pages.

    Logs into Odoo, navigates each menu item, and captures a screenshot.
    Useful for visual regression testing and documentation.

    Examples:
      kctl-odoo e2e screenshots                  # All menus
      kctl-odoo e2e screenshots --module sale     # Sale module menus only
      kctl-odoo e2e screenshots -o docs/screens   # Custom output dir
    """
    e2e_dir = _find_e2e_dir()
    if not e2e_dir.is_dir():
        console.print(f"[red]ERROR[/red] e2e/ directory not found at {e2e_dir}")
        raise typer.Exit(1)

    cmd = ["npx", "playwright", "test", "tests/smoke/all-menus.spec.ts", "--project", "desktop"]

    extra_env: dict[str, str] = {"ODOO_E2E_SCREENSHOTS": "on", "ODOO_E2E_SCREENSHOT_DIR": output}
    if module:
        extra_env["ODOO_E2E_MODULE"] = module

    env = _build_env(ctx, extra_env)

    target = f" for module={module}" if module else ""
    console.print(f"[blue]INFO[/blue] Capturing screenshots{target}...")

    try:
        proc = subprocess.run(cmd, cwd=e2e_dir, env=env, check=False)
        if proc.returncode == 0:
            out_dir = e2e_dir / output
            if out_dir.is_dir():
                count = len(list(out_dir.rglob("*.png")))
                console.print(f"[green]OK[/green] {count} screenshot(s) in e2e/{output}/")
            else:
                console.print("[green]OK[/green] Screenshots captured")
        else:
            console.print("[red]FAIL[/red] Screenshot capture failed")
            raise typer.Exit(1)
    except FileNotFoundError:
        console.print("[red]ERROR[/red] npx not found.")
        raise typer.Exit(1) from None


@app.command()
def discover(
    ctx: typer.Context,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview without writing.")] = False,
) -> None:
    """Discover Odoo menus and generate page test registry.

    Connects to Odoo via JSON-RPC, reads ir.ui.menu records, and generates
    a TypeScript registry of all accessible menu paths for smoke testing.

    Examples:
      kctl-odoo e2e discover            # Generate registry
      kctl-odoo e2e discover --dry-run  # Preview only
    """
    actx: AppContext = ctx.obj
    client = actx.client

    console.print("[blue]INFO[/blue] Discovering Odoo menus from live instance...")

    # Fetch all menus with web_icon (top-level apps) and their children
    menus = client.search_read(
        "ir.ui.menu",
        domain=[],
        fields=["id", "name", "complete_name", "parent_id", "action", "web_icon"],
        limit=0,
    )

    if not menus:
        console.print("[yellow]WARN[/yellow] No menus found")
        raise typer.Exit(0)

    # Build menu tree
    top_level = [m for m in menus if not m.get("parent_id")]
    children = [m for m in menus if m.get("parent_id") and m.get("action")]

    console.print(f"  Found {len(top_level)} top-level apps, {len(children)} actionable menu items")

    if dry_run:
        from rich.table import Table

        table = Table(title="Odoo Menu Registry (dry run)", show_header=True, header_style="bold")
        table.add_column("ID", style="dim")
        table.add_column("Path")
        table.add_column("Action", style="cyan")

        for m in sorted(children, key=lambda x: x.get("complete_name", "")):
            action = str(m.get("action", ""))
            table.add_row(str(m["id"]), m.get("complete_name", ""), action)

        console.print(table)
        console.print(f"\n  Total: {len(children)} actionable menus")
        return

    # Write the registry file
    e2e_dir = _find_e2e_dir()
    registry_file = e2e_dir / "odoo-menu-registry.json"

    import json

    registry = {
        "generated": True,
        "topLevelApps": [{"id": m["id"], "name": m["name"], "webIcon": m.get("web_icon", "")} for m in top_level],
        "menuItems": [
            {
                "id": m["id"],
                "name": m["name"],
                "path": m.get("complete_name", ""),
                "parentId": m["parent_id"][0] if isinstance(m.get("parent_id"), list) else m.get("parent_id"),
                "action": str(m.get("action", "")),
            }
            for m in children
        ],
    }

    registry_file.write_text(json.dumps(registry, indent=2) + "\n")
    console.print(f"[green]OK[/green] Menu registry written to e2e/odoo-menu-registry.json ({len(children)} items)")
