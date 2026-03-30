"""Cron job debugging commands."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

import typer
from croniter import croniter  # type: ignore[import-untyped]

from kctl_claw.core.callbacks import AppContext
from kctl_claw.core.exceptions import GatewayError
from kctl_claw.core.resolve import resolve_cron_job

app = typer.Typer(help="Debug cron jobs: dry-run, simulate, history, failures.")

_GATEWAY_HINT = "Start the gateway first: kctl-claw deploy up"


@app.command("dry-run")
def dry_run(
    ctx: typer.Context,
    job: Annotated[str, typer.Argument(help="Cron job ID")],
) -> None:
    """Execute a cron job without side effects (info/dry-run mode)."""
    actx: AppContext = ctx.obj
    out = actx.output

    job_cfg = resolve_cron_job(actx.config_mgr, job)

    out.info(f"Dry-run for job {job!r}:")
    sections = [
        (
            "Job Info",
            [
                ("ID", job_cfg["id"]),
                ("Name", job_cfg.get("name", "")),
                ("Schedule", job_cfg.get("schedule", "")),
                ("Agent", job_cfg.get("agent", "")),
                ("Model", job_cfg.get("model", "default")),
                ("Enabled", str(job_cfg.get("enabled", True))),
                ("Prompt (preview)", job_cfg.get("prompt", "")[:150]),
            ],
        )
    ]
    out.detail(f"Dry-run: {job}", sections, data_for_json={"mode": "dry-run", **job_cfg})
    out.info("To run live, use: kctl-claw deploy up, then wait for scheduled execution.")

    try:
        data = actx.gateway.post(f"/api/cron/{job}/dry-run", {"dry_run": True})
        if isinstance(data, dict):
            out.info(f"Gateway dry-run: {data}")
    except GatewayError:
        out.info("(Gateway not available — showing config only)")


@app.command()
def simulate(
    ctx: typer.Context,
    job: Annotated[str, typer.Argument(help="Cron job ID")],
    from_date: Annotated[str, typer.Option("--from", help="Start date (YYYY-MM-DD)")] = "",
    to_date: Annotated[str, typer.Option("--to", help="End date (YYYY-MM-DD)")] = "",
) -> None:
    """Show execution times for a cron job over a date range."""
    actx: AppContext = ctx.obj
    out = actx.output

    job_cfg = resolve_cron_job(actx.config_mgr, job)
    schedule = job_cfg.get("schedule", "")

    if not croniter.is_valid(schedule):
        out.error(f"Invalid cron expression: {schedule!r}")
        raise typer.Exit(1)

    # Parse date range
    now = datetime.now(tz=UTC)
    try:
        start_dt = datetime.strptime(from_date, "%Y-%m-%d").replace(tzinfo=UTC) if from_date else now
        end_dt = (
            datetime.strptime(to_date, "%Y-%m-%d").replace(tzinfo=UTC)
            if to_date
            else datetime(now.year, now.month, now.day, 23, 59, 59, tzinfo=UTC)
        )
    except ValueError as e:
        out.error(f"Invalid date format (expected YYYY-MM-DD): {e}")
        raise typer.Exit(1) from e

    # Compute execution times using croniter
    cron = croniter(schedule, start_dt)
    times = []
    max_entries = 50
    while len(times) < max_entries:
        next_dt = cron.get_next(datetime)
        if next_dt > end_dt:
            break
        times.append(next_dt)

    rows = [[str(i + 1), t.strftime("%Y-%m-%d %H:%M UTC"), schedule] for i, t in enumerate(times)]
    json_data = [{"run": i + 1, "at": t.isoformat(), "schedule": schedule} for i, t in enumerate(times)]

    out.table(
        f"Simulated Runs: {job} ({len(times)} executions)",
        [("#", "dim"), ("Scheduled At", "cyan"), ("Schedule", "")],
        rows,
        data_for_json=json_data,
    )

    if not times:
        out.warn("No executions found in the given date range.")


@app.command()
def history(
    ctx: typer.Context,
    job: Annotated[str, typer.Argument(help="Cron job ID")],
    count: Annotated[int, typer.Option("--count", help="Number of history entries")] = 20,
) -> None:
    """Show execution history for a cron job with status and duration."""
    actx: AppContext = ctx.obj
    out = actx.output

    resolve_cron_job(actx.config_mgr, job)
    out.info(f"Fetching execution history for {job!r} (last {count})...")

    try:
        data = actx.gateway.get(f"/api/cron/{job}/history", count=count)
        if isinstance(data, list):
            rows = [
                [
                    str(e.get("run_id", "")),
                    str(e.get("started_at", "")),
                    str(e.get("status", "")),
                    str(e.get("duration_ms", ""))[:10],
                ]
                for e in data
            ]
            out.table(
                f"Execution History: {job} ({len(data)} entries)",
                [("Run ID", "dim"), ("Started At", "cyan"), ("Status", ""), ("Duration (ms)", "")],
                rows,
                data_for_json=data,
            )
        else:
            out.text(str(data))
    except GatewayError as e:
        out.warn(f"Gateway not available: {e}")
        out.info(_GATEWAY_HINT)


@app.command()
def output(
    ctx: typer.Context,
    job: Annotated[str, typer.Argument(help="Cron job ID")],
) -> None:
    """Show output of the last cron job execution."""
    actx: AppContext = ctx.obj
    out = actx.output

    resolve_cron_job(actx.config_mgr, job)
    out.info(f"Fetching last output for {job!r}...")

    try:
        data = actx.gateway.get(f"/api/cron/{job}/output/last")
        if isinstance(data, dict):
            sections = [
                (
                    "Last Run",
                    [
                        ("Job ID", job),
                        ("Run ID", str(data.get("run_id", ""))),
                        ("Status", str(data.get("status", ""))),
                        ("Started At", str(data.get("started_at", ""))),
                        ("Duration (ms)", str(data.get("duration_ms", ""))),
                    ],
                ),
                ("Output", [("", str(data.get("output", ""))[:500])]),
            ]
            out.detail(f"Last Output: {job}", sections, data_for_json=data)
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
                [
                    str(e.get("job_id", "")),
                    str(e.get("started_at", "")),
                    str(e.get("error", ""))[:60],
                ]
                for e in data
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
