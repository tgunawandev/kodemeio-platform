"""Queue job management commands (OCA queue_job module)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

import typer

from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.exceptions import RPCError

app = typer.Typer(help="Manage OCA queue jobs (requires queue_job module).")

_QUEUE_JOB_MODEL = "queue.job"
_NOT_INSTALLED_MSG = (
    "queue.job model not found. The OCA queue_job module may not be installed.\n"
    "Install it with: kctl-odoo modules install queue_job"
)


def _check_queue_job(client, out) -> bool:
    """Check if queue_job module is available. Returns True if available."""
    try:
        client.search_count(_QUEUE_JOB_MODEL, [])
        return True
    except RPCError as e:
        if "does not exist" in str(e) or "not found" in str(e).lower() or "invalid model" in str(e).lower():
            out.error(_NOT_INSTALLED_MSG)
            return False
        # Re-raise if it's a different error (auth, connection, etc.)
        raise


@app.command("list")
def list_(
    ctx: typer.Context,
    state: Annotated[
        str | None, typer.Option("--state", "-s", help="Filter by state (pending, enqueued, started, done, failed)")
    ] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List queue jobs."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _check_queue_job(c, out):
        raise typer.Exit(1)

    domain: list = []
    if state:
        domain.append(("state", "=", state))

    jobs = c.search_read(
        _QUEUE_JOB_MODEL,
        domain=domain,
        fields=["id", "name", "state", "date_created", "date_started", "date_done", "exc_name", "retry", "channel"],
        limit=limit,
        order="date_created desc",
    )

    if not jobs:
        out.info(f"No queue jobs found{f' with state={state}' if state else ''}.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for j in jobs:
        job_state = j.get("state", "")
        state_display = _state_color(job_state)
        name = (j.get("name") or "")[:40]
        channel = j.get("channel") or "default"
        rows.append(
            [
                str(j["id"]),
                name,
                state_display,
                channel,
                str(j.get("retry", 0)),
                str(j.get("date_created", "")),
            ]
        )
        json_data.append(
            {
                "id": j["id"],
                "name": j.get("name"),
                "state": job_state,
                "channel": channel,
                "retry": j.get("retry"),
                "date_created": j.get("date_created"),
                "date_started": j.get("date_started"),
                "date_done": j.get("date_done"),
                "exc_name": j.get("exc_name"),
            }
        )

    out.table(
        f"Queue Jobs ({len(jobs)})",
        [("ID", "cyan"), ("Name", ""), ("State", ""), ("Channel", ""), ("Retries", ""), ("Created", "dim")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def failed(
    ctx: typer.Context,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 20,
) -> None:
    """Show failed queue jobs with error details."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _check_queue_job(c, out):
        raise typer.Exit(1)

    jobs = c.search_read(
        _QUEUE_JOB_MODEL,
        domain=[("state", "=", "failed")],
        fields=["id", "name", "exc_name", "exc_message", "date_created", "retry", "channel"],
        limit=limit,
        order="date_created desc",
    )

    if not jobs:
        out.info("No failed queue jobs found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for j in jobs:
        name = (j.get("name") or "")[:35]
        exc_name = (j.get("exc_name") or "Unknown")[:25]
        exc_msg = (j.get("exc_message") or "")[:40]
        rows.append(
            [
                str(j["id"]),
                name,
                exc_name,
                exc_msg,
                str(j.get("retry", 0)),
                str(j.get("date_created", "")),
            ]
        )
        json_data.append(
            {
                "id": j["id"],
                "name": j.get("name"),
                "exc_name": j.get("exc_name"),
                "exc_message": j.get("exc_message"),
                "retry": j.get("retry"),
                "date_created": j.get("date_created"),
                "channel": j.get("channel"),
            }
        )

    out.table(
        f"Failed Queue Jobs ({len(jobs)})",
        [
            ("ID", "cyan"),
            ("Name", ""),
            ("Error Type", "red"),
            ("Error Message", ""),
            ("Retries", ""),
            ("Created", "dim"),
        ],
        rows,
        data_for_json=json_data,
    )


@app.command()
def retry(
    ctx: typer.Context,
    ids: Annotated[str, typer.Argument(help="Comma-separated job IDs to retry")],
) -> None:
    """Requeue failed jobs by setting state to pending."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _check_queue_job(c, out):
        raise typer.Exit(1)

    job_ids = [int(i.strip()) for i in ids.split(",")]

    # Verify jobs exist and are in failed state
    existing = c.search(_QUEUE_JOB_MODEL, [("id", "in", job_ids), ("state", "=", "failed")])
    if not existing:
        out.error("No failed jobs found with the given IDs.")
        raise typer.Exit(1)

    c.write(
        _QUEUE_JOB_MODEL,
        existing,
        {
            "state": "pending",
            "exc_name": False,
            "exc_message": False,
            "exc_info": False,
            "date_started": False,
            "date_done": False,
        },
    )

    out.success(f"Requeued {len(existing)} job(s) for retry")
    if len(existing) < len(job_ids):
        skipped = len(job_ids) - len(existing)
        out.warn(f"{skipped} job(s) were not in 'failed' state and were skipped")


@app.command("retry-all")
def retry_all(
    ctx: typer.Context,
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Requeue all failed jobs."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _check_queue_job(c, out):
        raise typer.Exit(1)

    failed_ids = c.search(_QUEUE_JOB_MODEL, [("state", "=", "failed")])
    if not failed_ids:
        out.info("No failed jobs to retry.")
        return

    if not force and not typer.confirm(f"Retry all {len(failed_ids)} failed jobs?"):
        raise typer.Exit(0)

    c.write(
        _QUEUE_JOB_MODEL,
        failed_ids,
        {
            "state": "pending",
            "exc_name": False,
            "exc_message": False,
            "exc_info": False,
            "date_started": False,
            "date_done": False,
        },
    )

    out.success(f"Requeued {len(failed_ids)} failed job(s)")


@app.command()
def cancel(
    ctx: typer.Context,
    ids: Annotated[str, typer.Argument(help="Comma-separated job IDs to cancel")],
) -> None:
    """Cancel queue jobs by setting state to cancelled."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _check_queue_job(c, out):
        raise typer.Exit(1)

    job_ids = [int(i.strip()) for i in ids.split(",")]

    # Only cancel jobs that are not already done
    cancellable = c.search(_QUEUE_JOB_MODEL, [("id", "in", job_ids), ("state", "not in", ["done", "cancelled"])])
    if not cancellable:
        out.error("No cancellable jobs found with the given IDs.")
        raise typer.Exit(1)

    c.write(_QUEUE_JOB_MODEL, cancellable, {"state": "cancelled"})
    out.success(f"Cancelled {len(cancellable)} job(s)")


@app.command()
def stats(
    ctx: typer.Context,
    watch: Annotated[bool, typer.Option("--watch", "-w", help="Continuously monitor")] = False,
    interval: Annotated[int, typer.Option("--interval", "-i", help="Watch interval in seconds")] = 10,
) -> None:
    """Show queue job statistics by state."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _check_queue_job(c, out):
        raise typer.Exit(1)

    def _run_once() -> None:
        states = ["pending", "enqueued", "started", "done", "failed", "cancelled"]
        rows = []
        json_data = []
        total = 0

        for state in states:
            count = c.search_count(_QUEUE_JOB_MODEL, [("state", "=", state)])
            total += count
            rows.append([_state_color(state), str(count)])
            json_data.append({"state": state, "count": count})

        rows.append(["[bold]total[/bold]", f"[bold]{total}[/bold]"])
        json_data.append({"state": "total", "count": total})

        out.table(
            "Queue Job Statistics",
            [("State", ""), ("Count", "cyan")],
            rows,
            data_for_json=json_data,
        )

        cutoff_24h = (datetime.now(tz=UTC) - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        recent_count = c.search_count(_QUEUE_JOB_MODEL, [("date_created", ">", cutoff_24h)])
        recent_failed = c.search_count(_QUEUE_JOB_MODEL, [("state", "=", "failed"), ("date_created", ">", cutoff_24h)])
        out.info(f"Last 24 hours: {recent_count} created, {recent_failed} failed")

    _run_once()
    if watch:
        import time

        try:
            while True:
                time.sleep(interval)
                out.header(f"Refresh at {time.strftime('%H:%M:%S')}")
                _run_once()
        except KeyboardInterrupt:
            out.info("Stopped watching")


@app.command()
def cleanup(
    ctx: typer.Context,
    days: Annotated[int, typer.Option("--days", "-d", help="Delete jobs older than N days")] = 30,
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete old completed and cancelled queue jobs."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _check_queue_job(c, out):
        raise typer.Exit(1)

    cutoff = (datetime.now(tz=UTC) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

    done_ids = c.search(_QUEUE_JOB_MODEL, [("state", "=", "done"), ("date_done", "<", cutoff)])
    cancelled_ids = c.search(_QUEUE_JOB_MODEL, [("state", "=", "cancelled"), ("date_created", "<", cutoff)])

    total = len(done_ids) + len(cancelled_ids)

    json_result = {
        "cutoff_days": days,
        "done_count": len(done_ids),
        "cancelled_count": len(cancelled_ids),
        "total": total,
    }

    if total == 0:
        if actx.json_mode:
            json_result["deleted"] = 0
            out.raw_json(json_result)
            return
        out.info("Nothing to clean.")
        return

    out.info(f"Jobs older than {days} days:")
    out.kv("Completed", str(len(done_ids)))
    out.kv("Cancelled", str(len(cancelled_ids)))
    out.kv("Total", str(total))

    if not force and not typer.confirm(f"Delete {total} old queue jobs?"):
        raise typer.Exit(0)

    all_ids = done_ids + cancelled_ids
    batch_size = 500
    deleted = 0
    for i in range(0, len(all_ids), batch_size):
        batch = all_ids[i : i + batch_size]
        c.unlink(_QUEUE_JOB_MODEL, batch)
        deleted += len(batch)

    if actx.json_mode:
        json_result["deleted"] = deleted
        out.raw_json(json_result)
    else:
        out.success(f"Deleted {deleted} queue job records")


def _state_color(state: str) -> str:
    colors = {
        "pending": "[yellow]pending[/yellow]",
        "enqueued": "[blue]enqueued[/blue]",
        "started": "[cyan]started[/cyan]",
        "done": "[green]done[/green]",
        "failed": "[red]failed[/red]",
        "cancelled": "[dim]cancelled[/dim]",
    }
    return colors.get(state, state)
