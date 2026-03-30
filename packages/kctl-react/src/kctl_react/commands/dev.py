"""Dev server management commands."""

from __future__ import annotations

import signal
import subprocess
from typing import Annotated

import typer

from kctl_react.core.callbacks import AppContext

app = typer.Typer(help="Dev server management.")


@app.command()
def start(
    ctx: typer.Context,
    app_name: Annotated[str | None, typer.Argument(help="App name (omit for all apps)")] = None,
) -> None:
    """Start dev server(s) via Turbo.

    Examples:
      kctl-react dev start sfa     # Start SFA only
      kctl-react dev start         # Start all apps
    """
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    if app_name:
        actx.validate_app(app_name)
        info = actx.apps[app_name]
        out.info(f"Starting {app_name} on port {info['port']}...")
        cmd = ["pnpm", "turbo", "run", "dev", "--filter", f"@kodemeio/{app_name}"]
    else:
        out.info("Starting all apps...")
        cmd = ["pnpm", "turbo", "run", "dev"]

    try:
        proc = subprocess.Popen(cmd, cwd=root)
        proc.wait()
    except KeyboardInterrupt:
        out.info("Stopping dev server(s)...")
        proc.send_signal(signal.SIGINT)
        proc.wait()


@app.command()
def logs(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name")],
) -> None:
    """Show build output / dev logs for an app (re-runs dev with output)."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    actx.validate_app(app_name)
    info = actx.apps[app_name]
    out.info(f"Tailing dev output for {app_name} (port {info['port']})...")

    try:
        proc = subprocess.Popen(
            ["pnpm", "turbo", "run", "dev", "--filter", f"@kodemeio/{app_name}"],
            cwd=root,
        )
        proc.wait()
    except KeyboardInterrupt:
        proc.send_signal(signal.SIGINT)
        proc.wait()


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List available apps and their dev ports."""
    actx: AppContext = ctx.obj
    out = actx.output

    rows: list[list[str]] = []
    for name in actx.app_names:
        info = actx.apps[name]
        rows.append(
            [
                name,
                str(info["port"]),
                f"pnpm dev:{name}",
                f"http://localhost:{info['port']}",
            ]
        )

    out.table(
        "Dev Servers",
        [("App", "cyan"), ("Port", "green"), ("Command", "dim"), ("URL", "")],
        rows,
    )
