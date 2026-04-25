"""Database maintenance commands for kctl-supa.

Database maintenance operations.
"""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_supa.core.callbacks import AppContext
from kctl_supa.core.docker import DockerOps
from kctl_supa.core.exceptions import DockerError

app = typer.Typer(help="Database maintenance operations.")


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
def vacuum(
    ctx: typer.Context,
    full: Annotated[bool, typer.Option("--full", help="Run VACUUM FULL")] = False,
) -> None:
    """Run VACUUM or VACUUM FULL."""
    actx: AppContext = ctx.obj
    out = actx.output

    query = "VACUUM FULL" if full else "VACUUM"
    out.info(f"Running {query}...")
    result = _run_psql(actx, query)
    typer.echo(result)
    out.success(f"{query} complete")


@app.command()
def reindex(ctx: typer.Context) -> None:
    """Run REINDEX DATABASE."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info("Running REINDEX DATABASE...")
    result = _run_psql(actx, "REINDEX DATABASE postgres")
    typer.echo(result)
    out.success("REINDEX complete")


@app.command()
def analyze(ctx: typer.Context) -> None:
    """Run ANALYZE."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info("Running ANALYZE...")
    result = _run_psql(actx, "ANALYZE")
    typer.echo(result)
    out.success("ANALYZE complete")


@app.command("pool-stats")
def pool_stats(ctx: typer.Context) -> None:
    """Show Supavisor connection pool stats."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        docker = _get_docker(actx)
        result = docker.docker_exec("pooler", "cat /proc/1/status 2>/dev/null || supavisor stats 2>/dev/null || echo 'pool stats not available'")
        docker.close()
    except DockerError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc

    typer.echo(result)


@app.command()
def connections(ctx: typer.Context) -> None:
    """Detailed pg_stat_activity breakdown."""
    actx: AppContext = ctx.obj
    result = _run_psql(
        actx,
        "SELECT state, count(*) as count, max(now() - query_start) as max_duration "
        "FROM pg_stat_activity GROUP BY state ORDER BY count DESC",
    )
    typer.echo(result)


@app.command("kill-idle")
def kill_idle(ctx: typer.Context) -> None:
    """Terminate idle-in-transaction connections."""
    actx: AppContext = ctx.obj
    out = actx.output

    if not typer.confirm("Terminate all idle-in-transaction connections?"):
        raise typer.Exit(0)

    out.info("Terminating idle-in-transaction connections...")
    result = _run_psql(
        actx,
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state='idle in transaction'",
    )
    typer.echo(result)
    out.success("Done")
