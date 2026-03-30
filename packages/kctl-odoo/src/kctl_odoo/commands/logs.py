"""Log streaming and analysis commands."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

import typer
from rich.console import Console

from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.local import LocalClient

app = typer.Typer(help="Stream and analyze Odoo logs.")
console = Console()


def _get_local_client() -> LocalClient:
    try:
        return LocalClient()
    except Exception:
        console.print(
            "[red]ERROR[/red] Not inside a Docker Compose project directory.\n"
            "  The 'follow' command requires a local Docker environment."
        )
        raise typer.Exit(1) from None


@app.command()
def follow(
    level: Annotated[
        str | None, typer.Option("--level", "-l", help="Filter by log level (INFO, WARNING, ERROR)")
    ] = None,
    lines: Annotated[int, typer.Option("--lines", "-n", help="Number of initial lines to show")] = 100,
    service: Annotated[str | None, typer.Option("--service", "-s", help="Docker service name")] = None,
) -> None:
    """Stream Docker container logs in real time.

    Connects to the local Docker Compose environment and streams logs.
    Optionally filter by log level using grep-style post-processing.

    Examples:
        kctl-odoo logs follow
        kctl-odoo logs follow --level ERROR --lines 50
        kctl-odoo logs follow --service db
    """
    client = _get_local_client()

    if level:
        console.print(f"[blue]INFO[/blue] Streaming logs (level filter: {level.upper()})...")
        # Use docker compose logs with grep for level filtering
        import subprocess

        compose_cmd = client.compose_cmd() + ["logs", f"--tail={lines}", "-f"]
        if service:
            compose_cmd.append(service)
        proc = None
        try:
            proc = subprocess.Popen(
                compose_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=str(client.project_dir),
            )
            assert proc.stdout is not None
            level_upper = level.upper()
            for line in proc.stdout:
                if level_upper in line.upper():
                    console.print(line, end="", highlight=False)
        except KeyboardInterrupt:
            pass
        finally:
            if proc is not None and proc.poll() is None:
                proc.terminate()
    else:
        client.logs(follow=True, lines=lines, service=service)


def _cutoff_date(days: int) -> str:
    """Return an Odoo-formatted datetime string N days ago."""
    dt = datetime.now(tz=UTC) - timedelta(days=days)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


@app.command()
def errors(
    ctx: typer.Context,
    days: Annotated[int, typer.Option("--days", "-d", help="Look back N days")] = 7,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max records to return")] = 50,
) -> None:
    """Show recent errors from ir.logging (works remotely via JSON-RPC).

    Queries the ir.logging model for error-level log entries.
    Falls back gracefully if ir.logging is not available.

    Examples:
        kctl-odoo logs errors
        kctl-odoo logs errors --days 1 --limit 20
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    cutoff = _cutoff_date(days)
    domain = [
        ("level", "in", ["ERROR", "CRITICAL"]),
        ("create_date", ">=", cutoff),
    ]

    try:
        records = c.search_read(
            "ir.logging",
            domain=domain,
            fields=["id", "name", "type", "path", "message", "level", "create_date"],
            limit=limit,
            order="create_date desc",
        )
    except Exception as exc:
        out.warn(f"ir.logging not available: {exc}")
        out.info("This model may not be installed or accessible on this instance.")
        if actx.json_mode:
            out.raw_json([])
        return

    if not records:
        out.info(f"No errors found in the last {days} day(s).")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for r in records:
        msg = str(r.get("message", ""))[:80]
        rows.append(
            [
                str(r["id"]),
                str(r.get("create_date", ""))[:19],
                r.get("level", ""),
                r.get("type", ""),
                str(r.get("path", ""))[:40],
                msg,
            ]
        )
        json_data.append(
            {
                "id": r["id"],
                "create_date": r.get("create_date"),
                "level": r.get("level"),
                "type": r.get("type"),
                "path": r.get("path"),
                "message": r.get("message"),
            }
        )

    out.table(
        f"Errors ({len(records)}, last {days} days)",
        [
            ("ID", "cyan"),
            ("Date", "dim"),
            ("Level", "red"),
            ("Type", ""),
            ("Path", "dim"),
            ("Message", ""),
        ],
        rows,
        data_for_json=json_data,
    )


@app.command()
def search(
    ctx: typer.Context,
    pattern: Annotated[str, typer.Argument(help="Search pattern (matched against message and path)")],
    days: Annotated[int, typer.Option("--days", "-d", help="Look back N days")] = 7,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max records to return")] = 50,
) -> None:
    """Search ir.logging records matching a pattern.

    Searches both message and path fields using ilike.

    Examples:
        kctl-odoo logs search "account.move"
        kctl-odoo logs search "timeout" --days 1
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    cutoff = _cutoff_date(days)
    domain = [
        ("create_date", ">=", cutoff),
        "|",
        ("message", "ilike", pattern),
        ("path", "ilike", pattern),
    ]

    try:
        records = c.search_read(
            "ir.logging",
            domain=domain,
            fields=["id", "name", "type", "path", "level", "message", "create_date"],
            limit=limit,
            order="create_date desc",
        )
    except Exception as exc:
        out.warn(f"ir.logging not available: {exc}")
        if actx.json_mode:
            out.raw_json([])
        return

    if not records:
        out.info(f"No log entries matching '{pattern}' in the last {days} day(s).")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for r in records:
        msg = str(r.get("message", ""))[:80]
        rows.append(
            [
                str(r["id"]),
                str(r.get("create_date", ""))[:19],
                r.get("level", ""),
                r.get("type", ""),
                str(r.get("path", ""))[:40],
                msg,
            ]
        )
        json_data.append(
            {
                "id": r["id"],
                "create_date": r.get("create_date"),
                "level": r.get("level"),
                "type": r.get("type"),
                "path": r.get("path"),
                "message": r.get("message"),
            }
        )

    out.table(
        f"Log Search: '{pattern}' ({len(records)} matches, last {days} days)",
        [
            ("ID", "cyan"),
            ("Date", "dim"),
            ("Level", ""),
            ("Type", ""),
            ("Path", "dim"),
            ("Message", ""),
        ],
        rows,
        data_for_json=json_data,
    )
