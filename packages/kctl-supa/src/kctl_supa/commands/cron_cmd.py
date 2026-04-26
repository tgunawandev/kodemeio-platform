"""pg_cron job management commands for kctl-supa."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_supa.core.callbacks import AppContext
from kctl_supa.core.docker import DockerOps
from kctl_supa.core.exceptions import DockerError

app = typer.Typer(help="Manage pg_cron scheduled jobs.")


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
def list_jobs(ctx: typer.Context) -> None:
    """List all cron jobs."""
    actx: AppContext = ctx.obj
    result = _run_psql(
        actx,
        "SELECT jobid, schedule, command, nodename, nodeport, database, username, active FROM cron.job ORDER BY jobid",
    )
    typer.echo(result)


@app.command()
def create(
    ctx: typer.Context,
    schedule: Annotated[str, typer.Argument(help="Cron schedule expression (e.g. '*/5 * * * *')")],
    command: Annotated[str, typer.Argument(help="SQL command to run")],
) -> None:
    """Create a new cron job."""
    actx: AppContext = ctx.obj
    out = actx.output
    result = _run_psql(
        actx,
        f"SELECT cron.schedule('{schedule}', $${command}$$)",
    )
    out.success("Cron job created")
    typer.echo(result)


@app.command()
def delete(
    ctx: typer.Context,
    job_id: Annotated[int, typer.Argument(help="Job ID to delete")],
) -> None:
    """Delete a cron job."""
    actx: AppContext = ctx.obj
    out = actx.output
    _run_psql(actx, f"SELECT cron.unschedule({job_id})")
    out.success(f"Cron job {job_id} deleted")


@app.command()
def enable(
    ctx: typer.Context,
    job_id: Annotated[int, typer.Argument(help="Job ID to enable")],
) -> None:
    """Enable a cron job."""
    actx: AppContext = ctx.obj
    out = actx.output
    _run_psql(actx, f"UPDATE cron.job SET active = true WHERE jobid = {job_id}")
    out.success(f"Cron job {job_id} enabled")


@app.command()
def disable(
    ctx: typer.Context,
    job_id: Annotated[int, typer.Argument(help="Job ID to disable")],
) -> None:
    """Disable a cron job."""
    actx: AppContext = ctx.obj
    out = actx.output
    _run_psql(actx, f"UPDATE cron.job SET active = false WHERE jobid = {job_id}")
    out.success(f"Cron job {job_id} disabled")


@app.command()
def history(
    ctx: typer.Context,
    limit: Annotated[int, typer.Option("--limit", "-n", help="Number of entries")] = 20,
) -> None:
    """Show cron job execution history."""
    actx: AppContext = ctx.obj
    result = _run_psql(
        actx,
        f"SELECT jobid, command, status, return_message, start_time, end_time "
        f"FROM cron.job_run_details ORDER BY start_time DESC LIMIT {limit}",
    )
    typer.echo(result)
