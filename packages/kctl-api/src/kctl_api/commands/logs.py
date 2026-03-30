"""Log viewing commands for kctl-api.

Follow, search, and filter service logs via docker compose.
"""

from __future__ import annotations

import contextlib
import subprocess
from typing import Annotated

import typer

from kctl_api.core.callbacks import AppContext
from kctl_api.core.utils import find_project_root

app = typer.Typer(name="logs", help="Log viewer — follow, errors, search, tail.", no_args_is_help=True)


def _compose_log_cmd(args: list[str]) -> list[str]:
    """Build a docker compose logs command."""
    root = find_project_root()
    return ["docker", "compose", "-f", str(root / "docker-compose.yml"), "logs", *args]


# ---------------------------------------------------------------------------
# follow
# ---------------------------------------------------------------------------
@app.command()
def follow(
    ctx: typer.Context,
    service: Annotated[str | None, typer.Argument(help="Service name (all if omitted).")] = None,
    tail: Annotated[int, typer.Option("--tail", "-n", help="Initial lines to show.")] = 50,
) -> None:
    """Follow service logs in real time."""
    cmd = _compose_log_cmd(["--follow", "--tail", str(tail)])
    if service:
        cmd.append(service)
    with contextlib.suppress(KeyboardInterrupt):
        subprocess.run(cmd, capture_output=False)


# ---------------------------------------------------------------------------
# errors
# ---------------------------------------------------------------------------
@app.command()
def errors(
    ctx: typer.Context,
    service: Annotated[str | None, typer.Argument(help="Service name (all if omitted).")] = None,
    tail: Annotated[int, typer.Option("--tail", "-n", help="Lines to scan.")] = 500,
) -> None:
    """Show only error-level log lines from services."""
    actx: AppContext = ctx.obj
    out = actx.output

    cmd = _compose_log_cmd(["--tail", str(tail)])
    if service:
        cmd.append(service)

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        out.error(f"Failed to fetch logs: {result.stderr.strip()}")
        raise typer.Exit(1)

    error_lines = [
        line
        for line in result.stdout.splitlines()
        if any(kw in line.upper() for kw in ("ERROR", "CRITICAL", "FATAL", "EXCEPTION", "TRACEBACK"))
    ]

    if not error_lines:
        out.success("No errors found in recent logs.")
        return

    out.header(f"Errors ({len(error_lines)} lines)")
    for line in error_lines:
        out.text(f"[red]{line}[/red]")


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------
@app.command()
def search(
    ctx: typer.Context,
    pattern: Annotated[str, typer.Argument(help="Text pattern to search for.")],
    service: Annotated[str | None, typer.Option("--service", "-s", help="Service name.")] = None,
    tail: Annotated[int, typer.Option("--tail", "-n", help="Lines to scan.")] = 1000,
) -> None:
    """Search service logs for a pattern."""
    actx: AppContext = ctx.obj
    out = actx.output

    cmd = _compose_log_cmd(["--tail", str(tail)])
    if service:
        cmd.append(service)

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        out.error(f"Failed to fetch logs: {result.stderr.strip()}")
        raise typer.Exit(1)

    matching = [line for line in result.stdout.splitlines() if pattern.lower() in line.lower()]

    if not matching:
        out.info(f"No matches for '{pattern}' in recent logs.")
        return

    out.header(f"Search: '{pattern}' ({len(matching)} matches)")
    for line in matching:
        out.text(line)


# ---------------------------------------------------------------------------
# tail
# ---------------------------------------------------------------------------
@app.command()
def tail(
    ctx: typer.Context,
    service: Annotated[str | None, typer.Argument(help="Service name (all if omitted).")] = None,
    lines: Annotated[int, typer.Option("--lines", "-n", help="Number of lines.")] = 100,
) -> None:
    """Show the last N lines of service logs."""
    cmd = _compose_log_cmd(["--tail", str(lines)])
    if service:
        cmd.append(service)
    subprocess.run(cmd, capture_output=False)


