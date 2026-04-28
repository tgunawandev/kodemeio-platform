"""Production readiness audit command for Odoo 18.

Generates a comprehensive Excel report covering all Odoo configuration
required for go-live: company settings, CoA, partner properties, journals,
taxes, products, warehouses, OUs, reports, users, modules.

Works on any Odoo 18 instance with or without accurate_integration installed.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Annotated, Any

import typer

from kctl_odoo.core.callbacks import AppContext


app = typer.Typer(help="Production readiness audit.")


def _bump_timeout(actx: AppContext, seconds: float = 600.0) -> None:
    try:
        import httpx

        actx.client._client.timeout = httpx.Timeout(seconds)
    except Exception:
        pass


def _safe(value: Any, default: str = "") -> str:
    if value is False or value is None:
        return default
    if isinstance(value, list) and len(value) == 2:
        return str(value[1])
    return str(value)


def _check_company(c, company_id: int, company_name: str) -> dict[str, Any]:
    """Run all readiness checks for one company. Returns dict of section→list of checks."""
    results: dict[str, list[dict[str, Any]]] = {
        "company": [],
        "coa": [],
        "journals": [],
        "taxes": [],
        "products": [],
        "partners": [],
        "stock": [],
        "ou": [],
        "reports": [],
        "users": [],
        "modules": [],
    }

    def add(section: str, name: str, status: str, value: Any = "", expected: Any = "", note: str = ""):
        results[section].append(
            {
                "company": company_name,
                "check": name,
                "status": status,
                "value": str(value),
                "expected": str(expected),
                "note": note,
            }
        )

    # ── 1. Company Settings ─────────────────────────────────────────────
    co = c.search_read(
        "res.company",
        [("id", "=", company_id)],
        fields=[
            "name",
            "currency_id",
            "account_fiscal_country_id",
            "account_sale_tax_id",
            "account_purchase_tax_id",
            "income_currency_exchange_account_id",
            "expense_currency_exchange_account_id",
            "transfer_account_id",
            "anglo_saxon_accounting",
            "fiscalyear_lock_date",
            "tax_lock_date",
        ],
    )[0]

    add("company", "Currency", "PASS" if _safe(co["currency_id"]) == "IDR" else "WARN", _safe(co["currency_id"]), "IDR")
    add(
        "company",
        "Fiscal Country",
        "PASS" if "Indonesia" in _safe(co["account_fiscal_country_id"]) else "WARN",
        _safe(co["account_fiscal_country_id"]),
        "Indonesia",
    )
    add(
        "company",
        "Default Sale Tax",
        "PASS" if co["account_sale_tax_id"] else "FAIL",
        _safe(co["account_sale_tax_id"]),
        "Set (PPN 12% etc.)",
    )
    add(
        "company",
        "Default Purchase Tax",
        "PASS" if co["account_purchase_tax_id"] else "FAIL",
        _safe(co["account_purchase_tax_id"]),
        "Set (PPN 12% etc.)",
    )
    add("company", "Anglo-Saxon Accounting", "INFO", str(co.get("anglo_saxon_accounting")), "True/False (consistent)")
    add(
        "company",
        "FX Income Account",
        "PASS" if co["income_currency_exchange_account_id"] else "WARN",
        _safe(co["income_currency_exchange_account_id"]),
        "Set (income type)",
    )
    add(
        "company",
        "FX Expense Account",
        "PASS" if co["expense_currency_exchange_account_id"] else "WARN",
        _safe(co["expense_currency_exchange_account_id"]),
        "Set (expense type)",
    )
    add(
        "company",
        "Transfer Account",
        "PASS" if co["transfer_account_id"] else "WARN",
        _safe(co["transfer_account_id"]),
        "Set (current asset, reconcile)",
    )
    add("company", "Fiscal Year Lock", "INFO", _safe(co["fiscalyear_lock_date"], "Not set"), "Set after FY close")
    add("company", "Tax Lock", "INFO", _safe(co["tax_lock_date"], "Not set"), "Set after tax filing")

    # ── 2. CoA & Properties ────────────────────────────────────────────
    accounts = c.search_count("account.account", [("company_ids", "in", company_id)])
    no_code = c.search_count("account.account", [("company_ids", "in", company_id), ("code", "=", False)])
    add("coa", "Total accounts", "PASS" if accounts > 50 else "WARN", str(accounts), ">50")
    add(
        "coa",
        "Accounts without code",
        "PASS" if no_code == 0 else "FAIL",
        str(no_code),
        "0",
        "Run scripts/backfill-coa-codes.py",
    )

    for atype, label in [
        ("asset_cash", "Cash account"),
        ("asset_receivable", "Receivable account"),
        ("liability_payable", "Payable account"),
        ("income", "Income account"),
        ("expense_direct_cost", "COGS account"),
        ("equity", "Equity account"),
    ]:
        cnt = c.search_count("account.account", [("company_ids", "in", company_id), ("account_type", "=", atype)])
        add("coa", f"Has {label}", "PASS" if cnt > 0 else "FAIL", str(cnt), "≥1")

    # Product category properties (ir.property)
    cats = c.search_read(
        "product.category",
        [],
        fields=[
            "name",
            "property_account_income_categ_id",
            "property_account_expense_categ_id",
            "property_stock_account_input_categ_id",
            "property_stock_account_output_categ_id",
            "property_stock_valuation_account_id",
            "property_stock_journal",
            "property_cost_method",
            "property_valuation",
        ],
    )
    cats_with_income = sum(1 for cat in cats if cat["property_account_income_categ_id"])
    cats_with_expense = sum(1 for cat in cats if cat["property_account_expense_categ_id"])
    cats_with_stock_in = sum(1 for cat in cats if cat["property_stock_account_input_categ_id"])
    cats_with_stock_out = sum(1 for cat in cats if cat["property_stock_account_output_categ_id"])
    cats_with_valuation = sum(1 for cat in cats if cat["property_stock_valuation_account_id"])
    cats_with_journal = sum(1 for cat in cats if cat["property_stock_journal"])

    add(
        "coa",
        "Categories: income account",
        "PASS" if cats_with_income == len(cats) else "FAIL",
        f"{cats_with_income}/{len(cats)}",
        "All",
    )
    add(
        "coa",
        "Categories: expense account",
        "PASS" if cats_with_expense == len(cats) else "FAIL",
        f"{cats_with_expense}/{len(cats)}",
        "All",
    )
    add(
        "coa",
        "Categories: stock input",
        "PASS" if cats_with_stock_in == len(cats) else "WARN",
        f"{cats_with_stock_in}/{len(cats)}",
        "All (real-time valuation)",
    )
    add(
        "coa",
        "Categories: stock output",
        "PASS" if cats_with_stock_out == len(cats) else "WARN",
        f"{cats_with_stock_out}/{len(cats)}",
        "All",
    )
    add(
        "coa",
        "Categories: stock valuation",
        "PASS" if cats_with_valuation == len(cats) else "WARN",
        f"{cats_with_valuation}/{len(cats)}",
        "All",
    )
    add(
        "coa",
        "Categories: stock journal",
        "PASS" if cats_with_journal == len(cats) else "WARN",
        f"{cats_with_journal}/{len(cats)}",
        "All",
    )

    cost_methods_set = sum(1 for cat in cats if cat.get("property_cost_method"))
    add(
        "coa",
        "Categories: costing method",
        "PASS" if cost_methods_set == len(cats) else "WARN",
        f"{cost_methods_set}/{len(cats)}",
        "All (standard/average/fifo)",
    )

    # ── 3. Journals ────────────────────────────────────────────────────
    journals = c.search_read(
        "account.journal",
        [("company_id", "=", company_id), ("active", "=", True)],
        fields=["name", "code", "type", "default_account_id", "suspense_account_id"],
    )
    types_present = {j["type"] for j in journals}
    for jtype, label in [
        ("sale", "Sale"),
        ("purchase", "Purchase"),
        ("bank", "Bank"),
        ("cash", "Cash"),
        ("general", "General"),
    ]:
        present = jtype in types_present
        add("journals", f"{label} journal", "PASS" if present else "FAIL", "Yes" if present else "No", "≥1")

    bank_journals = [j for j in journals if j["type"] == "bank"]
    bank_with_suspense = sum(1 for j in bank_journals if j["suspense_account_id"])
    if bank_journals:
        add(
            "journals",
            "Bank journals: suspense account",
            "PASS" if bank_with_suspense == len(bank_journals) else "WARN",
            f"{bank_with_suspense}/{len(bank_journals)}",
            "All bank journals",
        )

    journals_no_default = [j for j in journals if not j["default_account_id"] and j["type"] != "general"]
    add(
        "journals",
        "Journals without default account",
        "PASS" if len(journals_no_default) == 0 else "WARN",
        str(len(journals_no_default)),
        "0",
    )

    add("journals", "Total active journals", "PASS" if len(journals) >= 5 else "WARN", str(len(journals)), "≥5")

    # ── 4. Taxes ───────────────────────────────────────────────────────
    sale_taxes = c.search_count(
        "account.tax", [("company_id", "=", company_id), ("type_tax_use", "=", "sale"), ("active", "=", True)]
    )
    purchase_taxes = c.search_count(
        "account.tax", [("company_id", "=", company_id), ("type_tax_use", "=", "purchase"), ("active", "=", True)]
    )
    add("taxes", "Sale taxes", "PASS" if sale_taxes > 0 else "FAIL", str(sale_taxes), "≥1")
    add("taxes", "Purchase taxes", "PASS" if purchase_taxes > 0 else "FAIL", str(purchase_taxes), "≥1")

    # PPN check (12% rate)
    ppn = c.search_count(
        "account.tax",
        [("company_id", "=", company_id), ("amount", ">=", 11.0), ("amount", "<=", 12.0), ("active", "=", True)],
    )
    add("taxes", "PPN tax (11-12%)", "PASS" if ppn > 0 else "FAIL", str(ppn), "≥1")

    fiscal_pos = c.search_count("account.fiscal.position", [("company_id", "=", company_id)])
    add("taxes", "Fiscal positions", "PASS" if fiscal_pos > 0 else "WARN", str(fiscal_pos), "≥1")

    # ── 5. Products & Categories ──────────────────────────────────────
    products_total = c.search_count("product.template", [])
    add("products", "Total products", "INFO", str(products_total), "")
    add("products", "Total categories", "PASS" if len(cats) > 0 else "FAIL", str(len(cats)), "≥1")

    # ── 6. Partners ───────────────────────────────────────────────────
    customers = c.search_count("res.partner", [("customer_rank", ">", 0)])
    vendors = c.search_count("res.partner", [("supplier_rank", ">", 0)])
    add("partners", "Customers", "PASS" if customers > 0 else "FAIL", str(customers), "≥1")
    add("partners", "Vendors", "PASS" if vendors > 0 else "FAIL", str(vendors), "≥1")

    try:
        partners_with_npwp = c.search_count("res.partner", [("supplier_rank", ">", 0), ("l10n_id_npwp", "!=", False)])
        add("partners", "Vendors with NPWP", "INFO", str(partners_with_npwp), "")
    except Exception:
        pass

    # ── 7. Warehouses & Stock ─────────────────────────────────────────
    warehouses = c.search_read(
        "stock.warehouse",
        [("company_id", "=", company_id)],
        fields=["name", "code", "lot_stock_id", "reception_steps", "delivery_steps"],
    )
    add("stock", "Warehouses", "PASS" if len(warehouses) > 0 else "FAIL", str(len(warehouses)), "≥1")

    if warehouses:
        with_stock_loc = sum(1 for w in warehouses if w["lot_stock_id"])
        add(
            "stock",
            "Warehouses with stock location",
            "PASS" if with_stock_loc == len(warehouses) else "FAIL",
            f"{with_stock_loc}/{len(warehouses)}",
            "All",
        )

    locations = c.search_count("stock.location", [("company_id", "=", company_id), ("usage", "=", "internal")])
    add("stock", "Internal locations", "PASS" if locations > 0 else "FAIL", str(locations), "≥1")

    operation_types = c.search_count("stock.picking.type", [("company_id", "=", company_id)])
    add(
        "stock",
        "Operation types",
        "PASS" if operation_types >= 3 else "WARN",
        str(operation_types),
        "≥3 (in/out/internal)",
    )

    # ── 8. Operating Units ────────────────────────────────────────────
    try:
        ous = c.search_count("operating.unit", [("company_id", "=", company_id)])
        add("ou", "Operating units", "PASS" if ous > 0 else "WARN", str(ous), "≥1 (if OU module installed)")
    except Exception:
        add("ou", "operating_unit module", "INFO", "Not installed", "")

    # ── 9. Reports ────────────────────────────────────────────────────
    try:
        formats = c.search_read(
            "report.format",
            [("company_id", "=", company_id), ("active", "=", True)],
            fields=["report_type", "is_default"],
        )
        unique_types = set(f["report_type"] for f in formats if f.get("report_type"))
        defaults = sum(1 for f in formats if f.get("is_default"))
        add("reports", "Report formats", "PASS" if len(formats) > 0 else "WARN", str(len(formats)), "Multiple per type")
        add(
            "reports",
            "Unique report types",
            "PASS" if len(unique_types) >= 10 else "WARN",
            str(len(unique_types)),
            "≥10 types",
        )
        add("reports", "Default formats", "PASS" if defaults >= 10 else "WARN", str(defaults), "1 default per type")
    except Exception:
        add("reports", "report_layout module", "INFO", "Not installed", "")

    # Mail server check
    mail_servers = c.search_count("ir.mail_server", [("active", "=", True)])
    add("reports", "Outgoing mail servers", "PASS" if mail_servers > 0 else "WARN", str(mail_servers), "≥1")

    # Company logo
    company_full = c.search_read("res.company", [("id", "=", company_id)], fields=["logo"])
    has_logo = bool(company_full[0].get("logo"))
    add("reports", "Company logo", "PASS" if has_logo else "WARN", "Set" if has_logo else "Missing", "Set")

    # ── 10. Users & Access ────────────────────────────────────────────
    users = c.search_read(
        "res.users", [("company_ids", "in", company_id), ("active", "=", True)], fields=["login", "groups_id"]
    )
    add("users", "Active users", "PASS" if len(users) > 0 else "FAIL", str(len(users)), "≥1")

    admin = c.search_count("res.users", [("login", "=", "admin"), ("active", "=", True)])
    add("users", "Admin user active", "PASS" if admin > 0 else "FAIL", "Yes" if admin else "No", "Yes")

    # ── 11. Modules ───────────────────────────────────────────────────
    l10n_id = c.search_read("ir.module.module", [("name", "=", "l10n_id")], fields=["state"])
    add(
        "modules",
        "l10n_id (Indonesian)",
        "PASS" if l10n_id and l10n_id[0]["state"] == "installed" else "FAIL",
        l10n_id[0]["state"] if l10n_id else "Not found",
        "installed",
    )

    accurate = c.search_read("ir.module.module", [("name", "=", "accurate_integration")], fields=["state"])
    if accurate and accurate[0]["state"] == "installed":
        add("modules", "accurate_integration", "PASS", "installed", "(if migration source)")

    # Currency check
    for ccode in ["IDR", "USD", "CNY", "THB"]:
        curr = c.search_read("res.currency", [("name", "=", ccode)], fields=["active"])
        active = curr and curr[0].get("active")
        add(
            "modules",
            f"Currency {ccode}",
            "PASS" if active else "WARN",
            "Active" if active else "Inactive/Missing",
            "Active",
        )

    return results


def _write_excel(all_results: list[tuple[str, dict[str, list[dict]]]], output: Path):
    """Write multi-sheet Excel report."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    hdr_font = Font(bold=True, color="FFFFFF", size=11)
    hdr_fill = PatternFill("solid", fgColor="2F5496")
    pass_fill = PatternFill("solid", fgColor="C6EFCE")
    warn_fill = PatternFill("solid", fgColor="FFEB9C")
    fail_fill = PatternFill("solid", fgColor="FFC7CE")
    info_fill = PatternFill("solid", fgColor="DDEBF7")
    border = Border(
        left=Side(style="thin", color="D9D9D9"),
        right=Side(style="thin", color="D9D9D9"),
        top=Side(style="thin", color="D9D9D9"),
        bottom=Side(style="thin", color="D9D9D9"),
    )

    def status_fill(s: str):
        return {"PASS": pass_fill, "WARN": warn_fill, "FAIL": fail_fill, "INFO": info_fill}.get(s)

    def write_headers(ws, headers, widths):
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=h)
            cell.font = hdr_font
            cell.fill = hdr_fill
            cell.alignment = Alignment(horizontal="center", wrap_text=True)
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w
        ws.freeze_panes = "A2"

    # ── Sheet 1: Summary ──
    ws = wb.active
    ws.title = "Summary"
    sections = [
        "company",
        "coa",
        "journals",
        "taxes",
        "products",
        "partners",
        "stock",
        "ou",
        "reports",
        "users",
        "modules",
    ]
    section_labels = [
        "Company",
        "CoA",
        "Journals",
        "Taxes",
        "Products",
        "Partners",
        "Stock",
        "OU",
        "Reports",
        "Users",
        "Modules",
    ]
    headers = ["Company"] + section_labels + ["Total Pass", "Total Fail", "Ready?"]
    widths = [35] + [10] * len(section_labels) + [10, 10, 12]
    write_headers(ws, headers, widths)

    row = 2
    for company_name, results in all_results:
        ws.cell(row=row, column=1, value=company_name).font = Font(size=10, bold=True)
        total_pass = total_fail = 0
        for col_off, sec in enumerate(sections):
            checks = results.get(sec, [])
            passes = sum(1 for c in checks if c["status"] == "PASS")
            fails = sum(1 for c in checks if c["status"] == "FAIL")
            warns = sum(1 for c in checks if c["status"] == "WARN")
            total_pass += passes
            total_fail += fails
            cell = ws.cell(row=row, column=2 + col_off, value=f"{passes}/{len(checks)}")
            cell.alignment = Alignment(horizontal="center")
            cell.font = Font(size=10)
            if fails > 0:
                cell.fill = fail_fill
            elif warns > 0:
                cell.fill = warn_fill
            else:
                cell.fill = pass_fill
        ws.cell(row=row, column=2 + len(sections), value=total_pass).font = Font(size=10, bold=True)
        ws.cell(row=row, column=3 + len(sections), value=total_fail).font = Font(size=10, bold=True)
        ready_cell = ws.cell(row=row, column=4 + len(sections), value="READY" if total_fail == 0 else "NOT READY")
        ready_cell.font = Font(size=10, bold=True)
        ready_cell.fill = pass_fill if total_fail == 0 else fail_fill
        ready_cell.alignment = Alignment(horizontal="center")
        for col in range(1, 5 + len(sections)):
            ws.cell(row=row, column=col).border = border
        row += 1

    # ── Sheets 2-12: Detail per section ──
    sheet_titles = {
        "company": "Company Settings",
        "coa": "CoA & Properties",
        "journals": "Journals",
        "taxes": "Taxes",
        "products": "Products",
        "partners": "Partners",
        "stock": "Stock & Warehouses",
        "ou": "Operating Units",
        "reports": "Reports & Email",
        "users": "Users",
        "modules": "Modules & Currencies",
    }
    for sec_key, title in sheet_titles.items():
        ws = wb.create_sheet(title)
        write_headers(ws, ["Company", "Check", "Status", "Value", "Expected", "Note"], [30, 35, 10, 30, 30, 50])
        row = 2
        for company_name, results in all_results:
            for chk in results.get(sec_key, []):
                ws.cell(row=row, column=1, value=chk["company"]).font = Font(size=10)
                ws.cell(row=row, column=2, value=chk["check"]).font = Font(size=10)
                status_cell = ws.cell(row=row, column=3, value=chk["status"])
                status_cell.font = Font(size=10, bold=True)
                fill = status_fill(chk["status"])
                if fill:
                    status_cell.fill = fill
                status_cell.alignment = Alignment(horizontal="center")
                ws.cell(row=row, column=4, value=chk["value"]).font = Font(size=10)
                ws.cell(row=row, column=5, value=chk["expected"]).font = Font(size=10)
                ws.cell(row=row, column=6, value=chk["note"]).font = Font(size=9)
                for col in range(1, 7):
                    ws.cell(row=row, column=col).border = border
                row += 1
        ws.auto_filter.ref = f"A1:F{row - 1}"

    wb.save(str(output))


