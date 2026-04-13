from __future__ import annotations

import typer

from kctl_mm.core.callbacks import AppContext

app = typer.Typer(help="Server maintenance commands.", no_args_is_help=True)


def _c(ctx: typer.Context) -> AppContext:
    return ctx.ensure_object(AppContext)


@app.command("cleanup")
def cleanup_cmd(ctx: typer.Context) -> None:
    c = _c(ctx)
    r = c.mm_exec.mmctl(["maintenance", "cleanup"])
    typer.echo(r.stdout)


@app.command("optimize")
def optimize_cmd(ctx: typer.Context) -> None:
    c = _c(ctx)
    r = c.mm_exec.mmctl(["maintenance", "optimize"])
    typer.echo(r.stdout)


@app.command("reset-caches")
def reset_caches_cmd(ctx: typer.Context) -> None:
    c = _c(ctx)
    r = c.mm_exec.mmctl(["maintenance", "reset-caches"])
    typer.echo(r.stdout)


@app.command("vacuum")
def vacuum_cmd(ctx: typer.Context) -> None:
    c = _c(ctx)
    r = c.mm_exec.docker_compose(
        [
            "exec",
            "-T",
            "mm-postgres",
            "psql",
            "-U",
            "mattermost",
            "-d",
            "mattermost",
            "-c",
            "VACUUM ANALYZE;",
        ]
    )
    typer.echo(r.stdout)
