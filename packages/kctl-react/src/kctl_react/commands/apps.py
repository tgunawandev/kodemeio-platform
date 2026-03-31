"""App inventory and health check commands."""

from __future__ import annotations

import subprocess
import time
from typing import Annotated

import httpx
import typer

from kctl_react import __version__
from kctl_react.commands.clean import run_clean
from kctl_react.commands.dashboard import _display_dashboard, _fetch_dashboard
from kctl_react.commands.doctor import run_doctor
from kctl_react.core.callbacks import AppContext
from kctl_react.core.discovery import get_app_dir
from kctl_react.core.config import resolve_active_profile_name

app = typer.Typer(help="App inventory, status, and health checks.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all apps with ports and package names."""
    actx: AppContext = ctx.obj
    out = actx.output

    rows: list[list[str]] = []
    json_data: list[dict] = []

    for app_name, info in actx.apps.items():
        app_dir = actx.get_app_dir(app_name)
        exists = app_dir.is_dir()
        status = "[green]OK[/green]" if exists else "[red]missing[/red]"

        rows.append(
            [
                app_name,
                info["name"],
                str(info["port"]),
                info["package"],
                status,
            ]
        )
        json_data.append(
            {
                "app": app_name,
                "name": info["name"],
                "port": info["port"],
                "package": info["package"],
                "exists": exists,
            }
        )

    out.table(
        "Apps",
        [("App", "cyan"), ("Description", ""), ("Port", "green"), ("Package", "dim"), ("Status", "")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def ports(ctx: typer.Context) -> None:
    """Show port assignments for all apps."""
    actx: AppContext = ctx.obj
    out = actx.output

    rows: list[list[str]] = []
    for app_name, info in actx.apps.items():
        rows.append([app_name, str(info["port"]), f"http://localhost:{info['port']}"])

    out.table(
        "Port Assignments",
        [("App", "cyan"), ("Port", "green"), ("URL", "dim")],
        rows,
    )


@app.command()
def status(
    ctx: typer.Context,
    app_name: Annotated[str | None, typer.Argument(help="App name (optional, checks all if omitted)")] = None,
) -> None:
    """Check status of app(s): directory exists, package.json, env file, dist."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    apps_to_check = [app_name] if app_name else actx.app_names
    if app_name:
        actx.validate_app(app_name)

    rows: list[list[str]] = []
    json_data: list[dict] = []

    for name in apps_to_check:
        info = actx.apps[name]
        app_dir = get_app_dir(root, name)

        has_dir = app_dir.is_dir()
        has_pkg = (app_dir / "package.json").exists()
        has_src = (app_dir / "src").is_dir()
        has_dist = (app_dir / "dist").is_dir() or (app_dir / ".next").is_dir()
        has_env = (app_dir / ".env").exists() or (app_dir / ".env.local").exists()
        has_tests = (
            (
                (app_dir / "src" / "__tests__").is_dir()
                or any((app_dir / "src").rglob("*.test.ts"))
                or any((app_dir / "src").rglob("*.test.tsx"))
            )
            if has_src
            else False
        )

        def icon(ok: bool) -> str:
            return "[green]OK[/green]" if ok else "[red]--[/red]"

        rows.append(
            [
                name,
                str(info["port"]),
                icon(has_dir),
                icon(has_pkg),
                icon(has_src),
                icon(has_dist),
                icon(has_env),
                icon(has_tests),
            ]
        )
        json_data.append(
            {
                "app": name,
                "port": info["port"],
                "directory": has_dir,
                "package_json": has_pkg,
                "src": has_src,
                "dist": has_dist,
                "env": has_env,
                "tests": has_tests,
            }
        )

    out.table(
        "App Status",
        [
            ("App", "cyan"),
            ("Port", "green"),
            ("Dir", ""),
            ("Pkg", ""),
            ("Src", ""),
            ("Dist", ""),
            ("Env", ""),
            ("Tests", ""),
        ],
        rows,
        data_for_json=json_data,
    )


def _check_health(actx: AppContext, app_name: str | None) -> tuple[list[list[str]], list[dict], int, int]:
    """Run health checks and return (rows, json_data, healthy, total)."""
    apps_to_check = [app_name] if app_name else actx.app_names

    rows: list[list[str]] = []
    json_data: list[dict] = []
    healthy = 0
    total = 0

    for name in apps_to_check:
        info = actx.apps[name]
        port = info["port"]
        url = f"http://localhost:{port}"
        total += 1

        try:
            r = httpx.get(url, timeout=3, follow_redirects=True)
            is_up = r.status_code < 500
            status = f"[green]{r.status_code}[/green]" if is_up else f"[red]{r.status_code}[/red]"
            if is_up:
                healthy += 1
        except (httpx.HTTPError, Exception):
            is_up = False
            status = "[red]offline[/red]"

        rows.append([name, str(port), status])
        json_data.append({"app": name, "port": port, "healthy": is_up})

    return rows, json_data, healthy, total


@app.command()
def health(
    ctx: typer.Context,
    app_name: Annotated[str | None, typer.Argument(help="App name (optional, checks all if omitted)")] = None,
    watch: Annotated[bool, typer.Option("--watch", "-w", help="Continuously monitor.")] = False,
    interval: Annotated[int, typer.Option("--interval", "-i", help="Refresh interval in seconds.")] = 5,
) -> None:
    """Check health of running dev servers."""
    actx: AppContext = ctx.obj
    out = actx.output

    if app_name:
        actx.validate_app(app_name)

    if watch:
        try:
            while True:
                rows, json_data, healthy, total = _check_health(actx, app_name)
                out.console.clear()
                out.table(
                    "Dev Server Health",
                    [("App", "cyan"), ("Port", "green"), ("Status", "")],
                    rows,
                    data_for_json=json_data,
                )
                out.text(f"\n  {healthy}/{total} healthy — refreshing every {interval}s (Ctrl+C to stop)")
                time.sleep(interval)
        except KeyboardInterrupt:
            out.info("Stopped watching.")
        return

    rows, json_data, healthy, total = _check_health(actx, app_name)

    out.table(
        "Dev Server Health",
        [("App", "cyan"), ("Port", "green"), ("Status", "")],
        rows,
        data_for_json=json_data,
    )

    if healthy == total:
        out.success(f"All {total} apps healthy")
    elif healthy > 0:
        out.warn(f"{healthy}/{total} apps healthy")
    else:
        out.info(f"No apps running (checked {total})")


@app.command()
def info(ctx: typer.Context) -> None:
    """Show quick project info: version, root, profile, node/pnpm versions."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    def _cmd_version(cmd: str) -> str:
        try:
            r = subprocess.run([cmd, "--version"], capture_output=True, text=True, timeout=5)
            return r.stdout.strip().split("\n")[0]
        except Exception:
            return "not found"

    node_ver = _cmd_version("node")
    pnpm_ver = _cmd_version("pnpm")

    git_branch = ""
    try:
        r = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        git_branch = r.stdout.strip()
    except Exception:
        pass

    profile = resolve_active_profile_name(actx.profile)
    apps_count = sum(1 for a in actx.app_names if (get_app_dir(root, a)).is_dir())

    sections: list[tuple[str, list[tuple[str, str]]]] = [
        (
            "kctl-react",
            [
                ("Version", __version__),
                ("Profile", profile),
                ("Project root", str(root)),
                ("Git branch", git_branch or "[dim]unknown[/dim]"),
                ("Node", node_ver),
                ("pnpm", pnpm_ver),
                ("Apps", f"{apps_count}/{len(actx.app_names)}"),
            ],
        ),
    ]

    out.detail(
        "Info",
        sections,
        data_for_json={
            "version": __version__,
            "profile": profile,
            "root": str(root),
            "git_branch": git_branch,
            "node": node_ver,
            "pnpm": pnpm_ver,
            "apps": apps_count,
        },
    )


@app.command()
def dashboard(
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


@app.command()
def doctor(ctx: typer.Context) -> None:
    """Run comprehensive monorepo health checks.

    Checks: node, pnpm, turbo, git, docker, all apps, packages, env files,
    codegen config, and dependency installation.
    """
    actx: AppContext = ctx.obj
    run_doctor(actx)


@app.command()
def clean(
    ctx: typer.Context,
    app_name: Annotated[str | None, typer.Argument(help="App name (omit for all)")] = None,
    all_: Annotated[bool, typer.Option("--all", "-a", help="Also remove node_modules.")] = False,
) -> None:
    """Clean dist, .turbo, and coverage directories.

    Examples:
      kctl-react apps clean             # Clean all apps
      kctl-react apps clean sfa         # Clean SFA only
      kctl-react apps clean --all       # Clean + remove node_modules
    """
    actx: AppContext = ctx.obj
    run_clean(actx, app_name=app_name, all_=all_)
