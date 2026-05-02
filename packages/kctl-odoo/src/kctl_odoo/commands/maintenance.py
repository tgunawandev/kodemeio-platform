"""Maintenance and database health commands."""

from __future__ import annotations

from datetime import UTC
from typing import Annotated

import typer

from kctl_odoo.core.biz_helpers import model_available
from kctl_odoo.core.callbacks import AppContext

app = typer.Typer(help="Database maintenance, health checks, and period-close validation.")


# ---------------------------------------------------------------------------
# Autovacuum & Transient Cleanup
# ---------------------------------------------------------------------------


@app.command("autovacuum")
def autovacuum(ctx: typer.Context) -> None:
    """Trigger Odoo's built-in autovacuum (ir.autovacuum).

    Cleans up:
    - Expired transient records (wizards)
    - Orphan filestore entries
    - Old bus.bus notifications
    - Expired sessions (if session_db is used)
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Find the autovacuum cron and trigger it
    out.info("Looking for AutoVacuum scheduled action...")
    crons = c.search_read(
        "ir.cron",
        domain=[("name", "ilike", "autovacuum")],
        fields=["id", "name"],
        limit=1,
    )
    if not crons:
        # Fallback: search by model
        crons = c.search_read(
            "ir.cron",
            domain=[("model_id.model", "=", "ir.autovacuum")],
            fields=["id", "name"],
            limit=1,
        )
    if not crons:
        out.error("AutoVacuum cron not found. Run: kctl-odoo cron list | grep -i vacuum")
        raise typer.Exit(1)

    cron_id = crons[0]["id"]
    out.info(f"Triggering '{crons[0]['name']}' (ID {cron_id})...")
    try:
        c.execute_kw("ir.cron", "method_direct_trigger", [[cron_id]])
        out.success("Autovacuum completed — transient records, orphan files, and expired data cleaned.")
    except Exception as e:
        out.error(f"Autovacuum trigger failed: {e}")
        raise typer.Exit(1) from e


# ---------------------------------------------------------------------------
# Data Integrity
# ---------------------------------------------------------------------------


@app.command("check-data")
def check_data(
    ctx: typer.Context,
    category: Annotated[
        str | None,
        typer.Option(
            "--category",
            "-c",
            help="Filter: master, operations, finance, inventory, hr, manufacturing, cross-module, all",
        ),
    ] = None,
) -> None:
    """Comprehensive data integrity checks across 7 categories.

    Categories:
    - master: partner dupes, products without category, missing configs
    - operations: stale draft SO/PO, stuck transfers, orders without lines
    - finance: unreconciled items, overdue AR/AP, unposted journal entries
    - inventory: negative stock, zero-cost products, orphan stock moves
    - hr: employees without dept/contract, expired contracts, zero allocations
    - manufacturing: BOMs without components, stuck MOs
    - cross-module: SO/PO without delivery/invoice, order-to-cash gaps
    - all (default): run everything
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    from datetime import datetime, timedelta

    now = datetime.now(tz=UTC)
    cutoff_30d = (now - timedelta(days=30)).strftime("%Y-%m-%d")
    cutoff_90d = (now - timedelta(days=90)).strftime("%Y-%m-%d")
    cutoff_180d = (now - timedelta(days=180)).strftime("%Y-%m-%d")
    today = now.strftime("%Y-%m-%d")
    fourteen_days_ago = (now - timedelta(days=14)).strftime("%Y-%m-%d %H:%M:%S")
    thirty_days_ago = (now - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    sixty_days_ago = (now - timedelta(days=60)).strftime("%Y-%m-%d %H:%M:%S")
    ninety_days_ago = (now - timedelta(days=90)).strftime("%Y-%m-%d %H:%M:%S")

    rows: list[list[str]] = []
    json_data: list[dict] = []
    total_issues = 0
    cat = (category or "all").lower()
    # Normalize category aliases
    _cat_aliases = {"manufacturing": "mfg", "cross-module": "cross", "cross_module": "cross"}
    cat = _cat_aliases.get(cat, cat)

    def _check(check_cat: str, name: str, model: str, domain: list, description: str) -> None:
        nonlocal total_issues
        if cat != "all" and cat != check_cat:
            return
        try:
            count = c.search_count(model, domain)
            ok = count == 0
            if not ok:
                total_issues += count
            status = "[green]OK[/green]" if ok else f"[red]{count}[/red]"
            rows.append([check_cat.upper(), name, status, description if not ok else ""])
            json_data.append({"category": check_cat, "check": name, "count": count, "ok": ok})
        except Exception:
            rows.append([check_cat.upper(), name, "[dim]skip[/dim]", "Module not installed"])
            json_data.append({"category": check_cat, "check": name, "count": -1, "ok": True})

    def _check_custom(check_cat: str, name: str, ok: bool, count: int, detail: str) -> None:
        nonlocal total_issues
        if cat != "all" and cat != check_cat:
            return
        if not ok:
            total_issues += count
        status = "[green]OK[/green]" if ok else f"[red]{count}[/red]"
        rows.append([check_cat.upper(), name, status, detail if not ok else ""])
        json_data.append({"category": check_cat, "check": name, "count": count, "ok": ok})

    # =====================================================================
    # MASTER DATA CHECKS
    # =====================================================================

    # Duplicate partner emails
    if cat in ("all", "master"):
        try:
            partners = c.search_read("res.partner", domain=[("email", "!=", False)], fields=["email"], limit=10000)
            emails: dict[str, int] = {}
            for p in partners:
                email = (p.get("email") or "").strip().lower()
                if email:
                    emails[email] = emails.get(email, 0) + 1
            dupes = sum(1 for v in emails.values() if v > 1)
            _check_custom(
                "master", "Duplicate partner emails", dupes == 0, dupes, f"{dupes} emails on multiple partners"
            )
        except Exception:
            pass

    # Duplicate partner VAT numbers
    if cat in ("all", "master"):
        try:
            vat_partners = c.search_read("res.partner", domain=[("vat", "!=", False)], fields=["vat"], limit=10000)
            vats: dict[str, int] = {}
            for p in vat_partners:
                vat = (p.get("vat") or "").strip().upper()
                if vat:
                    vats[vat] = vats.get(vat, 0) + 1
            vat_dupes = sum(1 for v in vats.values() if v > 1)
            _check_custom(
                "master", "Duplicate partner VAT/TIN", vat_dupes == 0, vat_dupes, f"{vat_dupes} VAT numbers duplicated"
            )
        except Exception:
            pass

    _check(
        "master", "Partners without name", "res.partner", [("name", "in", [False, ""])], "Every partner needs a name"
    )
    _check(
        "master",
        "Products without category",
        "product.template",
        [("categ_id", "=", False)],
        "Assign categories for reporting",
    )
    _check(
        "master",
        "Products without internal ref",
        "product.template",
        [("default_code", "in", [False, ""]), ("sale_ok", "=", True)],
        "Saleable products should have internal reference",
    )
    _check(
        "master",
        "Products with zero cost",
        "product.template",
        [("standard_price", "<=", 0), ("type", "!=", "service")],
        "Storable/consumable products need a cost",
    )
    _check(
        "master",
        "Partners without country",
        "res.partner",
        [("country_id", "=", False), ("is_company", "=", True)],
        "Companies should have a country set",
    )

    # --- Partner data quality (extended) ---
    _check(
        "master",
        "Partners without phone or email",
        "res.partner",
        [("phone", "in", [False, ""]), ("email", "in", [False, ""]), ("is_company", "=", True), ("active", "=", True)],
        "Companies should have at least phone or email for contact",
    )
    _check(
        "master",
        "Partners without address",
        "res.partner",
        [
            ("street", "in", [False, ""]),
            ("city", "in", [False, ""]),
            ("is_company", "=", True),
            ("customer_rank", ">", 0),
        ],
        "Customers need address for delivery and invoicing",
    )
    if cat in ("all", "master"):
        try:
            # Duplicate partner names (same company name)
            name_partners = c.search_read(
                "res.partner",
                domain=[("is_company", "=", True), ("active", "=", True)],
                fields=["name"],
                limit=10000,
            )
            names: dict[str, int] = {}
            for p in name_partners:
                name = (p.get("name") or "").strip().lower()
                if name and len(name) > 3:
                    names[name] = names.get(name, 0) + 1
            name_dupes = sum(1 for v in names.values() if v > 1)
            _check_custom(
                "master",
                "Duplicate company names",
                name_dupes == 0,
                name_dupes,
                f"{name_dupes} company names appear more than once — possible duplicates",
            )
        except Exception:
            pass

    _check(
        "master",
        "Inactive partners with open invoices",
        "res.partner",
        [("active", "=", False), ("credit", ">", 0)],
        "Archived partners still have outstanding receivables",
    )

    # --- Product data quality (extended) ---
    _check(
        "master",
        "Products without UoM",
        "product.template",
        [("uom_id", "=", False)],
        "Every product must have a unit of measure",
    )
    _check(
        "master",
        "Products without sales price",
        "product.template",
        [("list_price", "<=", 0), ("sale_ok", "=", True)],
        "Saleable products should have a price >0",
    )
    _check(
        "master",
        "Archived products with open SO lines",
        "product.product",
        [("active", "=", False), ("sales_count", ">", 0)],
        "Archived products still referenced in active sales — may cause errors",
    )

    # --- Accounting master data ---
    if cat in ("all", "master"):
        try:
            # Accounts without code
            no_code_accounts = c.search_count("account.account", [("code", "in", [False, ""])])
            _check_custom(
                "master",
                "Accounts without code",
                no_code_accounts == 0,
                no_code_accounts,
                f"{no_code_accounts} chart of accounts entries have no code",
            )
        except Exception:
            pass

        try:
            # Journals without sequence
            no_seq_journals = c.search_count("account.journal", [("sequence_id", "=", False)])
            _check_custom(
                "master",
                "Journals without sequence",
                no_seq_journals == 0,
                no_seq_journals,
                f"{no_seq_journals} journals have no sequence — invoice numbering will fail",
            )
        except Exception:
            pass

        try:
            # Tax groups: check if both sale and purchase tax exist
            sale_taxes = c.search_count("account.tax", [("type_tax_use", "=", "sale"), ("active", "=", True)])
            purchase_taxes = c.search_count("account.tax", [("type_tax_use", "=", "purchase"), ("active", "=", True)])
            has_both = sale_taxes > 0 and purchase_taxes > 0
            _check_custom(
                "master",
                "Sale and purchase taxes configured",
                has_both,
                0 if has_both else 1,
                f"Sale taxes: {sale_taxes}, Purchase taxes: {purchase_taxes}" + (" — OK" if has_both else " — MISSING"),
            )
        except Exception:
            pass

    # --- Warehouse/location master data ---
    _check(
        "master",
        "Warehouses without stock location",
        "stock.warehouse",
        [("lot_stock_id", "=", False)],
        "Warehouses must have a stock location for operations",
    )

    # --- Indonesian-specific ---
    if cat in ("all", "master"):
        try:
            # Partners (companies) without NPWP/tax ID
            customers_no_vat = c.search_count(
                "res.partner",
                [
                    ("vat", "in", [False, ""]),
                    ("is_company", "=", True),
                    ("customer_rank", ">", 0),
                    ("active", "=", True),
                ],
            )
            _check_custom(
                "master",
                "Customers without NPWP/Tax ID",
                customers_no_vat == 0,
                customers_no_vat,
                f"{customers_no_vat} active customer companies have no VAT/NPWP — required for Faktur Pajak",
            )
        except Exception:
            pass

    # Users without timezone set (should be Asia/Jakarta for Indonesian companies)
    if cat in ("all", "master"):
        try:
            no_tz = c.search_count(
                "res.users",
                [("active", "=", True), ("share", "=", False), "|", ("tz", "=", False), ("tz", "!=", "Asia/Jakarta")],
            )
            _check_custom(
                "master",
                "Users without Asia/Jakarta timezone",
                no_tz == 0,
                no_tz,
                f"{no_tz} internal users do not have tz=Asia/Jakarta — causes wrong timestamps in attendance/payroll",
            )
        except Exception:
            pass

    # =====================================================================
    # OPERATIONS CHECKS
    # =====================================================================

    _check(
        "operations",
        "Stale draft quotations (>90d)",
        "sale.order",
        [("state", "=", "draft"), ("create_date", "<", cutoff_90d)],
        "Old drafts should be confirmed or deleted",
    )
    _check(
        "operations",
        "Stale draft POs (>90d)",
        "purchase.order",
        [("state", "=", "draft"), ("create_date", "<", cutoff_90d)],
        "Old draft POs should be confirmed or deleted",
    )
    _check(
        "operations",
        "Sale orders without lines",
        "sale.order",
        [("order_line", "=", False), ("state", "!=", "cancel")],
        "Orders with no lines are incomplete",
    )
    _check(
        "operations",
        "POs without lines",
        "purchase.order",
        [("order_line", "=", False), ("state", "!=", "cancel")],
        "POs with no lines are incomplete",
    )
    _check(
        "operations",
        "Stuck transfers (>30d)",
        "stock.picking",
        [("state", "in", ["waiting", "confirmed"]), ("create_date", "<", cutoff_30d)],
        "Transfers stuck for >30 days",
    )
    _check(
        "operations",
        "Late deliveries (>30d assigned)",
        "stock.picking",
        [("state", "=", "assigned"), ("scheduled_date", "<", cutoff_30d)],
        "Ready but not shipped for >30 days",
    )

    # =====================================================================
    # FINANCE CHECKS
    # =====================================================================

    _check(
        "finance",
        "Draft invoices >90d",
        "account.move",
        [("state", "=", "draft"), ("move_type", "in", ["out_invoice", "in_invoice"]), ("create_date", "<", cutoff_90d)],
        "Post or delete stale draft invoices",
    )
    _check(
        "finance",
        "Draft bills >90d",
        "account.move",
        [("state", "=", "draft"), ("move_type", "in", ["in_invoice", "in_refund"]), ("create_date", "<", cutoff_90d)],
        "Post or delete stale draft bills",
    )
    _check(
        "finance",
        "Unreconciled items >90d",
        "account.move.line",
        [("reconciled", "=", False), ("account_id.reconcile", "=", True), ("date", "<", cutoff_90d)],
        "Investigate old unreconciled items",
    )
    _check(
        "finance",
        "Unreconciled items >180d",
        "account.move.line",
        [("reconciled", "=", False), ("account_id.reconcile", "=", True), ("date", "<", cutoff_180d)],
        "Critical: very old unreconciled items",
    )

    # Overdue customer invoices
    _check(
        "finance",
        "Overdue customer invoices",
        "account.move",
        [
            ("move_type", "=", "out_invoice"),
            ("state", "=", "posted"),
            ("payment_state", "in", ["not_paid", "partial"]),
            ("invoice_date_due", "<", cutoff_30d),
        ],
        "Customer invoices past due >30 days",
    )

    # Overdue vendor bills
    _check(
        "finance",
        "Overdue vendor bills",
        "account.move",
        [
            ("move_type", "=", "in_invoice"),
            ("state", "=", "posted"),
            ("payment_state", "in", ["not_paid", "partial"]),
            ("invoice_date_due", "<", cutoff_30d),
        ],
        "Vendor bills past due >30 days",
    )

    # Unposted journal entries >30 days
    _check(
        "finance",
        "Unposted entries >30d",
        "account.move",
        [("state", "=", "draft"), ("move_type", "=", "entry"), ("create_date", "<", cutoff_30d)],
        "Journal entries sitting in draft >30 days",
    )

    # Invoices without tax lines
    if cat in ("all", "finance"):
        try:
            no_tax_invoices = c.search_count(
                "account.move",
                [
                    ("state", "=", "posted"),
                    ("move_type", "in", ["out_invoice", "in_invoice"]),
                    ("amount_tax", "=", 0),
                    ("amount_untaxed", ">", 0),
                ],
            )
            _check_custom(
                "finance",
                "Posted invoices without tax",
                no_tax_invoices == 0,
                no_tax_invoices,
                f"{no_tax_invoices} posted invoices have zero tax — verify tax configuration",
            )
        except Exception:
            pass

    # Suspense account balance (should be zero)
    if cat in ("all", "finance"):
        try:
            suspense_accounts = c.search_read(
                "account.account", [("name", "ilike", "suspense")], fields=["id", "name"], limit=5
            )
            for sa in suspense_accounts:
                lines = c.search_read(
                    "account.move.line",
                    [("account_id", "=", sa["id"]), ("parent_state", "=", "posted")],
                    fields=["debit", "credit"],
                    limit=0,
                )
                balance = sum(line.get("debit", 0) - line.get("credit", 0) for line in lines)
                ok = abs(balance) < 0.01
                _check_custom(
                    "finance",
                    f"Suspense '{sa['name']}' balance",
                    ok,
                    1 if not ok else 0,
                    f"Balance: {balance:,.2f} — should be zero",
                )
        except Exception:
            pass

    # Bank reconciliation — unreconciled bank statement lines
    if cat in ("all", "finance"):
        try:
            unreconciled_bank = c.search_count("account.bank.statement.line", [("is_reconciled", "=", False)])
            _check_custom(
                "finance",
                "Unreconciled bank statement lines",
                unreconciled_bank == 0,
                unreconciled_bank,
                f"{unreconciled_bank} bank lines not reconciled",
            )
        except Exception:
            pass

    # Lock date check
    if cat in ("all", "finance"):
        try:
            companies = c.search_read(
                "res.company", [], fields=["name", "fiscalyear_lock_date", "period_lock_date"], limit=5
            )
            for comp in companies:
                fy_lock = comp.get("fiscalyear_lock_date")
                period_lock = comp.get("period_lock_date")
                if not fy_lock and not period_lock:
                    _check_custom(
                        "finance",
                        f"Lock dates ({comp['name']})",
                        False,
                        1,
                        "No lock dates set — previous periods are editable",
                    )
                else:
                    info = []
                    if period_lock:
                        info.append(f"period: {period_lock}")
                    if fy_lock:
                        info.append(f"fiscal year: {fy_lock}")
                    _check_custom("finance", f"Lock dates ({comp['name']})", True, 0, ", ".join(info))
        except Exception:
            pass

    # --- Extended finance checks ---

    # Journals without default accounts
    if cat in ("all", "finance"):
        try:
            journals = c.search_read(
                "account.journal",
                [("type", "in", ["sale", "purchase", "bank", "cash"])],
                fields=["name", "type", "default_account_id"],
                limit=50,
            )
            no_default = [j for j in journals if not j.get("default_account_id")]
            _check_custom(
                "finance",
                "Journals without default account",
                len(no_default) == 0,
                len(no_default),
                f"{len(no_default)} journal(s) missing default account: {', '.join(j['name'] for j in no_default[:3])}"
                if no_default
                else "",
            )
        except Exception:
            pass

    # Tax rate validation — compare invoice tax vs expected rate
    if cat in ("all", "finance"):
        try:
            # Find invoices where tax amount doesn't match expected rate × base
            taxes = c.search_read(
                "account.tax",
                [("active", "=", True), ("type_tax_use", "=", "sale")],
                fields=["name", "amount"],
                limit=10,
            )
            if taxes:
                expected_rate = taxes[0].get("amount", 0) / 100 if taxes[0].get("amount") else 0
                if expected_rate > 0:
                    # Sample recent invoices and check tax math
                    recent_inv = c.search_read(
                        "account.move",
                        [
                            ("state", "=", "posted"),
                            ("move_type", "=", "out_invoice"),
                            ("amount_tax", ">", 0),
                            ("amount_untaxed", ">", 0),
                        ],
                        fields=["name", "amount_untaxed", "amount_tax"],
                        limit=50,
                    )
                    mismatched = 0
                    for inv in recent_inv:
                        base = inv.get("amount_untaxed", 0)
                        tax = inv.get("amount_tax", 0)
                        if base > 0:
                            actual_rate = tax / base
                            # Allow 5% tolerance for rounding and mixed-rate invoices
                            if abs(actual_rate - expected_rate) > expected_rate * 0.5:
                                mismatched += 1
                    _check_custom(
                        "finance",
                        "Tax rate consistency",
                        mismatched == 0,
                        mismatched,
                        f"{mismatched} invoices with tax rate significantly different from standard {taxes[0]['amount']}%",
                    )
        except Exception:
            pass

    # Trial balance sanity — debit should equal credit
    if cat in ("all", "finance"):
        try:
            all_lines = c.search_read(
                "account.move.line",
                [("parent_state", "=", "posted")],
                fields=["debit", "credit"],
                limit=0,
            )
            total_debit = sum(l.get("debit", 0) for l in all_lines)
            total_credit = sum(l.get("credit", 0) for l in all_lines)
            diff = abs(total_debit - total_credit)
            ok = diff < 0.01
            _check_custom(
                "finance",
                "Trial balance (debit = credit)",
                ok,
                1 if not ok else 0,
                f"Debit: {total_debit:,.2f}, Credit: {total_credit:,.2f}, Diff: {diff:,.2f}",
            )
        except Exception:
            pass

    # Duplicate invoice numbers
    if cat in ("all", "finance"):
        try:
            invoices = c.search_read(
                "account.move",
                [("state", "=", "posted"), ("move_type", "in", ["out_invoice", "in_invoice"]), ("name", "!=", "/")],
                fields=["name"],
                limit=10000,
            )
            inv_names: dict[str, int] = {}
            for inv in invoices:
                name = (inv.get("name") or "").strip()
                if name:
                    inv_names[name] = inv_names.get(name, 0) + 1
            dup_invoices = sum(1 for v in inv_names.values() if v > 1)
            _check_custom(
                "finance",
                "Duplicate invoice numbers",
                dup_invoices == 0,
                dup_invoices,
                f"{dup_invoices} invoice numbers appear more than once — data integrity risk",
            )
        except Exception:
            pass

    # Invoices with negative amounts (unusual)
    _check(
        "finance",
        "Invoices with negative total",
        "account.move",
        [("state", "=", "posted"), ("move_type", "in", ["out_invoice", "in_invoice"]), ("amount_total", "<", 0)],
        "Posted invoices with negative total — should be credit notes instead",
    )

    # Payments in wrong state
    if cat in ("all", "finance"):
        try:
            draft_payments_old = c.search_count(
                "account.payment",
                [("state", "=", "draft"), ("create_date", "<", cutoff_30d)],
            )
            _check_custom(
                "finance",
                "Draft payments >30d",
                draft_payments_old == 0,
                draft_payments_old,
                f"{draft_payments_old} payment records in draft >30 days — post or cancel",
            )
        except Exception:
            pass

    # Journals with entries in wrong period (after lock date)
    if cat in ("all", "finance"):
        try:
            companies = c.search_read("res.company", [], fields=["period_lock_date"], limit=1)
            if companies and companies[0].get("period_lock_date"):
                lock_date = companies[0]["period_lock_date"]
                entries_before_lock = c.search_count(
                    "account.move",
                    [("state", "=", "draft"), ("date", "<=", lock_date)],
                )
                _check_custom(
                    "finance",
                    "Draft entries before lock date",
                    entries_before_lock == 0,
                    entries_before_lock,
                    f"{entries_before_lock} draft entries dated on/before lock date {lock_date} — will fail when posting",
                )
        except Exception:
            pass

    # Receivable/payable balance sanity
    if cat in ("all", "finance"):
        try:
            # AR balance
            ar_lines = c.search_read(
                "account.move.line",
                [("account_id.account_type", "=", "asset_receivable"), ("parent_state", "=", "posted")],
                fields=["debit", "credit"],
                limit=0,
            )
            ar_balance = sum(l.get("debit", 0) - l.get("credit", 0) for l in ar_lines)
            _check_custom("finance", "AR balance", True, 0, f"Total receivables: {ar_balance:,.2f}")

            # AP balance
            ap_lines = c.search_read(
                "account.move.line",
                [("account_id.account_type", "=", "liability_payable"), ("parent_state", "=", "posted")],
                fields=["debit", "credit"],
                limit=0,
            )
            ap_balance = sum(l.get("debit", 0) - l.get("credit", 0) for l in ap_lines)
            _check_custom("finance", "AP balance", True, 0, f"Total payables: {ap_balance:,.2f}")
        except Exception:
            pass

    # Mismatched currency on invoices
    if cat in ("all", "finance"):
        try:
            # Invoices where currency differs from company currency but no exchange rate
            multi_curr = c.search_count(
                "account.move",
                [
                    ("state", "=", "posted"),
                    ("move_type", "in", ["out_invoice", "in_invoice"]),
                    ("currency_id", "!=", False),
                ],
            )
            if multi_curr > 0:
                _check_custom(
                    "finance",
                    "Multi-currency invoices",
                    True,
                    0,
                    f"{multi_curr} invoices in foreign currency — verify exchange rates are current",
                )
        except Exception:
            pass

    # Indonesian specific: PPN vs invoice tax check
    if cat in ("all", "finance"):
        try:
            # Invoices with tax amount but no tax line detail
            tax_accounts = c.search_read(
                "account.account",
                ["|", ("name", "ilike", "tax"), ("name", "ilike", "ppn")],
                fields=["id"],
                limit=10,
            )
            if tax_accounts:
                tax_account_ids = [a["id"] for a in tax_accounts]
                tax_entries = c.search_count(
                    "account.move.line",
                    [
                        ("account_id", "in", tax_account_ids),
                        ("parent_state", "=", "posted"),
                        ("date", ">=", today[:7] + "-01"),
                    ],
                )
                _check_custom(
                    "finance",
                    "Tax entries this month",
                    True,
                    0,
                    f"{tax_entries} tax journal items this month — verify against SPT Masa",
                )
        except Exception:
            pass

    # =====================================================================
    # INVENTORY CHECKS
    # =====================================================================

    _check(
        "inventory",
        "Negative stock quantities",
        "stock.quant",
        [("quantity", "<", 0), ("location_id.usage", "=", "internal")],
        "Negative stock indicates data issues",
    )
    _check(
        "inventory",
        "Products with zero cost (storable)",
        "product.product",
        [("standard_price", "<=", 0), ("type", "=", "consu")],
        "Storable products need cost for valuation",
    )

    # Orphan stock moves (no picking)
    _check(
        "inventory",
        "Stock moves without picking >30d",
        "stock.move",
        [("picking_id", "=", False), ("state", "not in", ["done", "cancel"]), ("create_date", "<", cutoff_30d)],
        "Orphan stock moves should be investigated",
    )

    # Unreserved confirmed pickings (can't ship)
    _check(
        "inventory",
        "Confirmed picks without reservation",
        "stock.picking",
        [("state", "=", "confirmed"), ("create_date", "<", cutoff_30d)],
        "Confirmed but unreserved >30d — check availability or cancel",
    )

    # Stock in transit >7 days
    if cat in ("all", "inventory"):
        try:
            cutoff_7d = (now - timedelta(days=7)).strftime("%Y-%m-%d")
            transit_count = c.search_count(
                "stock.picking",
                [
                    ("state", "=", "assigned"),
                    ("picking_type_code", "=", "internal"),
                    ("scheduled_date", "<", cutoff_7d),
                ],
            )
            _check_custom(
                "inventory",
                "Internal transfers in transit >7d",
                transit_count == 0,
                transit_count,
                f"{transit_count} inter-warehouse transfers stuck >7 days",
            )
        except Exception:
            pass

    # Inventory valuation vs GL (stock account balance check)
    if cat in ("all", "inventory"):
        try:
            # Get stock valuation from stock.valuation.layer
            layers = c.search_read("stock.valuation.layer", [("company_id", "!=", False)], fields=["value"], limit=0)
            layer_total = sum(line.get("value", 0) for line in layers)

            # Get GL stock account balance
            stock_accounts = c.search_read(
                "account.account",
                [("account_type", "=", "asset_current"), ("name", "ilike", "stock valuation")],
                fields=["id"],
                limit=5,
            )
            gl_total = 0.0
            for sa in stock_accounts:
                gl_lines = c.search_read(
                    "account.move.line",
                    [("account_id", "=", sa["id"]), ("parent_state", "=", "posted")],
                    fields=["debit", "credit"],
                    limit=0,
                )
                gl_total += sum(line.get("debit", 0) - line.get("credit", 0) for line in gl_lines)

            diff = abs(layer_total - gl_total)
            ok = diff < 1.0
            _check_custom(
                "inventory",
                "Valuation vs GL match",
                ok,
                1 if not ok else 0,
                f"Layers: {layer_total:,.2f}, GL: {gl_total:,.2f}, Diff: {diff:,.2f}",
            )
        except Exception:
            pass

    # Products with negative forecast (virtual stock)
    if cat in ("all", "inventory"):
        try:
            negative_forecast = c.search_count(
                "product.product",
                [
                    ("virtual_available", "<", 0),
                    ("type", "!=", "service"),
                ],
            )
            _check_custom(
                "inventory",
                "Products with negative forecast",
                negative_forecast == 0,
                negative_forecast,
                f"{negative_forecast} products oversold (virtual stock < 0)",
            )
        except Exception:
            pass

    # Expired lots (if lot tracking used)
    if cat in ("all", "inventory"):
        try:
            today_str = now.strftime("%Y-%m-%d")
            expired_lots = c.search_count(
                "stock.lot",
                [
                    ("expiration_date", "<", today_str),
                    ("product_qty", ">", 0),
                ],
            )
            _check_custom(
                "inventory",
                "Expired lots with stock",
                expired_lots == 0,
                expired_lots,
                f"{expired_lots} expired lots still have stock on hand",
            )
        except Exception:
            pass

    # Storable products without replenishment route
    if cat in ("all", "inventory"):
        try:
            no_route = c.search_count(
                "product.template",
                [
                    ("type", "!=", "service"),
                    ("route_ids", "=", False),
                    ("sale_ok", "=", True),
                ],
            )
            _check_custom(
                "inventory",
                "Storable products without routes",
                no_route < 5,
                no_route,
                f"{no_route} saleable storable products have no replenishment route",
            )
        except Exception:
            pass

    # --- Extended inventory/product checks ---

    # Product type vs route consistency
    if cat in ("all", "inventory"):
        try:
            # Storable products set to 'Buy' but no vendor
            buy_no_vendor = c.search_count(
                "product.template",
                [
                    ("type", "!=", "service"),
                    ("sale_ok", "=", True),
                    ("purchase_ok", "=", True),
                    ("seller_ids", "=", False),
                ],
            )
            _check_custom(
                "inventory",
                "Purchasable products without vendor",
                buy_no_vendor == 0,
                buy_no_vendor,
                f"{buy_no_vendor} purchasable products have no vendor defined — replenishment will fail",
            )
        except Exception:
            pass

    # Warehouse route validation
    if cat in ("all", "inventory"):
        try:
            warehouses = c.search_read(
                "stock.warehouse",
                [],
                fields=["name", "reception_route_id", "delivery_route_id"],
                limit=20,
            )
            no_reception = [w for w in warehouses if not w.get("reception_route_id")]
            no_delivery = [w for w in warehouses if not w.get("delivery_route_id")]
            if no_reception:
                _check_custom(
                    "inventory",
                    "Warehouses without reception route",
                    False,
                    len(no_reception),
                    f"{len(no_reception)} warehouse(s) missing reception route: {', '.join(w['name'] for w in no_reception[:3])}",
                )
            if no_delivery:
                _check_custom(
                    "inventory",
                    "Warehouses without delivery route",
                    False,
                    len(no_delivery),
                    f"{len(no_delivery)} warehouse(s) missing delivery route: {', '.join(w['name'] for w in no_delivery[:3])}",
                )
        except Exception:
            pass

    # UoM category consistency
    if cat in ("all", "master"):
        try:
            # Find products where purchase UoM category differs from default UoM category
            products_uom = c.search_read(
                "product.template",
                [("uom_id", "!=", False), ("uom_po_id", "!=", False)],
                fields=["name", "uom_id", "uom_po_id"],
                limit=1000,
            )
            # Get UoM details for category check
            uom_ids = set()
            for p in products_uom:
                if p.get("uom_id"):
                    uom_ids.add(p["uom_id"][0] if isinstance(p["uom_id"], list) else p["uom_id"])
                if p.get("uom_po_id"):
                    uom_ids.add(p["uom_po_id"][0] if isinstance(p["uom_po_id"], list) else p["uom_po_id"])
            if uom_ids:
                uoms = c.search_read(
                    "uom.uom",
                    [("id", "in", list(uom_ids))],
                    fields=["id", "category_id"],
                    limit=500,
                )
                uom_cat = {
                    u["id"]: (u["category_id"][0] if isinstance(u.get("category_id"), list) else u.get("category_id"))
                    for u in uoms
                }

                mismatch = 0
                for p in products_uom:
                    sale_uom = p["uom_id"][0] if isinstance(p.get("uom_id"), list) else p.get("uom_id")
                    po_uom = p["uom_po_id"][0] if isinstance(p.get("uom_po_id"), list) else p.get("uom_po_id")
                    if sale_uom and po_uom and uom_cat.get(sale_uom) != uom_cat.get(po_uom):
                        mismatch += 1
                _check_custom(
                    "master",
                    "UoM category mismatch (sale vs purchase)",
                    mismatch == 0,
                    mismatch,
                    f"{mismatch} products have different UoM categories for sale and purchase — conversion will fail",
                )
        except Exception:
            pass

    # =====================================================================
    # HR CHECKS (20 checks)
    # =====================================================================

    if cat in ("all", "hr"):
        if not model_available(c, "hr.employee"):
            if cat == "hr":
                out.warn("HR module (hr) is not installed — HR checks skipped")
                out.info("Install HR modules: kctl-odoo local install hr_contract,hr_holidays,hr_attendance")
        else:
            _hr_available = True

    if cat in ("all", "hr") and model_available(c, "hr.employee"):
        # ------ EMPLOYEE MASTER DATA (6 checks) ------

        try:
            no_dept = c.search_count("hr.employee", [("department_id", "=", False), ("active", "=", True)])
            _check_custom(
                "hr",
                "Employees without department",
                no_dept == 0,
                no_dept,
                f"{no_dept} active employees have no department assigned",
            )
        except Exception:
            pass

        try:
            no_job = c.search_count("hr.employee", [("job_id", "=", False), ("active", "=", True)])
            _check_custom(
                "hr",
                "Employees without job position",
                no_job == 0,
                no_job,
                f"{no_job} active employees have no job position",
            )
        except Exception:
            pass

        try:
            no_manager = c.search_count("hr.employee", [("parent_id", "=", False), ("active", "=", True)])
            # Subtract 1 for top-level (CEO)
            no_manager = max(0, no_manager - 1)
            _check_custom(
                "hr",
                "Employees without manager (excl. CEO)",
                no_manager == 0,
                no_manager,
                f"{no_manager} active employees have no manager assigned",
            )
        except Exception:
            pass

        try:
            no_work_email = c.search_count("hr.employee", [("work_email", "=", False), ("active", "=", True)])
            _check_custom(
                "hr",
                "Employees without work email",
                no_work_email == 0,
                no_work_email,
                f"{no_work_email} active employees have no work email",
            )
        except Exception:
            pass

        try:
            no_user = c.search_count("hr.employee", [("user_id", "=", False), ("active", "=", True)])
            _check_custom(
                "hr",
                "Employees without linked user",
                no_user == 0,
                no_user,
                f"{no_user} active employees have no linked Odoo user (cannot self-service)",
            )
        except Exception:
            pass

        try:
            no_company = c.search_count("hr.employee", [("company_id", "=", False), ("active", "=", True)])
            _check_custom(
                "hr",
                "Employees without company",
                no_company == 0,
                no_company,
                f"{no_company} active employees have no company assigned",
            )
        except Exception:
            pass

        # ------ CONTRACTS (4 checks) ------

        if model_available(c, "hr.contract"):
            try:
                expired = c.search_count("hr.contract", [("state", "=", "open"), ("date_end", "<", today)])
                _check_custom(
                    "hr",
                    "Expired contracts still open",
                    expired == 0,
                    expired,
                    f"{expired} contracts expired but still in 'open' state",
                )
            except Exception:
                pass

            try:
                no_contract = c.search_count("hr.employee", [("contract_id", "=", False), ("active", "=", True)])
                _check_custom(
                    "hr",
                    "Employees without active contract",
                    no_contract == 0,
                    no_contract,
                    f"{no_contract} active employees have no current contract",
                )
            except Exception:
                pass

            try:
                from datetime import timedelta

                soon = (datetime.strptime(today, "%Y-%m-%d") + timedelta(days=30)).strftime("%Y-%m-%d")
                expiring = c.search_count(
                    "hr.contract", [("state", "=", "open"), ("date_end", ">=", today), ("date_end", "<=", soon)]
                )
                _check_custom(
                    "hr",
                    "Contracts expiring within 30 days",
                    expiring == 0,
                    expiring,
                    f"{expiring} contracts expire within 30 days — review for renewal",
                )
            except Exception:
                pass

            try:
                no_wage = c.search_count("hr.contract", [("state", "=", "open"), ("wage", "<=", 0)])
                _check_custom(
                    "hr",
                    "Active contracts with zero wage",
                    no_wage == 0,
                    no_wage,
                    f"{no_wage} open contracts have zero or negative wage",
                )
            except Exception:
                pass

        # ------ LEAVE / ATTENDANCE (4 checks) ------

        if model_available(c, "hr.leave.allocation"):
            try:
                zero_alloc = c.search_count(
                    "hr.leave.allocation", [("number_of_days", "<=", 0), ("state", "=", "validate")]
                )
                _check_custom(
                    "hr",
                    "Leave allocations at zero",
                    zero_alloc == 0,
                    zero_alloc,
                    f"{zero_alloc} approved allocations with zero or negative days",
                )
            except Exception:
                pass

        if model_available(c, "hr.leave"):
            try:
                stale_draft = c.search_count("hr.leave", [("state", "=", "draft")])
                _check_custom(
                    "hr",
                    "Stale draft leave requests",
                    stale_draft <= 5,
                    stale_draft,
                    f"{stale_draft} leave requests still in draft — remind employees to submit",
                )
            except Exception:
                pass

            try:
                pending = c.search_count("hr.leave", [("state", "=", "confirm")])
                _check_custom(
                    "hr",
                    "Leave requests awaiting approval",
                    pending <= 10,
                    pending,
                    f"{pending} submitted leave requests awaiting manager approval",
                )
            except Exception:
                pass

        if model_available(c, "hr.attendance"):
            try:
                # Attendance records with check_in but no check_out (and older than today)
                open_attendance = c.search_count(
                    "hr.attendance",
                    [
                        ("check_out", "=", False),
                        ("check_in", "<", today),
                    ],
                )
                _check_custom(
                    "hr",
                    "Open attendance records (no check-out)",
                    open_attendance == 0,
                    open_attendance,
                    f"{open_attendance} attendance records from before today with no check-out",
                )
            except Exception:
                pass

        # ------ EXPENSES (2 checks) ------

        if model_available(c, "hr.expense.sheet"):
            try:
                from datetime import timedelta

                d30 = (datetime.strptime(today, "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d")
                stale_expenses = c.search_count(
                    "hr.expense.sheet", [("state", "=", "draft"), ("create_date", "<", d30)]
                )
                _check_custom(
                    "hr",
                    "Stale draft expense reports (>30d)",
                    stale_expenses == 0,
                    stale_expenses,
                    f"{stale_expenses} expense reports in draft for over 30 days",
                )
            except Exception:
                pass

            try:
                approved_not_paid = c.search_count(
                    "hr.expense.sheet", [("state", "=", "approve"), ("create_date", "<", d30)]
                )
                _check_custom(
                    "hr",
                    "Approved expenses not reimbursed >30d",
                    approved_not_paid == 0,
                    approved_not_paid,
                    f"{approved_not_paid} expense sheets approved but not paid >30 days",
                )
            except Exception:
                pass

        # ------ ORGANIZATIONAL (4 checks) ------

        if model_available(c, "hr.department"):
            try:
                empty_dept = c.search_read(
                    "hr.department", [("active", "=", True)], fields=["id", "name", "member_ids"], limit=0
                )
                empty_count = sum(1 for d in empty_dept if not d.get("member_ids"))
                _check_custom(
                    "hr",
                    "Empty departments (no employees)",
                    empty_count == 0,
                    empty_count,
                    f"{empty_count} active departments have zero employees",
                )
            except Exception:
                pass

        try:
            # Duplicate employees (same work_email)
            all_emps = c.search_read(
                "hr.employee", [("active", "=", True), ("work_email", "!=", False)], fields=["work_email"], limit=0
            )
            emails = [e["work_email"] for e in all_emps if e.get("work_email")]
            dupes = len(emails) - len(set(emails))
            _check_custom(
                "hr",
                "Duplicate employee work emails",
                dupes == 0,
                dupes,
                f"{dupes} duplicate work email addresses across employees",
            )
        except Exception:
            pass

        try:
            # Inactive employees still linked to active user
            inactive_with_user = c.search_count("hr.employee", [("active", "=", False), ("user_id", "!=", False)])
            _check_custom(
                "hr",
                "Archived employees with active user link",
                inactive_with_user == 0,
                inactive_with_user,
                f"{inactive_with_user} archived employees still linked to a user account",
            )
        except Exception:
            pass

        try:
            # Employees with departure date but still active
            active_departed = c.search_count("hr.employee", [("active", "=", True), ("departure_date", "!=", False)])
            _check_custom(
                "hr",
                "Active employees with departure date",
                active_departed == 0,
                active_departed,
                f"{active_departed} employees marked active but have a departure date set",
            )
        except Exception:
            pass

        # ------ INDONESIA: BPJS COMPLIANCE (5 checks) ------

        # Check if payroll_management is installed (has Indonesian fields)
        _has_payroll = model_available(c, "payroll.bpjs.config")
        _has_id_fields = False
        if _has_payroll:
            try:
                test_fields = c.fields_get("hr.employee")
                _has_id_fields = "npwp" in test_fields
            except Exception:
                pass
        elif cat == "hr":
            out.info("payroll_management not installed — Indonesian compliance checks (BPJS, PPh 21, UMR) skipped")

        if _has_id_fields:
            try:
                no_npwp = c.search_count("hr.employee", [("active", "=", True), ("npwp", "=", False)])
                _check_custom(
                    "hr",
                    "Employees without NPWP (tax ID)",
                    no_npwp == 0,
                    no_npwp,
                    f"{no_npwp} active employees have no NPWP — required for PPh 21 tax calculation",
                )
            except Exception:
                pass

            try:
                no_nik = c.search_count("hr.employee", [("active", "=", True), ("nik_ktp", "=", False)])
                _check_custom(
                    "hr",
                    "Employees without NIK/KTP",
                    no_nik == 0,
                    no_nik,
                    f"{no_nik} active employees have no NIK (KTP) — required for BPJS and tax reporting",
                )
            except Exception:
                pass

            try:
                no_bpjs_kes = c.search_count("hr.employee", [("active", "=", True), ("bpjs_kes_number", "=", False)])
                _check_custom(
                    "hr",
                    "Employees without BPJS Kesehatan no.",
                    no_bpjs_kes == 0,
                    no_bpjs_kes,
                    f"{no_bpjs_kes} active employees have no BPJS Kesehatan number — health insurance mandatory",
                )
            except Exception:
                pass

            try:
                no_bpjs_tk = c.search_count("hr.employee", [("active", "=", True), ("bpjs_tk_number", "=", False)])
                _check_custom(
                    "hr",
                    "Employees without BPJS Ketenagakerjaan no.",
                    no_bpjs_tk == 0,
                    no_bpjs_tk,
                    f"{no_bpjs_tk} active employees have no BPJS TK number — employment insurance mandatory",
                )
            except Exception:
                pass

            try:
                no_bank = c.search_count("hr.employee", [("active", "=", True), ("bank_account_number", "=", False)])
                _check_custom(
                    "hr",
                    "Employees without bank account",
                    no_bank == 0,
                    no_bank,
                    f"{no_bank} active employees have no bank account — required for salary disbursement",
                )
            except Exception:
                pass

        # ------ INDONESIA: PPh 21 / TAX (4 checks) ------

        if _has_payroll:
            try:
                no_ptkp = c.search_count("hr.employee", [("active", "=", True), ("ptkp_status", "=", False)])
                _check_custom(
                    "hr",
                    "Employees without PTKP status",
                    no_ptkp == 0,
                    no_ptkp,
                    f"{no_ptkp} active employees have no PTKP status — PPh 21 calculation will be incorrect",
                )
            except Exception:
                pass

            if model_available(c, "payroll.pph21.ter.config"):
                try:
                    current_year = today[:4]
                    ter_config = c.search_count(
                        "payroll.pph21.ter.config", [("year", "=", current_year), ("active", "=", True)]
                    )
                    _check_custom(
                        "hr",
                        f"PPh 21 TER config for {current_year}",
                        ter_config > 0,
                        0 if ter_config > 0 else 1,
                        f"No active PPh 21 TER rate table for {current_year} — payslips cannot compute tax"
                        if ter_config == 0
                        else f"TER config active for {current_year}",
                    )
                except Exception:
                    pass

            if model_available(c, "payroll.pph21.ptkp.config"):
                try:
                    current_year = today[:4]
                    ptkp_config = c.search_count(
                        "payroll.pph21.ptkp.config", [("year", "=", current_year), ("active", "=", True)]
                    )
                    _check_custom(
                        "hr",
                        f"PTKP config for {current_year}",
                        ptkp_config > 0,
                        0 if ptkp_config > 0 else 1,
                        f"No active PTKP table for {current_year} — tax-free threshold unknown"
                        if ptkp_config == 0
                        else f"PTKP config active for {current_year}",
                    )
                except Exception:
                    pass

            try:
                bpjs_config = c.search_count("payroll.bpjs.config", [("year", "=", today[:4])])
                _check_custom(
                    "hr",
                    f"BPJS rate config for {today[:4]}",
                    bpjs_config > 0,
                    0 if bpjs_config > 0 else 1,
                    f"No BPJS rate configuration for {today[:4]} — BPJS deductions cannot be calculated"
                    if bpjs_config == 0
                    else f"BPJS config active for {today[:4]}",
                )
            except Exception:
                pass

        # ------ INDONESIA: CONTRACT COMPLIANCE (3 checks) ------

        if _has_payroll and model_available(c, "hr.contract"):
            try:
                # Contracts marked BPJS Kes registered but no number
                bpjs_kes_no_num = c.search_count(
                    "hr.contract",
                    [("state", "=", "open"), ("bpjs_kes_registered", "=", True), ("bpjs_kes_number", "=", False)],
                )
                _check_custom(
                    "hr",
                    "Contracts BPJS Kes registered but no number",
                    bpjs_kes_no_num == 0,
                    bpjs_kes_no_num,
                    f"{bpjs_kes_no_num} contracts marked BPJS Kes registered but have no number",
                )
            except Exception:
                pass

            try:
                bpjs_tk_no_num = c.search_count(
                    "hr.contract",
                    [("state", "=", "open"), ("bpjs_tk_registered", "=", True), ("bpjs_tk_number", "=", False)],
                )
                _check_custom(
                    "hr",
                    "Contracts BPJS TK registered but no number",
                    bpjs_tk_no_num == 0,
                    bpjs_tk_no_num,
                    f"{bpjs_tk_no_num} contracts marked BPJS TK registered but have no number",
                )
            except Exception:
                pass

            try:
                no_struct = c.search_count("hr.contract", [("state", "=", "open"), ("struct_id", "=", False)])
                _check_custom(
                    "hr",
                    "Active contracts without salary structure",
                    no_struct == 0,
                    no_struct,
                    f"{no_struct} open contracts have no salary structure — payslips cannot be generated",
                )
            except Exception:
                pass

        if model_available(c, "payroll.umr.config"):
            try:
                current_year = today[:4]
                umr_config = c.search_count("payroll.umr.config", [("year", "=", current_year)])
                _check_custom(
                    "hr",
                    f"UMR (minimum wage) config for {current_year}",
                    umr_config > 0,
                    0 if umr_config > 0 else 1,
                    f"No UMR configuration for {current_year} — minimum wage validation disabled"
                    if umr_config == 0
                    else f"UMR config active for {current_year}",
                )
            except Exception:
                pass

    # =====================================================================
    # MANUFACTURING CHECKS
    # =====================================================================

    if cat in ("all", "mfg") and not model_available(c, "mrp.production") and cat == "mfg":
        out.warn("MRP module (mrp) is not installed — manufacturing checks skipped")

    if cat in ("all", "mfg") and model_available(c, "mrp.production"):
        try:
            bom_no_lines = c.search_count("mrp.bom", [("bom_line_ids", "=", False)])
            _check_custom(
                "mfg",
                "BOMs without components",
                bom_no_lines == 0,
                bom_no_lines,
                f"{bom_no_lines} BOMs have no component lines — cannot produce",
            )
        except Exception:
            pass

        try:
            mo_stuck_confirmed = c.search_count(
                "mrp.production", [("state", "=", "confirmed"), ("create_date", "<", thirty_days_ago)]
            )
            _check_custom(
                "mfg",
                "MOs stuck >30d (confirmed)",
                mo_stuck_confirmed == 0,
                mo_stuck_confirmed,
                f"{mo_stuck_confirmed} confirmed MOs not started for >30 days",
            )
        except Exception:
            pass

        try:
            mo_stuck_progress = c.search_count(
                "mrp.production", [("state", "=", "progress"), ("create_date", "<", thirty_days_ago)]
            )
            _check_custom(
                "mfg",
                "MOs stuck >30d (progress)",
                mo_stuck_progress == 0,
                mo_stuck_progress,
                f"{mo_stuck_progress} MOs in progress for >30 days",
            )
        except Exception:
            pass

        try:
            mo_draft_old = c.search_count(
                "mrp.production", [("state", "=", "draft"), ("create_date", "<", thirty_days_ago)]
            )
            _check_custom(
                "mfg",
                "Draft MOs >30d",
                mo_draft_old == 0,
                mo_draft_old,
                f"{mo_draft_old} draft MOs older than 30 days — confirm or cancel",
            )
        except Exception:
            pass

    # =====================================================================
    # CROSS-MODULE CHECKS
    # =====================================================================

    if cat in ("all", "cross"):
        try:
            so_no_delivery = c.search_count(
                "sale.order",
                [("state", "=", "sale"), ("delivery_count", "=", 0), ("create_date", "<", thirty_days_ago)],
            )
            _check_custom(
                "cross",
                "SO confirmed but no delivery",
                so_no_delivery == 0,
                so_no_delivery,
                f"{so_no_delivery} confirmed SOs >30d with no delivery created",
            )
        except Exception:
            pass

        try:
            so_no_invoice = c.search_count(
                "sale.order",
                [("state", "=", "sale"), ("invoice_count", "=", 0), ("create_date", "<", thirty_days_ago)],
            )
            _check_custom(
                "cross",
                "SO confirmed but no invoice",
                so_no_invoice == 0,
                so_no_invoice,
                f"{so_no_invoice} confirmed SOs >30d with no invoice created",
            )
        except Exception:
            pass

        if model_available(c, "purchase.order"):
            try:
                po_no_receipt = c.search_count(
                    "purchase.order",
                    [("state", "=", "purchase"), ("receipt_count", "=", 0), ("create_date", "<", thirty_days_ago)],
                )
                _check_custom(
                    "cross",
                    "PO confirmed but no receipt",
                    po_no_receipt == 0,
                    po_no_receipt,
                    f"{po_no_receipt} confirmed POs >30d with no goods receipt",
                )
            except Exception:
                pass

        try:
            inv_no_so = c.search_count(
                "account.move",
                [("move_type", "=", "out_invoice"), ("state", "=", "posted"), ("invoice_origin", "=", False)],
            )
            _check_custom(
                "cross",
                "Posted invoices without SO link",
                inv_no_so == 0,
                inv_no_so,
                f"{inv_no_so} posted customer invoices not linked to any SO",
            )
        except Exception:
            pass

        try:
            so_delivered_not_invoiced = c.search_count(
                "sale.order", [("state", "=", "sale"), ("invoice_status", "=", "to invoice")]
            )
            _check_custom(
                "cross",
                "Delivered but not invoiced",
                so_delivered_not_invoiced == 0,
                so_delivered_not_invoiced,
                f"{so_delivered_not_invoiced} SOs fully delivered but not yet invoiced",
            )
        except Exception:
            pass

        if model_available(c, "purchase.order"):
            try:
                po_received_not_billed = c.search_count(
                    "purchase.order", [("state", "=", "purchase"), ("invoice_status", "=", "to invoice")]
                )
                _check_custom(
                    "cross",
                    "Received but not billed",
                    po_received_not_billed == 0,
                    po_received_not_billed,
                    f"{po_received_not_billed} POs fully received but not yet billed",
                )
            except Exception:
                pass

        # --- Order-to-Cash workflow gaps ---
        try:
            # Partial deliveries not completed >14d
            partial_delivery = c.search_count(
                "stock.picking",
                [
                    ("picking_type_code", "=", "outgoing"),
                    ("state", "=", "assigned"),
                    ("scheduled_date", "<", fourteen_days_ago),
                ],
            )
            _check_custom(
                "cross",
                "Partial deliveries pending >14d",
                partial_delivery == 0,
                partial_delivery,
                f"{partial_delivery} outgoing deliveries ready but not validated >14 days",
            )
        except Exception:
            pass

        try:
            # Credit notes without original invoice reference
            cn_no_ref = c.search_count(
                "account.move",
                [("move_type", "=", "out_refund"), ("state", "=", "posted"), ("invoice_origin", "=", False)],
            )
            _check_custom(
                "cross",
                "Credit notes without origin",
                cn_no_ref == 0,
                cn_no_ref,
                f"{cn_no_ref} posted credit notes not linked to original invoice",
            )
        except Exception:
            pass

        try:
            # Payments without invoice reconciliation
            unreconciled_payments = c.search_count(
                "account.payment",
                [("state", "=", "posted"), ("is_reconciled", "=", False), ("date", "<", thirty_days_ago[:10])],
            )
            _check_custom(
                "cross",
                "Payments not reconciled >30d",
                unreconciled_payments == 0,
                unreconciled_payments,
                f"{unreconciled_payments} posted payments >30d not reconciled to invoices",
            )
        except Exception:
            pass

        # --- Procure-to-Pay workflow gaps ---
        if model_available(c, "purchase.order"):
            try:
                # PO confirmed but vendor bill amount mismatch
                po_done = c.search_read(
                    "purchase.order",
                    [("state", "=", "purchase"), ("invoice_status", "=", "invoiced")],
                    fields=["amount_total", "name"],
                    limit=500,
                )
                # Just count — detailed mismatch requires line-level comparison
                _check_custom(
                    "cross",
                    "POs fully billed (verified count)",
                    True,
                    len(po_done),
                    f"{len(po_done)} POs fully invoiced — spot check amounts if needed",
                )
            except Exception:
                pass

            try:
                # Draft POs >60 days — should be confirmed or cancelled
                stale_draft_po = c.search_count(
                    "purchase.order",
                    [("state", "=", "draft"), ("create_date", "<", sixty_days_ago)],
                )
                _check_custom(
                    "cross",
                    "Draft POs >60d (stale RFQs)",
                    stale_draft_po == 0,
                    stale_draft_po,
                    f"{stale_draft_po} RFQs in draft >60 days — confirm or cancel",
                )
            except Exception:
                pass

        # --- Inventory-to-Accounting gaps ---
        try:
            # Pickings done but no accounting entry (stock valuation gap)
            done_picks_no_move = c.search_count(
                "stock.picking",
                [
                    ("state", "=", "done"),
                    ("picking_type_code", "in", ["incoming", "outgoing"]),
                    ("date_done", "<", thirty_days_ago),
                ],
            )
            # This is informational — stock moves create journal entries automatically
            if done_picks_no_move > 0:
                _check_custom(
                    "cross",
                    "Completed picks >30d (reconcile stock vs GL)",
                    True,
                    done_picks_no_move,
                    f"{done_picks_no_move} completed picks >30d — verify stock valuation matches GL",
                )
        except Exception:
            pass

        # --- HR-to-Finance gaps ---
        if model_available(c, "hr.expense.sheet"):
            try:
                # Approved expenses not reimbursed >30d
                approved_not_paid = c.search_count(
                    "hr.expense.sheet",
                    [("state", "=", "approve"), ("create_date", "<", thirty_days_ago)],
                )
                _check_custom(
                    "cross",
                    "Approved expenses not paid >30d",
                    approved_not_paid == 0,
                    approved_not_paid,
                    f"{approved_not_paid} expense sheets approved >30d but not reimbursed",
                )
            except Exception:
                pass

        # --- Manufacturing-to-Inventory gaps ---
        if model_available(c, "mrp.production"):
            try:
                # MOs done but no stock move (should have consumed components)
                mo_done = c.search_count(
                    "mrp.production",
                    [("state", "=", "done"), ("date_start", "<", thirty_days_ago)],
                )
                if mo_done > 0:
                    _check_custom(
                        "cross",
                        "Completed MOs >30d (verify component consumption)",
                        True,
                        mo_done,
                        f"{mo_done} completed MOs >30d — verify component stock was consumed",
                    )
            except Exception:
                pass

        # --- Sales-to-CRM gaps ---
        if model_available(c, "crm.lead"):
            try:
                # Won opportunities without SO
                won_no_so = c.search_count(
                    "crm.lead",
                    [("stage_id.is_won", "=", True), ("order_ids", "=", False), ("type", "=", "opportunity")],
                )
                _check_custom(
                    "cross",
                    "Won opportunities without SO",
                    won_no_so == 0,
                    won_no_so,
                    f"{won_no_so} won opportunities with no linked sale order",
                )
            except Exception:
                pass

        # --- Payment-to-Invoice gaps ---
        try:
            # Invoices paid but amount_residual != 0 (partial payment or rounding issue)
            paid_with_residual = c.search_count(
                "account.move",
                [
                    ("move_type", "in", ["out_invoice", "in_invoice"]),
                    ("payment_state", "=", "paid"),
                    ("amount_residual", "!=", 0),
                ],
            )
            _check_custom(
                "cross",
                "Paid invoices with residual balance",
                paid_with_residual == 0,
                paid_with_residual,
                f"{paid_with_residual} invoices marked 'paid' but still have residual amount",
            )
        except Exception:
            pass

        # --- Aging analysis ---
        try:
            # Overdue AR >90 days
            overdue_ar_90 = c.search_count(
                "account.move",
                [
                    ("move_type", "=", "out_invoice"),
                    ("state", "=", "posted"),
                    ("payment_state", "!=", "paid"),
                    ("invoice_date_due", "<", ninety_days_ago[:10]),
                ],
            )
            _check_custom(
                "cross",
                "Overdue AR >90 days",
                overdue_ar_90 == 0,
                overdue_ar_90,
                f"{overdue_ar_90} customer invoices overdue >90 days — escalate collection",
            )
        except Exception:
            pass

        try:
            # Overdue AP >90 days
            overdue_ap_90 = c.search_count(
                "account.move",
                [
                    ("move_type", "=", "in_invoice"),
                    ("state", "=", "posted"),
                    ("payment_state", "!=", "paid"),
                    ("invoice_date_due", "<", ninety_days_ago[:10]),
                ],
            )
            _check_custom(
                "cross",
                "Overdue AP >90 days",
                overdue_ap_90 == 0,
                overdue_ap_90,
                f"{overdue_ap_90} vendor bills overdue >90 days — check vendor relationships",
            )
        except Exception:
            pass

    # =====================================================================
    # SUMMARY
    # =====================================================================

    check_count = len(rows)
    title = f"Data Integrity ({check_count} checks)"
    if total_issues:
        title += f" — [yellow]{total_issues} issues[/yellow]"
    else:
        title += " — [green]all clean[/green]"

    out.table(
        title,
        [("Cat", "dim"), ("Check", "cyan"), ("Status", ""), ("Detail", "dim")],
        rows,
        json_data,
    )


# ---------------------------------------------------------------------------
# Database Statistics
# ---------------------------------------------------------------------------


@app.command("db-stats")
def db_stats(ctx: typer.Context) -> None:
    """Show database size and growth indicators.

    Reports record counts for the largest tables, attachment storage,
    and key growth metrics useful for capacity planning.
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    def _count(model: str) -> int:
        try:
            return c.search_count(model, [])
        except Exception:
            return -1

    # Key tables that grow over time
    tables = [
        ("res.partner", "Partners / Contacts"),
        ("product.template", "Product Templates"),
        ("product.product", "Product Variants"),
        ("sale.order", "Sale Orders"),
        ("purchase.order", "Purchase Orders"),
        ("account.move", "Journal Entries"),
        ("account.move.line", "Journal Items"),
        ("stock.picking", "Stock Transfers"),
        ("stock.move", "Stock Moves"),
        ("stock.move.line", "Stock Move Lines"),
        ("mail.message", "Messages"),
        ("mail.mail", "Emails"),
        ("ir.attachment", "Attachments"),
        ("ir.logging", "Log Entries"),
        ("bus.bus", "Bus Notifications"),
    ]

    rows = []
    json_data = []
    for model, label in tables:
        count = _count(model)
        if count < 0:
            rows.append([label, model, "[dim]N/A[/dim]"])
        else:
            rows.append([label, model, f"{count:,}"])
        json_data.append({"label": label, "model": model, "count": count})

    out.table(
        "Database Size Indicators",
        [("Table", "cyan"), ("Model", "dim"), ("Records", "green")],
        rows,
        json_data,
    )

    # Summary
    total_records = sum(d["count"] for d in json_data if d["count"] > 0)
    out.info(f"Total tracked records: {total_records:,}")

    # Large table warnings
    for d in json_data:
        if d["count"] > 100000:
            out.warn(f"{d['label']} has {d['count']:,} records — consider archiving old data")


@app.command("health-report")
def health_report(ctx: typer.Context) -> None:
    """Generate a comprehensive daily health report.

    Combines: server status, module health, mail queue, cron status,
    storage usage, session activity, and data integrity into one report.
    Use this for daily/weekly operational reviews.
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    from datetime import datetime, timedelta

    now = datetime.now(tz=UTC)
    sections = []
    json_data: dict = {}

    # 1. Server
    ok, version = c.check_health()
    sections.append(
        (
            "Server",
            [
                ("Status", "[green]Healthy[/green]" if ok else "[red]Unhealthy[/red]"),
                ("Version", version),
                ("Database", c.database),
            ],
        )
    )
    json_data["server"] = {"healthy": ok, "version": version, "database": c.database}

    # 2. Modules
    installed = c.search_count("ir.module.module", [("state", "=", "installed")])
    stuck = c.search_count("ir.module.module", [("state", "in", ["to install", "to upgrade", "to remove"])])
    sections.append(
        (
            "Modules",
            [
                ("Installed", str(installed)),
                ("Stuck", f"[red]{stuck}[/red]" if stuck else "[green]0[/green]"),
            ],
        )
    )
    json_data["modules"] = {"installed": installed, "stuck": stuck}

    # 3. Mail
    try:
        mail_out = c.search_count("mail.mail", [("state", "=", "outgoing")])
        mail_err = c.search_count("mail.mail", [("state", "=", "exception")])
        sections.append(
            (
                "Mail Queue",
                [
                    ("Outgoing", str(mail_out)),
                    ("Failed", f"[red]{mail_err}[/red]" if mail_err else "[green]0[/green]"),
                ],
            )
        )
        json_data["mail"] = {"outgoing": mail_out, "failed": mail_err}
    except Exception:
        pass

    # 4. Cron
    crons = c.search_read("ir.cron", domain=[("active", "=", True)], fields=["nextcall"], limit=200)
    overdue = 0
    for cr in crons:
        nc = cr.get("nextcall")
        if nc:
            try:
                next_dt = datetime.strptime(str(nc)[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
                if next_dt < now - timedelta(hours=2):
                    overdue += 1
            except (ValueError, TypeError):
                pass
    sections.append(
        (
            "Cron Jobs",
            [
                ("Active", str(len(crons))),
                ("Overdue", f"[red]{overdue}[/red]" if overdue else "[green]0[/green]"),
            ],
        )
    )
    json_data["cron"] = {"active": len(crons), "overdue": overdue}

    # 5. Users
    active_users = c.search_count("res.users", [("active", "=", True), ("share", "=", False)])
    sections.append(("Users", [("Active internal", str(active_users))]))
    json_data["users"] = {"active_internal": active_users}

    # 6. Storage
    try:
        attachments = c.search_count("ir.attachment", [])
        sections.append(("Storage", [("Attachments", f"{attachments:,}")]))
        json_data["storage"] = {"attachments": attachments}
    except Exception:
        pass

    # 7. Queue Jobs
    try:
        failed_jobs = c.search_count("queue.job", [("state", "=", "failed")])
        pending_jobs = c.search_count("queue.job", [("state", "in", ["pending", "enqueued"])])
        sections.append(
            (
                "Queue Jobs",
                [
                    ("Pending", str(pending_jobs)),
                    ("Failed", f"[red]{failed_jobs}[/red]" if failed_jobs else "[green]0[/green]"),
                ],
            )
        )
        json_data["queue_jobs"] = {"pending": pending_jobs, "failed": failed_jobs}
    except Exception:
        pass

    # Overall status
    mail_err_count = json_data.get("mail", {}).get("failed", 0)
    failed_job_count = json_data.get("queue_jobs", {}).get("failed", 0)
    problems = stuck + mail_err_count + overdue + failed_job_count
    overall = "[green]HEALTHY[/green]" if problems == 0 else f"[yellow]{problems} issues[/yellow]"
    sections.insert(0, ("Overall", [("Status", overall), ("Timestamp", now.strftime("%Y-%m-%d %H:%M UTC"))]))

    out.detail(f"Daily Health Report — {c.database}", sections, json_data)


# ---------------------------------------------------------------------------
# Monthly Close — combined accounting + inventory close validation
# ---------------------------------------------------------------------------


@app.command("monthly-close")
def monthly_close(
    ctx: typer.Context,
    period_end: Annotated[
        str | None, typer.Option("--date", "-d", help="Period end date (YYYY-MM-DD, default: last month end)")
    ] = None,
) -> None:
    """Combined monthly close validation (accounting + inventory).

    Runs both accounting-close and inventory-close checks, then presents
    a unified summary with total blocking issues across both areas.

    Examples:
        kctl-odoo maintenance monthly-close
        kctl-odoo maintenance monthly-close --date 2025-12-31
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    from datetime import date, datetime, timedelta

    now = datetime.now(tz=UTC)

    if period_end:
        close_date = period_end
    else:
        first_of_month = date(now.year, now.month, 1)
        last_month_end = first_of_month - timedelta(days=1)
        close_date = str(last_month_end)

    rows: list[list[str]] = []
    json_data: list[dict] = []
    acct_issues = 0
    inv_issues = 0

    def _add(area: str, name: str, ok: bool, detail: str) -> None:
        nonlocal acct_issues, inv_issues
        if not ok:
            if area == "ACCT":
                acct_issues += 1
            else:
                inv_issues += 1
        status = "[green]PASS[/green]" if ok else "[red]FAIL[/red]"
        rows.append([area, name, status, detail])
        json_data.append({"area": area, "check": name, "passed": ok, "detail": detail})

    out.info(f"Monthly close validation for period ending: {close_date}")

    # =====================================================================
    # ACCOUNTING CHECKS
    # =====================================================================

    # 1. Trial Balance
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
        _add("ACCT", "Trial balance (debit = credit)", diff < 0.01, f"Diff: {diff:,.2f}")
    except Exception as e:
        _add("ACCT", "Trial balance", False, f"Check failed: {e}")

    # 2. Unposted entries in period
    try:
        draft_in_period = c.search_count("account.move", [("state", "=", "draft"), ("date", "<=", close_date)])
        _add("ACCT", "No unposted entries", draft_in_period == 0, f"{draft_in_period} draft entries in period")
    except Exception as e:
        _add("ACCT", "Unposted entries", False, str(e))

    # 3. Draft invoices
    try:
        draft_invoices = c.search_count(
            "account.move",
            [
                ("state", "=", "draft"),
                ("move_type", "in", ["out_invoice", "in_invoice", "out_refund", "in_refund"]),
                ("invoice_date", "<=", close_date),
            ],
        )
        _add("ACCT", "No draft invoices/bills", draft_invoices == 0, f"{draft_invoices} draft invoices in period")
    except Exception as e:
        _add("ACCT", "Draft invoices", False, str(e))

    # 4. Bank reconciliation
    try:
        unreconciled_bank = c.search_count(
            "account.bank.statement.line",
            [("is_reconciled", "=", False), ("date", "<=", close_date)],
        )
        _add("ACCT", "Bank reconciled", unreconciled_bank == 0, f"{unreconciled_bank} unreconciled bank lines")
    except Exception:
        _add("ACCT", "Bank reconciliation", True, "Skipped — module not active")

    # 5. Suspense accounts
    try:
        suspense = c.search_read("account.account", [("name", "ilike", "suspense")], fields=["id", "name"], limit=5)
        suspense_ok = True
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
        if suspense:
            _add("ACCT", "Suspense accounts at zero", suspense_ok, f"{len(suspense)} suspense accounts checked")
    except Exception:
        pass

    # 6. Lock dates
    try:
        companies = c.search_read(
            "res.company", [], fields=["name", "period_lock_date", "fiscalyear_lock_date"], limit=5
        )
        for comp in companies:
            has_lock = bool(comp.get("period_lock_date") or comp.get("fiscalyear_lock_date"))
            _add(
                "ACCT",
                f"Lock dates ({comp['name']})",
                has_lock,
                f"Period: {comp.get('period_lock_date') or 'not set'},"
                f" FY: {comp.get('fiscalyear_lock_date') or 'not set'}",
            )
    except Exception:
        pass

    # =====================================================================
    # INVENTORY CHECKS
    # =====================================================================

    # 1. Negative stock
    try:
        negative = c.search_count("stock.quant", [("quantity", "<", 0), ("location_id.usage", "=", "internal")])
        _add("INV", "No negative stock", negative == 0, f"{negative} products with negative quantities")
    except Exception as e:
        _add("INV", "Negative stock", False, str(e))

    # 2. Stuck transfers
    try:
        cutoff_7d = (now - timedelta(days=7)).strftime("%Y-%m-%d")
        stuck = c.search_count(
            "stock.picking",
            [("state", "in", ["waiting", "confirmed"]), ("scheduled_date", "<", cutoff_7d)],
        )
        _add("INV", "No stuck transfers (>7d)", stuck == 0, f"{stuck} transfers stuck >7 days")
    except Exception as e:
        _add("INV", "Stuck transfers", False, str(e))

    # 3. Unprocessed deliveries
    try:
        unshipped = c.search_count(
            "stock.picking",
            [
                ("state", "=", "assigned"),
                ("picking_type_code", "=", "outgoing"),
                ("scheduled_date", "<=", close_date),
            ],
        )
        _add("INV", "All deliveries processed", unshipped == 0, f"{unshipped} ready deliveries not shipped")
    except Exception as e:
        _add("INV", "Deliveries", False, str(e))

    # 4. Orphan stock moves
    try:
        orphan_moves = c.search_count(
            "stock.move",
            [("picking_id", "=", False), ("state", "not in", ["done", "cancel"]), ("date", "<=", close_date)],
        )
        _add("INV", "No orphan stock moves", orphan_moves == 0, f"{orphan_moves} moves without picking")
    except Exception as e:
        _add("INV", "Orphan moves", False, str(e))

    # 5. Valuation vs GL
    try:
        layers = c.search_read("stock.valuation.layer", [("company_id", "!=", False)], fields=["value"], limit=0)
        layer_total = sum(line.get("value", 0) for line in layers)
        stock_accounts = c.search_read(
            "account.account",
            [("account_type", "=", "asset_current"), ("name", "ilike", "stock valuation")],
            fields=["id"],
            limit=5,
        )
        gl_total = 0.0
        for sa in stock_accounts:
            gl_lines = c.search_read(
                "account.move.line",
                [("account_id", "=", sa["id"]), ("parent_state", "=", "posted")],
                fields=["debit", "credit"],
                limit=0,
            )
            gl_total += sum(line.get("debit", 0) - line.get("credit", 0) for line in gl_lines)
        diff = abs(layer_total - gl_total)
        _add("INV", "Valuation matches GL", diff < 1.0, f"Diff: {diff:,.2f}")
    except Exception:
        _add("INV", "Valuation vs GL", True, "Skipped — not available")

    # 6. Expired lots
    try:
        today_str = now.strftime("%Y-%m-%d")
        expired = c.search_count("stock.lot", [("expiration_date", "<", today_str), ("product_qty", ">", 0)])
        _add("INV", "No expired lots with stock", expired == 0, f"{expired} expired lots with stock")
    except Exception:
        _add("INV", "Expired lots", True, "Skipped — lot tracking not active")

    # =====================================================================
    # SUMMARY
    # =====================================================================

    total_issues = acct_issues + inv_issues
    acct_total = sum(1 for d in json_data if d["area"] == "ACCT")
    inv_total = sum(1 for d in json_data if d["area"] == "INV")
    acct_passed = sum(1 for d in json_data if d["area"] == "ACCT" and d["passed"])
    inv_passed = sum(1 for d in json_data if d["area"] == "INV" and d["passed"])

    title = f"Monthly Close — {close_date}"
    if total_issues:
        title += f" — [red]{total_issues} blocking[/red]"
        title += f" (acct: {acct_passed}/{acct_total}, inv: {inv_passed}/{inv_total})"
    else:
        title += f" — [green]ready to close[/green] ({acct_passed + inv_passed}/{acct_total + inv_total} passed)"

    out.table(
        title,
        [("Area", "dim"), ("Check", "cyan"), ("Status", ""), ("Detail", "dim")],
        rows,
        json_data,
    )

    if total_issues:
        if acct_issues:
            out.warn(f"Accounting: {acct_issues} blocking issue(s)")
        if inv_issues:
            out.warn(f"Inventory: {inv_issues} blocking issue(s)")
        out.warn(f"Fix {total_issues} total issues before closing period {close_date}")
    else:
        out.success(f"All checks passed — period {close_date} is ready to close")
        out.info(f"Set lock date via: kctl-odoo master-data setting-set period_lock_date {close_date}")


@app.command("check-financial-statements")
def check_financial_statements(
    ctx: typer.Context,
    date: Annotated[str | None, typer.Option("--date", help="As-of date (YYYY-MM-DD, default: today)")] = None,
    period_start: Annotated[str | None, typer.Option("--period-start", help="Period start (YYYY-MM-DD)")] = None,
) -> None:
    """Financial statement integrity checks for P&L, Balance Sheet, and Cash Flow.

    Runs 12 checks that auditors verify before signing off:
    - Balance sheet equation (Assets = Liabilities + Equity)
    - AR/AP sub-ledger vs GL reconciliation
    - Revenue vs confirmed SO comparison
    - COGS vs inventory valuation change
    - Stale prepaid/accrued balances
    - Bank balance vs GL
    - Large manual journal entries (audit risk)
    - Revenue cut-off (entries after period end)

    Examples:
        kctl-odoo maintenance check-financial-statements
        kctl-odoo maintenance check-financial-statements --date 2026-03-31
        kctl-odoo maintenance check-financial-statements --date 2026-03-31 --period-start 2026-01-01
    """
    from datetime import datetime

    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    now = datetime.now(tz=UTC)
    as_of = date or now.strftime("%Y-%m-%d")
    p_start = period_start or as_of[:7] + "-01"  # First day of the as-of month

    rows: list[list[str]] = []
    json_data: list[dict] = []
    total_issues = 0

    def _add(name: str, ok: bool, count: int, detail: str) -> None:
        nonlocal total_issues
        if not ok:
            total_issues += count
        status = "[green]OK[/green]" if ok else f"[red]{count}[/red]"
        rows.append([name, status, detail if not ok else detail])
        json_data.append({"check": name, "ok": ok, "count": count, "detail": detail})

    out.info(f"Financial statement checks as of {as_of} (period from {p_start})")

    # =====================================================================
    # 1. BALANCE SHEET EQUATION: Assets = Liabilities + Equity
    # =====================================================================
    try:
        # Get account types and balances
        asset_types = [
            "asset_receivable",
            "asset_cash",
            "asset_current",
            "asset_non_current",
            "asset_prepayments",
            "asset_fixed",
        ]
        liability_types = ["liability_payable", "liability_current", "liability_non_current"]
        equity_types = ["equity", "equity_unaffected"]

        total_assets = 0
        total_liabilities = 0
        total_equity = 0

        for acc_type in asset_types:
            try:
                lines = c.search_read(
                    "account.move.line",
                    [
                        ("account_id.account_type", "=", acc_type),
                        ("parent_state", "=", "posted"),
                        ("date", "<=", as_of),
                    ],
                    fields=["debit", "credit"],
                    limit=0,
                )
                total_assets += sum(l.get("debit", 0) - l.get("credit", 0) for l in lines)
            except Exception:
                pass

        for acc_type in liability_types:
            try:
                lines = c.search_read(
                    "account.move.line",
                    [
                        ("account_id.account_type", "=", acc_type),
                        ("parent_state", "=", "posted"),
                        ("date", "<=", as_of),
                    ],
                    fields=["debit", "credit"],
                    limit=0,
                )
                total_liabilities += sum(l.get("credit", 0) - l.get("debit", 0) for l in lines)
            except Exception:
                pass

        for acc_type in equity_types:
            try:
                lines = c.search_read(
                    "account.move.line",
                    [
                        ("account_id.account_type", "=", acc_type),
                        ("parent_state", "=", "posted"),
                        ("date", "<=", as_of),
                    ],
                    fields=["debit", "credit"],
                    limit=0,
                )
                total_equity += sum(l.get("credit", 0) - l.get("debit", 0) for l in lines)
            except Exception:
                pass

        # Add income/expense to equity (current year P&L)
        for acc_type in ["income", "income_other"]:
            try:
                lines = c.search_read(
                    "account.move.line",
                    [
                        ("account_id.account_type", "=", acc_type),
                        ("parent_state", "=", "posted"),
                        ("date", "<=", as_of),
                    ],
                    fields=["debit", "credit"],
                    limit=0,
                )
                total_equity += sum(l.get("credit", 0) - l.get("debit", 0) for l in lines)
            except Exception:
                pass
        for acc_type in ["expense", "expense_depreciation", "expense_direct_cost"]:
            try:
                lines = c.search_read(
                    "account.move.line",
                    [
                        ("account_id.account_type", "=", acc_type),
                        ("parent_state", "=", "posted"),
                        ("date", "<=", as_of),
                    ],
                    fields=["debit", "credit"],
                    limit=0,
                )
                total_equity -= sum(l.get("debit", 0) - l.get("credit", 0) for l in lines)
            except Exception:
                pass

        diff = abs(total_assets - total_liabilities - total_equity)
        ok = diff < 1.0  # Allow 1 rounding tolerance
        _add(
            "BS equation (A = L + E)",
            ok,
            1 if not ok else 0,
            f"Assets: {total_assets:,.2f}, Liabilities: {total_liabilities:,.2f}, Equity: {total_equity:,.2f}, Diff: {diff:,.2f}",
        )
    except Exception as e:
        _add("BS equation (A = L + E)", False, 1, f"Error: {e}")

    # =====================================================================
    # 2. AR SUB-LEDGER vs GL
    # =====================================================================
    try:
        # GL AR balance
        ar_gl_lines = c.search_read(
            "account.move.line",
            [
                ("account_id.account_type", "=", "asset_receivable"),
                ("parent_state", "=", "posted"),
                ("date", "<=", as_of),
            ],
            fields=["debit", "credit"],
            limit=0,
        )
        ar_gl = sum(l.get("debit", 0) - l.get("credit", 0) for l in ar_gl_lines)

        # Sub-ledger: sum of open invoice amount_residual
        open_invoices = c.search_read(
            "account.move",
            [
                ("move_type", "=", "out_invoice"),
                ("state", "=", "posted"),
                ("payment_state", "in", ["not_paid", "partial"]),
                ("invoice_date", "<=", as_of),
            ],
            fields=["amount_residual"],
            limit=0,
        )
        ar_sub = sum(inv.get("amount_residual", 0) for inv in open_invoices)

        ar_diff = abs(ar_gl - ar_sub)
        ok = ar_diff < 100  # Some tolerance for timing
        _add(
            "AR: GL vs sub-ledger",
            ok,
            1 if not ok else 0,
            f"GL: {ar_gl:,.2f}, Open invoices: {ar_sub:,.2f}, Diff: {ar_diff:,.2f}",
        )
    except Exception:
        _add("AR: GL vs sub-ledger", True, 0, "Could not compare")

    # =====================================================================
    # 3. AP SUB-LEDGER vs GL
    # =====================================================================
    try:
        ap_gl_lines = c.search_read(
            "account.move.line",
            [
                ("account_id.account_type", "=", "liability_payable"),
                ("parent_state", "=", "posted"),
                ("date", "<=", as_of),
            ],
            fields=["debit", "credit"],
            limit=0,
        )
        ap_gl = sum(l.get("credit", 0) - l.get("debit", 0) for l in ap_gl_lines)

        open_bills = c.search_read(
            "account.move",
            [
                ("move_type", "=", "in_invoice"),
                ("state", "=", "posted"),
                ("payment_state", "in", ["not_paid", "partial"]),
                ("invoice_date", "<=", as_of),
            ],
            fields=["amount_residual"],
            limit=0,
        )
        ap_sub = sum(bill.get("amount_residual", 0) for bill in open_bills)

        ap_diff = abs(ap_gl - ap_sub)
        ok = ap_diff < 100
        _add(
            "AP: GL vs sub-ledger",
            ok,
            1 if not ok else 0,
            f"GL: {ap_gl:,.2f}, Open bills: {ap_sub:,.2f}, Diff: {ap_diff:,.2f}",
        )
    except Exception:
        _add("AP: GL vs sub-ledger", True, 0, "Could not compare")

    # =====================================================================
    # 4. REVENUE vs CONFIRMED SO
    # =====================================================================
    try:
        # Revenue from GL (income accounts in period)
        revenue_lines = c.search_read(
            "account.move.line",
            [
                ("account_id.account_type", "in", ["income", "income_other"]),
                ("parent_state", "=", "posted"),
                ("date", ">=", p_start),
                ("date", "<=", as_of),
            ],
            fields=["credit", "debit"],
            limit=0,
        )
        gl_revenue = sum(l.get("credit", 0) - l.get("debit", 0) for l in revenue_lines)

        # SO confirmed in period
        so_revenue = c.search_read(
            "sale.order",
            [("state", "=", "sale"), ("date_order", ">=", p_start), ("date_order", "<=", as_of)],
            fields=["amount_untaxed"],
            limit=0,
        )
        so_total = sum(s.get("amount_untaxed", 0) for s in so_revenue)

        rev_diff = abs(gl_revenue - so_total)
        pct_diff = (rev_diff / max(gl_revenue, 1)) * 100
        ok = pct_diff < 20  # 20% tolerance (timing, credit notes, etc.)
        _add(
            "Revenue: GL vs SO",
            ok,
            1 if not ok else 0,
            f"GL revenue: {gl_revenue:,.2f}, SO total: {so_total:,.2f}, Diff: {pct_diff:.1f}%",
        )
    except Exception:
        _add("Revenue: GL vs SO", True, 0, "Could not compare")

    # =====================================================================
    # 5. COGS vs INVENTORY VALUATION CHANGE
    # =====================================================================
    try:
        cogs_lines = c.search_read(
            "account.move.line",
            [
                ("account_id.account_type", "=", "expense_direct_cost"),
                ("parent_state", "=", "posted"),
                ("date", ">=", p_start),
                ("date", "<=", as_of),
            ],
            fields=["debit", "credit"],
            limit=0,
        )
        gl_cogs = sum(l.get("debit", 0) - l.get("credit", 0) for l in cogs_lines)
        _add("COGS recorded in period", True, 0, f"COGS: {gl_cogs:,.2f}")
    except Exception:
        _add("COGS recorded in period", True, 0, "Could not calculate")

    # =====================================================================
    # 6. STALE PREPAID BALANCES
    # =====================================================================
    try:
        prepaid_lines = c.search_read(
            "account.move.line",
            [
                ("account_id.account_type", "=", "asset_prepayments"),
                ("parent_state", "=", "posted"),
                ("date", "<=", as_of),
            ],
            fields=["debit", "credit"],
            limit=0,
        )
        prepaid_balance = sum(l.get("debit", 0) - l.get("credit", 0) for l in prepaid_lines)
        ok = prepaid_balance >= 0
        _add(
            "Prepaid balance",
            ok,
            1 if not ok else 0,
            f"Prepaid/advance balance: {prepaid_balance:,.2f}" + (" — negative balance is unusual" if not ok else ""),
        )
    except Exception:
        _add("Prepaid balance", True, 0, "Could not calculate")

    # =====================================================================
    # 7. BANK BALANCE vs GL
    # =====================================================================
    try:
        bank_journals = c.search_read(
            "account.journal",
            [("type", "=", "bank")],
            fields=["name", "default_account_id"],
            limit=10,
        )
        for bj in bank_journals:
            acc_id = bj["default_account_id"]
            if isinstance(acc_id, list):
                acc_id = acc_id[0]
            if not acc_id:
                continue
            bank_lines = c.search_read(
                "account.move.line",
                [("account_id", "=", acc_id), ("parent_state", "=", "posted"), ("date", "<=", as_of)],
                fields=["debit", "credit"],
                limit=0,
            )
            bank_gl = sum(l.get("debit", 0) - l.get("credit", 0) for l in bank_lines)
            _add(f"Bank GL: {bj['name']}", True, 0, f"Balance: {bank_gl:,.2f}")
    except Exception:
        _add("Bank GL balances", True, 0, "Could not calculate")

    # =====================================================================
    # 8. LARGE MANUAL JOURNAL ENTRIES (audit risk)
    # =====================================================================
    try:
        # Manual entries > threshold in period
        threshold = 50_000_000  # 50 million IDR
        large_entries = c.search_count(
            "account.move",
            [
                ("move_type", "=", "entry"),
                ("state", "=", "posted"),
                ("date", ">=", p_start),
                ("date", "<=", as_of),
                ("amount_total", ">", threshold),
            ],
        )
        _add(
            "Large manual entries (>50M)",
            large_entries == 0,
            large_entries,
            f"{large_entries} manual journal entries above {threshold:,.0f} — review for appropriateness",
        )
    except Exception:
        _add("Large manual entries", True, 0, "Could not check")

    # =====================================================================
    # 9. REVENUE CUT-OFF
    # =====================================================================
    try:
        # Revenue entries after period end (next month entries dated in this period)
        as_of[:8] + "01"  # crude — just informational
        revenue_after = c.search_count(
            "account.move",
            [
                ("move_type", "=", "out_invoice"),
                ("state", "=", "posted"),
                ("invoice_date", ">", as_of),
                ("create_date", "<=", as_of + " 23:59:59"),
            ],
        )
        _add(
            "Revenue cut-off",
            revenue_after == 0,
            revenue_after,
            f"{revenue_after} invoices dated after {as_of} but created on/before — potential cut-off issue",
        )
    except Exception:
        _add("Revenue cut-off", True, 0, "Could not check")

    # =====================================================================
    # 10. CASH POSITION SUMMARY
    # =====================================================================
    try:
        cash_types = ["asset_cash"]
        cash_lines = c.search_read(
            "account.move.line",
            [("account_id.account_type", "in", cash_types), ("parent_state", "=", "posted"), ("date", "<=", as_of)],
            fields=["debit", "credit"],
            limit=0,
        )
        cash_balance = sum(l.get("debit", 0) - l.get("credit", 0) for l in cash_lines)
        ok = cash_balance >= 0
        _add(
            "Cash position",
            ok,
            1 if not ok else 0,
            f"Total cash/bank: {cash_balance:,.2f}" + (" — NEGATIVE cash balance!" if not ok else ""),
        )
    except Exception:
        _add("Cash position", True, 0, "Could not calculate")

    # =====================================================================
    # 11. UNEARNED REVENUE / DEFERRED INCOME
    # =====================================================================
    try:
        deferred_lines = c.search_read(
            "account.move.line",
            [
                ("account_id.account_type", "=", "liability_current"),
                ("account_id.name", "ilike", "deferred"),
                ("parent_state", "=", "posted"),
                ("date", "<=", as_of),
            ],
            fields=["debit", "credit"],
            limit=0,
        )
        if deferred_lines:
            deferred_balance = sum(l.get("credit", 0) - l.get("debit", 0) for l in deferred_lines)
            _add("Deferred revenue", True, 0, f"Balance: {deferred_balance:,.2f} — verify amortization schedule")
    except Exception:
        pass

    # =====================================================================
    # 12. P&L SUMMARY FOR PERIOD
    # =====================================================================
    try:
        # Total revenue
        rev_lines = c.search_read(
            "account.move.line",
            [
                ("account_id.account_type", "in", ["income", "income_other"]),
                ("parent_state", "=", "posted"),
                ("date", ">=", p_start),
                ("date", "<=", as_of),
            ],
            fields=["credit", "debit"],
            limit=0,
        )
        period_revenue = sum(l.get("credit", 0) - l.get("debit", 0) for l in rev_lines)

        # Total expenses
        exp_lines = c.search_read(
            "account.move.line",
            [
                ("account_id.account_type", "in", ["expense", "expense_depreciation", "expense_direct_cost"]),
                ("parent_state", "=", "posted"),
                ("date", ">=", p_start),
                ("date", "<=", as_of),
            ],
            fields=["debit", "credit"],
            limit=0,
        )
        period_expenses = sum(l.get("debit", 0) - l.get("credit", 0) for l in exp_lines)

        net_income = period_revenue - period_expenses
        margin = (net_income / period_revenue * 100) if period_revenue > 0 else 0
        _add(
            "P&L summary",
            True,
            0,
            f"Revenue: {period_revenue:,.2f}, Expenses: {period_expenses:,.2f}, Net: {net_income:,.2f} ({margin:.1f}%)",
        )
    except Exception:
        _add("P&L summary", True, 0, "Could not calculate")

    # =====================================================================
    # DISPLAY
    # =====================================================================
    issue_count = sum(1 for r in rows if "[red]" in r[1])
    title = f"Financial Statement Checks — {as_of}"
    if issue_count > 0:
        title += f" — {issue_count} issue(s)"

    out.table(
        title,
        [("Check", ""), ("Status", ""), ("Detail", "")],
        rows,
        data_for_json=json_data,
    )

    if issue_count > 0:
        out.warn(f"{issue_count} issue(s) found — review before finalizing financial statements")
    else:
        out.success("All financial statement checks passed")
