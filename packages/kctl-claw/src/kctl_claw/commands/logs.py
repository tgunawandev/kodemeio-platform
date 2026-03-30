"""Log management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_claw.core.callbacks import AppContext
from kctl_claw.core.exceptions import DockerError

app = typer.Typer(help="View OpenClaw gateway logs.")


@app.command()
def tail(
    ctx: typer.Context,
    lines: Annotated[int, typer.Option("--lines", "-n", help="Number of log lines to show")] = 100,
    follow: Annotated[bool, typer.Option("--follow", "-f", help="Follow log output")] = False,
) -> None:
    """Tail gateway logs."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        actx.docker.logs(tail=lines, follow=follow)
    except DockerError as e:
        out.error(f"Docker error: {e}")
        out.info("Is the gateway running? Check with: kctl-claw deploy status")
        raise typer.Exit(1) from e


@app.command()
def search(
    ctx: typer.Context,
    pattern: Annotated[str, typer.Argument(help="Search pattern")],
    lines: Annotated[int, typer.Option("--lines", "-n", help="Lines to search through")] = 500,
) -> None:
    """Search logs for a pattern."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        result = actx.docker.logs_grep(pattern, tail=lines)
        if result:
            typer.echo(result)
        else:
            out.info(f"No log lines matching: {pattern!r}")
    except DockerError as e:
        out.error(f"Docker error: {e}")
        raise typer.Exit(1) from e


@app.command()
def errors(
    ctx: typer.Context,
    lines: Annotated[int, typer.Option("--lines", "-n", help="Lines to search through")] = 500,
) -> None:
    """Show recent error-level log lines."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        result = actx.docker.logs_grep("ERROR", tail=lines)
        if result:
            typer.echo(result)
        else:
            out.info("No ERROR lines found in recent logs.")
    except DockerError as e:
        out.error(f"Docker error: {e}")
        raise typer.Exit(1) from e
