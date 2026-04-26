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
        "SELECT schemaname, relname AS table, n_live_tup FROM pg_stat_user_tables ORDER BY n_live_tup DESC",
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


@app.command(name="functions")
def pg_functions(ctx: typer.Context) -> None:
    """List PostgreSQL functions."""
    actx: AppContext = ctx.obj
    result = _run_psql(
        actx,
        "SELECT n.nspname AS schema, p.proname AS name, "
        "pg_get_function_result(p.oid) AS return_type, "
        "pg_get_function_arguments(p.oid) AS arguments "
        "FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
        "WHERE n.nspname NOT IN ('pg_catalog', 'information_schema') "
        "ORDER BY n.nspname, p.proname",
    )
    typer.echo(result)


@app.command()
def triggers(ctx: typer.Context) -> None:
    """List triggers."""
    actx: AppContext = ctx.obj
    result = _run_psql(
        actx,
        "SELECT trigger_schema, trigger_name, event_manipulation, "
        "event_object_schema, event_object_table, action_timing "
        "FROM information_schema.triggers "
        "ORDER BY trigger_schema, event_object_table, trigger_name",
    )
    typer.echo(result)


@app.command()
def enums(ctx: typer.Context) -> None:
    """List enum types and their values."""
    actx: AppContext = ctx.obj
    result = _run_psql(
        actx,
        "SELECT n.nspname AS schema, t.typname AS name, "
        "string_agg(e.enumlabel, ', ' ORDER BY e.enumsortorder) AS values "
        "FROM pg_type t JOIN pg_enum e ON t.oid = e.enumtypid "
        "JOIN pg_namespace n ON n.oid = t.typnamespace "
        "GROUP BY n.nspname, t.typname ORDER BY n.nspname, t.typname",
    )
    typer.echo(result)


@app.command()
def indexes(
    ctx: typer.Context,
    schema: Annotated[str, typer.Option("--schema", "-s", help="Filter by schema")] = "public",
) -> None:
    """List indexes."""
    actx: AppContext = ctx.obj
    result = _run_psql(
        actx,
        f"SELECT schemaname, relname AS table, indexrelname AS index, "
        f"pg_size_pretty(pg_relation_size(indexrelid)) AS size "
        f"FROM pg_stat_user_indexes "
        f"WHERE schemaname = '{schema}' "
        f"ORDER BY pg_relation_size(indexrelid) DESC",
    )
    typer.echo(result)


@app.command()
def columns(
    ctx: typer.Context,
    table: Annotated[str, typer.Argument(help="Table name (schema.table or just table)")],
) -> None:
    """List columns for a table."""
    actx: AppContext = ctx.obj
    parts = table.split(".", 1)
    schema = parts[0] if len(parts) == 2 else "public"
    tbl = parts[1] if len(parts) == 2 else parts[0]
    result = _run_psql(
        actx,
        f"SELECT column_name, data_type, is_nullable, column_default "
        f"FROM information_schema.columns "
        f"WHERE table_schema = '{schema}' AND table_name = '{tbl}' "
        f"ORDER BY ordinal_position",
    )
    typer.echo(result)


@app.command()
def roles(ctx: typer.Context) -> None:
    """List database roles."""
    actx: AppContext = ctx.obj
    result = _run_psql(
        actx,
        "SELECT rolname, rolsuper, rolcreaterole, rolcreatedb, rolcanlogin, rolreplication "
        "FROM pg_roles ORDER BY rolname",
    )
    typer.echo(result)


@app.command(name="publications")
def db_publications(ctx: typer.Context) -> None:
    """List publications (used by Realtime)."""
    actx: AppContext = ctx.obj
    result = _run_psql(
        actx,
        "SELECT pubname, puballtables, pubinsert, pubupdate, pubdelete FROM pg_publication ORDER BY pubname",
    )
    typer.echo(result)


@app.command()
def wrappers(ctx: typer.Context) -> None:
    """List foreign data wrappers."""
    actx: AppContext = ctx.obj
    result = _run_psql(
        actx,
        "SELECT fdw.fdwname AS wrapper, srv.srvname AS server, "
        "um.usename AS owner "
        "FROM pg_foreign_data_wrapper fdw "
        "LEFT JOIN pg_foreign_server srv ON srv.srvfdw = fdw.oid "
        "LEFT JOIN (SELECT umserver, pg_get_userbyid(umuser) AS usename "
        "FROM pg_user_mapping) um ON um.umserver = srv.oid "
        "ORDER BY fdw.fdwname",
    )
    typer.echo(result)


@app.command()
def webhooks(ctx: typer.Context) -> None:
    """List database webhooks (pg_net requests)."""
    actx: AppContext = ctx.obj
    out = actx.output
    check = _run_psql(actx, "SELECT 1 FROM pg_extension WHERE extname = 'pg_net'")
    if "1" not in check:
        out.warn("pg_net not installed. Enable it: CREATE EXTENSION pg_net;")
        return
    result = _run_psql(
        actx,
        "SELECT id, status_code, content_type, timed_out, error_msg, created FROM net._http_response ORDER BY created DESC LIMIT 50",
    )
    typer.echo(result)
