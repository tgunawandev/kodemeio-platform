from __future__ import annotations

import typer

from kctl_mm.core.callbacks import AppContext

app = typer.Typer(help="Job management.", no_args_is_help=True)


def _c(ctx: typer.Context) -> AppContext:
    return ctx.ensure_object(AppContext)


@app.command("list")
def list_cmd(
    ctx: typer.Context,
    job_type: str | None = typer.Option(None, "--type"),
) -> None:
    c = _c(ctx)
    c.output.raw_json(c.client.list_jobs(job_type=job_type))


@app.command("status")
def status_cmd(ctx: typer.Context, job_id: str) -> None:
    c = _c(ctx)
    c.output.raw_json(c.client.get_job(job_id))


@app.command("cancel")
def cancel_cmd(ctx: typer.Context, job_id: str) -> None:
    c = _c(ctx)
    c.output.raw_json(c.client.cancel_job(job_id))
