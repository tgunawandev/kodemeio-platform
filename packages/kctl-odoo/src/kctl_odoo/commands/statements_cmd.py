"""Partner statement commands — customer/vendor account statements."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated

import typer

from kctl_odoo.core.biz_helpers import model_available
from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.exceptions import RPCError

app = typer.Typer(help="Customer/vendor account statements.")

_PARTNER_MODEL = "res.partner"
_MOVE_LINE_MODEL = "account.move.line"
_STATEMENTS_HINT = "OCA partner_statement module extends res.partner. Ensure account module is installed."


def _m2o_name(val: object) -> str:
    if isinstance(val, list):
        return str(val[1])
    return str(val or "-")


# ===================================================================
# GENERATE
# ===================================================================


@app.command("generate")
def generate(
    ctx: typer.Context,
    partner: Annotated[str | None, typer.Option("--partner", help="Partner name or ID")] = None,
    stmt_type: Annotated[str | None, typer.Option("--type", help="Statement type: activity or outstanding")] = None,
    stmt_date: Annotated[str | None, typer.Option("--date", help="Statement date (YYYY-MM-DD)")] = None,
) -> None:
    """Instructions for generating partner statements via Odoo wizard.

    The OCA partner_statement module adds statement generation to the partner
    form. Use the Odoo UI or wizard to generate PDF statements.

    Examples:
        kctl-odoo statements generate
        kctl-odoo statements generate --partner "Acme Corp" --type activity
    """
    actx: AppContext = ctx.obj
    out = actx.output

    stmt_date_str = stmt_date or date.today().strftime("%Y-%m-%d")
    stmt_type_str = stmt_type or "activity"

    out.info("Partner Statement Generation")
    out.info("")
    out.info("To generate statements via Odoo UI:")
    out.info("  1. Go to: Accounting > Customers/Vendors > Partners")
    if partner:
        out.info(f"  2. Search for partner: {partner}")
    else:
        out.info("  2. Select one or more partners")
    out.info(f"  3. Action > Print Statement (type: {stmt_type_str}, date: {stmt_date_str})")
    out.info("")
    out.info("Supported statement types:")
    out.info("  activity    — All transactions in period")
    out.info("  outstanding — Only open/unpaid items")
    out.info("")
    out.info("Use 'kctl-odoo statements overdue' to list partners with overdue balances.")

    if actx.json_mode:
        out.raw_json(
            {
                "action": "generate_statement",
                "partner": partner,
                "type": stmt_type_str,
                "date": stmt_date_str,
                "instructions": "Use Odoo UI: Accounting > Partners > Action > Print Statement",
            }
        )


# ===================================================================
# OVERDUE
# ===================================================================


@app.command("overdue")
def overdue(
    ctx: typer.Context,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List partners with overdue balances (unpaid past due date).

    Examples:
        kctl-odoo statements overdue
        kctl-odoo statements overdue --limit 20
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _MOVE_LINE_MODEL):
        out.warn(_STATEMENTS_HINT)
        return

    today_str = date.today().strftime("%Y-%m-%d")

    try:
        # Find overdue move lines grouped by partner
        lines = c.search_read(  # type: ignore[attr-defined]
            _MOVE_LINE_MODEL,
            domain=[
                ("date_maturity", "<", today_str),
                ("date_maturity", "!=", False),
                ("amount_residual", ">", 0),
                ("parent_state", "=", "posted"),
                ("account_id.reconcile", "=", True),
            ],
            fields=["partner_id", "date_maturity", "amount_residual", "currency_id", "move_id"],
            limit=limit * 5,  # fetch more to allow grouping
            order="date_maturity asc",
        )
    except RPCError as e:
        out.error(f"Failed to fetch overdue lines: {e}")
        raise typer.Exit(1) from e

    if not lines:
        out.info("No overdue balances found.")
        if actx.json_mode:
            out.raw_json([])
        return

    # Group by partner
    partner_totals: dict[str, dict] = {}
    for ln in lines:
        partner_key = str(_m2o_name(ln.get("partner_id")))
        partner_id_val = ln.get("partner_id")
        pid = partner_id_val[0] if isinstance(partner_id_val, list) else 0
        if partner_key not in partner_totals:
            partner_totals[partner_key] = {"partner_id": pid, "partner": partner_key, "total_overdue": 0.0, "lines": 0}
        partner_totals[partner_key]["total_overdue"] += ln.get("amount_residual", 0.0) or 0.0
        partner_totals[partner_key]["lines"] += 1

    # Sort by overdue amount desc, limit
    sorted_partners = sorted(partner_totals.values(), key=lambda x: x["total_overdue"], reverse=True)[:limit]

    rows = []
    json_data = []
    for p in sorted_partners:
        rows.append([p["partner"], str(p["lines"]), f"{p['total_overdue']:,.2f}"])
        json_data.append(p)

    out.table(
        f"Partners with Overdue Balances ({len(sorted_partners)})",
        [("Partner", "cyan"), ("Overdue Lines", ""), ("Total Overdue", "red")],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# AGING
# ===================================================================


@app.command("aging")
def aging(ctx: typer.Context) -> None:
    """Show aged receivable summary by aging bucket.

    This groups overdue receivables into standard aging buckets:
    current, 1-30 days, 31-60 days, 61-90 days, 90+ days.

    Examples:
        kctl-odoo statements aging
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _MOVE_LINE_MODEL):
        out.warn(_STATEMENTS_HINT)
        return

    today = date.today()
    today_str = today.strftime("%Y-%m-%d")

    buckets = [
        ("Current (not due)", None, today_str, False),
        ("1-30 days", (today - timedelta(days=30)).strftime("%Y-%m-%d"), today_str, True),
        (
            "31-60 days",
            (today - timedelta(days=60)).strftime("%Y-%m-%d"),
            (today - timedelta(days=31)).strftime("%Y-%m-%d"),
            True,
        ),
        (
            "61-90 days",
            (today - timedelta(days=90)).strftime("%Y-%m-%d"),
            (today - timedelta(days=61)).strftime("%Y-%m-%d"),
            True,
        ),
        ("90+ days", None, (today - timedelta(days=91)).strftime("%Y-%m-%d"), True),
    ]

    rows = []
    json_data = []
    grand_total = 0.0

    for bucket_name, date_from, date_to, overdue in buckets:
        try:
            domain: list = [
                ("amount_residual", ">", 0),
                ("parent_state", "=", "posted"),
                ("account_id.reconcile", "=", True),
            ]
            if overdue and date_to:
                domain.append(("date_maturity", "<", date_to))
            elif not overdue:
                domain.append(("date_maturity", ">=", today_str))
            if date_from:
                domain.append(("date_maturity", ">=", date_from))
            if date_to and overdue:
                domain.append(("date_maturity", "<", date_to))

            bucket_lines = c.search_read(  # type: ignore[attr-defined]
                _MOVE_LINE_MODEL,
                domain=domain,
                fields=["amount_residual"],
                limit=0,
            )
            bucket_total = sum(ln.get("amount_residual", 0.0) or 0.0 for ln in bucket_lines)
            count = len(bucket_lines)
        except RPCError:
            bucket_total = 0.0
            count = 0

        grand_total += bucket_total
        rows.append([bucket_name, str(count), f"{bucket_total:,.2f}"])
        json_data.append({"bucket": bucket_name, "count": count, "amount": bucket_total})

    rows.append(["[bold]TOTAL[/bold]", "", f"[bold red]{grand_total:,.2f}[/bold red]"])

    out.table(
        "Aged Receivable Summary",
        [("Aging Bucket", "cyan"), ("Lines", ""), ("Amount", "red")],
        rows,
        data_for_json={"buckets": json_data, "grand_total": grand_total},
    )


