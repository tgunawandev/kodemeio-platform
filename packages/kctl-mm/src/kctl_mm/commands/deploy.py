from __future__ import annotations

import typer

from kctl_mm.core.callbacks import AppContext

app = typer.Typer(help="Deploy lifecycle operations.", no_args_is_help=True)


def _mm(ctx: typer.Context):
    return ctx.ensure_object(AppContext).mm_exec


@app.command("up")
def up_cmd(ctx: typer.Context) -> None:
    _mm(ctx).docker_compose(["up", "-d"])


@app.command("down")
def down_cmd(ctx: typer.Context) -> None:
    _mm(ctx).docker_compose(["down"])


@app.command("restart")
def restart_cmd(ctx: typer.Context) -> None:
    _mm(ctx).docker_compose(["restart"])


@app.command("rebuild")
def rebuild_cmd(ctx: typer.Context) -> None:
    _mm(ctx).docker_compose(["up", "-d", "--build"])


@app.command("pull")
def pull_cmd(ctx: typer.Context) -> None:
    _mm(ctx).docker_compose(["pull"])
