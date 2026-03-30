"""Cron job management commands."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

import typer
from croniter import croniter  # type: ignore[import-untyped]

from kctl_claw.core.callbacks import AppContext
from kctl_claw.core.config_manager import ConfigFile
from kctl_claw.core.exceptions import GatewayError
from kctl_claw.core.resolve import get_all_cron_jobs, resolve_cron_job

_GATEWAY_HINT = "Start the gateway first: kctl-claw deploy up"

app = typer.Typer(help="Manage cron jobs.")


def _next_run(schedule: str) -> str:
    """Compute next run time from cron expression."""
    try:
        from datetime import datetime

        cron = croniter(schedule, datetime.now(tz=UTC))
        return cron.get_next(datetime).strftime("%Y-%m-%d %H:%M UTC")  # type: ignore[no-any-return]
    except (ValueError, KeyError):
        return "invalid schedule"


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all cron jobs."""
    actx: AppContext = ctx.obj
    out = actx.output
    jobs = get_all_cron_jobs(actx.config_mgr)

    rows = []
    json_data = []
    for j in jobs:
        jid = j["id"]
        schedule = j.get("schedule", "")
        agent = j.get("agent", "")
        enabled = j.get("enabled", True)
        status = "[green]enabled[/green]" if enabled else "[red]disabled[/red]"
        next_run = _next_run(schedule) if enabled else "skipped"
        rows.append([jid, schedule, agent, status, next_run])
        json_data.append(
            {
                "id": jid,
                "schedule": schedule,
                "agent": agent,
                "enabled": enabled,
                "next_run": next_run if enabled else None,
            }
        )

    out.table(
        f"Cron Jobs ({len(jobs)})",
        [("ID", "cyan"), ("Schedule", ""), ("Agent", ""), ("Status", ""), ("Next Run", "dim")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def get(
    ctx: typer.Context,
    job_id: Annotated[str, typer.Argument(help="Cron job ID")],
) -> None:
    """Show cron job details."""
    actx: AppContext = ctx.obj
    out = actx.output
    job = resolve_cron_job(actx.config_mgr, job_id)

    enabled = job.get("enabled", True)
    sections = [
        (
            "Config",
            [
                ("ID", job["id"]),
                ("Name", job.get("name", "")),
                ("Schedule", job.get("schedule", "")),
                ("Agent", job.get("agent", "")),
                ("Model", job.get("model", "default")),
                ("Enabled", "[green]yes[/green]" if enabled else "[red]no[/red]"),
                ("Silent", str(job.get("silent", False))),
                ("Next Run", _next_run(job.get("schedule", "")) if enabled else "skipped"),
            ],
        ),
    ]
    if job.get("retry"):
        r = job["retry"]
        sections.append(
            (
                "Retry",
                [
                    ("Max Attempts", str(r.get("max_attempts", 3))),
                    ("Backoff", r.get("backoff", "exponential")),
                ],
            )
        )
    sections.append(("Prompt", [("", job.get("prompt", "")[:200])]))

    out.detail(f"Cron Job: {job_id}", sections, data_for_json=job)


@app.command()
def enable(
    ctx: typer.Context,
    job_id: Annotated[str, typer.Argument(help="Cron job ID")],
) -> None:
    """Enable a disabled cron job."""
    actx: AppContext = ctx.obj
    out = actx.output
    mgr = actx.config_mgr

    resolve_cron_job(mgr, job_id)
    mgr.backup_before_modify(ConfigFile.CRON_JOBS)
    data = mgr.read(ConfigFile.CRON_JOBS)
    for j in data["jobs"]:
        if j["id"] == job_id:
            j["enabled"] = True
            break
    mgr.write(ConfigFile.CRON_JOBS, data)
    out.success(f"Enabled {job_id}")

    if actx.live:
        out.info("Reloading gateway...")


@app.command()
def disable(
    ctx: typer.Context,
    job_id: Annotated[str, typer.Argument(help="Cron job ID")],
) -> None:
    """Disable a cron job."""
    actx: AppContext = ctx.obj
    out = actx.output
    mgr = actx.config_mgr

    resolve_cron_job(mgr, job_id)
    mgr.backup_before_modify(ConfigFile.CRON_JOBS)
    data = mgr.read(ConfigFile.CRON_JOBS)
    for j in data["jobs"]:
        if j["id"] == job_id:
            j["enabled"] = False
            break
    mgr.write(ConfigFile.CRON_JOBS, data)
    out.success(f"Disabled {job_id}")

    if actx.live:
        out.info("Reloading gateway...")


@app.command("set-schedule")
def set_schedule(
    ctx: typer.Context,
    job_id: Annotated[str, typer.Argument(help="Cron job ID")],
    cron_expr: Annotated[str, typer.Argument(help="Cron expression (e.g. '0 7 * * *')")],
) -> None:
    """Update a cron job's schedule."""
    actx: AppContext = ctx.obj
    out = actx.output
    mgr = actx.config_mgr

    if not croniter.is_valid(cron_expr):
        out.error(f"Invalid cron expression: {cron_expr}")
        raise typer.Exit(1)

    resolve_cron_job(mgr, job_id)
    mgr.backup_before_modify(ConfigFile.CRON_JOBS)
    data = mgr.read(ConfigFile.CRON_JOBS)
    old = ""
    for j in data["jobs"]:
        if j["id"] == job_id:
            old = j.get("schedule", "")
            j["schedule"] = cron_expr
            break
    mgr.write(ConfigFile.CRON_JOBS, data)
    out.success(f"{job_id}: schedule {old} -> {cron_expr}")


@app.command("set-model")
def set_model(
    ctx: typer.Context,
    job_id: Annotated[str, typer.Argument(help="Cron job ID")],
    model: Annotated[str, typer.Argument(help="Model ID")],
) -> None:
    """Change a cron job's model."""
    actx: AppContext = ctx.obj
    out = actx.output
    mgr = actx.config_mgr

    resolve_cron_job(mgr, job_id)
    mgr.backup_before_modify(ConfigFile.CRON_JOBS)
    data = mgr.read(ConfigFile.CRON_JOBS)
    for j in data["jobs"]:
        if j["id"] == job_id:
            j["model"] = model
            break
    mgr.write(ConfigFile.CRON_JOBS, data)
    out.success(f"{job_id}: model -> {model}")


@app.command("dry-run")
def dry_run(
    ctx: typer.Context,
    job_id: Annotated[str, typer.Argument(help="Cron job ID")],
) -> None:
    """Quick alias — execute job in dry-run (info-only) mode."""
    actx: AppContext = ctx.obj
    out = actx.output

    job = resolve_cron_job(actx.config_mgr, job_id)
    sections = [
        (
            "Dry-run Info",
            [
                ("ID", job["id"]),
                ("Schedule", job.get("schedule", "")),
                ("Agent", job.get("agent", "")),
                ("Model", job.get("model", "default")),
                ("Prompt (preview)", job.get("prompt", "")[:150]),
            ],
        )
    ]
    out.detail(f"Dry-run: {job_id}", sections, data_for_json={"mode": "dry-run", **job})

    try:
        data = actx.gateway.post(f"/api/cron/{job_id}/dry-run", {"dry_run": True})
        if isinstance(data, dict):
            out.info(f"Gateway dry-run result: {data}")
    except GatewayError:
        out.info("(Gateway not available — showing config only)")


@app.command()
def history(
    ctx: typer.Context,
    job_id: Annotated[str, typer.Argument(help="Cron job ID")],
    count: Annotated[int, typer.Option("--count", help="Number of history entries")] = 20,
) -> None:
    """Show execution history for a cron job."""
    actx: AppContext = ctx.obj
    out = actx.output

    resolve_cron_job(actx.config_mgr, job_id)
    out.info(f"Fetching execution history for {job_id!r} (last {count})...")

    try:
        data = actx.gateway.get(f"/api/cron/{job_id}/history", count=count)
        if isinstance(data, list):
            rows = [
                [
                    str(e.get("run_id", ""))[:8],
                    str(e.get("started_at", "")),
                    str(e.get("status", "")),
                    str(e.get("duration_ms", "")) + "ms",
                ]
                for e in data
            ]
            out.table(
                f"Execution History: {job_id} ({len(data)} entries)",
                [("Run ID", "dim"), ("Started At", "cyan"), ("Status", ""), ("Duration", "")],
                rows,
                data_for_json=data,
            )
        else:
            out.text(str(data))
    except GatewayError as e:
        out.warn(f"Gateway not available: {e}")
        out.info(_GATEWAY_HINT)


@app.command()
def failures(
    ctx: typer.Context,
    count: Annotated[int, typer.Option("--count", help="Number of recent failures")] = 10,
) -> None:
    """Show recent cron job failures with error details."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info(f"Fetching last {count} cron failures...")
    try:
        data = actx.gateway.get("/api/cron/failures", count=count)
        if isinstance(data, list):
            rows = [
                [str(e.get("job_id", "")), str(e.get("started_at", "")), str(e.get("error", ""))[:60]] for e in data
            ]
            out.table(
                f"Recent Failures ({len(data)})",
                [("Job ID", "cyan"), ("When", ""), ("Error", "dim")],
                rows,
                data_for_json=data,
            )
            if not data:
                out.success("No recent failures.")
        else:
            out.text(str(data))
    except GatewayError as e:
        out.warn(f"Gateway not available: {e}")
        out.info(_GATEWAY_HINT)


@app.command("next")
def next_(
    ctx: typer.Context,
    job_id: Annotated[str, typer.Argument(help="Cron job ID")],
    count: Annotated[int, typer.Option("--count", help="Number of upcoming runs to show")] = 5,
) -> None:
    """Show next scheduled runs for a cron job."""
    actx: AppContext = ctx.obj
    out = actx.output

    job = resolve_cron_job(actx.config_mgr, job_id)
    schedule = job.get("schedule", "")

    if not croniter.is_valid(schedule):
        out.error(f"Invalid cron expression: {schedule!r}")
        raise typer.Exit(1)

    cron = croniter(schedule, datetime.now(tz=UTC))
    rows = []
    json_data = []
    for i in range(count):
        next_dt = cron.get_next(datetime)
        rows.append([str(i + 1), next_dt.strftime("%Y-%m-%d %H:%M UTC"), schedule])
        json_data.append({"run": i + 1, "at": next_dt.isoformat(), "schedule": schedule})

    out.table(
        f"Next Runs: {job_id}",
        [("#", "dim"), ("Scheduled At", "cyan"), ("Schedule", "")],
        rows,
        data_for_json=json_data,
    )