# ===================================================================
# PARTNER STATEMENT
# ===================================================================


@app.command("partner")
def partner_statement(
    ctx: typer.Context,
    partner_name: Annotated[str, typer.Argument(help="Partner name or ID")],
    date_from: Annotated[str | None, typer.Option("--date-from", help="Start date")] = None,
    output: Annotated[str | None, typer.Option("--output", "-o", help="Export to CSV")] = None,
) -> None:
    """Show account statement for a specific partner.

    Lists all receivable/payable journal items for a partner with running balance.

    Examples:
        kctl-odoo statements partner "PT Maju Bersama"
        kctl-odoo statements partner "PT Maju" --date-from 2026-01-01
        kctl-odoo statements partner "PT Maju" -o statement.csv
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    from kctl_odoo.core.field_helpers import safe_fields

    # Resolve partner
    if partner_name.isdigit():
        partners = c.search_read(
            _PARTNER_MODEL, domain=[("id", "=", int(partner_name))], fields=["id", "name"], limit=1
        )
    else:
        partners = c.search_read(
            _PARTNER_MODEL, domain=[("name", "ilike", partner_name)], fields=["id", "name"], limit=1
        )

    if not partners:
        out.error(f"Partner not found: {partner_name}")
        raise typer.Exit(1)

    partner = partners[0]
    partner_id = partner["id"]

    # Get receivable/payable lines
    domain: list = [
        ("partner_id", "=", partner_id),
        ("account_id.reconcile", "=", True),
        ("parent_state", "=", "posted"),
    ]
    if date_from:
        domain.append(("date", ">=", date_from))

    preferred = ["date", "move_id", "name", "ref", "debit", "credit", "amount_residual", "reconciled"]
    fields = safe_fields(c, _MOVE_LINE_MODEL, preferred)

    try:
        lines = c.search_read(  # type: ignore[attr-defined]
            _MOVE_LINE_MODEL, domain=domain, fields=fields, limit=1000, order="date asc, id asc"
        )
    except RPCError as e:
        out.error(f"Failed: {e}")
        raise typer.Exit(1) from e

    if not lines:
        out.info(f"No statement lines found for {partner['name']}")
        return

    # Build table
    running = 0.0
    rows: list[list[str]] = []
    for line in lines:
        debit = line.get("debit", 0) or 0
        credit = line.get("credit", 0) or 0
        running += debit - credit
        move = line.get("move_id")
        move_name = move[1] if isinstance(move, list) else str(move or "")
        label = line.get("name", "") or line.get("ref", "")
        residual = line.get("amount_residual", 0) or 0
        rows.append(
            [
                str(line.get("date", "")),
                move_name,
                label,
                f"{debit:,.2f}" if debit else "",
                f"{credit:,.2f}" if credit else "",
                f"{running:,.2f}",
                f"{residual:,.2f}" if residual else "0.00",
            ]
        )

    out.table(
        f"Statement: {partner['name']} ({len(lines)} items, balance: {running:,.2f})",
        [("Date", ""), ("Entry", ""), ("Label", ""), ("Debit", ""), ("Credit", ""), ("Balance", ""), ("Residual", "")],
        rows,
    )

    # Export to CSV if requested
    if output:
        import csv

        with open(output, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Date", "Entry", "Label", "Debit", "Credit", "Balance", "Residual"])
            run2 = 0.0
            for line in lines:
                debit = line.get("debit", 0) or 0
                credit = line.get("credit", 0) or 0
                run2 += debit - credit
                move = line.get("move_id")
                move_name = move[1] if isinstance(move, list) else str(move or "")
                writer.writerow(
                    [
                        line.get("date", ""),
                        move_name,
                        line.get("name", "") or line.get("ref", ""),
                        f"{debit:.2f}",
                        f"{credit:.2f}",
                        f"{run2:.2f}",
                        f"{(line.get('amount_residual', 0) or 0):.2f}",
                    ]
                )
        out.success(f"Exported to {output}")
