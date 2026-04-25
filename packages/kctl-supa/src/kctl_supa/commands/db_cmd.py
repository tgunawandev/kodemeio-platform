"""Database operation commands for kctl-supa.

Database operations via psql.
"""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_supa.core.callbacks import AppContext
from kctl_supa.core.docker import DockerOps
from kctl_supa.core.exceptions import DockerError

app = typer.Typer(help="Database operations.")


def _get_docker(actx: AppContext) -> DockerOps:
    return DockerOps(actx.config)


def _run_psql(actx: AppContext, query: str) -> str:
    out = actx.output
    try:
        docker = _get_docker(actx)
        result = docker.psql(query)
        docker.close()
        return result
    except DockerError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc


@app.command()
def size(ctx: typer.Context) -> None:
    """Show database and schema sizes."""
    actx: AppContext = ctx.obj
    result = _run_psql(actx, "SELECT pg_size_pretty(pg_database_size(current_database()))")
    typer.echo(result)


@app.command()
def tables(ctx: typer.Context) -> None:
    """List tables with row counts."""
    actx: AppContext = ctx.obj
    result = _run_psql(
        actx,
        "SELECT schemaname, tablename, n_live_tup FROM pg_stat_user_tables ORDER BY n_live_tup DESC",
    )
    typer.echo(result)


@app.command()
def extensions(ctx: typer.Context) -> None:
    """List installed extensions."""
    actx: AppContext = ctx.obj
    result = _run_psql(actx, "SELECT * FROM pg_extension")
    typer.echo(result)


@app.command()
def query(
    ctx: typer.Context,
    sql: Annotated[str, typer.Argument(help="SQL query to execute")],
) -> None:
    """Run arbitrary SQL."""
    actx: AppContext = ctx.obj
    result = _run_psql(actx, sql)
    typer.echo(result)


@app.command()
def schemas(ctx: typer.Context) -> None:
    """List schemas."""
    actx: AppContext = ctx.obj
    result = _run_psql(actx, "SELECT schema_name FROM information_schema.schemata")
    typer.echo(result)


@app.command()
def connections(ctx: typer.Context) -> None:
    """Show pg_stat_activity."""
    actx: AppContext = ctx.obj
    result = _run_psql(
        actx,
        "SELECT pid, usename, application_name, client_addr, state, query_start, query "
        "FROM pg_stat_activity ORDER BY query_start DESC NULLS LAST",
    )
    typer.echo(result)
