"""kctl-accurate statements — financial statement extraction.

Subcommands
-----------
opening-bs  Extract opening Balance Sheet at a given as-of date.
ytd-bs      Extract year-to-date Balance Sheet (current balances).
ytd-pl      Extract year-to-date Profit & Loss (current balances).
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

import typer

from kctl_accurate.core.callbacks import AppContext
from kctl_accurate.core.streaming import OutputSink

try:
    from accurate_sdk.migration.extractors.opening_bs import extract_opening_bs
    from accurate_sdk.migration.extractors.ytd_bs import extract_ytd_bs
    from accurate_sdk.migration.extractors.ytd_pl import extract_ytd_pl
    from accurate_sdk.migration.models import BalanceEntry

    _STATEMENTS_AVAILABLE = True
except ImportError:  # pragma: no cover
    _STATEMENTS_AVAILABLE = False

app = typer.Typer(
    help="Financial statement extraction (opening BS, YTD BS, YTD P&L).",
    no_args_is_help=True,
)

_BALANCE_COLUMNS = ["accurate_no", "name", "accurate_account_type", "balance"]


def _entry_to_dict(entry: "BalanceEntry") -> dict:  # noqa: F821
    return asdict(entry)


def _print_balance_table(entries: list, title: str, json_mode: bool) -> None:
    if json_mode:
        print(json.dumps([_entry_to_dict(e) for e in entries], indent=2, ensure_ascii=False, default=str))
        return

    from rich.console import Console
    from rich.table import Table

    console = Console()
    table = Table(
        title=f"[bold]{title} ({len(entries)} accounts)[/bold]",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("No", style="dim")
    table.add_column("Account Name")
    table.add_column("Type")
    table.add_column("Balance", justify="right")

    for entry in entries:
        table.add_row(
            entry.accurate_no,
            entry.name,
            entry.accurate_account_type,
            f"{entry.balance:,.2f}",
        )

    console.print()
    console.print(table)


def _write_to_sink(entries: list, out: Path, quiet: bool) -> int:
    out.parent.mkdir(parents=True, exist_ok=True)
    with OutputSink(out, columns=_BALANCE_COLUMNS) as sink:
        for entry in entries:
            sink.write_record(_entry_to_dict(entry))
    return sink.record_count


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command("opening-bs")
def opening_bs(
    ctx: typer.Context,
    as_of: Annotated[
        str,
        typer.Option("--as-of", help="Balance sheet date, ISO format YYYY-MM-DD.", show_default=False),
    ],
    out: Annotated[
        Path | None,
        typer.Option("--out", help="Output file (.jsonl, .json, .csv). Prints table if omitted."),
    ] = None,
) -> None:
    """Extract opening Balance Sheet at a specific historical date.

    Pulls per-account balances from Accurate's balance-sheet report at
    AS-OF date, joined with the chart of accounts for account type metadata.
    """
    if not _STATEMENTS_AVAILABLE:
        typer.echo(
            "This command requires accurate-sdk with migration extras installed.",
            err=True,
        )
        raise typer.Exit(1)

    from datetime import date

    try:
        as_of_date = date.fromisoformat(as_of)
    except ValueError:
        typer.echo(f"--as-of must be YYYY-MM-DD format, got: {as_of!r}", err=True)
        raise typer.Exit(2)

    actx: AppContext = ctx.obj

    if not actx.quiet:
        typer.echo(f"Extracting opening BS as of {as_of_date} …", err=True)

    entries = extract_opening_bs(actx.client.raw, as_of_date)

    if out is not None:
        count = _write_to_sink(entries, out, actx.quiet)
        if actx.json_mode:
            print(json.dumps({"records": count, "file": str(out)}, indent=2))
        elif not actx.quiet:
            typer.echo(f"Wrote {count} accounts to {out}", err=True)
    else:
        _print_balance_table(entries, f"Opening BS — {as_of_date}", actx.json_mode)


@app.command("ytd-bs")
def ytd_bs(
    ctx: typer.Context,
    out: Annotated[
        Path | None,
        typer.Option("--out", help="Output file (.jsonl, .json, .csv). Prints table if omitted."),
    ] = None,
) -> None:
    """Extract year-to-date Balance Sheet (current account balances).

    Returns all BS-type leaf accounts with non-zero current balance from
    Accurate's general ledger account list.
    """
    if not _STATEMENTS_AVAILABLE:
        typer.echo(
            "This command requires accurate-sdk with migration extras installed.",
            err=True,
        )
        raise typer.Exit(1)

    actx: AppContext = ctx.obj

    if not actx.quiet:
        typer.echo("Extracting YTD Balance Sheet …", err=True)

    entries = extract_ytd_bs(actx.client.raw)

    if out is not None:
        count = _write_to_sink(entries, out, actx.quiet)
        if actx.json_mode:
            print(json.dumps({"records": count, "file": str(out)}, indent=2))
        elif not actx.quiet:
            typer.echo(f"Wrote {count} accounts to {out}", err=True)
    else:
        _print_balance_table(entries, "YTD Balance Sheet", actx.json_mode)


@app.command("ytd-pl")
def ytd_pl(
    ctx: typer.Context,
    out: Annotated[
        Path | None,
        typer.Option("--out", help="Output file (.jsonl, .json, .csv). Prints table if omitted."),
    ] = None,
) -> None:
    """Extract year-to-date Profit & Loss (current account balances).

    Returns all P&L-type leaf accounts with non-zero current balance from
    Accurate's general ledger account list.
    """
    if not _STATEMENTS_AVAILABLE:
        typer.echo(
            "This command requires accurate-sdk with migration extras installed.",
            err=True,
        )
        raise typer.Exit(1)

    actx: AppContext = ctx.obj

    if not actx.quiet:
        typer.echo("Extracting YTD Profit & Loss …", err=True)

    entries = extract_ytd_pl(actx.client.raw)

    if out is not None:
        count = _write_to_sink(entries, out, actx.quiet)
        if actx.json_mode:
            print(json.dumps({"records": count, "file": str(out)}, indent=2))
        elif not actx.quiet:
            typer.echo(f"Wrote {count} accounts to {out}", err=True)
    else:
        _print_balance_table(entries, "YTD Profit & Loss", actx.json_mode)