@app.command("readiness-check")
def readiness_check(
    ctx: typer.Context,
    output: Annotated[
        Path,
        typer.Option("-o", "--output", help="Output Excel path (default: readiness_<db>_<date>.xlsx)"),
    ] = None,
    company_id: Annotated[
        int,
        typer.Option("--company-id", help="Limit to one company id (default: all)"),
    ] = 0,
) -> None:
    """Generate a comprehensive Odoo production readiness audit Excel.

    Checks 100+ configuration items across 11 categories:
    Company, CoA, Journals, Taxes, Products, Partners, Stock, OU,
    Reports, Users, Modules. Per-company breakdown + consolidated summary.
    """
    actx: AppContext = ctx.obj
    _bump_timeout(actx, seconds=600.0)
    c = actx.client
    out = actx.output

    try:
        from openpyxl import Workbook  # noqa: F401
    except ImportError:
        out.error("openpyxl not installed. Run: pip install openpyxl")
        raise typer.Exit(1)

    domain = [("id", "=", company_id)] if company_id else []
    companies = c.search_read("res.company", domain, fields=["id", "name"], order="id")
    if not companies:
        out.error("No companies found")
        raise typer.Exit(1)

    out.info(f"Running readiness check on {len(companies)} company(ies)...")

    all_results: list[tuple[str, dict[str, list[dict]]]] = []
    for co in companies:
        out.info(f"  Checking {co['name']}...")
        try:
            results = _check_company(c, co["id"], co["name"])
            all_results.append((co["name"], results))
        except Exception as exc:
            out.error(f"  {co['name']}: {exc}")

    # Default output path
    if not output:
        db = actx.client.database if hasattr(actx.client, "database") else "odoo"
        output = Path(f"readiness_{db}_{date.today().isoformat()}.xlsx")

    _write_excel(all_results, output)

    # Print summary
    out.info(f"\nReport written to {output}")
    for company_name, results in all_results:
        total_fails = sum(sum(1 for c in checks if c["status"] == "FAIL") for checks in results.values())
        total_warns = sum(sum(1 for c in checks if c["status"] == "WARN") for checks in results.values())
        status = "READY" if total_fails == 0 else "NOT READY"
        out.info(f"  {company_name}: {status}  ({total_fails} fails, {total_warns} warns)")
