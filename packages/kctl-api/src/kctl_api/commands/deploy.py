"""Deployment management commands for kctl-api.

Status, logs, restart, and rollback via Dokploy API (stubs).
"""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_api.core.callbacks import AppContext

app = typer.Typer(name="deploy", help="Deployment management — status, logs, restart, rollback.", no_args_is_help=True)


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------
@app.command()
def status(
    ctx: typer.Context,
    app_name: Annotated[str | None, typer.Argument(help="App name (all if omitted).")] = None,
) -> None:
    """Show deployment status (will use Dokploy API)."""
    actx: AppContext = ctx.obj
    out = actx.output
    out.info(f"Not yet implemented. Will query Dokploy API for: {app_name or 'all apps'}")


# ---------------------------------------------------------------------------
# logs
# ---------------------------------------------------------------------------
@app.command()
def logs(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name.")],
    tail: Annotated[int, typer.Option("--tail", "-n", help="Number of lines.")] = 100,
) -> None:
    """View deployment logs (will use Dokploy API)."""
    actx: AppContext = ctx.obj
    out = actx.output
    out.info(f"Not yet implemented. Will fetch last {tail} log lines for: {app_name}")


# ---------------------------------------------------------------------------
# restart
# ---------------------------------------------------------------------------
@app.command()
def restart(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name to restart.")],
) -> None:
    """Restart a deployed app (will use Dokploy API)."""
    actx: AppContext = ctx.obj
    out = actx.output
    out.info(f"Not yet implemented. Will restart deployment: {app_name}")


# ---------------------------------------------------------------------------
# rollback
# ---------------------------------------------------------------------------
@app.command()
def rollback(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name to rollback.")],
    revision: Annotated[str | None, typer.Option("--revision", "-r", help="Target revision.")] = None,
) -> None:
    """Rollback a deployment to a previous revision (will use Dokploy API)."""
    actx: AppContext = ctx.obj
    out = actx.output
    rev_msg = f" to revision {revision}" if revision else " to previous revision"
    out.info(f"Not yet implemented. Will rollback {app_name}{rev_msg}")


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------
@app.command(name="list")
def list_deployments(ctx: typer.Context) -> None:
    """List all deployments (will use Dokploy API)."""
    actx: AppContext = ctx.obj
    out = actx.output
    out.info("Not yet implemented. Will list all Dokploy deployments.")
