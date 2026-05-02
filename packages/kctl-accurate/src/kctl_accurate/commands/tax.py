"""kctl-accurate tax — e-Faktur (DJP-facing) commands.

Subcommands
-----------
efaktur-list       List faktur pajak records for a date range or period.
efaktur-export-csv Export faktur pajak records to a file (JSONL / JSON / CSV).
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Annotated

import typer

from kctl_accurate.core.callbacks import AppContext
from kctl_accurate.core.streaming import OutputSink

try:
    from accurate_sdk.migration.extractors.efaktur import extract_efaktur_period

    _EFAKTUR_AVAILABLE = True
except ImportError:  # pragma: no cover
    _EFAKTUR_AVAILABLE = False

app = typer.Typer(
    help="e-Faktur (DJP) commands — list and export faktur pajak data.",
    no_args_is_help=True,
)

_EFAKTUR_COLUMNS = [
    "invoice_accurate_id",
    "invoice_number",
    "invoice_date",
    "faktur_pajak_no",
    "faktur_pajak_date",
    "partner_name",
    "partner_npwp",
    "base_amount",
    "tax_amount",
    "direction",
]


def _parse_period(period: str) -> tuple[date, date]:
    """Parse YYYY-MM into (first_day, last_day)."""
    try:
        dt = datetime.strptime(period, "%Y-%m")
    except ValueError:
        raise typer.BadParameter(f"--period must be YYYY-MM format, got: {period!r}")
    import calendar

    last = calendar.monthrange(dt.year, dt.month)[1]
    return date(dt.year, dt.month, 1), date(dt.year, dt.month, last)


def _parse_date(value: str, flag: str) -> date:
    """Parse ISO date string (YYYY-MM-DD)."""
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise typer.BadParameter(f"{flag} must be YYYY-MM-DD format, got: {value!r}")


def _resolve_dates(
    since: str | None,
    period: str | None,
) -> tuple[date, date]:
    """Resolve --since / --period into (start, end).

    Priority: --period > --since (with today as end) > current month default.
    """
    if period is not None:
        return _parse_period(period)
    today = date.today()
    if since is not None:
        return _parse_date(since, "--since"), today
    # Default: current calendar month
    import calendar

    last = calendar.monthrange(today.year, today.month)[1]
    return date(today.year, today.month, 1), date(today.year, today.month, last)


def _print_efaktur_table(rows: list[dict], json_mode: bool) -> None:
    if json_mode:
        print(json.dumps(rows, indent=2, ensure_ascii=False, default=str))
        return

    from rich.console import Console
    from rich.table import Table

    console = Console()
    table = Table(
        title=f"[bold]e-Faktur records ({len(rows)})[/bold]",
        show_header=True,
        header_style="bold cyan",
    )
    for col in _EFAKTUR_COLUMNS:
        justify = "right" if col in {"base_amount", "tax_amount"} else "left"
        table.add_column(col.replace("_", " ").title(), justify=justify)

    for row in rows:
        table.add_row(*[str(row.get(c, "")) for c in _EFAKTUR_COLUMNS])

    console.print()
    console.print(table)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command("efaktur-list")
def efaktur_list(
    ctx: typer.Context,
    since: Annotated[
        str | None,
        typer.Option(
            "--since", help="Start date ISO format YYYY-MM-DD (inclusive). Defaults to first of current month."
        ),
    ] = None,
    period: Annotated[
        str | None,
        typer.Option("--period", help="Calendar month YYYY-MM (overrides --since; sets start+end to full month)."),
    ] = None,
    out: Annotated[
        Path | None,
        typer.Option("--out", help="Output file path (.jsonl, .json, .csv). Prints to stdout if omitted."),
    ] = None,
) -> None:
    """List faktur pajak records for a date range or calendar period.

    Fetches both output (sales) and input (purchase) faktur pajak numbers
    issued in the given period from Accurate Online.
    """
    if not _EFAKTUR_AVAILABLE:
        typer.echo(
            "This command requires accurate-sdk with migration extras installed.",
            err=True,
        )
        raise typer.Exit(1)

    actx: AppContext = ctx.obj
    start, end = _resolve_dates(since, period)

    if not actx.quiet:
        typer.echo(f"Fetching e-Faktur records {start} → {end} …", err=True)

    rows = extract_efaktur_period(actx.client.raw, start, end)

    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        with OutputSink(out, columns=_EFAKTUR_COLUMNS) as sink:
            for row in rows:
                sink.write_record(row)
        if not actx.quiet:
            typer.echo(f"Wrote {sink.record_count} records to {out}", err=True)
    else:
        _print_efaktur_table(rows, actx.json_mode)


@app.command("efaktur-export-csv")
def efaktur_export_csv(
    ctx: typer.Context,
    out: Annotated[
        Path,
        typer.Option("--out", help="Output file path (.jsonl, .json, .csv).", show_default=False),
    ],
    period: Annotated[
        str | None,
        typer.Option("--period", help="Calendar month YYYY-MM (default: current month)."),
    ] = None,
    since: Annotated[
        str | None,
        typer.Option("--since", help="Start date ISO format YYYY-MM-DD. Ignored if --period is set."),
    ] = None,
) -> None:
    """Export faktur pajak records to a file.

    Writes to the format determined by the --out file extension:
    .csv, .jsonl, .ndjson, or .json.
    """
    if not _EFAKTUR_AVAILABLE:
        typer.echo(
            "This command requires accurate-sdk with migration extras installed.",
            err=True,
        )
        raise typer.Exit(1)

    actx: AppContext = ctx.obj
    start, end = _resolve_dates(since, period)

    if not actx.quiet:
        typer.echo(f"Exporting e-Faktur records {start} → {end} → {out} …", err=True)

    rows = extract_efaktur_period(actx.client.raw, start, end)

    out.parent.mkdir(parents=True, exist_ok=True)
    with OutputSink(out, columns=_EFAKTUR_COLUMNS) as sink:
        for row in rows:
            sink.write_record(row)

    if actx.json_mode:
        print(json.dumps({"records": sink.record_count, "file": str(out)}, indent=2))
    elif not actx.quiet:
        typer.echo(f"Exported {sink.record_count} records to {out}", err=True)
