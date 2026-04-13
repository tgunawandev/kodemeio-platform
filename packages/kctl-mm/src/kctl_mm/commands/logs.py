from __future__ import annotations

from typing import Annotated

import typer

from kctl_mm.core.callbacks import AppContext

app = typer.Typer(help="Tail Mattermost service logs.", invoke_without_command=True)


@app.callback(invoke_without_command=True)
def run(
    ctx: typer.Context,
    service: Annotated[str, typer.Argument()] = "mattermost",
    lines: Annotated[int, typer.Option("--lines", "-n")] = 100,
) -> None:
    """Tail logs for a Mattermost service."""
    c: AppContext = ctx.ensure_object(AppContext)
    r = c.mm_exec.docker_compose(["logs", "--tail", str(lines), service])
    typer.echo(r.stdout)
