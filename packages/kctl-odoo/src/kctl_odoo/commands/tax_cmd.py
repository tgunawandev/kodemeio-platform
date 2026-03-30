"""Tax reporting and compliance commands — Indonesian PPN/PPh."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

import typer

from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.exceptions import RPCError
from kctl_odoo.core.utils import check_module_installed

app = typer.Typer(help="Tax reporting and compliance (Indonesian PPN/PPh).")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _m2o_name(val: object) -> str:
    """Extract display name from an M2O field value ([id, name] or False)."""
    if isinstance(val, list):
        return str(val[1])
    return str(val or "")


def _fmt_amount(amount: float) -> str:
    """Format a monetary amount with thousands separator."""
    if amount >= 0:
        return f"{amount:,.2f}"
    return f"-{abs(amount):,.2f}"


def _default_date_range() -> tuple[str, str]:
    """Return (first_day, last_day) of the previous month as YYYY-MM-DD strings."""
    today = datetime.now(tz=UTC).date()
    first_this_month = today.replace(day=1)
    last_prev = first_this_month - timedelta(days=1)
    first_prev = last_prev.replace(day=1)
    return first_prev.strftime("%Y-%m-%d"), last_prev.strftime("%Y-%m-%d")


def _parse_period(period: str) -> tuple[str, str]:
    """Parse a YYYY-MM period string into (first_day, last_day)."""
    try:
        dt = datetime.strptime(period, "%Y-%m")
    except ValueError:
        raise typer.BadParameter(f"Invalid period format: {period}. Use YYYY-MM.") from None
    first_day = dt.replace(day=1)
    # Last day: go to next month, subtract 1 day
    if dt.month == 12:
        next_month = dt.replace(year=dt.year + 1, month=1, day=1)
    else:
        next_month = dt.replace(month=dt.month + 1, day=1)
    last_day = next_month - timedelta(days=1)
    return first_day.strftime("%Y-%m-%d"), last_day.strftime("%Y-%m-%d")


# ===================================================================
# PPN SUMMARY
# ===================================================================


@app.command("ppn-summary")
def ppn_summary(
    ctx: typer.Context,
    date_from: Annotated[str | None, typer.Option("--date-from", help="Start date (YYYY-MM-DD)")] = None,
    date_to: Annotated[str | None, typer.Option("--date-to", help="End date (YYYY-MM-DD)")] = None,
) -> None:
    """PPN (VAT) summary — output PPN, input PPN, and net amount.

    Queries posted invoices and bills within the date range and aggregates
    tax line amounts.  Defaults to the current month if no dates given.

    Examples:
        kctl-odoo tax ppn-summary
        kctl-odoo tax ppn-summary --date-from 2026-01-01 --date-to 2026-03-31
        kctl-odoo tax ppn-summary --json
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not date_from or not date_to:
        d_from, d_to = _default_date_range()
        date_from = date_from or d_from
        date_to = date_to or d_to

    # Fetch posted invoices/bills with tax lines
    domain = [
        ("state", "=", "posted"),
        ("date", ">=", date_from),
        ("date", "<=", date_to),
        ("move_type", "in", ["out_invoice", "out_refund", "in_invoice", "in_refund"]),
    ]

    try:
        moves = c.search_read(
            "account.move",
            domain=domain,
            fields=["id", "move_type", "amount_tax"],
            limit=0,
        )
    except RPCError as e:
        out.error(f"Failed to query invoices: {e}")
        raise typer.Exit(1) from e

    output_ppn = 0.0
    input_ppn = 0.0

    for m in moves:
        tax_amt = m.get("amount_tax", 0) or 0
        move_type = m.get("move_type", "")
        if move_type in ("out_invoice",):
            output_ppn += tax_amt
        elif move_type in ("out_refund",):
            output_ppn -= tax_amt
        elif move_type in ("in_invoice",):
            input_ppn += tax_amt
        elif move_type in ("in_refund",):
            input_ppn -= tax_amt

    net_ppn = output_ppn - input_ppn

    result = {
        "period": f"{date_from} to {date_to}",
        "output_ppn": output_ppn,
        "input_ppn": input_ppn,
        "net_ppn": net_ppn,
        "invoices_count": len(moves),
    }

    sections = [
        (
            "PPN Summary",
            [
                ("Period", f"{date_from} to {date_to}"),
                ("Invoices/Bills", str(len(moves))),
                ("PPN Keluaran (Output)", _fmt_amount(output_ppn)),
                ("PPN Masukan (Input)", _fmt_amount(input_ppn)),
                ("Net PPN (Payable)", _fmt_amount(net_ppn)),
            ],
        )
    ]

    out.detail("PPN Summary", sections, data_for_json=result)


