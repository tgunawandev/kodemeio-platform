"""Accounting commands — invoices, journal entries, payments, aging, trial balance."""

from __future__ import annotations

import contextlib
from datetime import UTC, datetime, timedelta
from typing import Annotated

import typer

from kctl_odoo.core.biz_helpers import fmt_amount, model_available, module_hint, period_domain
from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.exceptions import RPCError
from kctl_odoo.core.field_helpers import safe_fields
from kctl_odoo.core.resolve import resolve_account, resolve_journal

app = typer.Typer(help="Accounting: invoices, journal entries, payments, aging reports.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _m2o(val: object) -> str:
    """Format an M2O field value — Odoo returns [id, name] lists."""
    if isinstance(val, list):
        return str(val[1]) if len(val) > 1 else str(val[0])
    return str(val or "")


def _fmt_amount(amount: float) -> str:
    """Format a monetary amount with thousands separator."""
    if amount >= 0:
        return f"{amount:,.2f}"
    return f"-{abs(amount):,.2f}"


def _resolve(c: object, model: str, domain_field: str, value: str, label: str = "Record") -> tuple[int, str]:
    """Resolve a record by name or ID. Returns (id, display_name)."""
    if value.isdigit():
        records = c.read(model, [int(value)], ["id", "display_name"])  # type: ignore[attr-defined]
    else:
        records = c.search_read(  # type: ignore[attr-defined]
            model,
            [(domain_field, "ilike", value)],
            ["id", "display_name"],
            limit=1,
        )
    if not records:
        raise typer.BadParameter(f"{label} not found: {value}")
    return records[0]["id"], records[0].get("display_name", str(records[0]["id"]))


# ===================================================================
# READ COMMANDS
# ===================================================================


@app.command()
def invoices(
    ctx: typer.Context,
    state: Annotated[str | None, typer.Option("--state", help="Filter by state: draft, posted, paid")] = None,
    inv_type: Annotated[
        str | None, typer.Option("--type", help="Invoice type: out_invoice, in_invoice, out_refund, in_refund")
    ] = None,
    partner: Annotated[str | None, typer.Option("--partner", help="Filter by partner name (ilike)")] = None,
    date_from: Annotated[str | None, typer.Option("--date-from", help="From date (YYYY-MM-DD)")] = None,
    date_to: Annotated[str | None, typer.Option("--date-to", help="To date (YYYY-MM-DD)")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List invoices.

    Examples:
        kctl-odoo accounting invoices
        kctl-odoo accounting invoices --state posted --type out_invoice
        kctl-odoo accounting invoices --partner "Acme" --limit 10
        kctl-odoo accounting invoices --date-from 2026-01-01 --date-to 2026-03-31
        kctl-odoo accounting invoices --json
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    domain: list = [("move_type", "in", ["out_invoice", "in_invoice", "out_refund", "in_refund"])]
    if state:
        domain.append(("state", "=", state))
    if inv_type:
        domain.append(("move_type", "=", inv_type))
    if partner:
        domain.append(("partner_id.name", "ilike", partner))
    if date_from:
        domain.append(("invoice_date", ">=", date_from))
    if date_to:
        domain.append(("invoice_date", "<=", date_to))

    try:
        records = c.search_read(
            "account.move",
            domain=domain,
            fields=["id", "name", "partner_id", "invoice_date", "amount_total", "state", "move_type"],
            limit=limit,
            order="invoice_date desc, id desc",
        )
    except RPCError as e:
        out.error(f"Failed to fetch invoices: {e.detail}")
        raise typer.Exit(1) from e

    if not records:
        out.info("No invoices found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for r in records:
        rows.append(
            [
                str(r.get("name") or ""),
                _m2o(r.get("partner_id")),
                str(r.get("invoice_date") or ""),
                _fmt_amount(r.get("amount_total", 0.0)),
                str(r.get("state") or ""),
                str(r.get("move_type") or ""),
            ]
        )
        json_data.append(
            {
                "id": r["id"],
                "name": r.get("name"),
                "partner": _m2o(r.get("partner_id")),
                "date": r.get("invoice_date"),
                "amount_total": r.get("amount_total"),
                "state": r.get("state"),
                "move_type": r.get("move_type"),
            }
        )

    out.table(
        f"Invoices ({len(records)})",
        [("Number", "cyan"), ("Partner", ""), ("Date", "dim"), ("Amount", ""), ("State", ""), ("Type", "dim")],
        rows,
        data_for_json=json_data,
    )


@app.command("get-invoice")
def invoice_get(
    ctx: typer.Context,
    number: Annotated[str, typer.Argument(help="Invoice number or ID")],
) -> None:
    """Get invoice detail by number or ID.

    Shows header information and invoice lines.

    Examples:
        kctl-odoo accounting get-invoice INV/2026/0001
        kctl-odoo accounting get-invoice 42
        kctl-odoo accounting get-invoice INV/2026/0001 --json
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Resolve invoice
    domain = [("id", "=", int(number))] if number.isdigit() else [("name", "=", number)]

    try:
        records = c.search_read(
            "account.move",
            domain=domain,
            fields=[
                "id",
                "name",
                "partner_id",
                "invoice_date",
                "invoice_date_due",
                "amount_total",
                "amount_residual",
                "state",
                "move_type",
                "journal_id",
                "currency_id",
                "ref",
                "invoice_line_ids",
            ],
            limit=1,
        )
    except RPCError as e:
        out.error(f"Failed to fetch invoice: {e.detail}")
        raise typer.Exit(1) from e

    if not records:
        out.error(f"Invoice not found: {number}")
        raise typer.Exit(1)

    inv = records[0]

    # Fetch invoice lines
    line_ids = inv.get("invoice_line_ids", [])
    lines = []
    if line_ids:
        with contextlib.suppress(RPCError):
            lines = c.read(
                "account.move.line",
                line_ids,
                ["product_id", "name", "quantity", "price_unit", "price_subtotal", "tax_ids"],
            )

    # Header detail
    sections = [
        (
            "Invoice",
            [
                ("Number", inv.get("name", "")),
                ("Type", inv.get("move_type", "")),
                ("State", inv.get("state", "")),
                ("Partner", _m2o(inv.get("partner_id"))),
                ("Journal", _m2o(inv.get("journal_id"))),
                ("Currency", _m2o(inv.get("currency_id"))),
                ("Reference", str(inv.get("ref") or "")),
            ],
        ),
        (
            "Amounts",
            [
                ("Date", str(inv.get("invoice_date") or "")),
                ("Due Date", str(inv.get("invoice_date_due") or "")),
                ("Total", _fmt_amount(inv.get("amount_total", 0.0))),
                ("Amount Due", _fmt_amount(inv.get("amount_residual", 0.0))),
            ],
        ),
    ]

    json_result = {
        "id": inv["id"],
        "name": inv.get("name"),
        "move_type": inv.get("move_type"),
        "state": inv.get("state"),
        "partner": _m2o(inv.get("partner_id")),
        "journal": _m2o(inv.get("journal_id")),
        "currency": _m2o(inv.get("currency_id")),
        "ref": inv.get("ref"),
        "invoice_date": inv.get("invoice_date"),
        "invoice_date_due": inv.get("invoice_date_due"),
        "amount_total": inv.get("amount_total"),
        "amount_residual": inv.get("amount_residual"),
        "lines": [],
    }

    out.detail("Invoice Detail", sections, data_for_json=json_result if not lines else None)

    # Lines table
    if lines:
        line_rows = []
        line_json = []
        for ln in lines:
            product = _m2o(ln.get("product_id"))
            desc = (ln.get("name") or "")[:40]
            qty = ln.get("quantity", 0.0)
            price = ln.get("price_unit", 0.0)
            subtotal = ln.get("price_subtotal", 0.0)
            line_rows.append(
                [
                    product or desc,
                    f"{qty:,.2f}",
                    _fmt_amount(price),
                    _fmt_amount(subtotal),
                ]
            )
            line_json.append(
                {
                    "product": product,
                    "description": ln.get("name"),
                    "quantity": qty,
                    "price_unit": price,
                    "price_subtotal": subtotal,
                }
            )

        json_result["lines"] = line_json

        if actx.json_mode:
            out.raw_json(json_result)
        else:
            out.table(
                "Invoice Lines",
                [("Product", ""), ("Qty", ""), ("Price", ""), ("Subtotal", "")],
                line_rows,
                data_for_json=line_json,
            )
    elif actx.json_mode:
        out.raw_json(json_result)


@app.command("journal-entries")
def journal_entries(
    ctx: typer.Context,
    journal: Annotated[str | None, typer.Option("--journal", help="Journal name (ilike)")] = None,
    date_from: Annotated[str | None, typer.Option("--date-from", help="Start date (YYYY-MM-DD)")] = None,
    date_to: Annotated[str | None, typer.Option("--date-to", help="End date (YYYY-MM-DD)")] = None,
    ref: Annotated[str | None, typer.Option("--ref", help="Filter by reference (ilike)")] = None,
    partner: Annotated[str | None, typer.Option("--partner", help="Filter by partner name (ilike)")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List journal entries.

    Examples:
        kctl-odoo accounting journal-entries
        kctl-odoo accounting journal-entries --journal "Bank" --date-from 2026-01-01
        kctl-odoo accounting journal-entries --ref "INV/2026" --partner "Acme"
        kctl-odoo accounting journal-entries --json
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    domain: list = []
    if journal:
        domain.append(("journal_id.name", "ilike", journal))
    if date_from:
        domain.append(("date", ">=", date_from))
    if date_to:
        domain.append(("date", "<=", date_to))
    if ref:
        domain.append(("ref", "ilike", ref))
    if partner:
        domain.append(("partner_id.name", "ilike", partner))

    try:
        records = c.search_read(
            "account.move",
            domain=domain,
            fields=["id", "name", "journal_id", "date", "ref", "amount_total", "state"],
            limit=limit,
            order="date desc, id desc",
        )
    except RPCError as e:
        out.error(f"Failed to fetch journal entries: {e.detail}")
        raise typer.Exit(1) from e

    if not records:
        out.info("No journal entries found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for r in records:
        rows.append(
            [
                r.get("name", ""),
                _m2o(r.get("journal_id")),
                str(r.get("date") or ""),
                (r.get("ref") or "")[:30],
                _fmt_amount(r.get("amount_total", 0.0)),
                r.get("state", ""),
            ]
        )
        json_data.append(
            {
                "id": r["id"],
                "name": r.get("name"),
                "journal": _m2o(r.get("journal_id")),
                "date": r.get("date"),
                "ref": r.get("ref"),
                "amount_total": r.get("amount_total"),
                "state": r.get("state"),
            }
        )

    out.table(
        f"Journal Entries ({len(records)})",
        [("Name", "cyan"), ("Journal", ""), ("Date", "dim"), ("Reference", ""), ("Amount", ""), ("State", "")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def unreconciled(
    ctx: typer.Context,
    account: Annotated[str | None, typer.Option("--account", help="Account code filter")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """Show unreconciled journal items.

    Searches account.move.line where reconciliation is incomplete
    on reconcilable accounts.

    Examples:
        kctl-odoo accounting unreconciled
        kctl-odoo accounting unreconciled --account 1100
        kctl-odoo accounting unreconciled --json
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    domain: list = [
        ("full_reconcile_id", "=", False),
        ("account_id.reconcile", "=", True),
        ("parent_state", "=", "posted"),
    ]
    if account:
        domain.append(("account_id.code", "ilike", account))

    try:
        records = c.search_read(
            "account.move.line",
            domain=domain,
            fields=["id", "move_name", "account_id", "partner_id", "debit", "credit", "date"],
            limit=limit,
            order="date desc",
        )
    except RPCError as e:
        out.error(f"Failed to fetch unreconciled items: {e.detail}")
        raise typer.Exit(1) from e

    if not records:
        out.info("No unreconciled items found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for r in records:
        rows.append(
            [
                r.get("move_name", ""),
                _m2o(r.get("account_id")),
                _m2o(r.get("partner_id")),
                _fmt_amount(r.get("debit", 0.0)),
                _fmt_amount(r.get("credit", 0.0)),
                str(r.get("date") or ""),
            ]
        )
        json_data.append(
            {
                "id": r["id"],
                "move_name": r.get("move_name"),
                "account": _m2o(r.get("account_id")),
                "partner": _m2o(r.get("partner_id")),
                "debit": r.get("debit"),
                "credit": r.get("credit"),
                "date": r.get("date"),
            }
        )

    out.table(
        f"Unreconciled Items ({len(records)})",
        [("Entry", "cyan"), ("Account", ""), ("Partner", ""), ("Debit", ""), ("Credit", ""), ("Date", "dim")],
        rows,
        data_for_json=json_data,
    )


@app.command("aged-receivable")
def aged_receivable(
    ctx: typer.Context,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max line items to scan")] = 500,
) -> None:
    """AR aging report.

    Groups receivable balances into aging buckets:
    Current, 1-30, 31-60, 61-90, 90+ days.

    Examples:
        kctl-odoo accounting aged-receivable
        kctl-odoo accounting aged-receivable --json
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    _aged_report(c, out, actx, account_type="asset_receivable", title="Aged Receivable", limit=limit)


@app.command("aged-payable")
def aged_payable(
    ctx: typer.Context,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max line items to scan")] = 500,
) -> None:
    """AP aging report.

    Groups payable balances into aging buckets:
    Current, 1-30, 31-60, 61-90, 90+ days.

    Examples:
        kctl-odoo accounting aged-payable
        kctl-odoo accounting aged-payable --json
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    _aged_report(c, out, actx, account_type="liability_payable", title="Aged Payable", limit=limit)


def _aged_report(c: object, out: object, actx: AppContext, account_type: str, title: str, limit: int) -> None:
    """Shared logic for aged receivable/payable reports."""
    today = datetime.now(tz=UTC).date()

    domain: list = [
        ("full_reconcile_id", "=", False),
        ("account_id.account_type", "=", account_type),
        ("parent_state", "=", "posted"),
    ]

    try:
        lines = c.search_read(  # type: ignore[attr-defined]
            "account.move.line",
            domain=domain,
            fields=["id", "partner_id", "date_maturity", "date", "debit", "credit", "amount_residual"],
            limit=limit,
        )
    except RPCError as e:
        out.error(f"Failed to fetch aging data: {e.detail}")  # type: ignore[attr-defined]
        raise typer.Exit(1) from e

    buckets = {"current": 0.0, "1_30": 0.0, "31_60": 0.0, "61_90": 0.0, "90_plus": 0.0}

    for ln in lines:
        amount = ln.get("amount_residual", 0.0)
        due_str = ln.get("date_maturity") or ln.get("date")
        if not due_str:
            buckets["current"] += abs(amount)
            continue

        if isinstance(due_str, str):
            try:
                due_date = datetime.strptime(due_str, "%Y-%m-%d").date()
            except ValueError:
                buckets["current"] += abs(amount)
                continue
        else:
            due_date = due_str

        days = (today - due_date).days
        if days <= 0:
            buckets["current"] += abs(amount)
        elif days <= 30:
            buckets["1_30"] += abs(amount)
        elif days <= 60:
            buckets["31_60"] += abs(amount)
        elif days <= 90:
            buckets["61_90"] += abs(amount)
        else:
            buckets["90_plus"] += abs(amount)

    total = sum(buckets.values())

    rows = [
        ["Current", _fmt_amount(buckets["current"])],
        ["1-30 days", _fmt_amount(buckets["1_30"])],
        ["31-60 days", _fmt_amount(buckets["31_60"])],
        ["61-90 days", _fmt_amount(buckets["61_90"])],
        ["90+ days", _fmt_amount(buckets["90_plus"])],
        ["[bold]Total[/bold]", f"[bold]{_fmt_amount(total)}[/bold]"],
    ]

    json_data = [
        {"bucket": "current", "amount": buckets["current"]},
        {"bucket": "1_30", "amount": buckets["1_30"]},
        {"bucket": "31_60", "amount": buckets["31_60"]},
        {"bucket": "61_90", "amount": buckets["61_90"]},
        {"bucket": "90_plus", "amount": buckets["90_plus"]},
        {"bucket": "total", "amount": total},
    ]

    out.table(  # type: ignore[attr-defined]
        title,
        [("Bucket", ""), ("Amount", "cyan")],
        rows,
        data_for_json=json_data,
    )


@app.command("trial-balance")
def trial_balance(
    ctx: typer.Context,
    date_from: Annotated[str | None, typer.Option("--date-from", help="Start date (YYYY-MM-DD)")] = None,
    date_to: Annotated[str | None, typer.Option("--date-to", help="End date (YYYY-MM-DD)")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max accounts to return")] = 200,
) -> None:
    """Trial balance report.

    Aggregates debit/credit per account for posted journal entries
    within an optional date range.

    Examples:
        kctl-odoo accounting trial-balance
        kctl-odoo accounting trial-balance --date-from 2026-01-01 --date-to 2026-03-31
        kctl-odoo accounting trial-balance --json
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    domain: list = [("parent_state", "=", "posted")]
    if date_from:
        domain.append(("date", ">=", date_from))
    if date_to:
        domain.append(("date", "<=", date_to))

    try:
        lines = c.search_read(
            "account.move.line",
            domain=domain,
            fields=["account_id", "debit", "credit"],
            limit=0,  # fetch all to aggregate
        )
    except RPCError as e:
        out.error(f"Failed to fetch trial balance data: {e.detail}")
        raise typer.Exit(1) from e

    if not lines:
        out.info("No posted journal items found for the given period.")
        if actx.json_mode:
            out.raw_json([])
        return

    # Aggregate per account
    accounts: dict[int, dict] = {}
    for ln in lines:
        acct = ln.get("account_id")
        if not acct:
            continue
        acct_id = acct[0] if isinstance(acct, list) else acct
        acct_name = acct[1] if isinstance(acct, list) else str(acct)

        if acct_id not in accounts:
            accounts[acct_id] = {"name": acct_name, "debit": 0.0, "credit": 0.0}
        accounts[acct_id]["debit"] += ln.get("debit", 0.0)
        accounts[acct_id]["credit"] += ln.get("credit", 0.0)

    # Sort by account name (which includes code in Odoo)
    sorted_accounts = sorted(accounts.values(), key=lambda a: a["name"])

    # Limit output
    display = sorted_accounts[:limit]

    rows = []
    json_data = []
    total_debit = 0.0
    total_credit = 0.0
    for a in display:
        balance = a["debit"] - a["credit"]
        total_debit += a["debit"]
        total_credit += a["credit"]
        rows.append(
            [
                a["name"],
                _fmt_amount(a["debit"]),
                _fmt_amount(a["credit"]),
                _fmt_amount(balance),
            ]
        )
        json_data.append(
            {
                "account": a["name"],
                "debit": round(a["debit"], 2),
                "credit": round(a["credit"], 2),
                "balance": round(balance, 2),
            }
        )

    # Totals row
    rows.append(
        [
            "[bold]Total[/bold]",
            f"[bold]{_fmt_amount(total_debit)}[/bold]",
            f"[bold]{_fmt_amount(total_credit)}[/bold]",
            f"[bold]{_fmt_amount(total_debit - total_credit)}[/bold]",
        ]
    )
    json_data.append(
        {
            "account": "TOTAL",
            "debit": round(total_debit, 2),
            "credit": round(total_credit, 2),
            "balance": round(total_debit - total_credit, 2),
        }
    )

    period_label = ""
    if date_from or date_to:
        period_label = f" ({date_from or '...'} to {date_to or '...'})"

    out.table(
        f"Trial Balance{period_label}",
        [("Account", ""), ("Debit", ""), ("Credit", ""), ("Balance", "cyan")],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# WRITE COMMANDS
# ===================================================================


@app.command("create-invoice")
def invoice_create(
    ctx: typer.Context,
    partner_name: Annotated[str, typer.Option("--partner", help="Partner name (ilike search)")],
    product_name: Annotated[str, typer.Option("--product", help="Product name (ilike search)")],
    qty: Annotated[float, typer.Option("--qty", help="Quantity")] = 1.0,
    price: Annotated[float, typer.Option("--price", help="Unit price")] = 0.0,
    inv_type: Annotated[str, typer.Option("--type", help="out_invoice or in_invoice")] = "out_invoice",
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show what would be created")] = False,
    force: Annotated[bool, typer.Option("--force", "-y", help="Skip confirmation")] = False,
) -> None:
    """Create a customer or vendor invoice.

    Resolves partner and product by name, then creates an account.move
    with one invoice line.

    Examples:
        kctl-odoo accounting create-invoice --partner "Acme" --product "Widget" --qty 10 --price 100
        kctl-odoo accounting create-invoice --partner "Supplier" --product "Raw Material" --type in_invoice
        kctl-odoo accounting create-invoice --partner "Acme" --product "Widget" --dry-run
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if inv_type not in ("out_invoice", "in_invoice"):
        out.error("--type must be 'out_invoice' or 'in_invoice'")
        raise typer.Exit(1)

    # Resolve partner
    try:
        partner_id, partner_display = _resolve(c, "res.partner", "name", partner_name, "Partner")
    except typer.BadParameter as e:
        out.error(str(e))
        raise typer.Exit(1) from e

    # Resolve product
    try:
        product_id, product_display = _resolve(c, "product.product", "name", product_name, "Product")
    except typer.BadParameter as e:
        out.error(str(e))
        raise typer.Exit(1) from e

    vals = {
        "move_type": inv_type,
        "partner_id": partner_id,
        "invoice_line_ids": [
            (
                0,
                0,
                {
                    "product_id": product_id,
                    "quantity": qty,
                    "price_unit": price,
                },
            )
        ],
    }

    if dry_run:
        result = {
            "action": "dry_run",
            "move_type": inv_type,
            "partner": partner_display,
            "product": product_display,
            "quantity": qty,
            "price_unit": price,
        }
        if actx.json_mode:
            out.raw_json(result)
        else:
            out.info("Dry run — would create:")
            out.kv("Type", inv_type)
            out.kv("Partner", partner_display)
            out.kv("Product", product_display)
            out.kv("Quantity", str(qty))
            out.kv("Price", _fmt_amount(price))
        return

    if not force:
        out.info(f"Creating {inv_type} for {partner_display} with {product_display} x{qty} @ {_fmt_amount(price)}")
        if not typer.confirm("Proceed?"):
            raise typer.Exit(0)

    try:
        move_id = c.create("account.move", vals)
    except RPCError as e:
        out.error(f"Failed to create invoice: {e.detail}")
        raise typer.Exit(1) from e

    # Re-read to get the computed name
    try:
        created = c.search_read("account.move", [("id", "=", move_id)], ["name", "amount_total"], limit=1)
        name = created[0].get("name", str(move_id)) if created else str(move_id)
        amount = created[0].get("amount_total", 0.0) if created else 0.0
    except RPCError:
        name = str(move_id)
        amount = 0.0

    out.success(f"Invoice created: {name} (ID {move_id}, total: {_fmt_amount(amount)})")
    if actx.json_mode:
        out.raw_json({"id": move_id, "name": name, "amount_total": amount})


@app.command("post-invoice")
def invoice_post(
    ctx: typer.Context,
    ids: Annotated[str, typer.Argument(help="Comma-separated invoice IDs")],
    force: Annotated[bool, typer.Option("--force", "-y", help="Skip confirmation")] = False,
) -> None:
    """Post one or more draft invoices/bills.

    Parses the comma-separated IDs, verifies each is in draft state,
    and calls action_post on all of them.

    Examples:
        kctl-odoo accounting post-invoice 42
        kctl-odoo accounting post-invoice 42,43,44
        kctl-odoo accounting post-invoice 42,43 --force
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Parse IDs
    try:
        move_ids = [int(x.strip()) for x in ids.split(",") if x.strip()]
    except ValueError:
        out.error(f"Invalid IDs (must be comma-separated integers): {ids}")
        raise typer.Exit(1) from None

    if not move_ids:
        out.error("No IDs provided.")
        raise typer.Exit(1)

    # Verify all exist and are draft
    try:
        records = c.search_read(
            "account.move",
            domain=[("id", "in", move_ids)],
            fields=["id", "name", "state"],
        )
    except RPCError as e:
        out.error(f"Failed to find invoices: {e.detail}")
        raise typer.Exit(1) from e

    if not records:
        out.error(f"No invoices found for IDs: {ids}")
        raise typer.Exit(1)

    non_draft = [r for r in records if r.get("state") != "draft"]
    if non_draft:
        names = ", ".join(r.get("name", str(r["id"])) for r in non_draft)
        out.error(f"These invoices are not in draft state: {names}")
        raise typer.Exit(1)

    draft_ids = [r["id"] for r in records]
    names = ", ".join(r.get("name", str(r["id"])) for r in records)

    if not force and not typer.confirm(f"Post {len(draft_ids)} invoice(s): {names}?"):
        raise typer.Exit(0)

    try:
        c.execute_kw("account.move", "action_post", [draft_ids])
    except RPCError as e:
        out.error(f"Failed to post invoices: {e.detail}")
        raise typer.Exit(1) from e

    out.success(f"Posted {len(draft_ids)} invoice(s): {names}")
    if actx.json_mode:
        out.raw_json({"posted": [{"id": r["id"], "name": r.get("name")} for r in records]})


@app.command("register-payment")
def payment_register(
    ctx: typer.Context,
    invoice_number: Annotated[str, typer.Argument(help="Invoice number or ID")],
    amount: Annotated[float | None, typer.Option("--amount", help="Payment amount (default: full amount)")] = None,
    journal_name: Annotated[str | None, typer.Option("--journal", help="Payment journal name (e.g. 'Bank')")] = None,
    force: Annotated[bool, typer.Option("--force", "-y", help="Skip confirmation")] = False,
) -> None:
    """Register payment for an invoice.

    Uses the account.payment.register wizard to create a payment,
    following the standard Odoo payment registration flow.

    Examples:
        kctl-odoo accounting register-payment INV/2026/0001
        kctl-odoo accounting register-payment INV/2026/0001 --amount 500 --journal "Bank"
        kctl-odoo accounting register-payment 42 --force
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Resolve invoice
    domain = [("id", "=", int(invoice_number))] if invoice_number.isdigit() else [("name", "=", invoice_number)]

    try:
        records = c.search_read(
            "account.move",
            domain=domain,
            fields=["id", "name", "amount_residual", "state", "move_type"],
            limit=1,
        )
    except RPCError as e:
        out.error(f"Failed to find invoice: {e.detail}")
        raise typer.Exit(1) from e

    if not records:
        out.error(f"Invoice not found: {invoice_number}")
        raise typer.Exit(1)

    inv = records[0]
    if inv.get("state") != "posted":
        out.error(f"Invoice {inv.get('name')} must be posted before payment (state={inv.get('state')})")
        raise typer.Exit(1)

    pay_amount = amount if amount is not None else inv.get("amount_residual", 0.0)
    if pay_amount <= 0:
        out.info(f"Invoice {inv.get('name')} has no outstanding balance.")
        return

    # Resolve journal
    journal_id = None
    if journal_name:
        try:
            journal_id = resolve_journal(c, journal_name)
        except typer.Exit:
            raise

    if not force:
        out.info(f"Registering payment of {_fmt_amount(pay_amount)} for {inv.get('name')}")
        if not typer.confirm("Proceed?"):
            raise typer.Exit(0)

    # Create payment via the wizard
    wizard_vals: dict = {
        "payment_date": datetime.now(tz=UTC).strftime("%Y-%m-%d"),
        "amount": pay_amount,
    }
    if journal_id:
        wizard_vals["journal_id"] = journal_id

    try:
        # The wizard needs the active_ids context to know which invoices to pay
        wizard_id = c.execute_kw(
            "account.payment.register",
            "create",
            [wizard_vals],
            {"context": {"active_model": "account.move", "active_ids": [inv["id"]]}},
        )
        c.execute_kw(
            "account.payment.register",
            "action_create_payments",
            [[wizard_id]],
            {"context": {"active_model": "account.move", "active_ids": [inv["id"]]}},
        )
    except RPCError as e:
        out.error(f"Failed to register payment: {e.detail}")
        raise typer.Exit(1) from e

    out.success(f"Payment of {_fmt_amount(pay_amount)} registered for {inv.get('name')}")
    if actx.json_mode:
        out.raw_json(
            {
                "invoice_id": inv["id"],
                "invoice_name": inv.get("name"),
                "amount": pay_amount,
            }
        )


@app.command("create-entry")
def entry_create(
    ctx: typer.Context,
    journal_name: Annotated[str, typer.Option("--journal", help="Journal name")],
    lines_str: Annotated[
        str, typer.Option("--lines", help="Lines: account_code:debit:credit,account_code:debit:credit")
    ],
    ref: Annotated[str | None, typer.Option("--ref", help="Reference / memo")] = None,
    date: Annotated[str | None, typer.Option("--date", help="Entry date (YYYY-MM-DD)")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show what would be created")] = False,
    force: Annotated[bool, typer.Option("--force", "-y", help="Skip confirmation")] = False,
) -> None:
    """Create a manual journal entry.

    Lines format: account_code:debit:credit separated by commas.
    Debits and credits must balance.

    Examples:
        kctl-odoo accounting create-entry --journal "Miscellaneous" \\
            --lines "1100:1000:0,2100:0:1000" --ref "Manual adjustment"
        kctl-odoo accounting create-entry --journal "Bank" \\
            --lines "1100:500:0,6100:0:500" --date 2026-03-01 --dry-run
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Resolve journal
    try:
        journal_id = resolve_journal(c, journal_name)
    except typer.Exit:
        raise

    # Parse lines
    parsed_lines = []
    total_debit = 0.0
    total_credit = 0.0
    for part in lines_str.split(","):
        pieces = part.strip().split(":")
        if len(pieces) != 3:
            out.error(f"Invalid line format '{part}'. Expected account_code:debit:credit")
            raise typer.Exit(1)
        acct_code, debit_str, credit_str = pieces
        try:
            debit_val = float(debit_str)
            credit_val = float(credit_str)
        except ValueError:
            out.error(f"Invalid amounts in line '{part}'")
            raise typer.Exit(1) from None

        # Resolve account by code
        try:
            acct_id = resolve_account(c, acct_code)
        except typer.Exit:
            raise

        parsed_lines.append(
            {
                "account_id": acct_id,
                "account_code": acct_code,
                "debit": debit_val,
                "credit": credit_val,
            }
        )
        total_debit += debit_val
        total_credit += credit_val

    # Validate balance
    if abs(total_debit - total_credit) > 0.01:
        out.error(f"Entry does not balance: debit={_fmt_amount(total_debit)}, credit={_fmt_amount(total_credit)}")
        raise typer.Exit(1)

    entry_date = date or datetime.now(tz=UTC).strftime("%Y-%m-%d")

    if dry_run:
        result = {
            "action": "dry_run",
            "journal": journal_name,
            "date": entry_date,
            "ref": ref,
            "lines": parsed_lines,
            "total_debit": total_debit,
            "total_credit": total_credit,
        }
        if actx.json_mode:
            out.raw_json(result)
        else:
            out.info("Dry run — would create journal entry:")
            out.kv("Journal", journal_name)
            out.kv("Date", entry_date)
            out.kv("Reference", ref or "(none)")
            out.kv("Total Debit", _fmt_amount(total_debit))
            out.kv("Total Credit", _fmt_amount(total_credit))
            for pl in parsed_lines:
                out.kv(f"  {pl['account_code']}", f"D:{_fmt_amount(pl['debit'])} C:{_fmt_amount(pl['credit'])}")
        return

    if not force:
        out.info(f"Creating journal entry: {_fmt_amount(total_debit)} total, {len(parsed_lines)} line(s)")
        if not typer.confirm("Proceed?"):
            raise typer.Exit(0)

    line_commands = [
        (
            0,
            0,
            {
                "account_id": pl["account_id"],
                "debit": pl["debit"],
                "credit": pl["credit"],
                "name": ref or "",
            },
        )
        for pl in parsed_lines
    ]

    vals: dict = {
        "journal_id": journal_id,
        "date": entry_date,
        "line_ids": line_commands,
    }
    if ref:
        vals["ref"] = ref

    try:
        move_id = c.create("account.move", vals)
    except RPCError as e:
        out.error(f"Failed to create journal entry: {e.detail}")
        raise typer.Exit(1) from e

    # Re-read the name
    try:
        created = c.search_read("account.move", [("id", "=", move_id)], ["name"], limit=1)
        name = created[0].get("name", str(move_id)) if created else str(move_id)
    except RPCError:
        name = str(move_id)

    out.success(f"Journal entry created: {name} (ID {move_id})")
    if actx.json_mode:
        out.raw_json({"id": move_id, "name": name})


@app.command("lock-period")
def lock_period(
    ctx: typer.Context,
    date: Annotated[str, typer.Argument(help="Lock date (YYYY-MM-DD)")],
    tax_only: Annotated[bool, typer.Option("--tax-only", help="Set only the tax lock date")] = False,
    force: Annotated[bool, typer.Option("--force", "-y", help="Skip confirmation")] = False,
) -> None:
    """Set accounting lock date.

    Sets the period lock date (or tax lock date with --tax-only)
    on the current company. Entries before this date cannot be modified.

    Examples:
        kctl-odoo accounting lock-period 2026-02-28
        kctl-odoo accounting lock-period 2026-02-28 --tax-only
        kctl-odoo accounting lock-period 2026-02-28 --force
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Get current company
    try:
        user = c.search_read("res.users", [("id", "=", c.uid)], ["company_id"], limit=1)
        if not user:
            out.error("Cannot determine current company")
            raise typer.Exit(1)
        company_id = user[0]["company_id"]
        if isinstance(company_id, list):
            company_id = company_id[0]
    except RPCError as e:
        out.error(f"Failed to get current company: {e.detail}")
        raise typer.Exit(1) from e

    if tax_only:
        field_name = "tax_lock_date"
        label = "tax lock date"
    else:
        field_name = "fiscalyear_lock_date"
        label = "period lock date"

    if not force and not typer.confirm(f"Set {label} to {date} for company ID {company_id}?"):
        raise typer.Exit(0)

    try:
        c.write("res.company", [company_id], {field_name: date})
    except RPCError as e:
        out.error(f"Failed to set lock date: {e.detail}")
        raise typer.Exit(1) from e

    out.success(f"Set {label} to {date}")
    if actx.json_mode:
        out.raw_json({"company_id": company_id, "field": field_name, "date": date})


# ===================================================================
# WRITE: INVOICE CANCEL (reverse to draft)
# ===================================================================


@app.command("cancel-invoice")
def invoice_cancel(
    ctx: typer.Context,
    ids: Annotated[str, typer.Argument(help="Comma-separated invoice IDs")],
    force: Annotated[bool, typer.Option("--force", "-y", help="Skip confirmation")] = False,
) -> None:
    """Cancel posted invoices/bills (reverse to draft).

    Calls button_draft on the specified invoices to reset them
    from posted state back to draft.

    Examples:
        kctl-odoo accounting cancel-invoice 42
        kctl-odoo accounting cancel-invoice 42,43,44
        kctl-odoo accounting cancel-invoice 42 --force
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Parse IDs
    try:
        move_ids = [int(x.strip()) for x in ids.split(",") if x.strip()]
    except ValueError:
        out.error(f"Invalid IDs (must be comma-separated integers): {ids}")
        raise typer.Exit(1) from None

    if not move_ids:
        out.error("No IDs provided.")
        raise typer.Exit(1)

    # Verify all exist and are posted
    try:
        records = c.search_read(
            "account.move",
            domain=[("id", "in", move_ids)],
            fields=["id", "name", "state"],
        )
    except RPCError as e:
        out.error(f"Failed to find invoices: {e.detail}")
        raise typer.Exit(1) from e

    if not records:
        out.error(f"No invoices found for IDs: {ids}")
        raise typer.Exit(1)

    non_posted = [r for r in records if r.get("state") != "posted"]
    if non_posted:
        names = ", ".join(f"{r.get('name', str(r['id']))} ({r.get('state')})" for r in non_posted)
        out.error(f"These invoices are not in posted state: {names}")
        raise typer.Exit(1)

    posted_ids = [r["id"] for r in records]
    names = ", ".join(r.get("name", str(r["id"])) for r in records)

    if not force and not typer.confirm(f"Cancel (reset to draft) {len(posted_ids)} invoice(s): {names}?"):
        raise typer.Exit(0)

    try:
        c.execute_kw("account.move", "button_draft", [posted_ids])
    except RPCError as e:
        out.error(f"Failed to cancel invoices: {e.detail}")
        raise typer.Exit(1) from e

    out.success(f"Cancelled {len(posted_ids)} invoice(s) (reset to draft): {names}")
    if actx.json_mode:
        out.raw_json({"cancelled": [{"id": r["id"], "name": r.get("name")} for r in records]})


# ===================================================================
# WRITE: BATCH POST
# ===================================================================


@app.command("batch-post")
def batch_post(
    ctx: typer.Context,
    move_type: Annotated[str, typer.Option("--type", help="Move type: out_invoice, in_invoice, entry")] = "out_invoice",
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max invoices to post")] = 100,
    force: Annotated[bool, typer.Option("--force", "-y", help="Skip confirmation")] = False,
) -> None:
    """Post all draft invoices/bills of a given type.

    Searches for all draft account.move records of the specified move_type
    and posts them in a single batch.

    Examples:
        kctl-odoo accounting batch-post
        kctl-odoo accounting batch-post --type in_invoice --limit 50
        kctl-odoo accounting batch-post --type entry --force
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    valid_types = ("out_invoice", "in_invoice", "out_refund", "in_refund", "entry")
    if move_type not in valid_types:
        out.error(f"--type must be one of: {', '.join(valid_types)}")
        raise typer.Exit(1)

    # Search draft moves of the given type
    try:
        records = c.search_read(
            "account.move",
            domain=[("state", "=", "draft"), ("move_type", "=", move_type)],
            fields=["id", "name", "partner_id", "amount_total"],
            limit=limit,
            order="id asc",
        )
    except RPCError as e:
        out.error(f"Failed to search draft moves: {e.detail}")
        raise typer.Exit(1) from e

    if not records:
        out.info(f"No draft {move_type} moves found.")
        if actx.json_mode:
            out.raw_json({"posted": [], "count": 0})
        return

    # Show summary
    total_amount = sum(r.get("amount_total", 0.0) for r in records)
    out.info(f"Found {len(records)} draft {move_type} move(s), total: {_fmt_amount(total_amount)}")

    if not force and not typer.confirm(f"Post all {len(records)} draft {move_type} move(s)?"):
        raise typer.Exit(0)

    draft_ids = [r["id"] for r in records]

    try:
        c.execute_kw("account.move", "action_post", [draft_ids])
    except RPCError as e:
        out.error(f"Failed to batch post: {e.detail}")
        raise typer.Exit(1) from e

    out.success(f"Posted {len(draft_ids)} {move_type} move(s)")

    if actx.json_mode:
        out.raw_json(
            {
                "posted": [{"id": r["id"], "name": r.get("name")} for r in records],
                "count": len(draft_ids),
                "move_type": move_type,
                "total_amount": total_amount,
            }
        )


# ---------------------------------------------------------------------------
# Accounting Close — period/year-end validation
# ---------------------------------------------------------------------------


@app.command("close-period")
def accounting_close(
    ctx: typer.Context,
    period_end: Annotated[
        str | None, typer.Option("--date", "-d", help="Period end date (YYYY-MM-DD, default: last month end)")
    ] = None,
) -> None:
    """Period/year-end accounting close validation.

    Runs all checks needed before closing an accounting period:
    - Trial balance (debit = credit)
    - Bank reconciliation status
    - Suspense account balances
    - Unposted journal entries
    - Draft invoices/bills
    - Unreconciled items
    - Lock date status
    - Depreciation completeness
    - Tax return readiness
    - Multi-currency revaluation

    Examples:
        kctl-odoo accounting close-period
        kctl-odoo accounting close-period --date 2025-12-31
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    from datetime import date as _date

    now = datetime.now(tz=UTC)

    if period_end:
        close_date = period_end
    else:
        # Default: last day of previous month
        first_of_month = _date(now.year, now.month, 1)
        last_month_end = first_of_month - timedelta(days=1)
        close_date = str(last_month_end)

    rows: list[list[str]] = []
    json_data: list[dict] = []
    total_issues = 0

    def _add(name: str, ok: bool, detail: str) -> None:
        nonlocal total_issues
        if not ok:
            total_issues += 1
        status = "[green]PASS[/green]" if ok else "[red]FAIL[/red]"
        rows.append([name, status, detail])
        json_data.append({"check": name, "passed": ok, "detail": detail})

    out.info(f"Accounting close validation for period ending: {close_date}")

    # 1. Trial Balance — total debit must equal total credit
    try:
        posted_lines = c.search_read(
            "account.move.line",
            [("parent_state", "=", "posted"), ("date", "<=", close_date)],
            fields=["debit", "credit"],
            limit=0,
        )
        total_debit = sum(line.get("debit", 0) for line in posted_lines)
        total_credit = sum(line.get("credit", 0) for line in posted_lines)
        diff = abs(total_debit - total_credit)
        ok = diff < 0.01
        _add(
            "Trial balance (debit = credit)",
            ok,
            f"Debit: {total_debit:,.2f}, Credit: {total_credit:,.2f}, Diff: {diff:,.2f}",
        )
    except Exception as e:
        _add("Trial balance", False, f"Check failed: {e}")

    # 2. Unposted entries in period
    try:
        draft_in_period = c.search_count(
            "account.move",
            [
                ("state", "=", "draft"),
                ("date", "<=", close_date),
            ],
        )
        _add(
            "No unposted entries in period",
            draft_in_period == 0,
            f"{draft_in_period} draft entries dated on or before {close_date}",
        )
    except Exception as e:
        _add("Unposted entries", False, str(e))

    # 3. Draft invoices in period
    try:
        draft_invoices = c.search_count(
            "account.move",
            [
                ("state", "=", "draft"),
                ("move_type", "in", ["out_invoice", "in_invoice", "out_refund", "in_refund"]),
                ("invoice_date", "<=", close_date),
            ],
        )
        _add(
            "No draft invoices/bills in period",
            draft_invoices == 0,
            f"{draft_invoices} draft invoices/bills dated in period",
        )
    except Exception as e:
        _add("Draft invoices", False, str(e))

    # 4. Bank reconciliation
    try:
        unreconciled_bank = c.search_count(
            "account.bank.statement.line",
            [
                ("is_reconciled", "=", False),
                ("date", "<=", close_date),
            ],
        )
        _add(
            "Bank statements reconciled",
            unreconciled_bank == 0,
            f"{unreconciled_bank} unreconciled bank lines in period",
        )
    except Exception:
        _add("Bank reconciliation", True, "bank statement module not active (skipped)")

    # 5. Suspense accounts at zero
    try:
        suspense = c.search_read("account.account", [("name", "ilike", "suspense")], fields=["id", "name"], limit=5)
        suspense_ok = True
        suspense_detail = []
        for sa in suspense:
            lines = c.search_read(
                "account.move.line",
                [("account_id", "=", sa["id"]), ("parent_state", "=", "posted"), ("date", "<=", close_date)],
                fields=["debit", "credit"],
                limit=0,
            )
            bal = sum(line.get("debit", 0) - line.get("credit", 0) for line in lines)
            if abs(bal) > 0.01:
                suspense_ok = False
                suspense_detail.append(f"{sa['name']}: {bal:,.2f}")
        if suspense:
            _add(
                "Suspense accounts at zero",
                suspense_ok,
                ", ".join(suspense_detail) if suspense_detail else f"{len(suspense)} suspense accounts all zero",
            )
        else:
            _add("Suspense accounts", True, "No suspense accounts found")
    except Exception:
        pass

    # 6. Unreconciled receivable/payable items
    try:
        unreconciled = c.search_count(
            "account.move.line",
            [
                ("reconciled", "=", False),
                ("account_id.reconcile", "=", True),
                ("parent_state", "=", "posted"),
                ("date", "<=", close_date),
            ],
        )
        _add(
            "Receivable/payable reconciled",
            unreconciled < 10,
            f"{unreconciled} unreconciled items on reconcilable accounts",
        )
    except Exception as e:
        _add("Reconciliation", False, str(e))

    # 7. Lock dates
    try:
        companies = c.search_read(
            "res.company", [], fields=["name", "period_lock_date", "fiscalyear_lock_date"], limit=5
        )
        for comp in companies:
            period_lock = comp.get("period_lock_date") or ""
            fy_lock = comp.get("fiscalyear_lock_date") or ""
            has_lock = bool(period_lock or fy_lock)
            detail = f"Period: {period_lock or 'not set'}, FY: {fy_lock or 'not set'}"
            _add(f"Lock dates ({comp['name']})", has_lock, detail)
    except Exception:
        pass

    # 8. Depreciation entries (fixed assets)
    try:
        # Check for unposted depreciation moves
        unposted_depreciation = c.search_count(
            "account.move",
            [
                ("state", "=", "draft"),
                ("move_type", "=", "entry"),
                ("ref", "ilike", "depreciation"),
                ("date", "<=", close_date),
            ],
        )
        _add(
            "Depreciation entries posted",
            unposted_depreciation == 0,
            f"{unposted_depreciation} unposted depreciation entries",
        )
    except Exception:
        _add("Depreciation", True, "Skipped — no depreciation entries found")

    # 9. Tax return readiness — all tax entries posted
    try:
        draft_with_tax = c.search_count(
            "account.move",
            [
                ("state", "=", "draft"),
                ("amount_tax", ">", 0),
                ("date", "<=", close_date),
            ],
        )
        _add(
            "Tax entries all posted", draft_with_tax == 0, f"{draft_with_tax} draft entries with tax amounts in period"
        )
    except Exception as e:
        _add("Tax readiness", False, str(e))

    # 10. Multi-currency — unrealized gain/loss
    try:
        multi_currency_lines = c.search_count(
            "account.move.line",
            [
                ("currency_id", "!=", False),
                ("parent_state", "=", "posted"),
                ("date", "<=", close_date),
                ("amount_residual_currency", "!=", 0),
            ],
        )
        _add(
            "Multi-currency revaluation",
            multi_currency_lines < 50,
            f"{multi_currency_lines} open foreign currency items — run revaluation if significant",
        )
    except Exception:
        _add("Multi-currency", True, "Skipped — no multi-currency entries")

    # Summary
    passed = sum(1 for d in json_data if d["passed"])
    total = len(json_data)
    title = f"Accounting Close — {close_date} ({passed}/{total} passed)"
    if total_issues:
        title += f" — [red]{total_issues} blocking[/red]"
    else:
        title += " — [green]ready to close[/green]"

    out.table(
        title,
        [("Check", "cyan"), ("Status", ""), ("Detail", "dim")],
        rows,
        json_data,
    )

    if total_issues:
        out.warn(f"Fix {total_issues} issues before closing period {close_date}")
    else:
        out.success(f"All checks passed — period {close_date} is ready to close")


# ===================================================================
# ACCOUNTING SUMMARY DASHBOARD
# ===================================================================


@app.command("summary")
def accounting_summary(
    ctx: typer.Context,
    period: Annotated[str, typer.Option("--period", help="Filter period: month, quarter, year")] = "month",
) -> None:
    """Accounting dashboard — invoices, receivables, payables, aging."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, "account.move"):
        out.error(module_hint("account.move"))
        raise typer.Exit(1)

    now = datetime.now(tz=UTC)
    pd = period_domain("invoice_date", period)

    # Customer invoices
    out_invoices = c.search_read(
        "account.move",
        domain=[("move_type", "=", "out_invoice")] + pd,
        fields=["state", "payment_state", "amount_total", "amount_residual", "invoice_date_due"],
    )

    draft_inv = [i for i in out_invoices if i.get("state") == "draft"]
    posted_inv = [i for i in out_invoices if i.get("state") == "posted"]
    overdue_inv = [
        i
        for i in posted_inv
        if i.get("payment_state") not in ("paid", "in_payment", "reversed")
        and i.get("invoice_date_due")
        and i["invoice_date_due"] < now.strftime("%Y-%m-%d")
    ]

    total_receivable = sum(
        i.get("amount_residual", 0) for i in posted_inv if i.get("payment_state") not in ("paid", "reversed")
    )

    # Vendor bills
    in_invoices = c.search_read(
        "account.move",
        domain=[("move_type", "=", "in_invoice")] + pd,
        fields=["state", "payment_state", "amount_total", "amount_residual"],
    )
    total_payable = sum(
        i.get("amount_residual", 0)
        for i in in_invoices
        if i.get("state") == "posted" and i.get("payment_state") not in ("paid", "reversed")
    )

    # Aging buckets
    buckets = {"current": 0.0, "30": 0.0, "60": 0.0, "90+": 0.0}
    for inv in posted_inv:
        if inv.get("payment_state") in ("paid", "in_payment", "reversed"):
            continue
        due = inv.get("invoice_date_due")
        residual = inv.get("amount_residual", 0)
        if not due or not residual:
            continue
        days_over = (now.date() - datetime.strptime(due, "%Y-%m-%d").date()).days if isinstance(due, str) else 0
        if days_over <= 0:
            buckets["current"] += residual
        elif days_over <= 30:
            buckets["30"] += residual
        elif days_over <= 60:
            buckets["60"] += residual
        else:
            buckets["90+"] += residual

    sections = [
        (
            "Customer Invoices",
            [
                ("Draft", str(len(draft_inv))),
                ("Posted", str(len(posted_inv))),
                ("Overdue", str(len(overdue_inv))),
                ("Total Receivable", fmt_amount(total_receivable)),
            ],
        ),
        (
            "Vendor Bills",
            [
                ("Total Payable", fmt_amount(total_payable)),
            ],
        ),
        (
            "Aging (Receivable)",
            [
                ("Current", fmt_amount(buckets["current"])),
                ("1-30 days", fmt_amount(buckets["30"])),
                ("31-60 days", fmt_amount(buckets["60"])),
                ("90+ days", fmt_amount(buckets["90+"])),
            ],
        ),
    ]

    json_out = {
        "draft_invoices": len(draft_inv),
        "posted_invoices": len(posted_inv),
        "overdue_invoices": len(overdue_inv),
        "total_receivable": total_receivable,
        "total_payable": total_payable,
        "aging": buckets,
    }

    out.detail(f"Accounting Summary ({period})", sections, data_for_json=json_out)


# ===================================================================
# OVERDUE INVOICES
# ===================================================================


@app.command("overdue")
def overdue_invoices(
    ctx: typer.Context,
    days: Annotated[int, typer.Option("--days", help="Minimum days overdue")] = 30,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List overdue invoices (customer and vendor)."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, "account.move"):
        out.error(module_hint("account.move"))
        raise typer.Exit(1)

    now = datetime.now(tz=UTC)
    cutoff = (now - timedelta(days=days)).strftime("%Y-%m-%d")

    invoices = c.search_read(
        "account.move",
        domain=[
            ("move_type", "in", ["out_invoice", "in_invoice"]),
            ("state", "=", "posted"),
            ("payment_state", "not in", ["paid", "in_payment", "reversed"]),
            ("invoice_date_due", "<", cutoff),
        ],
        fields=["name", "partner_id", "move_type", "amount_residual", "invoice_date_due"],
        limit=limit,
        order="invoice_date_due asc",
    )

    if not invoices:
        out.info(f"No invoices overdue by more than {days} days.")
        return

    rows = []
    json_data: list[dict] = []
    for inv in invoices:
        partner = inv.get("partner_id")
        partner_name = partner[1] if isinstance(partner, list) else str(partner or "-")
        due = inv.get("invoice_date_due", "")
        days_over = (now.date() - datetime.strptime(due, "%Y-%m-%d").date()).days if due else 0
        inv_type = "Customer" if inv.get("move_type") == "out_invoice" else "Vendor"
        rows.append(
            [
                inv.get("name", ""),
                partner_name,
                inv_type,
                fmt_amount(inv.get("amount_residual", 0)),
                str(days_over),
                due,
            ]
        )
        json_data.append(
            {
                "reference": inv.get("name"),
                "partner": partner_name,
                "type": inv_type,
                "amount_residual": inv.get("amount_residual"),
                "days_overdue": days_over,
                "due_date": due,
            }
        )

    out.table(
        f"Overdue Invoices (>{days} days) — {len(invoices)} found",
        [
            ("Reference", "cyan"),
            ("Partner", ""),
            ("Type", "dim"),
            ("Residual", "red"),
            ("Days", "yellow"),
            ("Due Date", "dim"),
        ],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# MULTI-CURRENCY REVALUATION CHECK
# ===================================================================


@app.command("revalue-currency")
def revalue_currency(
    ctx: typer.Context,
    date: Annotated[str | None, typer.Option("--date", help="Revaluation date (YYYY-MM-DD), defaults to today")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview mode label (informational)")] = False,
) -> None:
    """Multi-currency revaluation check.

    Shows unrealized gains/losses on foreign currency receivables/payables
    as of a given date. Does NOT create journal entries — shows what would
    be revalued.

    Examples:
        kctl-odoo accounting revalue-currency
        kctl-odoo accounting revalue-currency --date 2026-03-31 --dry-run
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, "account.move.line"):
        out.error(module_hint("account.move.line"))
        raise typer.Exit(1)

    reval_date = date or datetime.now(tz=UTC).strftime("%Y-%m-%d")

    fields = safe_fields(
        c,
        "account.move.line",
        ["id", "partner_id", "account_id", "currency_id", "amount_residual_currency", "amount_residual", "date"],
    )

    try:
        lines = c.search_read(
            "account.move.line",
            domain=[
                ("currency_id", "!=", False),
                ("amount_residual_currency", "!=", 0),
                ("account_id.reconcile", "=", True),
                ("date", "<=", reval_date),
                ("reconciled", "=", False),
                ("parent_state", "=", "posted"),
            ],
            fields=fields,
            order="partner_id, account_id",
        )
    except RPCError as e:
        out.error(f"Failed to fetch move lines: {e.detail}")
        raise typer.Exit(1) from e

    if not lines:
        out.info(f"No open foreign-currency lines as of {reval_date}.")
        return

    # Try to get current exchange rates via res.currency.rate
    rates: dict[int, float] = {}
    try:
        cur_ids = list(
            {ln.get("currency_id", [0])[0] if isinstance(ln.get("currency_id"), list) else 0 for ln in lines} - {0}
        )
        if cur_ids:
            rate_records = c.search_read(
                "res.currency.rate",
                domain=[("currency_id", "in", cur_ids), ("name", "<=", reval_date)],
                fields=["currency_id", "rate", "name"],
                order="currency_id, name desc",
            )
            seen_cur: set[int] = set()
            for rr in rate_records:
                cid = rr["currency_id"][0] if isinstance(rr.get("currency_id"), list) else 0
                if cid and cid not in seen_cur:
                    rates[cid] = rr.get("rate", 1.0) or 1.0
                    seen_cur.add(cid)
    except RPCError:
        pass  # Rates unavailable — show without gain/loss

    rows = []
    json_data: list[dict] = []
    total_gain_loss = 0.0

    for ln in lines:
        partner = ln.get("partner_id")
        partner_name = partner[1] if isinstance(partner, list) else "-"
        account = ln.get("account_id")
        account_name = account[1] if isinstance(account, list) else "-"
        currency = ln.get("currency_id")
        cur_id = currency[0] if isinstance(currency, list) else 0
        cur_name = currency[1] if isinstance(currency, list) else "-"

        fc_residual = ln.get("amount_residual_currency", 0.0) or 0.0
        book_value = ln.get("amount_residual", 0.0) or 0.0

        # Estimate current value using latest rate (inverse: 1/rate for company→foreign)
        rate = rates.get(cur_id, 0.0)
        if rate and rate != 0:
            current_value = fc_residual / rate
        else:
            current_value = book_value  # No rate available

        gain_loss = current_value - book_value
        total_gain_loss += gain_loss

        rows.append(
            [
                partner_name[:30],
                account_name[:30],
                cur_name,
                fmt_amount(fc_residual),
                fmt_amount(book_value),
                fmt_amount(current_value),
                fmt_amount(gain_loss),
            ]
        )
        json_data.append(
            {
                "partner": partner_name,
                "account": account_name,
                "currency": cur_name,
                "fc_residual": fc_residual,
                "book_value": book_value,
                "current_value": current_value,
                "gain_loss": gain_loss,
            }
        )

    mode = " [DRY RUN]" if dry_run else ""
    out.table(
        f"Currency Revaluation as of {reval_date}{mode} — {len(rows)} line(s) | Net G/L: {fmt_amount(total_gain_loss)}",
        [
            ("Partner", ""),
            ("Account", "cyan"),
            ("Currency", "dim"),
            ("FC Residual", ""),
            ("Book Value", ""),
            ("Current Value", ""),
            ("Gain/Loss", "yellow"),
        ],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# BANK ACCOUNT STATUS
# ===================================================================


@app.command("bank-status")
def bank_status(ctx: typer.Context) -> None:
    """Bank account balances and reconciliation status.

    Shows each bank/cash journal with current balance and unreconciled count.

    Examples:
        kctl-odoo accounting bank-status
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, "account.journal"):
        out.error(module_hint("account.journal"))
        raise typer.Exit(1)

    journal_fields = safe_fields(
        c,
        "account.journal",
        ["id", "name", "code", "type", "currency_id", "default_account_id"],
    )

    try:
        journals = c.search_read(
            "account.journal",
            domain=[("type", "in", ["bank", "cash"])],
            fields=journal_fields,
            order="type, name",
        )
    except RPCError as e:
        out.error(f"Failed to fetch journals: {e.detail}")
        raise typer.Exit(1) from e

    if not journals:
        out.info("No bank or cash journals found.")
        return

    # Count unreconciled bank statement lines per journal
    stmt_available = model_available(c, "account.bank.statement.line")

    rows = []
    json_data: list[dict] = []

    for j in journals:
        jid = j["id"]
        jname = j.get("name", "")
        jcode = j.get("code", "")
        jtype = j.get("type", "")
        currency = j.get("currency_id")
        cur_name = currency[1] if isinstance(currency, list) else "Company"

        unreconciled = 0
        if stmt_available:
            try:
                unreconciled = c.search_count(
                    "account.bank.statement.line",
                    [("journal_id", "=", jid), ("is_reconciled", "=", False)],
                )
            except RPCError:
                unreconciled = -1  # Model exists but query failed

        reconciled_label = str(unreconciled) if unreconciled >= 0 else "N/A"
        type_label = jtype.capitalize()

        rows.append([jname, jcode, type_label, cur_name, reconciled_label])
        json_data.append(
            {
                "journal": jname,
                "code": jcode,
                "type": jtype,
                "currency": cur_name,
                "unreconciled_lines": unreconciled if unreconciled >= 0 else None,
            }
        )

    out.table(
        f"Bank/Cash Journal Status — {len(rows)} journal(s)",
        [
            ("Journal", "cyan"),
            ("Code", "dim"),
            ("Type", ""),
            ("Currency", ""),
            ("Unreconciled Lines", "yellow"),
        ],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# GENERAL LEDGER DETAIL
# ===================================================================


@app.command("gl-detail")
def gl_detail(
    ctx: typer.Context,
    account_code: Annotated[str, typer.Argument(help="Account code (partial match)")],
    date_from: Annotated[str | None, typer.Option("--date-from", help="Start date YYYY-MM-DD")] = None,
    date_to: Annotated[str | None, typer.Option("--date-to", help="End date YYYY-MM-DD")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max lines")] = 50,
) -> None:
    """General ledger detail for a specific account.

    Shows all journal items for an account with running balance.

    Examples:
        kctl-odoo accounting gl-detail 101401
        kctl-odoo accounting gl-detail 121000 --date-from 2026-01-01 --date-to 2026-03-31
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, "account.account"):
        out.error(module_hint("account.account"))
        raise typer.Exit(1)

    # Resolve account
    try:
        accounts = c.search_read(
            "account.account",
            domain=[("code", "ilike", account_code)],
            fields=["id", "code", "name"],
            limit=5,
        )
    except RPCError as e:
        out.error(f"Failed to search accounts: {e.detail}")
        raise typer.Exit(1) from e

    if not accounts:
        out.error(f"No account found matching code: {account_code}")
        raise typer.Exit(1)

    if len(accounts) > 1:
        out.warn(
            f"Multiple accounts matched '{account_code}', using first: {accounts[0]['code']} {accounts[0]['name']}"
        )

    account = accounts[0]
    account_id = account["id"]
    account_label = f"{account['code']} {account['name']}"

    # Build domain for move lines
    domain: list = [
        ("account_id", "=", account_id),
        ("parent_state", "=", "posted"),
    ]
    if date_from:
        domain.append(("date", ">=", date_from))
    if date_to:
        domain.append(("date", "<=", date_to))

    line_fields = safe_fields(
        c,
        "account.move.line",
        ["id", "date", "move_id", "partner_id", "name", "debit", "credit", "balance"],
    )

    try:
        lines = c.search_read(
            "account.move.line",
            domain=domain,
            fields=line_fields,
            limit=limit,
            order="date asc, id asc",
        )
    except RPCError as e:
        out.error(f"Failed to fetch GL lines: {e.detail}")
        raise typer.Exit(1) from e

    if not lines:
        date_range = ""
        if date_from or date_to:
            date_range = f" for {date_from or '...'} -> {date_to or '...'}"
        out.info(f"No posted entries found for {account_label}{date_range}.")
        return

    rows = []
    json_data: list[dict] = []
    running_balance = 0.0

    for ln in lines:
        move = ln.get("move_id")
        move_ref = move[1] if isinstance(move, list) else "-"
        partner = ln.get("partner_id")
        partner_name = partner[1] if isinstance(partner, list) else "-"
        label = ln.get("name") or ""
        debit = ln.get("debit", 0.0) or 0.0
        credit = ln.get("credit", 0.0) or 0.0
        running_balance += debit - credit

        rows.append(
            [
                str(ln.get("date", "")),
                move_ref[:20],
                partner_name[:25],
                label[:30],
                fmt_amount(debit),
                fmt_amount(credit),
                fmt_amount(running_balance),
            ]
        )
        json_data.append(
            {
                "date": ln.get("date"),
                "move": move_ref,
                "partner": partner_name,
                "label": label,
                "debit": debit,
                "credit": credit,
                "running_balance": running_balance,
            }
        )

    date_range_label = ""
    if date_from or date_to:
        date_range_label = f" | {date_from or '...'} -> {date_to or '...'}"

    out.table(
        f"GL Detail: {account_label}{date_range_label} — {len(rows)} line(s)",
        [
            ("Date", "dim"),
            ("Move", "cyan"),
            ("Partner", ""),
            ("Label", ""),
            ("Debit", "green"),
            ("Credit", "red"),
            ("Balance", "yellow"),
        ],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# AUDIT TRAIL
# ===================================================================


@app.command("audit-trail")
def audit_trail(
    ctx: typer.Context,
    invoice: Annotated[str | None, typer.Option("--invoice", help="Invoice reference (e.g. INV/2026/0001)")] = None,
    days: Annotated[int, typer.Option("--days", help="Look-back window in days")] = 7,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """Audit trail for accounting entries — who posted/modified what.

    Shows recent journal entry modifications with user and timestamp.

    Examples:
        kctl-odoo accounting audit-trail
        kctl-odoo accounting audit-trail --invoice INV/2026/0001
        kctl-odoo accounting audit-trail --days 30
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, "account.move"):
        out.error(module_hint("account.move"))
        raise typer.Exit(1)

    move_fields = safe_fields(
        c,
        "account.move",
        ["id", "name", "state", "write_uid", "write_date", "partner_id", "amount_total", "move_type"],
    )

    domain: list = []
    if invoice:
        domain.append(("name", "ilike", invoice))
    else:
        cutoff = (datetime.now(tz=UTC) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        domain.append(("write_date", ">=", cutoff))
        domain.append(("move_type", "in", ["out_invoice", "in_invoice", "out_refund", "in_refund", "entry"]))

    try:
        moves = c.search_read(
            "account.move",
            domain=domain,
            fields=move_fields,
            limit=limit,
            order="write_date desc",
        )
    except RPCError as e:
        out.error(f"Failed to fetch journal entries: {e.detail}")
        raise typer.Exit(1) from e

    if not moves:
        if invoice:
            out.info(f"No journal entry found matching: {invoice}")
        else:
            out.info(f"No journal entries modified in the last {days} day(s).")
        return

    rows = []
    json_data: list[dict] = []

    for mv in moves:
        name = mv.get("name") or ""
        state = mv.get("state") or ""
        write_user = mv.get("write_uid")
        user_name = write_user[1] if isinstance(write_user, list) else "-"
        write_date = mv.get("write_date") or ""
        partner = mv.get("partner_id")
        partner_name = partner[1] if isinstance(partner, list) else "-"
        amount = mv.get("amount_total", 0.0) or 0.0
        mtype = mv.get("move_type", "entry") or "entry"
        type_label = {
            "out_invoice": "Invoice",
            "in_invoice": "Bill",
            "out_refund": "Credit Note",
            "in_refund": "Vendor Credit",
            "entry": "Entry",
        }.get(mtype, mtype)

        rows.append(
            [
                name,
                type_label,
                state,
                partner_name[:25],
                fmt_amount(amount),
                user_name[:20],
                write_date[:19],
            ]
        )
        json_data.append(
            {
                "reference": name,
                "type": type_label,
                "state": state,
                "partner": partner_name,
                "amount_total": amount,
                "modified_by": user_name,
                "modified_at": write_date,
            }
        )

    title = f"Audit Trail: {invoice}" if invoice else f"Audit Trail — last {days} day(s) — {len(rows)} entries"
    out.table(
        title,
        [
            ("Reference", "cyan"),
            ("Type", "dim"),
            ("State", ""),
            ("Partner", ""),
            ("Amount", ""),
            ("Modified By", "yellow"),
            ("Modified At", "dim"),
        ],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# GL EXPORT
# ===================================================================


@app.command("gl-export")
def gl_export(
    ctx: typer.Context,
    account_code: Annotated[str, typer.Argument(help="Account code (full or partial)")],
    date_from: Annotated[str | None, typer.Option("--date-from", help="Start date (YYYY-MM-DD)")] = None,
    date_to: Annotated[str | None, typer.Option("--date-to", help="End date (YYYY-MM-DD)")] = None,
    output: Annotated[str, typer.Option("--output", "-o", help="Output file path")] = "",
    fmt: Annotated[str, typer.Option("--format", "-f", help="Output format: csv (default)")] = "csv",
) -> None:
    """Export general ledger detail to CSV file.

    Exports all journal items for an account with date, move, partner,
    label, debit, credit, and running balance.

    Examples:
        kctl-odoo accounting gl-export 101401 -o bank_gl.csv
        kctl-odoo accounting gl-export 121000 --date-from 2026-01-01 --date-to 2026-03-31 -o ar.csv
        kctl-odoo accounting gl-export 251000 -o tax_payable.csv
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Find account
    try:
        accounts = c.search_read(
            "account.account",
            domain=[("code", "ilike", account_code)],
            fields=["id", "code", "name"],
            limit=5,
        )
    except RPCError as e:
        out.error(f"Failed to search accounts: {e}")
        raise typer.Exit(1) from e

    if not accounts:
        out.error(f"No account found matching code: {account_code}")
        raise typer.Exit(1)

    account = accounts[0]
    account_id = account["id"]
    account_name = f"{account['code']} {account['name']}"

    # Build domain
    domain: list = [("account_id", "=", account_id), ("parent_state", "=", "posted")]
    if date_from:
        domain.append(("date", ">=", date_from))
    if date_to:
        domain.append(("date", "<=", date_to))

    # Fetch all lines
    preferred = ["date", "move_id", "partner_id", "name", "ref", "debit", "credit", "balance"]
    fields = safe_fields(c, "account.move.line", preferred)

    try:
        lines = c.search_read(
            "account.move.line",
            domain=domain,
            fields=fields,
            limit=10000,
            order="date asc, id asc",
        )
    except RPCError as e:
        out.error(f"Failed to export GL: {e}")
        raise typer.Exit(1) from e

    if not lines:
        out.info(f"No journal items found for {account_name}")
        return

    # Calculate running balance
    import csv

    running = 0.0
    rows: list[dict] = []
    for line in lines:
        debit = line.get("debit", 0) or 0
        credit = line.get("credit", 0) or 0
        running += debit - credit
        move = line.get("move_id")
        move_name = move[1] if isinstance(move, list) else str(move or "")
        partner_val = line.get("partner_id")
        partner_name = partner_val[1] if isinstance(partner_val, list) else ""
        rows.append(
            {
                "date": str(line.get("date", "")),
                "move": move_name,
                "partner": partner_name,
                "label": line.get("name", "") or line.get("ref", ""),
                "debit": f"{debit:.2f}",
                "credit": f"{credit:.2f}",
                "balance": f"{running:.2f}",
            }
        )

    # Determine output file
    if not output:
        output = f"gl_{account['code']}_{(date_from or 'all')}.csv"

    # Write CSV
    with open(output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "move", "partner", "label", "debit", "credit", "balance"])
        writer.writeheader()
        writer.writerows(rows)

    out.success(f"Exported {len(rows)} lines to {output}")
    out.info(f"Account: {account_name}")
    out.info(f"Final balance: {running:,.2f}")
