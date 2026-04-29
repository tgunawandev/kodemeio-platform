"""Direct-Accurate variant of credit-limit-proposal (PILOT).

Pulls customer + invoice + receipt data straight from Accurate Online
via the SDK (no Odoo migration required) and writes a small 4-sheet
Excel proposal:

* Summary — tenant + run metadata + totals
* Proposal — one row per customer with the proposed credit limit
* Raw - Customers — full customer master rows
* Raw - Invoices — every invoice with payment state + DSO context

Spec: docs/superpowers/specs/2026-04-29-credit-limit-proposal-design.md
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Annotated, Any

import typer
import yaml
from accurate_sdk import AccurateClient

from kctl_odoo.commands._credit_limit.accurate_pull import (
    pull_customers,
    pull_sales_invoices_and_payments,
)
from kctl_odoo.commands._credit_limit.compute import (
    Params,
    ProposalRow,
    compute_per_pair,
)
from kctl_odoo.core.callbacks import AppContext

DEFAULT_ENV_FILE = Path("/home/tgunawan/project/00-new-projects/kodemeio-workspace/kodemeio-accurate/.env")
DEFAULT_CONFIG_PATH = Path("~/.config/kodemeio/config.yaml").expanduser()


# ---------------------------------------------------------------------------
# Token + secret resolution
# ---------------------------------------------------------------------------


def _read_env_file(path: Path) -> dict[str, str]:
    """Parse a ``.env`` file into a plain dict.

    Strips inline ``#`` comments, surrounding quotes, and whitespace.
    Lines without ``=`` and blank/comment lines are skipped.
    """
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        # Strip surrounding quotes if present
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]
        env[key] = value
    return env


def _resolve_token(env_key: str, env_file: Path) -> str:
    """Look up an Accurate API token in a ``.env`` file.

    Tries the literal ``env_key`` first, then ``ACCURATE_TOKEN_<env_key>``
    so callers can pass either ``TPK`` or the full variable name.
    """
    env = _read_env_file(env_file)
    if env_key in env and env[env_key]:
        return env[env_key]
    full_key = env_key if env_key.startswith("ACCURATE_TOKEN_") else f"ACCURATE_TOKEN_{env_key}"
    if full_key in env and env[full_key]:
        return env[full_key]
    raise typer.BadParameter(
        f"Token not found in {env_file} for key '{env_key}' or '{full_key}'. "
        "Make sure the .env file is readable and the variable is set."
    )


def _resolve_signature_secret(config_path: Path = DEFAULT_CONFIG_PATH) -> str:
    """Read ``profiles.idtpp.accurate.signature_secret`` from kctl config."""
    if not config_path.exists():
        raise typer.BadParameter(f"kctl config not found at {config_path} — cannot read Accurate signature_secret")
    cfg = yaml.safe_load(config_path.read_text()) or {}
    try:
        secret = cfg["profiles"]["idtpp"]["accurate"]["signature_secret"]
    except (KeyError, TypeError) as exc:
        raise typer.BadParameter(
            f"signature_secret missing in {config_path} (profiles.idtpp.accurate.signature_secret)"
        ) from exc
    if not secret:
        raise typer.BadParameter(f"signature_secret is empty in {config_path}")
    return secret


# ---------------------------------------------------------------------------
# Workbook writer
# ---------------------------------------------------------------------------


def _money_fmt() -> str:
    return "#,##0"


def _slugify(name: str) -> str:
    """Lowercase, replace spaces and dots with dashes, strip non-alnum/dash."""
    out = name.lower().strip()
    for ch in (" ", "."):
        out = out.replace(ch, "-")
    out = "".join(c for c in out if c.isalnum() or c == "-")
    while "--" in out:
        out = out.replace("--", "-")
    return out.strip("-") or "tenant"


def _write_pilot_workbook(
    output: Path,
    *,
    tenant_name: str,
    customers: list[dict[str, Any]],
    by_customer: dict[int, list[dict[str, Any]]],
    proposals: list[tuple[dict[str, Any], ProposalRow]],
    params: Params,
    coverage: float,
) -> None:
    """Render the 4-sheet pilot Excel.

    See module docstring for the sheet inventory.
    """
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    hdr_font = Font(bold=True, color="FFFFFF", size=11)
    hdr_fill = PatternFill("solid", fgColor="2F5496")
    review_fill = PatternFill("solid", fgColor="FFC7CE")
    insufficient_fill = PatternFill("solid", fgColor="FFEB9C")

    def _write_headers(ws: Any, headers: list[str], widths: list[int] | None = None) -> None:
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=h)
            cell.font = hdr_font
            cell.fill = hdr_fill
            cell.alignment = Alignment(horizontal="center", wrap_text=True)
        if widths:
            for i, w in enumerate(widths, 1):
                ws.column_dimensions[get_column_letter(i)].width = w
        ws.freeze_panes = "A2"

    # ── Sheet 1: Summary ────────────────────────────────────────────
    ws_sum = wb.active
    ws_sum.title = "Summary"
    n_invoices = sum(len(v) for v in by_customer.values())
    sum_current = sum(c.get("current_credit_limit", 0.0) or 0.0 for c in customers)
    sum_proposed = 0.0
    n_review = 0
    n_insufficient = 0
    for _cust, row in proposals:
        if isinstance(row.proposed_limit, (int, float)):
            sum_proposed += float(row.proposed_limit)
        if row.proposed_limit == "INSUFFICIENT_DATA":
            n_insufficient += 1
        if row.review_flag:
            n_review += 1

    summary_rows: list[tuple[str, Any]] = [
        ("Tenant", tenant_name),
        ("Run timestamp (UTC)", params.today.isoformat()),
        ("Coverage multiplier", coverage),
        ("Insufficient-data threshold (min settled invoices)", params.insufficient_min_invoices),
        ("Overdue review threshold (days)", params.overdue_review_days),
        ("", ""),
        ("Customer count", len(customers)),
        ("Customers with at least one invoice", len(by_customer)),
        ("Total invoices", n_invoices),
        ("Customers with proposal computed", len(proposals) - n_insufficient),
        ("Customers flagged INSUFFICIENT_DATA", n_insufficient),
        ("Customers flagged REVIEW_REQUIRED", n_review),
        ("", ""),
        ("Sum current credit limit (IDR)", sum_current),
        ("Sum proposed credit limit (IDR)", sum_proposed),
        ("Delta (IDR)", sum_proposed - sum_current),
    ]
    for r_idx, (label, value) in enumerate(summary_rows, start=1):
        ws_sum.cell(row=r_idx, column=1, value=label).font = Font(bold=True)
        cell = ws_sum.cell(row=r_idx, column=2, value=value)
        if isinstance(value, (int, float)) and "(IDR)" in label:
            cell.number_format = _money_fmt()
    ws_sum.column_dimensions["A"].width = 50
    ws_sum.column_dimensions["B"].width = 30

    # ── Sheet 2: Proposal ───────────────────────────────────────────
    ws_prop = wb.create_sheet("Proposal")
    headers = [
        "Customer ID",
        "Customer No",
        "Customer Name",
        "NPWP",
        "Invoice Count",
        "Settled Invoices",
        "First Invoice",
        "Months Active",
        "Total Sales (IDR)",
        "Avg Monthly Sales (IDR)",
        "Proposed Limit (IDR)",
        "Current Limit (IDR)",
        "Delta (IDR)",
        "Delta %",
        "Avg DSO (days)",
        "Payment Behavior",
        "Has Overdue >120d",
        "Oldest Overdue (days)",
        "Total Open AR (IDR)",
        "Review Flag",
        "Note",
    ]
    widths = [12, 14, 38, 22, 14, 14, 14, 14, 18, 18, 18, 18, 16, 10, 12, 16, 16, 16, 18, 18, 30]
    _write_headers(ws_prop, headers, widths)
    money_cols = {9, 10, 11, 12, 13, 19}  # 1-indexed
    for r_offset, (cust, row) in enumerate(proposals, start=2):
        proposed = row.proposed_limit
        proposed_value: Any = float(proposed) if isinstance(proposed, (int, float)) else proposed
        values = [
            cust["id"],
            cust.get("customer_no", ""),
            cust.get("name", ""),
            cust.get("npwp", ""),
            row.invoice_count,
            row.settled_invoice_count,
            row.first_invoice_date.isoformat() if row.first_invoice_date else "",
            row.months_active,
            row.total_sales_idr,
            row.avg_monthly_sales_idr,
            proposed_value,
            row.current_limit_sum_idr,
            row.delta_idr,
            row.delta_pct,
            row.avg_DSO_days if row.avg_DSO_days is not None else "",
            row.payment_behavior,
            "Y" if row.has_overdue_120d else "",
            row.oldest_overdue_days,
            row.total_open_AR_idr,
            row.review_flag,
            row.note,
        ]
        for c_idx, val in enumerate(values, start=1):
            cell = ws_prop.cell(row=r_offset, column=c_idx, value=val)
            if c_idx in money_cols and isinstance(val, (int, float)):
                cell.number_format = _money_fmt()
        # Conditional row tint
        if row.review_flag == "REVIEW_REQUIRED":
            for c_idx in range(1, len(headers) + 1):
                ws_prop.cell(row=r_offset, column=c_idx).fill = review_fill
        elif row.proposed_limit == "INSUFFICIENT_DATA":
            for c_idx in range(1, len(headers) + 1):
                ws_prop.cell(row=r_offset, column=c_idx).fill = insufficient_fill

    # ── Sheet 3: Raw - Customers ────────────────────────────────────
    ws_cust = wb.create_sheet("Raw - Customers")
    cust_headers = [
        "ID",
        "Customer No",
        "Name",
        "NPWP",
        "WP Name",
        "Email",
        "Mobile",
        "Billing Street",
        "Billing City",
        "Billing Province",
        "Billing Zip",
        "Billing Country",
        "Current Credit Limit (IDR)",
        "Suspended",
    ]
    cust_widths = [10, 14, 38, 22, 28, 28, 18, 28, 18, 18, 12, 14, 22, 12]
    _write_headers(ws_cust, cust_headers, cust_widths)
    cust_money_cols = {13}
    for r_offset, c in enumerate(customers, start=2):
        values = [
            c.get("id"),
            c.get("customer_no", ""),
            c.get("name", ""),
            c.get("npwp", ""),
            c.get("wp_name", ""),
            c.get("email", ""),
            c.get("mobile_phone", ""),
            c.get("billing_street", ""),
            c.get("billing_city", ""),
            c.get("billing_province", ""),
            c.get("billing_zip", ""),
            c.get("billing_country", ""),
            c.get("current_credit_limit", 0.0),
            "Y" if c.get("suspended") else "",
        ]
        for c_idx, val in enumerate(values, start=1):
            cell = ws_cust.cell(row=r_offset, column=c_idx, value=val)
            if c_idx in cust_money_cols and isinstance(val, (int, float)):
                cell.number_format = _money_fmt()

    # ── Sheet 4: Raw - Invoices ─────────────────────────────────────
    ws_inv = wb.create_sheet("Raw - Invoices")
    inv_headers = [
        "Invoice ID",
        "Doc Number",
        "Customer ID",
        "Customer No",
        "Customer Name",
        "Invoice Date",
        "Due Date",
        "Total (IDR)",
        "Residual (IDR)",
        "Payment State",
        "Accurate Status",
        "Last Payment Date",
        "Days to Pay",
    ]
    inv_widths = [12, 22, 12, 14, 38, 14, 14, 16, 16, 14, 14, 16, 12]
    _write_headers(ws_inv, inv_headers, inv_widths)
    inv_money_cols = {8, 9}
    r_offset = 2
    for cust_id in sorted(by_customer.keys()):
        for inv in by_customer[cust_id]:
            inv_date = inv.get("invoice_date")
            last_pay = inv.get("last_payment_date")
            days_to_pay: Any = ""
            if inv_date and last_pay:
                days_to_pay = (last_pay - inv_date).days
            values = [
                inv.get("id"),
                inv.get("doc_number", ""),
                inv.get("customer_id"),
                inv.get("customer_no", ""),
                inv.get("customer_name", ""),
                inv_date.isoformat() if inv_date else "",
                inv["invoice_date_due"].isoformat() if inv.get("invoice_date_due") else "",
                inv.get("amount_total", 0.0),
                inv.get("amount_residual", 0.0),
                inv.get("payment_state", ""),
                inv.get("status", ""),
                last_pay.isoformat() if last_pay else "",
                days_to_pay,
            ]
            for c_idx, val in enumerate(values, start=1):
                cell = ws_inv.cell(row=r_offset, column=c_idx, value=val)
                if c_idx in inv_money_cols and isinstance(val, (int, float)):
                    cell.number_format = _money_fmt()
            r_offset += 1

    output.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output)


# ---------------------------------------------------------------------------
# Typer command
# ---------------------------------------------------------------------------


def credit_limit_report(
    ctx: typer.Context,
    tenant_name: Annotated[
        str,
        typer.Option(
            "--tenant-name",
            help="Display name on the Excel cover sheet (e.g. 'CV TUNGGAL PANGAN PAKERTI')",
        ),
    ],
    env_key: Annotated[
        str,
        typer.Option(
            "--env-key",
            help="Token variable name in --env-file (short e.g. 'TPK' or full 'ACCURATE_TOKEN_TPK')",
        ),
    ],
    env_file: Annotated[
        Path,
        typer.Option("--env-file", help="Path to .env containing ACCURATE_TOKEN_* vars"),
    ] = DEFAULT_ENV_FILE,
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Output xlsx path"),
    ] = None,
    coverage: Annotated[
        float,
        typer.Option("--coverage", help="Multiplier on avg monthly sales"),
    ] = 1.5,
    limit_customers: Annotated[
        int | None,
        typer.Option(
            "--limit-customers",
            help="Pilot debug: only process the first N customers (default: all)",
        ),
    ] = None,
) -> None:
    """Pull customer + invoice data from Accurate Online and propose credit limits (PILOT).

    Uses the Accurate API directly — no Odoo migration required. Suitable
    for trading-company tenants that haven't been onboarded into the ERP
    yet. Run with ``--limit-customers 5`` first to validate field
    mappings against real data.
    """
    actx: AppContext = ctx.obj
    out = actx.output

    # Resolve credentials
    secret = _resolve_signature_secret()
    token = _resolve_token(env_key, env_file)

    today = date.today()
    if output is None:
        slug = _slugify(tenant_name)
        output = Path(f"./credit-limit-{slug}-{today.strftime('%Y%m%d')}.xlsx")

    out.info(f"Connecting to Accurate Online for: {tenant_name}")
    client = AccurateClient(api_token=token, signature_secret=secret)

    out.info("Pulling customers...")
    customers = pull_customers(client)
    if limit_customers is not None and limit_customers > 0:
        customers = customers[:limit_customers]
    out.info(f"  {len(customers)} customers")

    customer_ids = {c["id"] for c in customers}

    out.info("Pulling sales invoices + receipts...")
    by_customer_all = pull_sales_invoices_and_payments(client, today=today)
    # Restrict invoice map to the (possibly limited) customer set
    by_customer = {cid: invs for cid, invs in by_customer_all.items() if cid in customer_ids}
    n_invoices = sum(len(v) for v in by_customer.values())
    out.info(f"  {n_invoices} invoices across {len(by_customer)} customers (of {len(customers)} total)")

    out.info(f"Computing proposed limits at coverage={coverage}...")
    params = Params(coverage=coverage, today=today)
    proposals: list[tuple[dict[str, Any], ProposalRow]] = []
    for cust in customers:
        cust_id = cust["id"]
        invoices = by_customer.get(cust_id, [])
        current_limit = cust.get("current_credit_limit", 0.0) or 0.0
        row = compute_per_pair(
            invoices,
            current_limit=current_limit,
            partner_id=cust_id,
            partner_name=cust["name"],
            trading_companies=tenant_name,
            params=params,
        )
        proposals.append((cust, row))

    out.info(f"Writing {output}...")
    _write_pilot_workbook(
        output,
        tenant_name=tenant_name,
        customers=customers,
        by_customer=by_customer,
        proposals=proposals,
        params=params,
        coverage=coverage,
    )
    out.success(f"Wrote {output}")
