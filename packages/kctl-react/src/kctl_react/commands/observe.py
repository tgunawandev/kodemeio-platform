"""Error tracking and observability."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_react.core.callbacks import AppContext

app = typer.Typer(help="Error tracking and observability.")


@app.command()
def sentry(ctx: typer.Context, app_name: Annotated[str | None, typer.Argument(help="App name")] = None) -> None:
    """Show recent Sentry issues."""
    actx: AppContext = ctx.obj
    out = actx.output
    out.info("Sentry integration — requires SENTRY_AUTH_TOKEN and SENTRY_ORG in env")
    out.info("Configure via: kctl-react config set sentry_org kodemeio")


@app.command()
def errors(ctx: typer.Context, app_name: Annotated[str | None, typer.Argument(help="App name")] = None) -> None:
    """Show error trends."""
    ctx.invoke(sentry, app_name=app_name)


@app.command()
def uptime(ctx: typer.Context, app_name: Annotated[str | None, typer.Argument(help="App name")] = None) -> None:
    """Show Gatus uptime status."""
    actx: AppContext = ctx.obj
    out = actx.output
    out.info("Gatus integration — check https://status.kodeme.io")
