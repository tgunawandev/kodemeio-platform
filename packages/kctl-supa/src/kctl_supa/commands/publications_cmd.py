"""Realtime publication management commands for kctl-supa."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_supa.core.callbacks import AppContext
from kctl_supa.core.docker import DockerOps
from kctl_supa.core.exceptions import DockerError

app = typer.Typer(help="Manage Realtime publications.")


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


@app.command(name="list")
def list_publications(ctx: typer.Context) -> None:
    """List all publications."""
    actx: AppContext = ctx.obj
    result = _run_psql(
        actx,
        "SELECT pubname, puballtables, pubinsert, pubupdate, pubdelete, pubtruncate "
        "FROM pg_publication ORDER BY pubname",
    )
    typer.echo(result)


@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Publication name")],
    all_tables: Annotated[bool, typer.Option("--all-tables", help="Publish all tables")] = False,
) -> None:
    """Create a new publication."""
    actx: AppContext = ctx.obj
    out = actx.output
    suffix = "FOR ALL TABLES" if all_tables else ""
    _run_psql(actx, f"CREATE PUBLICATION {name} {suffix}")
    out.success(f"Publication '{name}' created")


@app.command()
def drop(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Publication name to drop")],
) -> None:
    """Drop a publication."""
    actx: AppContext = ctx.obj
    out = actx.output

    if not typer.confirm(f"Drop publication '{name}'?"):
        raise typer.Exit(0)

    _run_psql(actx, f"DROP PUBLICATION IF EXISTS {name}")
    out.success(f"Publication '{name}' dropped")


@app.command()
def tables(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Publication name")],
) -> None:
    """List tables in a publication."""
    actx: AppContext = ctx.obj
    result = _run_psql(
        actx,
        f"SELECT schemaname, tablename "
        f"FROM pg_publication_tables WHERE pubname = '{name}' "
        f"ORDER BY schemaname, tablename",
    )
    typer.echo(result)


@app.command("add-table")
def add_table(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Publication name")],
    table: Annotated[str, typer.Argument(help="Table to add (schema.table)")],
) -> None:
    """Add a table to a publication."""
    actx: AppContext = ctx.obj
    out = actx.output
    _run_psql(actx, f"ALTER PUBLICATION {name} ADD TABLE {table}")
    out.success(f"Table '{table}' added to publication '{name}'")


@app.command("remove-table")
def remove_table(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Publication name")],
    table: Annotated[str, typer.Argument(help="Table to remove (schema.table)")],
) -> None:
    """Remove a table from a publication."""
    actx: AppContext = ctx.obj
    out = actx.output
    _run_psql(actx, f"ALTER PUBLICATION {name} DROP TABLE {table}")
    out.success(f"Table '{table}' removed from publication '{name}'")
