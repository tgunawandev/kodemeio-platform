"""Bank reconciliation commands — statements, matching, import."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_odoo.core.biz_helpers import model_available
from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.exceptions import RPCError
from kctl_odoo.core.field_helpers import safe_fields

app = typer.Typer(help="Bank reconciliation: statements, matching, import.")

_STMT_LINE_MODEL = "account.bank.statement.line"
_JOURNAL_MODEL = "account.journal"
_MOVE_LINE_MODEL = "account.move.line"
_ACCOUNT_MODEL = "account.account"
_BANK_HINT = "Bank statement module not available. Ensure Odoo accounting module is installed."


def _m2o_name(val: object) -> str:
    if isinstance(val, list):
        return str(val[1])
    return str(val or "-")


# ===================================================================
# STATUS
# ===================================================================


@app.command("status")
def status(ctx: typer.Context) -> None:
    """Bank reconciliation overview.

    Shows counts of reconciled vs unreconciled bank statement lines.

    Examples:
        kctl-odoo bank status
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _STMT_LINE_MODEL):
        out.warn(_BANK_HINT)
        return

    try:
        total = c.search_count(  # type: ignore[attr-defined]
            _STMT_LINE_MODEL, []
        )
        reconciled = c.search_count(  # type: ignore[attr-defined]
            _STMT_LINE_MODEL, [("is_reconciled", "=", True)]
        )
        unreconciled = c.search_count(  # type: ignore[attr-defined]
            _STMT_LINE_MODEL, [("is_reconciled", "=", False)]
        )
    except RPCError as e:
        out.error(f"Failed to fetch bank statement stats: {e}")
        raise typer.Exit(1) from e

    # Compute unreconciled balance
    suspense_balance = 0.0
    try:
        unmatched_lines = c.search_read(  # type: ignore[attr-defined]
            _STMT_LINE_MODEL,
            domain=[("is_reconciled", "=", False)],
            fields=["amount"],
            limit=0,
        )
        suspense_balance = sum(ln.get("amount", 0.0) or 0.0 for ln in unmatched_lines)
    except RPCError:
        pass

    pct_reconciled = (reconciled / total * 100) if total else 0.0

    sections = [
        (
            "Bank Reconciliation Status",
            [
                ("Total Statement Lines", str(total)),
                ("Reconciled", f"{reconciled} ({pct_reconciled:.1f}%)"),
                ("Unreconciled", str(unreconciled)),
                ("Unreconciled Balance", f"{suspense_balance:,.2f}"),
            ],
        )
    ]

    json_result = {
        "total": total,
        "reconciled": reconciled,
        "unreconciled": unreconciled,
        "reconciled_pct": round(pct_reconciled, 2),
        "unreconciled_balance": suspense_balance,
    }

    out.detail("Bank Reconciliation Status", sections, data_for_json=json_result)


# ===================================================================
# UNMATCHED
# ===================================================================


