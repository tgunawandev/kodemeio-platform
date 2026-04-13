from __future__ import annotations

import typer

from kctl_mm.core.callbacks import AppContext

app = typer.Typer(help="Show Mattermost service status.", invoke_without_command=True)


@app.callback(invoke_without_command=True)
def run(ctx: typer.Context) -> None:
    c: AppContext = ctx.ensure_object(AppContext)
    r = c.mm_exec.docker_compose(["ps"])
    typer.echo(r.stdout)
