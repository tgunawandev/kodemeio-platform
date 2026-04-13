from __future__ import annotations

import os
import re
import time
from typing import Any

import typer

from kctl_lib.ssh import scp_upload

from kctl_mm.core.callbacks import AppContext
from kctl_mm.core.mm_exec import MMExec

app = typer.Typer(help="Bulk import/export (mmctl).", no_args_is_help=True)

_JOB_ID_RE = re.compile(r"\b([a-z0-9]{26})\b")
_TERMINAL = {"success", "error", "failed"}


def _c(ctx: typer.Context) -> AppContext:
    return ctx.ensure_object(AppContext)


def _poll_job(
    mm_exec: MMExec,
    kind: str,
    job_id: str,
    max_iters: int = 60,
    interval: int = 5,
) -> Any:
    job: Any = None
    for _ in range(max_iters):
        job = mm_exec.mmctl_json([kind, "job", "show", job_id])
        status = ""
        if isinstance(job, dict):
            status = str(job.get("status", "")).lower()
        if status in _TERMINAL:
            return job
        time.sleep(interval)
    return job


def _parse_job_id(stdout: str) -> str | None:
    match = _JOB_ID_RE.search(stdout)
    return match.group(1) if match else None


@app.command("export")
def export_cmd(
    ctx: typer.Context,
    team: str,
    out: str = typer.Option(None, "--out", help="Local path (informational for v0.1)."),
) -> None:
    c = _c(ctx)
    r = c.mm_exec.mmctl(["export", "create", team])
    typer.echo(r.stdout)
    job_id = _parse_job_id(r.stdout)
    if job_id:
        job = _poll_job(c.mm_exec, "export", job_id)
        c.output.raw_json(job)
    else:
        typer.echo("warning: could not parse job id from mmctl output; skipping poll.")
        c.output.raw_json(c.mm_exec.mmctl_json(["export", "job", "list"]))
    if out:
        typer.echo(f"To download the export archive, run: scp root@<host>:/mattermost/export/<file> {out}")


@app.command("import")
def import_cmd(ctx: typer.Context, local_path: str) -> None:
    c = _c(ctx)
    settings = c.settings
    basename = os.path.basename(local_path)
    remote = f"/mattermost/import/{basename}"
    scp_upload(
        str(settings["ssh_host"]),
        local_path,
        remote,
        user=str(settings.get("ssh_user", "root")),
    )
    r = c.mm_exec.mmctl(["import", "process", remote])
    typer.echo(r.stdout)
    job_id = _parse_job_id(r.stdout)
    if job_id:
        job = _poll_job(c.mm_exec, "import", job_id)
        c.output.raw_json(job)
    else:
        typer.echo("warning: could not parse job id from mmctl output; skipping poll.")


@app.command("jobs")
def jobs_cmd(ctx: typer.Context) -> None:
    c = _c(ctx)
    c.output.raw_json(
        {
            "export": c.mm_exec.mmctl_json(["export", "job", "list"]),
            "import": c.mm_exec.mmctl_json(["import", "job", "list"]),
        }
    )
