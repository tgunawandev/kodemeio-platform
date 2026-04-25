"""Performance monitoring commands for kctl-supa."""

from __future__ import annotations

from typing import Annotated

import typer
from rich import print as rprint
from rich.table import Table

from kctl_supa.core.callbacks import AppContext
from kctl_supa.core.docker import DockerOps
from kctl_supa.core.exceptions import DockerError

app = typer.Typer(help="Performance monitoring.")


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
def overview(ctx: typer.Context) -> None:
    """Quick metrics overview: connections, cache hit ratio, commit/rollback rates."""
    actx: AppContext = ctx.obj
    queries = {
        "Active connections": ("SELECT count(*) FROM pg_stat_activity WHERE state = 'active'"),
        "Total connections": ("SELECT count(*) FROM pg_stat_activity"),
        "Cache hit ratio": (
            "SELECT round(100.0 * sum(blks_hit) / nullif(sum(blks_hit) + sum(blks_read), 0), 2) AS cache_hit_pct "
            "FROM pg_stat_database"
        ),
        "Commits": ("SELECT sum(xact_commit) AS total_commits FROM pg_stat_database"),
        "Rollbacks": ("SELECT sum(xact_rollback) AS total_rollbacks FROM pg_stat_database"),
    }

    table = Table(title="DB Overview", show_header=True, header_style="bold cyan")
    table.add_column("Metric", style="cyan")
    table.add_column("Value")

    docker = _get_docker(actx)
    for label, query in queries.items():
        try:
            result = docker.psql(query)
            lines = [line.strip() for line in result.splitlines() if line.strip()]
            value = lines[-1] if lines else "N/A"
        except DockerError:
            value = "error"
        table.add_row(label, value)
    docker.close()

    rprint(table)


@app.command()
def connections(ctx: typer.Context) -> None:
    """Detailed connection breakdown by state."""
    actx: AppContext = ctx.obj

    result = _run_psql(
        actx,
        "SELECT state, count(*) AS count FROM pg_stat_activity GROUP BY state ORDER BY count DESC",
    )
    typer.echo(result)


@app.command()
def disk(ctx: typer.Context) -> None:
    """Database and top table sizes."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info("Database size:")
    db_size = _run_psql(
        actx,
        "SELECT pg_size_pretty(pg_database_size(current_database())) AS db_size",
    )
    typer.echo(db_size)

    out.info("Top tables by size:")
    table_sizes = _run_psql(
        actx,
        "SELECT schemaname, tablename, "
        "pg_size_pretty(pg_total_relation_size(schemaname || '.' || tablename)) AS total_size, "
        "pg_size_pretty(pg_relation_size(schemaname || '.' || tablename)) AS table_size "
        "FROM information_schema.tables "
        "WHERE table_schema NOT IN ('pg_catalog', 'information_schema') "
        "ORDER BY pg_total_relation_size(schemaname || '.' || tablename) DESC LIMIT 20",
    )
    typer.echo(table_sizes)


@app.command("slow-queries")
def slow_queries(
    ctx: typer.Context,
    threshold: Annotated[
        int,
        typer.Option("--threshold", "-t", help="Minimum query duration in seconds"),
    ] = 5,
) -> None:
    """Show long-running queries exceeding threshold seconds."""
    actx: AppContext = ctx.obj

    result = _run_psql(
        actx,
        f"SELECT pid, now()-query_start AS duration, state, left(query, 120) AS query "
        f"FROM pg_stat_activity "
        f"WHERE state='active' AND query_start < now()-interval '{threshold} seconds' "
        f"ORDER BY duration DESC",
    )
    typer.echo(result)