@app.command("unmatched")
def unmatched(
    ctx: typer.Context,
    journal: Annotated[str | None, typer.Option("--journal", help="Filter by journal name (partial match)")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List unreconciled bank statement lines.

    Examples:
        kctl-odoo bank unmatched
        kctl-odoo bank unmatched --journal "Bank" --limit 20
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _STMT_LINE_MODEL):
        out.warn(_BANK_HINT)
        return

    domain: list = [("is_reconciled", "=", False)]
    if journal:
        domain.append(("journal_id.name", "ilike", journal))

    preferred = ["display_name", "date", "amount", "partner_id", "journal_id", "is_reconciled"]
    fields = safe_fields(c, _STMT_LINE_MODEL, preferred)

    try:
        lines = c.search_read(  # type: ignore[attr-defined]
            _STMT_LINE_MODEL,
            domain=domain,
            fields=fields,
            limit=limit,
            order="date desc",
        )
    except RPCError as e:
        out.error(f"Failed to fetch unreconciled lines: {e}")
        raise typer.Exit(1) from e

    if not lines:
        out.info("No unreconciled bank statement lines found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for ln in lines:
        amount = ln.get("amount", 0.0) or 0.0
        amount_color = "[red]" if amount < 0 else ""
        amount_reset = "[/red]" if amount < 0 else ""
        rows.append(
            [
                str(ln["id"]),
                str(ln.get("date") or ""),
                f"{amount_color}{amount:,.2f}{amount_reset}",
                _m2o_name(ln.get("partner_id")),
                _m2o_name(ln.get("journal_id")),
            ]
        )
        json_data.append(
            {
                "id": ln["id"],
                "date": str(ln.get("date") or ""),
                "amount": amount,
                "partner": _m2o_name(ln.get("partner_id")),
                "journal": _m2o_name(ln.get("journal_id")),
            }
        )

    out.table(
        f"Unreconciled Bank Statement Lines ({len(lines)})",
        [
            ("ID", "dim"),
            ("Date", ""),
            ("Amount", ""),
            ("Partner", "cyan"),
            ("Journal", ""),
        ],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# JOURNALS
# ===================================================================


@app.command("journals")
def journals(ctx: typer.Context) -> None:
    """List bank and cash journals.

    Examples:
        kctl-odoo bank journals
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _JOURNAL_MODEL):
        out.warn("Journal model not available.")
        return

    preferred = ["display_name", "code", "type", "company_id", "bank_account_id", "currency_id"]
    fields = safe_fields(c, _JOURNAL_MODEL, preferred)

    try:
        jrnls = c.search_read(  # type: ignore[attr-defined]
            _JOURNAL_MODEL,
            domain=[("type", "in", ["bank", "cash"])],
            fields=fields,
            order="type asc, name asc",
            limit=0,
        )
    except RPCError as e:
        out.error(f"Failed to fetch journals: {e}")
        raise typer.Exit(1) from e

    if not jrnls:
        out.info("No bank or cash journals found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for j in jrnls:
        rows.append(
            [
                str(j["id"]),
                j.get("display_name") or j.get("name", ""),
                str(j.get("code") or ""),
                str(j.get("type") or ""),
                _m2o_name(j.get("bank_account_id")),
                _m2o_name(j.get("currency_id")),
                _m2o_name(j.get("company_id")),
            ]
        )
        json_data.append(
            {
                "id": j["id"],
                "name": j.get("display_name") or j.get("name"),
                "code": j.get("code"),
                "type": j.get("type"),
                "bank_account": _m2o_name(j.get("bank_account_id")),
                "currency": _m2o_name(j.get("currency_id")),
                "company": _m2o_name(j.get("company_id")),
            }
        )

    out.table(
        f"Bank / Cash Journals ({len(jrnls)})",
        [
            ("ID", "dim"),
            ("Name", "cyan"),
            ("Code", ""),
            ("Type", ""),
            ("Bank Account", ""),
            ("Currency", ""),
            ("Company", ""),
        ],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# SUSPENSE
# ===================================================================


@app.command("suspense")
def suspense(ctx: typer.Context) -> None:
    """Show suspense account balance.

    Searches for accounts with 'suspense' in the name or code, and sums
    outstanding debit/credit balances on account.move.line.

    Examples:
        kctl-odoo bank suspense
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _MOVE_LINE_MODEL):
        out.warn(_BANK_HINT)
        return

    # Find suspense accounts
    suspense_accounts: list[dict] = []
    if model_available(c, _ACCOUNT_MODEL):
        try:
            suspense_accounts = c.search_read(  # type: ignore[attr-defined]
                _ACCOUNT_MODEL,
                domain=["|", ("name", "ilike", "suspense"), ("code", "ilike", "suspense")],
                fields=["display_name", "code", "account_type"],
                limit=10,
            )
        except RPCError:
            pass

    if not suspense_accounts:
        # Fall back to bank suspense account type
        try:
            suspense_accounts = c.search_read(  # type: ignore[attr-defined]
                _ACCOUNT_MODEL,
                domain=[("account_type", "=", "asset_cash")],
                fields=["display_name", "code", "account_type"],
                limit=10,
            )
        except RPCError:
            pass

    if not suspense_accounts:
        out.info("No suspense accounts found.")
        if actx.json_mode:
            out.raw_json({"accounts": [], "total_balance": 0.0})
        return

    account_ids = [a["id"] for a in suspense_accounts]
    rows = []
    json_data = []
    grand_balance = 0.0

    for acct in suspense_accounts:
        try:
            move_lines = c.search_read(  # type: ignore[attr-defined]
                _MOVE_LINE_MODEL,
                domain=[("account_id", "=", acct["id"]), ("parent_state", "=", "posted")],
                fields=["debit", "credit"],
                limit=0,
            )
            debit = sum(ln.get("debit", 0.0) or 0.0 for ln in move_lines)
            credit = sum(ln.get("credit", 0.0) or 0.0 for ln in move_lines)
            balance = debit - credit
        except RPCError:
            debit = credit = balance = 0.0

        grand_balance += balance
        rows.append(
            [
                acct.get("code", "") or "",
                acct.get("display_name") or acct.get("name", ""),
                str(acct.get("account_type") or ""),
                f"{balance:,.2f}",
            ]
        )
        json_data.append(
            {
                "code": acct.get("code"),
                "name": acct.get("display_name") or acct.get("name"),
                "account_type": acct.get("account_type"),
                "balance": balance,
            }
        )

    rows.append(["", "[bold]TOTAL[/bold]", "", f"[bold]{grand_balance:,.2f}[/bold]"])

    out.table(
        f"Suspense Account Balance ({len(suspense_accounts)} accounts)",
        [("Code", "dim"), ("Account", "cyan"), ("Type", ""), ("Balance", "")],
        rows,
        data_for_json={"accounts": json_data, "total_balance": grand_balance},
    )

    # Suppress duplicate ids warning
    _ = account_ids


# ===================================================================
# IMPORT-GUIDE
# ===================================================================


@app.command("import-guide")
def import_guide(ctx: typer.Context) -> None:
    """Show instructions for importing bank statements.

    Examples:
        kctl-odoo bank import-guide
    """
    actx: AppContext = ctx.obj
    out = actx.output

    out.info("Bank Statement Import Guide")
    out.info("")
    out.info("Supported formats:")
    out.info("  CSV      — Comma-separated values (custom mapping required)")
    out.info("  OFX      — Open Financial Exchange (most banks)")
    out.info("  CAMT054  — ISO 20022 XML format (SEPA/international banks)")
    out.info("  MT940    — SWIFT bank statement format")
    out.info("")
    out.info("How to import via Odoo UI:")
    out.info("  1. Go to: Accounting > Bank > Bank Statements")
    out.info("  2. Click 'Import' or use the 'Load Statement' button on a bank journal")
    out.info("  3. Select your file (CSV/OFX/CAMT054/MT940)")
    out.info("  4. Map columns if using CSV format")
    out.info("  5. Click 'Import' to load statement lines")
    out.info("")
    out.info("Review unreconciled lines after import:")
    out.info("  kctl-odoo bank unmatched")
    out.info("")
    out.info("Check reconciliation status:")
    out.info("  kctl-odoo bank status")
    out.info("")
    out.info("OCA modules for enhanced import support:")
    out.info("  account_bank_statement_import_ofx    — OFX format")
    out.info("  account_bank_statement_import_camt   — CAMT.054 format")
    out.info("  account_bank_statement_import_mt940  — MT940 format")
    out.info("  account_bank_statement_import_csv    — CSV with auto-mapping")

    if actx.json_mode:
        out.raw_json(
            {
                "formats": ["CSV", "OFX", "CAMT054", "MT940"],
                "ui_path": "Accounting > Bank > Bank Statements > Import",
                "oca_modules": [
                    "account_bank_statement_import_ofx",
                    "account_bank_statement_import_camt",
                    "account_bank_statement_import_mt940",
                    "account_bank_statement_import_csv",
                ],
                "review_commands": [
                    "kctl-odoo bank unmatched",
                    "kctl-odoo bank status",
                ],
            }
        )


# ===================================================================
# IMPORT-STATEMENT
# ===================================================================


@app.command("import-statement")
def import_statement(
    ctx: typer.Context,
    file_path: Annotated[str, typer.Argument(help="CSV file to import")],
    journal: Annotated[str, typer.Option("--journal", "-j", help="Bank journal code (e.g. BNK1)")] = "BNK1",
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Parse and validate without importing")] = False,
) -> None:
    """Import bank statement lines from a CSV file.

    CSV format: date,label,amount,partner (header row required).
    Creates account.bank.statement.line records.

    Examples:
        kctl-odoo bank import-statement bank_march.csv --journal BNK1
        kctl-odoo bank import-statement bank.csv --dry-run
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    import csv
    from pathlib import Path

    if not model_available(c, _STMT_LINE_MODEL):
        out.warn(_BANK_HINT)
        return

    # Read CSV
    csv_file = Path(file_path)
    if not csv_file.exists():
        out.error(f"File not found: {file_path}")
        raise typer.Exit(1)

    # Find journal
    journals = c.search_read(  # type: ignore[attr-defined]
        _JOURNAL_MODEL,
        domain=[("code", "=", journal)],
        fields=["id", "name", "type"],
        limit=1,
    )
    if not journals:
        out.error(f"Journal not found: {journal}")
        raise typer.Exit(1)

    journal_id = journals[0]["id"]
    out.info(f"Journal: {journals[0]['name']} ({journal})")

    # Parse CSV
    rows = []
    with open(csv_file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(
                {
                    "date": row.get("date", ""),
                    "payment_ref": row.get("label", row.get("description", row.get("reference", ""))),
                    "amount": float(row.get("amount", 0)),
                    "partner_name": row.get("partner", ""),
                }
            )

    out.info(f"Parsed {len(rows)} line(s) from {file_path}")

    if dry_run:
        out.info("DRY RUN — no records created.")
        for i, row in enumerate(rows[:10], 1):
            out.info(f"  {i}. {row['date']} | {row['payment_ref'][:40]} | {row['amount']:,.2f}")
        if len(rows) > 10:
            out.info(f"  ... and {len(rows) - 10} more")
        return

    # Create statement lines
    created = 0
    errors = 0
    for row in rows:
        try:
            vals = {
                "date": row["date"],
                "payment_ref": row["payment_ref"],
                "amount": row["amount"],
                "journal_id": journal_id,
            }
            c.execute_kw(_STMT_LINE_MODEL, "create", [vals])  # type: ignore[attr-defined]
            created += 1
        except (RPCError, Exception) as e:
            errors += 1
            if errors <= 3:
                out.warn(f"  Error on row: {row['date']} {row['payment_ref'][:30]} — {e}")

    out.success(f"Created {created} statement line(s), {errors} error(s).")
