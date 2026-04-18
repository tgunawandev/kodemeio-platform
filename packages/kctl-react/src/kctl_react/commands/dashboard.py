"""Top-level dashboard command group."""

from __future__ import annotations

import subprocess
import time
from typing import Annotated

import httpx
import typer

from kctl_react.core.callbacks import AppContext
from kctl_react.core.discovery import get_app_dir

app = typer.Typer(help="Monorepo overview dashboard.")


def _fetch_dashboard(actx: AppContext) -> dict:
    """Collect all dashboard data."""
    root = actx.project_root

    apps_found = sum(1 for a in actx.app_names if (get_app_dir(root, a)).is_dir())
    pkgs_found = sum(1 for p in actx.packages if (root / "packages" / p / "package.json").exists())

    total_tests = 0
    for name in actx.app_names:
        src = get_app_dir(root, name) / "src"
        if src.is_dir():
            total_tests += len(list(src.rglob("*.test.ts"))) + len(list(src.rglob("*.test.tsx")))

    built_apps = sum(
        1
        for a in actx.app_names
        if (get_app_dir(root, a) / "dist").is_dir() or (get_app_dir(root, a) / ".next").is_dir()
    )

    running = 0
    app_running: dict[str, bool] = {}
    for name in actx.app_names:
        port = actx.apps[name]["port"]
        try:
            r = httpx.get(f"http://localhost:{port}", timeout=1, follow_redirects=True)
            is_up = r.status_code < 500
        except (httpx.HTTPError, Exception):
            is_up = False
        app_running[name] = is_up
        if is_up:
            running += 1

    has_node_modules = (root / "node_modules").is_dir()
    has_lockfile = (root / "pnpm-lock.yaml").exists()

    git_branch = ""
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        git_branch = result.stdout.strip()
    except Exception:
        pass

    return {
        "apps_total": len(actx.app_names),
        "apps_found": apps_found,
        "packages_total": len(actx.packages),
        "packages_found": pkgs_found,
        "test_files": total_tests,
        "built_apps": built_apps,
        "running_apps": running,
        "app_running": app_running,
        "has_node_modules": has_node_modules,
        "has_lockfile": has_lockfile,
        "git_branch": git_branch,
        "project_root": str(root),
    }


def _display_dashboard(actx: AppContext, data: dict) -> None:
    """Render dashboard output."""
    out = actx.output

    if out.json_mode:
        out.raw_json(data)
        return

    sections: list[tuple[str, list[tuple[str, str]]]] = []

    sections.append(
        (
            "Project",
            [
                ("Root", data["project_root"]),
                ("Git branch", data["git_branch"] or "[dim]unknown[/dim]"),
                ("Node modules", "[green]installed[/green]" if data["has_node_modules"] else "[red]missing[/red]"),
                ("Lock file", "[green]OK[/green]" if data["has_lockfile"] else "[red]missing[/red]"),
            ],
        )
    )

    sections.append(
        (
            "Resources",
            [
                ("Apps", f"{data['apps_found']}/{data['apps_total']}"),
                ("Shared packages", f"{data['packages_found']}/{data['packages_total']}"),
                ("Test files", str(data["test_files"])),
                ("Built apps", f"{data['built_apps']}/{data['apps_total']}"),
                ("Running dev servers", f"{data['running_apps']}/{data['apps_total']}"),
            ],
        )
    )

    app_running = data.get("app_running", {})
    app_kvs: list[tuple[str, str]] = []
    for name in actx.app_names:
        app_info = actx.apps[name]
        port = app_info["port"]
        is_running = app_running.get(name, False)

        app_dir = actx.get_app_dir(name)
        built = (app_dir / "dist").is_dir() or (app_dir / ".next").is_dir()
        status_parts = []
        if is_running:
            status_parts.append(f"[green]:{port}[/green]")
        if built:
            status_parts.append("[blue]built[/blue]")
        if not status_parts:
            status_parts.append("[dim]idle[/dim]")

        app_kvs.append((name, " ".join(status_parts)))

    sections.append(("Apps", app_kvs))

    root_name = data.get("project_root", "").rstrip("/").split("/")[-1]
    out.detail(f"{root_name} Dashboard", sections, data_for_json=data)


@app.command("show")
def show(
    ctx: typer.Context,
    watch: Annotated[bool, typer.Option("--watch", "-w", help="Continuously refresh.")] = False,
    interval: Annotated[int, typer.Option("--interval", "-i", help="Refresh interval in seconds.")] = 10,
) -> None:
    """Show monorepo overview dashboard."""
    actx: AppContext = ctx.obj

    if watch:
        try:
            while True:
                data = _fetch_dashboard(actx)
                actx.output.console.clear()
                _display_dashboard(actx, data)
                actx.output.text(f"\n[dim]Refreshing every {interval}s. Press Ctrl+C to stop.[/dim]")
                time.sleep(interval)
        except KeyboardInterrupt:
            actx.output.info("Stopped watching.")
    else:
        data = _fetch_dashboard(actx)
        _display_dashboard(actx, data)
