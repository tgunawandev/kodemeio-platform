"""kctl-accurate validate — pre-migration data quality checks.

Subcommands
-----------
nsfp    Check for duplicate NSFP (faktur pajak) numbers across open AR/AP invoices.
pph     Check PPh withholding consistency (requires pre-aggregated Odoo totals).
ar-ap   Check AR/AP open-balance parity (requires pre-aggregated Odoo balances).

Notes
-----
``validate nsfp`` fetches open AR and AP invoices from Accurate and runs the
blocking duplicate-NSFP check.  It only needs the AccurateClient.

``validate pph`` and ``validate ar-ap`` are post-migration checks that compare
Accurate totals against Odoo totals.  They require pre-aggregated balance dicts
from both sides, which are computed inside the Odoo addon
(accurate_integration) — not from the Accurate API alone.  These commands
accept JSON files (produced by the Odoo addon) and run the comparison.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated

import typer

from kctl_accurate.core.callbacks import AppContext

try:
    from accurate_sdk.migration.extractors.ar_open import extract_open_ar
    from accurate_sdk.migration.extractors.ap_open import extract_open_ap
    from accurate_sdk.migration.validators.pre import PreCheckResult, check_nsfp_uniqueness
    from accurate_sdk.migration.validators.post import (
        PostCheckResult,
        check_pph_expected_consistency,
        check_ar_ap_reconciliation,
    )

    _VALIDATORS_AVAILABLE = True
except ImportError:  # pragma: no cover
    _VALIDATORS_AVAILABLE = False

app = typer.Typer(
    help="Pre/post-migration data quality checks.",
    no_args_is_help=True,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _exit_pre(result: "PreCheckResult", json_mode: bool) -> None:  # noqa: F821
    """Print PreCheckResult and exit with 0 (OK) or 1 (FAIL)."""
    issues = result.errors + result.warnings
    if json_mode:
        print(
            json.dumps(
                {
                    "status": "fail" if result.is_blocking else "ok",
                    "issues": issues,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        raise typer.Exit(1 if result.is_blocking else 0)

    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    console = Console()
    if not issues:
        console.print(Panel("[bold green]OK[/bold green] — no duplicate NSFPs found."))
        raise typer.Exit(0)

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Issue")
    for msg in issues:
        colour = "red" if msg in result.errors else "yellow"
        table.add_row(f"[{colour}]{msg}[/{colour}]")

    label = "red" if result.is_blocking else "yellow"
    title = f"[bold {label}]FAIL ({len(issues)} issue{'s' if len(issues) != 1 else ''})[/bold {label}]"
    console.print(Panel(table, title=title))
    raise typer.Exit(1 if result.is_blocking else 0)


def _exit_post(result: "PostCheckResult", json_mode: bool, check_name: str) -> None:  # noqa: F821
    """Print PostCheckResult and exit with 0 (OK) or 1 (FAIL)."""
    passed = result.passed
    if json_mode:
        issues = []
        for m in result.mismatched:
            issues.append(
                {
                    "code": m.code,
                    "accurate": m.accurate_balance,
                    "odoo": m.odoo_balance,
                    "delta": m.delta,
                }
            )
        for code in result.unmatched_in_odoo:
            issues.append({"code": code, "reason": "missing_in_odoo"})
        for code in result.unmatched_in_accurate:
            issues.append({"code": code, "reason": "missing_in_accurate"})
        print(
            json.dumps(
                {"status": "ok" if passed else "fail", "issues": issues},
                indent=2,
                ensure_ascii=False,
            )
        )
        raise typer.Exit(0 if passed else 1)

    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    console = Console()
    if passed:
        console.print(
            Panel(f"[bold green]OK[/bold green] — {check_name} parity confirmed ({result.matched_count} matched).")
        )
        raise typer.Exit(0)

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Code / Partner")
    table.add_column("Accurate", justify="right")
    table.add_column("Odoo", justify="right")
    table.add_column("Delta", justify="right")

    for m in result.mismatched:
        table.add_row(m.code, f"{m.accurate_balance:,.2f}", f"{m.odoo_balance:,.2f}", f"[red]{m.delta:+,.2f}[/red]")
    for code in result.unmatched_in_odoo:
        table.add_row(code, "—", "[yellow]missing[/yellow]", "—")
    for code in result.unmatched_in_accurate:
        table.add_row(code, "[yellow]missing[/yellow]", "—", "—")

    n = len(result.mismatched) + len(result.unmatched_in_odoo) + len(result.unmatched_in_accurate)
    console.print(Panel(table, title=f"[bold red]FAIL ({n} issue{'s' if n != 1 else ''})[/bold red]"))
    raise typer.Exit(1)


def _load_totals_json(path: Path, flag: str) -> dict:
    """Load a JSON file containing a dict of int-keyed totals."""
    if not path.exists():
        typer.echo(f"{flag}: file not found: {path}", err=True)
        raise typer.Exit(2)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        typer.echo(f"{flag}: invalid JSON — {exc}", err=True)
        raise typer.Exit(2)
    if not isinstance(raw, dict):
        typer.echo(f"{flag}: expected a JSON object (dict), got {type(raw).__name__}", err=True)
        raise typer.Exit(2)
    # Keys are partner_id ints in JSON; cast back
    from decimal import Decimal

    return {int(k): Decimal(str(v)) for k, v in raw.items()}


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command("nsfp")
def validate_nsfp(
    ctx: typer.Context,
) -> None:
    """Check for duplicate NSFP numbers across open AR/AP invoices.

    Fetches all open AR invoices and all open AP invoices from Accurate,
    then flags any faktur-pajak number (NSFP) used by more than one invoice.
    DJP requires each NSFP to be unique; duplicates must be resolved in
    Accurate before migration.

    Exit 0 when clean, exit 1 when duplicates are found.
    """
    if not _VALIDATORS_AVAILABLE:
        typer.echo(
            "This command requires accurate-sdk with migration extras installed.",
            err=True,
        )
        raise typer.Exit(1)

    actx: AppContext = ctx.obj

    if not actx.quiet:
        typer.echo("Fetching open AR invoices …", err=True)
    ar_invoices = extract_open_ar(actx.client.raw)

    if not actx.quiet:
        typer.echo("Fetching open AP invoices …", err=True)
    ap_invoices = extract_open_ap(actx.client.raw)

    all_invoices = ar_invoices + ap_invoices
    if not actx.quiet:
        typer.echo(f"Checking {len(all_invoices)} invoices for duplicate NSFPs …", err=True)

    result = PreCheckResult()
    check_nsfp_uniqueness(all_invoices, result)
    _exit_pre(result, actx.json_mode)


@app.command("pph")
def validate_pph(
    ctx: typer.Context,
    accurate_totals: Annotated[
        Path,
        typer.Option(
            "--accurate-totals",
            help=(
                "JSON file: {partner_id: total_pph_decimal}. "
                "Produced by the accurate_integration Odoo addon's "
                "action_export_pph_totals helper."
            ),
            show_default=False,
        ),
    ],
    odoo_totals: Annotated[
        Path,
        typer.Option(
            "--odoo-totals",
            help=(
                "JSON file: {partner_id: total_pph_decimal}. "
                "SELECT partner_id, SUM(x_pph_expected_amount) FROM account_move "
                "WHERE move_type IN ('out_invoice','in_invoice') GROUP BY partner_id"
            ),
            show_default=False,
        ),
    ],
    tolerance: Annotated[
        float,
        typer.Option("--tolerance", help="Absolute tolerance per partner (IDR). Default 0.01."),
    ] = 0.01,
) -> None:
    """Check PPh withholding consistency (post-migration).

    Compares per-partner Σ(x_pph_expected_amount) from Odoo against
    Σ(witholdingTaxAmount) from Accurate.  Both sides must be pre-aggregated
    by the accurate_integration Odoo addon and exported to JSON files.

    Exit 0 when all partners match within tolerance, exit 1 on any mismatch.
    """
    if not _VALIDATORS_AVAILABLE:
        typer.echo(
            "This command requires accurate-sdk with migration extras installed.",
            err=True,
        )
        raise typer.Exit(1)

    actx: AppContext = ctx.obj

    acc = _load_totals_json(accurate_totals, "--accurate-totals")
    odoo = _load_totals_json(odoo_totals, "--odoo-totals")

    from accurate_sdk.migration.validators.post import PostCheckResult

    result = PostCheckResult()
    check_pph_expected_consistency(acc, odoo, result, tolerance=tolerance)
    _exit_post(result, actx.json_mode, "PPh expected")


@app.command("ar-ap")
def validate_ar_ap(
    ctx: typer.Context,
    accurate_balances: Annotated[
        Path,
        typer.Option(
            "--accurate-balances",
            help=(
                "JSON file: {partner_id: net_open_balance_decimal}. "
                "Produced by accurate_integration Odoo addon's "
                "action_export_ar_ap_balances helper."
            ),
            show_default=False,
        ),
    ],
    odoo_balances: Annotated[
        Path,
        typer.Option(
            "--odoo-balances",
            help=(
                "JSON file: {partner_id: net_open_balance_decimal}. "
                "SELECT partner_id, SUM(amount_residual) FROM account_move_line "
                "WHERE account_id IN (AR/AP accounts) GROUP BY partner_id"
            ),
            show_default=False,
        ),
    ],
    tolerance: Annotated[
        float,
        typer.Option("--tolerance", help="Absolute tolerance per partner (IDR). Default 0.01."),
    ] = 0.01,
) -> None:
    """Check AR/AP open-balance parity (post-migration).

    Compares per-partner net open balances between Accurate and Odoo.
    A mismatch indicates dropped or duplicated invoice/payment records.

    Both sides must be pre-aggregated by the accurate_integration Odoo addon
    and exported to JSON files before running this command.

    Exit 0 when all partners match within tolerance, exit 1 on any mismatch.
    """
    if not _VALIDATORS_AVAILABLE:
        typer.echo(
            "This command requires accurate-sdk with migration extras installed.",
            err=True,
        )
        raise typer.Exit(1)

    actx: AppContext = ctx.obj

    acc = _load_totals_json(accurate_balances, "--accurate-balances")
    odoo = _load_totals_json(odoo_balances, "--odoo-balances")

    from accurate_sdk.migration.validators.post import PostCheckResult

    result = PostCheckResult()
    check_ar_ap_reconciliation(acc, odoo, result, tolerance=tolerance)
    _exit_post(result, actx.json_mode, "AR/AP reconciliation")
