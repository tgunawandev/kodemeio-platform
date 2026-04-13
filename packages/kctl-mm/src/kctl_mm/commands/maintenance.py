from __future__ import annotations

import typer

from kctl_mm.core.callbacks import AppContext

app = typer.Typer(help="Server maintenance commands.", no_args_is_help=True)


def _c(ctx: typer.Context) -> AppContext:
    return ctx.ensure_object(AppContext)


@app.command("cleanup")
def cleanup_cmd(ctx: typer.Context) -> None:
    c = _c(ctx)
    c.client.recycle_database()
    typer.echo("Database recycled")


@app.command("optimize")
def optimize_cmd(ctx: typer.Context) -> None:
    """Alias for cleanup — Mattermost has no separate optimize endpoint."""
    c = _c(ctx)
    c.client.recycle_database()
    typer.echo("Database recycled")


@app.command("reset-caches")
def reset_caches_cmd(ctx: typer.Context) -> None:
    c = _c(ctx)
    c.client.invalidate_caches()
    typer.echo("Caches invalidated")


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