# ---------------------------------------------------------------------------
# structured
# ---------------------------------------------------------------------------
@app.command()
def structured(
    ctx: typer.Context,
    service: Annotated[str | None, typer.Argument(help="Service name (all if omitted).")] = None,
    tail_lines: Annotated[int, typer.Option("--tail", "-n", help="Lines to scan.")] = 500,
    level: Annotated[str | None, typer.Option("--level", "-l", help="Filter by log level.")] = None,
    event: Annotated[str | None, typer.Option("--event", "-e", help="Filter by event name.")] = None,
) -> None:
    """Parse and display JSON (structured) log lines from services."""
    actx: AppContext = ctx.obj
    out = actx.output

    cmd = _compose_log_cmd(["--tail", str(tail_lines)])
    if service:
        cmd.append(service)

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        out.error(f"Failed to fetch logs: {result.stderr.strip()}")
        raise typer.Exit(1)

    import json

    parsed: list[dict] = []
    for line in result.stdout.splitlines():
        # Try to extract JSON from lines (structlog may have container prefix)
        json_start = line.find("{")
        if json_start == -1:
            continue
        json_part = line[json_start:]
        try:
            entry = json.loads(json_part)
            parsed.append(entry)
        except json.JSONDecodeError:
            continue

    # Filter
    if level:
        parsed = [e for e in parsed if e.get("level", e.get("severity", "")).lower() == level.lower()]
    if event:
        parsed = [e for e in parsed if event.lower() in str(e.get("event", e.get("msg", ""))).lower()]

    if not parsed:
        out.info(f"No structured log entries found{' (with filters applied)' if level or event else ''}.")
        return

    rows = [
        [
            str(e.get("timestamp", e.get("time", ""))[:19]),
            str(e.get("level", e.get("severity", ""))),
            str(e.get("event", e.get("msg", ""))),
            str(e.get("logger", e.get("name", ""))),
        ]
        for e in parsed[-50:]  # last 50
    ]
    out.table(
        title=f"Structured Logs ({len(parsed)} entries)",
        columns=[("Timestamp", "dim"), ("Level", "bold"), ("Event", ""), ("Logger", "dim")],
        rows=rows,
        data_for_json=parsed[-100:],
    )


# ---------------------------------------------------------------------------
# correlation
# ---------------------------------------------------------------------------
@app.command()
def correlation(
    ctx: typer.Context,
    request_id: Annotated[str, typer.Argument(help="Request ID or correlation ID to trace.")],
    service: Annotated[str | None, typer.Option("--service", "-s", help="Service name.")] = None,
    tail_lines: Annotated[int, typer.Option("--tail", "-n", help="Lines to scan.")] = 2000,
) -> None:
    """Trace a request across services by correlation/request ID."""
    actx: AppContext = ctx.obj
    out = actx.output

    cmd = _compose_log_cmd(["--tail", str(tail_lines)])
    if service:
        cmd.append(service)

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        out.error(f"Failed to fetch logs: {result.stderr.strip()}")
        raise typer.Exit(1)

    import json

    matching_lines: list[dict] = []
    for line in result.stdout.splitlines():
        if request_id not in line:
            continue

        # Try to parse as structured log
        json_start = line.find("{")
        if json_start >= 0:
            try:
                entry = json.loads(line[json_start:])
                entry["_raw"] = line
                matching_lines.append(entry)
                continue
            except json.JSONDecodeError:
                pass

        # Plain text match
        matching_lines.append({"_raw": line, "event": line.strip()})

    if not matching_lines:
        out.info(f"No log entries found for request_id: {request_id}")
        return

    out.header(f"Correlation Trace: {request_id} ({len(matching_lines)} entries)")
    for entry in matching_lines:
        ts = entry.get("timestamp", entry.get("time", ""))[:19]
        level = entry.get("level", entry.get("severity", "INFO"))
        event = entry.get("event", entry.get("msg", entry.get("_raw", "")))
        logger = entry.get("logger", entry.get("name", ""))

        color = {"ERROR": "red", "WARNING": "yellow", "WARN": "yellow", "DEBUG": "dim"}.get(level.upper(), "")
        if color:
            out.text(f"  [{ts}] [{color}]{level}[/{color}] {logger}: {event}")
        else:
            out.text(f"  [{ts}] {level} {logger}: {event}")

    if actx.json_mode:
        out.raw_json({"request_id": request_id, "entries": matching_lines})