# ===================================================================
# PPH SUMMARY
# ===================================================================


@app.command("pph-summary")
def pph_summary(
    ctx: typer.Context,
    date_from: Annotated[str | None, typer.Option("--date-from", help="Start date (YYYY-MM-DD)")] = None,
    date_to: Annotated[str | None, typer.Option("--date-to", help="End date (YYYY-MM-DD)")] = None,
) -> None:
    """PPh withholding summary — grouped by PPh account.

    Searches journal items on accounts whose name contains 'PPh' and
    aggregates balances by account.

    Examples:
        kctl-odoo tax pph-summary
        kctl-odoo tax pph-summary --date-from 2026-01-01 --date-to 2026-03-31
        kctl-odoo tax pph-summary --json
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not date_from or not date_to:
        d_from, d_to = _default_date_range()
        date_from = date_from or d_from
        date_to = date_to or d_to

    # Find PPh accounts
    try:
        pph_accounts = c.search_read(
            "account.account",
            domain=[("name", "ilike", "PPh")],
            fields=["id", "code", "name"],
            limit=0,
        )
    except RPCError as e:
        out.error(f"Failed to search PPh accounts: {e}")
        raise typer.Exit(1) from e

    if not pph_accounts:
        out.info("No PPh accounts found in the chart of accounts.")
        if actx.json_mode:
            out.raw_json([])
        return

    acct_ids = [a["id"] for a in pph_accounts]
    acct_map = {a["id"]: a for a in pph_accounts}

    # Fetch move lines on PPh accounts
    try:
        lines = c.search_read(
            "account.move.line",
            domain=[
                ("account_id", "in", acct_ids),
                ("date", ">=", date_from),
                ("date", "<=", date_to),
                ("parent_state", "=", "posted"),
            ],
            fields=["account_id", "debit", "credit"],
            limit=0,
        )
    except RPCError as e:
        out.error(f"Failed to query move lines: {e}")
        raise typer.Exit(1) from e

    # Aggregate by account
    totals: dict[int, float] = {}
    for ln in lines:
        acct = ln.get("account_id")
        acct_id = acct[0] if isinstance(acct, list) else acct
        balance = (ln.get("credit", 0) or 0) - (ln.get("debit", 0) or 0)
        totals[acct_id] = totals.get(acct_id, 0) + balance

    rows: list[list[str]] = []
    json_data: list[dict] = []
    grand_total = 0.0
    for acct_id, total in sorted(totals.items(), key=lambda x: acct_map.get(x[0], {}).get("code", "")):
        acct_info = acct_map.get(acct_id, {})
        grand_total += total
        rows.append(
            [
                acct_info.get("code", ""),
                acct_info.get("name", ""),
                _fmt_amount(total),
            ]
        )
        json_data.append(
            {
                "account_code": acct_info.get("code"),
                "account_name": acct_info.get("name"),
                "total": total,
            }
        )

    json_data.append({"account_code": "", "account_name": "TOTAL", "total": grand_total})

    out.table(
        f"PPh Withholding Summary ({date_from} to {date_to})",
        [("Code", "cyan"), ("Account", ""), ("Total", "")],
        rows + [["", "[bold]TOTAL[/bold]", f"[bold]{_fmt_amount(grand_total)}[/bold]"]],
        data_for_json=json_data,
    )


# ===================================================================
# INVOICES WITH TAX
# ===================================================================


@app.command("invoices")
def invoices_with_tax(
    ctx: typer.Context,
    invoice_type: Annotated[
        str | None, typer.Option("--type", "-t", help="Filter: out (customer invoices), in (vendor bills)")
    ] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List posted invoices that have tax lines.

    Examples:
        kctl-odoo tax invoices
        kctl-odoo tax invoices --type out --limit 20
        kctl-odoo tax invoices --type in --json
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    type_map = {
        "out": ["out_invoice", "out_refund"],
        "in": ["in_invoice", "in_refund"],
    }

    domain: list = [
        ("state", "=", "posted"),
        ("amount_tax", "!=", 0),
    ]
    if invoice_type:
        move_types = type_map.get(invoice_type)
        if not move_types:
            out.error(f"Invalid type '{invoice_type}'. Use 'out' or 'in'.")
            raise typer.Exit(1)
        domain.append(("move_type", "in", move_types))
    else:
        domain.append(("move_type", "in", ["out_invoice", "out_refund", "in_invoice", "in_refund"]))

    try:
        records = c.search_read(
            "account.move",
            domain=domain,
            fields=["name", "partner_id", "amount_untaxed", "amount_tax", "amount_total", "move_type"],
            limit=limit,
            order="date desc",
        )
    except RPCError as e:
        out.error(f"Failed to query invoices: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.info("No invoices with tax found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows: list[list[str]] = []
    json_data: list[dict] = []
    for r in records:
        rows.append(
            [
                r.get("name", ""),
                _m2o_name(r.get("partner_id")),
                _fmt_amount(r.get("amount_untaxed", 0)),
                _fmt_amount(r.get("amount_tax", 0)),
                _fmt_amount(r.get("amount_total", 0)),
                r.get("move_type", ""),
            ]
        )
        json_data.append(
            {
                "name": r.get("name"),
                "partner": _m2o_name(r.get("partner_id")),
                "amount_untaxed": r.get("amount_untaxed", 0),
                "amount_tax": r.get("amount_tax", 0),
                "amount_total": r.get("amount_total", 0),
                "move_type": r.get("move_type"),
            }
        )

    out.table(
        f"Invoices with Tax ({len(records)})",
        [
            ("Number", "cyan"),
            ("Partner", ""),
            ("Untaxed", ""),
            ("Tax", ""),
            ("Total", ""),
            ("Type", "dim"),
        ],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# TAX REPORT (MONTHLY)
# ===================================================================


@app.command("report")
def tax_report(
    ctx: typer.Context,
    period: Annotated[
        str | None, typer.Option("--period", "-p", help="Period as YYYY-MM (default: last month)")
    ] = None,
) -> None:
    """Monthly tax summary combining PPN + PPh.

    Shows PPN Keluaran, PPN Masukan, Net PPN, and PPh breakdown by account type.
    Defaults to last month.

    Examples:
        kctl-odoo tax report
        kctl-odoo tax report --period 2026-02
        kctl-odoo tax report --json
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if period:
        try:
            date_from, date_to = _parse_period(period)
        except typer.BadParameter as e:
            out.error(str(e))
            raise typer.Exit(1) from e
    else:
        date_from, date_to = _default_date_range()

    # --- PPN section ---
    try:
        moves = c.search_read(
            "account.move",
            domain=[
                ("state", "=", "posted"),
                ("date", ">=", date_from),
                ("date", "<=", date_to),
                ("move_type", "in", ["out_invoice", "out_refund", "in_invoice", "in_refund"]),
            ],
            fields=["id", "move_type", "amount_tax"],
            limit=0,
        )
    except RPCError as e:
        out.error(f"Failed to query invoices for PPN: {e}")
        raise typer.Exit(1) from e

    output_ppn = 0.0
    input_ppn = 0.0
    for m in moves:
        tax_amt = m.get("amount_tax", 0) or 0
        move_type = m.get("move_type", "")
        if move_type == "out_invoice":
            output_ppn += tax_amt
        elif move_type == "out_refund":
            output_ppn -= tax_amt
        elif move_type == "in_invoice":
            input_ppn += tax_amt
        elif move_type == "in_refund":
            input_ppn -= tax_amt

    net_ppn = output_ppn - input_ppn

    # --- PPh section ---
    try:
        pph_accounts = c.search_read(
            "account.account",
            domain=[("name", "ilike", "PPh")],
            fields=["id", "code", "name"],
            limit=0,
        )
    except RPCError as e:
        out.error(f"Failed to search PPh accounts: {e}")
        raise typer.Exit(1) from e

    pph_totals: list[dict] = []
    pph_grand = 0.0
    if pph_accounts:
        acct_ids = [a["id"] for a in pph_accounts]
        acct_map = {a["id"]: a for a in pph_accounts}

        try:
            lines = c.search_read(
                "account.move.line",
                domain=[
                    ("account_id", "in", acct_ids),
                    ("date", ">=", date_from),
                    ("date", "<=", date_to),
                    ("parent_state", "=", "posted"),
                ],
                fields=["account_id", "debit", "credit"],
                limit=0,
            )
        except RPCError as e:
            out.error(f"Failed to query PPh lines: {e}")
            raise typer.Exit(1) from e

        totals_by_acct: dict[int, float] = {}
        for ln in lines:
            acct = ln.get("account_id")
            acct_id = acct[0] if isinstance(acct, list) else acct
            balance = (ln.get("credit", 0) or 0) - (ln.get("debit", 0) or 0)
            totals_by_acct[acct_id] = totals_by_acct.get(acct_id, 0) + balance

        for acct_id, total in sorted(totals_by_acct.items(), key=lambda x: acct_map.get(x[0], {}).get("code", "")):
            info = acct_map.get(acct_id, {})
            pph_grand += total
            pph_totals.append({"code": info.get("code", ""), "name": info.get("name", ""), "total": total})

    result = {
        "period": f"{date_from} to {date_to}",
        "ppn_keluaran": output_ppn,
        "ppn_masukan": input_ppn,
        "net_ppn": net_ppn,
        "pph_items": pph_totals,
        "pph_total": pph_grand,
    }

    sections = [
        (
            "PPN (Value Added Tax)",
            [
                ("PPN Keluaran (Output)", _fmt_amount(output_ppn)),
                ("PPN Masukan (Input)", _fmt_amount(input_ppn)),
                ("Net PPN (Payable)", _fmt_amount(net_ppn)),
            ],
        ),
        (
            "PPh (Income Tax Withholding)",
            [(f"{p['code']} {p['name']}", _fmt_amount(p["total"])) for p in pph_totals]
            + [("TOTAL PPh", _fmt_amount(pph_grand))],
        )
        if pph_totals
        else (
            "PPh (Income Tax Withholding)",
            [("No PPh accounts found", "-")],
        ),
    ]

    out.detail(f"Monthly Tax Report ({date_from} to {date_to})", sections, data_for_json=result)


