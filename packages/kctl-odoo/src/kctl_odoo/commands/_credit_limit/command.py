"""Credit limit proposal command — entrypoint and orchestration.

Implements `kctl-odoo partners credit-limit-proposal`. See
docs/superpowers/specs/2026-04-29-credit-limit-proposal-design.md.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from kctl_odoo.core.callbacks import AppContext


def credit_limit_proposal(
    ctx: typer.Context,
    company_type: Annotated[str, typer.Option("--company-type", help="res.company company-type filter")] = "trading",
    coverage: Annotated[float, typer.Option("--coverage", help="Multiplier on avg monthly sales")] = 1.5,
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Output xlsx path"),
    ] = None,
    ar_tolerance_rel: Annotated[
        float, typer.Option("--ar-tolerance-rel", help="AR aging parity rel tolerance")
    ] = 0.001,
    ar_tolerance_abs: Annotated[
        float, typer.Option("--ar-tolerance-abs", help="AR aging parity abs tolerance (IDR)")
    ] = 100_000.0,
    insufficient_min_invoices: Annotated[
        int,
        typer.Option(
            "--insufficient-min-invoices",
            help="Min settled invoice count before computing a proposal",
        ),
    ] = 3,
    overdue_review_days: Annotated[
        int,
        typer.Option(
            "--overdue-review-days",
            help="Open invoice days-overdue threshold to flag REVIEW_REQUIRED",
        ),
    ] = 120,
    strict: Annotated[bool, typer.Option("--strict/--no-strict", help="Halt if any company NOT_READY")] = False,
) -> None:
    """Propose credit limits for trading-company customers based on average sales."""
    actx: AppContext = ctx.obj
    actx.output.info("credit-limit-proposal: stub — implementation pending")
    raise typer.Exit(code=0)