# ===================================================================
# WITHHOLDINGS
# ===================================================================


@app.command("withholdings")
def withholdings(
    ctx: typer.Context,
    pph_type: Annotated[
        str | None, typer.Option("--type", "-t", help="PPh type filter: pph23, pph21, pph26, pph4")
    ] = None,
    date_from: Annotated[str | None, typer.Option("--date-from", help="Start date (YYYY-MM-DD)")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List withholding tax entries from PPh accounts.

    Searches journal items on accounts whose name matches the PPh type.

    Examples:
        kctl-odoo tax withholdings
        kctl-odoo tax withholdings --type pph23 --date-from 2026-01-01
        kctl-odoo tax withholdings --json
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Build account search domain
    pph_filter_map = {
        "pph21": "PPh 21",
        "pph23": "PPh 23",
        "pph26": "PPh 26",
        "pph4": "PPh 4",
    }

    acct_domain: list = []
    if pph_type:
        search_term = pph_filter_map.get(pph_type)
        if not search_term:
            out.error(f"Unknown PPh type '{pph_type}'. Use: pph21, pph23, pph26, pph4.")
            raise typer.Exit(1)
        acct_domain.append(("name", "ilike", search_term))
    else:
        acct_domain.append(("name", "ilike", "PPh"))

    try:
        pph_accounts = c.search_read(
            "account.account",
            domain=acct_domain,
            fields=["id", "code", "name"],
            limit=0,
        )
    except RPCError as e:
        out.error(f"Failed to search PPh accounts: {e}")
        raise typer.Exit(1) from e

    if not pph_accounts:
        out.info("No matching PPh accounts found.")
        if actx.json_mode:
            out.raw_json([])
        return

    acct_ids = [a["id"] for a in pph_accounts]

    line_domain: list = [
        ("account_id", "in", acct_ids),
        ("parent_state", "=", "posted"),
    ]
    if date_from:
        line_domain.append(("date", ">=", date_from))

    try:
        records = c.search_read(
            "account.move.line",
            domain=line_domain,
            fields=["date", "partner_id", "debit", "credit", "account_id"],
            limit=limit,
            order="date desc",
        )
    except RPCError as e:
        out.error(f"Failed to query withholding lines: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.info("No withholding entries found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows: list[list[str]] = []
    json_data: list[dict] = []
    for r in records:
        amount = (r.get("credit", 0) or 0) - (r.get("debit", 0) or 0)
        rows.append(
            [
                str(r.get("date", "")),
                _m2o_name(r.get("partner_id")),
                _fmt_amount(amount),
                _m2o_name(r.get("account_id")),
            ]
        )
        json_data.append(
            {
                "date": r.get("date"),
                "partner": _m2o_name(r.get("partner_id")),
                "amount": amount,
                "account": _m2o_name(r.get("account_id")),
            }
        )

    out.table(
        f"Withholding Tax Entries ({len(records)})",
        [("Date", "dim"), ("Partner", ""), ("Amount", ""), ("Account", "")],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# FAKTUR LIST
# ===================================================================


@app.command("faktur")
def faktur_list(
    ctx: typer.Context,
    state: Annotated[str | None, typer.Option("--state", "-s", help="Filter by state")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List Faktur Pajak records (tax_management module).

    Requires the ``tax_management`` module with the ``faktur.pajak`` model.
    Returns gracefully if the module is not installed.

    Examples:
        kctl-odoo tax faktur-list
        kctl-odoo tax faktur-list --state posted --limit 20
        kctl-odoo tax faktur-list --json
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not check_module_installed(c, "tax_management"):
        out.info("Module 'tax_management' is not installed — Faktur Pajak not available.")
        if actx.json_mode:
            out.raw_json([])
        return

    domain: list = []
    if state:
        domain.append(("state", "=", state))

    from kctl_odoo.core.field_helpers import safe_fields

    fields = safe_fields(c, "faktur.pajak", ["name", "buyer_name", "create_date", "state", "company_id"])

    try:
        records = c.search_read(
            "faktur.pajak",
            domain=domain,
            fields=fields,
            limit=limit,
            order="create_date desc",
        )
    except RPCError as e:
        out.error(f"Failed to list Faktur Pajak: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.info("No Faktur Pajak records found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows: list[list[str]] = []
    json_data: list[dict] = []
    for r in records:
        rows.append(
            [
                str(r["id"]),
                r.get("name", ""),
                r.get("buyer_name", "") or _m2o_name(r.get("partner_id")),
                str(r.get("create_date", "")),
                r.get("state", ""),
            ]
        )
        json_data.append(
            {
                "id": r["id"],
                "name": r.get("name"),
                "buyer": r.get("buyer_name", ""),
                "date": r.get("create_date"),
                "state": r.get("state"),
            }
        )

    out.table(
        f"Faktur Pajak ({len(records)})",
        [
            ("ID", "cyan"),
            ("Number", ""),
            ("Buyer", ""),
            ("Date", "dim"),
            ("State", ""),
        ],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# TAX ACCOUNTS
# ===================================================================


@app.command("accounts")
def tax_accounts(
    ctx: typer.Context,
) -> None:
    """List all tax-related GL accounts.

    Searches accounts whose name contains 'tax', 'ppn', 'pph', or 'pajak'.

    Examples:
        kctl-odoo tax tax-accounts
        kctl-odoo tax tax-accounts --json
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    domain = [
        "|",
        "|",
        "|",
        ("name", "ilike", "tax"),
        ("name", "ilike", "ppn"),
        ("name", "ilike", "pph"),
        ("name", "ilike", "pajak"),
    ]

    try:
        records = c.search_read(
            "account.account",
            domain=domain,
            fields=["id", "code", "name"],
            limit=0,
            order="code",
        )
    except RPCError as e:
        out.error(f"Failed to list tax accounts: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.info("No tax-related accounts found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows: list[list[str]] = []
    json_data: list[dict] = []
    for r in records:
        rows.append(
            [
                str(r.get("code") or ""),
                str(r.get("name") or ""),
            ]
        )
        json_data.append(
            {
                "code": r.get("code"),
                "name": r.get("name"),
            }
        )

    out.table(
        f"Tax-Related Accounts ({len(records)})",
        [("Code", "cyan"), ("Name", "")],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# CORETAX DJP STATUS
# ===================================================================


@app.command("coretax-status")
def coretax_status(ctx: typer.Context) -> None:
    """Check Coretax DJP integration status.

    Shows whether the tax_management Coretax connector is configured and
    its sync status. Requires the tax_management private module.

    Examples:
        kctl-odoo tax coretax-status
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    from kctl_odoo.core.biz_helpers import model_available

    if model_available(c, "coretax.config"):
        from kctl_odoo.core.field_helpers import safe_fields

        configs = c.search_read(
            "coretax.config",
            domain=[],
            fields=safe_fields(c, "coretax.config", ["display_name", "create_date"]),
            limit=5,
        )
        if configs:
            out.success(f"Coretax configured: {len(configs)} config(s)")
            for cfg in configs:
                out.info(f"  {cfg.get('display_name', 'Config')} (created: {cfg.get('create_date', '')})")
        else:
            out.warn("Coretax module installed but no configuration found.")
            out.info("Configure via: Odoo → Accounting → Configuration → Coretax DJP")
    else:
        # Check for system parameters
        try:
            params = c.search_read(
                "ir.config_parameter",
                domain=[("key", "ilike", "coretax")],
                fields=["key", "value"],
            )
            if params:
                out.info("Coretax system parameters found:")
                for p in params:
                    val = str(p.get("value", ""))
                    if len(val) > 40:
                        val = val[:37] + "..."
                    out.info(f"  {p['key']} = {val}")
            else:
                out.warn("No Coretax configuration found.")
                out.info("Install tax_management module and configure Coretax DJP integration.")
        except (RPCError, Exception):
            out.warn("Could not check Coretax status.")


# ===================================================================
# PPH 21 SUMMARY
# ===================================================================


@app.command("pph21-summary")
def pph21_summary(
    ctx: typer.Context,
    month: Annotated[str | None, typer.Option("--month", help="Period month (YYYY-MM)")] = None,
) -> None:
    """PPh 21 employee income tax summary.

    Shows payroll tax withholdings for a period. Requires hr_payroll
    or payroll_management module.

    Examples:
        kctl-odoo tax pph21-summary
        kctl-odoo tax pph21-summary --month 2026-03
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    from datetime import datetime

    from kctl_odoo.core.biz_helpers import model_available
    from kctl_odoo.core.field_helpers import safe_fields

    # Determine period
    if month:
        try:
            dt = datetime.strptime(month, "%Y-%m")
        except ValueError:
            out.error("Invalid month format. Use YYYY-MM (e.g. 2026-03)")
            raise typer.Exit(1)
        year, mon = dt.year, dt.month
    else:
        now = datetime.now()
        year, mon = now.year, now.month - 1
        if mon == 0:
            mon = 12
            year -= 1

    date_from = f"{year}-{mon:02d}-01"
    if mon == 12:
        date_to = f"{year + 1}-01-01"
    else:
        date_to = f"{year}-{mon + 1:02d}-01"

    # Try payslip approach
    if model_available(c, "hr.payslip"):
        payslips = c.search_read(
            "hr.payslip",
            domain=[
                ("date_from", ">=", date_from),
                ("date_to", "<", date_to),
                ("state", "=", "done"),
            ],
            fields=safe_fields(c, "hr.payslip", ["employee_id", "name", "date_from", "date_to"]),
            limit=500,
        )

        out.info(f"PPh 21 Summary for {year}-{mon:02d}")
        out.info(f"  Posted payslips: {len(payslips)}")

        # Check for PPh 21 related accounts
        pph21_accounts = c.search_read(
            "account.account",
            domain=["|", ("name", "ilike", "pph 21"), ("name", "ilike", "PPh 21")],
            fields=["id", "code", "name"],
            limit=5,
        )

        if pph21_accounts:
            for acc in pph21_accounts:
                # Sum journal items on this account in period
                try:
                    items = c.search_read(
                        "account.move.line",
                        domain=[
                            ("account_id", "=", acc["id"]),
                            ("date", ">=", date_from),
                            ("date", "<", date_to),
                            ("parent_state", "=", "posted"),
                        ],
                        fields=["credit"],
                        limit=1000,
                    )
                    total = sum(item.get("credit", 0) or 0 for item in items)
                    out.info(f"  {acc['code']} {acc['name']}: {total:,.2f}")
                except (RPCError, Exception):
                    out.info(f"  {acc['code']} {acc['name']}: (could not query)")
        else:
            out.warn("No PPh 21 accounts found. Check chart of accounts.")

        if actx.json_mode:
            out.raw_json(
                {
                    "period": f"{year}-{mon:02d}",
                    "payslips": len(payslips),
                    "pph21_accounts": [{"code": a["code"], "name": a["name"]} for a in pph21_accounts],
                }
            )
    else:
        out.warn("hr_payroll module not installed. Cannot calculate PPh 21.")
        out.info("Install hr_payroll or payroll_management for payslip-based tax reporting.")


# ===================================================================
# TAX INVOICES EXPORT
# ===================================================================


@app.command("tax-invoices-export")
def tax_invoices_export(
    ctx: typer.Context,
    invoice_type: Annotated[str, typer.Option("--type", "-t", help="Filter: out (sales) or in (purchases)")] = "out",
    date_from: Annotated[str | None, typer.Option("--date-from", help="Start date")] = None,
    date_to: Annotated[str | None, typer.Option("--date-to", help="End date")] = None,
    output: Annotated[str, typer.Option("--output", "-o", help="Output CSV file")] = "",
) -> None:
    """Export tax invoices to CSV for Coretax/e-Faktur filing.

    Exports posted invoices with tax lines to a CSV file suitable for
    Coretax DJP import.

    Examples:
        kctl-odoo tax tax-invoices-export --type out --date-from 2026-03-01 -o faktur_keluaran.csv
        kctl-odoo tax tax-invoices-export --type in --date-from 2026-03-01 -o faktur_masukan.csv
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    import csv

    from kctl_odoo.core.field_helpers import safe_fields

    move_type = "out_invoice" if invoice_type == "out" else "in_invoice"
    domain: list = [("move_type", "=", move_type), ("state", "=", "posted")]
    if date_from:
        domain.append(("invoice_date", ">=", date_from))
    if date_to:
        domain.append(("invoice_date", "<=", date_to))

    preferred = ["name", "partner_id", "invoice_date", "amount_untaxed", "amount_tax", "amount_total", "currency_id"]
    fields = safe_fields(c, "account.move", preferred)

    try:
        invoices = c.search_read("account.move", domain=domain, fields=fields, limit=5000, order="invoice_date asc")
    except RPCError as e:
        out.error(f"Failed to export: {e}")
        raise typer.Exit(1) from e

    if not invoices:
        out.info("No tax invoices found for the period.")
        return

    if not output:
        type_label = "keluaran" if invoice_type == "out" else "masukan"
        output = f"faktur_{type_label}_{date_from or 'all'}.csv"

    with open(output, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Invoice Number", "Partner", "Date", "Base Amount", "Tax Amount", "Total", "Currency"])
        for inv in invoices:
            partner = inv.get("partner_id")
            partner_name = partner[1] if isinstance(partner, list) else str(partner or "")
            currency = inv.get("currency_id")
            currency_name = currency[1] if isinstance(currency, list) else ""
            writer.writerow(
                [
                    inv.get("name", ""),
                    partner_name,
                    str(inv.get("invoice_date", "")),
                    inv.get("amount_untaxed", 0),
                    inv.get("amount_tax", 0),
                    inv.get("amount_total", 0),
                    currency_name,
                ]
            )

    out.success(f"Exported {len(invoices)} invoices to {output}")
