# Copyright 2026 Kodemeio
# License OPL-1

"""Configure Odoo master data — taxes, accounts, journals, warehouses, etc.

Provides read/write commands for all configuration data that's typically
set up once during implementation but needs CLI access for automation,
scripting, and multi-instance management.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

import typer

from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.exceptions import RPCError

app = typer.Typer(help="Configure Odoo master data (taxes, accounts, journals, warehouses, etc.).")


# ---------------------------------------------------------------------------
# Generic helper for simple CRUD on any model
# ---------------------------------------------------------------------------


def _list_records(c, out, actx, model: str, title: str, fields: list[str], domain: list | None = None, limit: int = 50):
    records = c.search_read(model, domain=domain or [], fields=fields, limit=limit, order="id")
    if not records:
        out.info(f"No {title.lower()} found.")
        if actx.json_mode:
            out.raw_json([])
        return

    cols = [(f.replace("_", " ").title(), "") for f in fields]
    rows = []
    json_data = []
    for r in records:
        row = []
        for f in fields:
            val = r.get(f, "")
            if isinstance(val, list) and len(val) == 2:
                val = val[1]  # Many2one display name
            row.append(str(val) if val else "")
        rows.append(row)
        json_data.append({f: r.get(f) for f in fields})

    out.table(f"{title} ({len(records)})", cols, rows, json_data)


def _create_record(c, out, model: str, vals: dict, label: str, company_id: int | None = None):
    try:
        if company_id:
            vals = {**vals, "company_id": company_id}
            ctx = {"allowed_company_ids": [company_id], "default_company_id": company_id}
            rec_id = c.execute_kw(model, "create", [vals], {"context": ctx})
        else:
            rec_id = c.create(model, vals)
        out.success(f"Created {label} (ID {rec_id})")
        return rec_id
    except Exception as e:
        out.error(f"Failed to create {label}: {e}")
        raise typer.Exit(1) from e


# ---------------------------------------------------------------------------
# Taxes
# ---------------------------------------------------------------------------


@app.command("taxes")
def taxes(
    ctx: typer.Context, use: Annotated[str | None, typer.Option("--use", help="Filter: sale, purchase, none")] = None
) -> None:
    """List taxes."""
    actx: AppContext = ctx.obj
    domain = [("type_tax_use", "=", use)] if use else []
    _list_records(
        actx.client,
        actx.output,
        actx,
        "account.tax",
        "Taxes",
        ["id", "name", "amount", "type_tax_use", "amount_type"],
        domain,
    )


@app.command("create-tax")
def tax_create(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", "-n", help="Tax name (e.g., PPN 11%%)")],
    amount: Annotated[float, typer.Option("--amount", "-a", help="Tax rate (e.g., 11)")],
    use: Annotated[str, typer.Option("--use", help="Type: sale, purchase, none")] = "sale",
    amount_type: Annotated[str, typer.Option("--type", help="Computation: percent, fixed, group")] = "percent",
) -> None:
    """Create a tax."""
    actx: AppContext = ctx.obj
    _create_record(
        actx.client,
        actx.output,
        "account.tax",
        {"name": name, "amount": amount, "type_tax_use": use, "amount_type": amount_type},
        f"tax '{name}'",
    )


# ---------------------------------------------------------------------------
# Chart of Accounts
# ---------------------------------------------------------------------------


@app.command("accounts")
def accounts(
    ctx: typer.Context,
    account_type: Annotated[str | None, typer.Option("--type", help="Filter by account type")] = None,
) -> None:
    """List chart of accounts."""
    actx: AppContext = ctx.obj
    domain = [("account_type", "=", account_type)] if account_type else []
    _list_records(
        actx.client,
        actx.output,
        actx,
        "account.account",
        "Chart of Accounts",
        ["id", "code", "name", "account_type"],
        domain,
        limit=100,
    )


@app.command("create-account")
def account_create(
    ctx: typer.Context,
    code: Annotated[str, typer.Option("--code", "-c", help="Account code (e.g., 110100)")],
    name: Annotated[str, typer.Option("--name", "-n", help="Account name")],
    account_type: Annotated[
        str,
        typer.Option(
            "--type", help="Type: asset_receivable, asset_current, liability_payable, equity, income, expense, etc."
        ),
    ] = "asset_current",
) -> None:
    """Create an account in the chart of accounts."""
    actx: AppContext = ctx.obj
    _create_record(
        actx.client,
        actx.output,
        "account.account",
        {"code": code, "name": name, "account_type": account_type},
        f"account '{code} {name}'",
    )


# ---------------------------------------------------------------------------
# Journals
# ---------------------------------------------------------------------------


@app.command("journals")
def journals(ctx: typer.Context) -> None:
    """List accounting journals."""
    actx: AppContext = ctx.obj
    _list_records(actx.client, actx.output, actx, "account.journal", "Journals", ["id", "code", "name", "type"])


@app.command("create-journal")
def journal_create(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", "-n", help="Journal name")],
    code: Annotated[str, typer.Option("--code", "-c", help="Short code (e.g., BNK1)")],
    journal_type: Annotated[str, typer.Option("--type", help="Type: sale, purchase, bank, cash, general")] = "general",
) -> None:
    """Create an accounting journal."""
    actx: AppContext = ctx.obj
    _create_record(
        actx.client,
        actx.output,
        "account.journal",
        {"name": name, "code": code, "type": journal_type},
        f"journal '{code} {name}'",
    )


# ---------------------------------------------------------------------------
# Payment Terms
# ---------------------------------------------------------------------------


@app.command("payment-terms")
def payment_terms(ctx: typer.Context) -> None:
    """List payment terms."""
    actx: AppContext = ctx.obj
    _list_records(actx.client, actx.output, actx, "account.payment.term", "Payment Terms", ["id", "name"])


@app.command("create-payment-term")
def payment_term_create(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", "-n", help="Payment term name (e.g., Net 30)")],
) -> None:
    """Create a payment term."""
    actx: AppContext = ctx.obj
    _create_record(actx.client, actx.output, "account.payment.term", {"name": name}, f"payment term '{name}'")


# ---------------------------------------------------------------------------
# Pricelists
# ---------------------------------------------------------------------------


@app.command("pricelists")
def pricelists(
    ctx: typer.Context,
    prefix: Annotated[str | None, typer.Option("--prefix", help="Filter by name prefix (e.g. 'TLN-')")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List pricelists.

    Examples:
        kctl-odoo master-data pricelists
        kctl-odoo master-data pricelists --prefix TLN-
        kctl-odoo master-data pricelists --prefix TLN- --limit 200
    """
    actx: AppContext = ctx.obj
    domain = [("name", "=like", f"{prefix}%")] if prefix else None
    _list_records(
        actx.client,
        actx.output,
        actx,
        "product.pricelist",
        "Pricelists",
        ["id", "name", "currency_id"],
        domain=domain,
        limit=limit,
    )


@app.command("create-pricelist")
def pricelist_create(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", "-n", help="Pricelist name")],
) -> None:
    """Create a pricelist."""
    actx: AppContext = ctx.obj
    _create_record(actx.client, actx.output, "product.pricelist", {"name": name}, f"pricelist '{name}'")


# ---------------------------------------------------------------------------
# Fiscal Positions
# ---------------------------------------------------------------------------


@app.command("fiscal-positions")
def fiscal_positions(ctx: typer.Context) -> None:
    """List fiscal positions."""
    actx: AppContext = ctx.obj
    _list_records(
        actx.client,
        actx.output,
        actx,
        "account.fiscal.position",
        "Fiscal Positions",
        ["id", "name", "auto_apply", "country_id"],
    )


@app.command("create-fiscal-position")
def fiscal_position_create(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", "-n", help="Fiscal position name")],
    auto_apply: Annotated[bool, typer.Option("--auto-apply", help="Auto-apply based on country")] = False,
) -> None:
    """Create a fiscal position."""
    actx: AppContext = ctx.obj
    _create_record(
        actx.client,
        actx.output,
        "account.fiscal.position",
        {"name": name, "auto_apply": auto_apply},
        f"fiscal position '{name}'",
    )


# ---------------------------------------------------------------------------
# Warehouses
# ---------------------------------------------------------------------------


@app.command("warehouses")
def warehouses(ctx: typer.Context) -> None:
    """List warehouses."""
    actx: AppContext = ctx.obj
    _list_records(
        actx.client, actx.output, actx, "stock.warehouse", "Warehouses", ["id", "code", "name", "lot_stock_id"]
    )


@app.command("create-warehouse")
def warehouse_create(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", "-n", help="Warehouse name")],
    code: Annotated[str, typer.Option("--code", "-c", help="Short code (e.g., WH, JKT)")],
    company_id: Annotated[
        int | None, typer.Option("--company-id", help="Target company id (defaults to user's current company)")
    ] = None,
) -> None:
    """Create a warehouse."""
    actx: AppContext = ctx.obj
    _create_record(
        actx.client,
        actx.output,
        "stock.warehouse",
        {"name": name, "code": code},
        f"warehouse '{code} {name}'",
        company_id=company_id,
    )


# ---------------------------------------------------------------------------
# Operating Units
# ---------------------------------------------------------------------------


@app.command("operating-units")
def operating_units(ctx: typer.Context) -> None:
    """List operating units."""
    actx: AppContext = ctx.obj
    try:
        _list_records(
            actx.client, actx.output, actx, "operating.unit", "Operating Units", ["id", "code", "name", "company_id"]
        )
    except Exception:
        actx.output.info("operating_unit module not installed.")


@app.command("create-operating-unit")
def operating_unit_create(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", "-n", help="Operating unit name")],
    code: Annotated[str, typer.Option("--code", "-c", help="Short code")],
    company_id: Annotated[
        int | None, typer.Option("--company-id", help="Target company id (defaults to user's current company)")
    ] = None,
    partner_id: Annotated[
        int | None, typer.Option("--partner-id", help="Address partner id (default: company partner)")
    ] = None,
) -> None:
    """Create an operating unit."""
    actx: AppContext = ctx.obj
    c = actx.client
    vals: dict = {"name": name, "code": code}
    if company_id and not partner_id:
        comp = c.read("res.company", [company_id], fields=["partner_id"])
        if comp and comp[0].get("partner_id"):
            vals["partner_id"] = comp[0]["partner_id"][0]
    elif partner_id:
        vals["partner_id"] = partner_id
    _create_record(
        actx.client,
        actx.output,
        "operating.unit",
        vals,
        f"operating unit '{code} {name}'",
        company_id=company_id,
    )


# ---------------------------------------------------------------------------
# Currencies
# ---------------------------------------------------------------------------


@app.command("currencies")
def currencies(
    ctx: typer.Context, all_currencies: Annotated[bool, typer.Option("--all", help="Show inactive too")] = False
) -> None:
    """List currencies."""
    actx: AppContext = ctx.obj
    domain = [] if all_currencies else [("active", "=", True)]
    _list_records(
        actx.client, actx.output, actx, "res.currency", "Currencies", ["id", "name", "symbol", "active"], domain
    )


@app.command("activate-currency")
def currency_activate(
    ctx: typer.Context,
    code: Annotated[str, typer.Argument(help="Currency code (e.g., IDR, EUR, USD)")],
) -> None:
    """Activate a currency."""
    actx: AppContext = ctx.obj
    c = actx.client
    out = actx.output
    currencies = c.search_read("res.currency", [("name", "=", code.upper())], fields=["id", "name", "active"])
    if not currencies:
        out.error(f"Currency '{code}' not found")
        raise typer.Exit(1)
    cur = currencies[0]
    if cur.get("active"):
        out.info(f"Currency {code.upper()} is already active")
        return
    c.write("res.currency", [cur["id"]], {"active": True})
    out.success(f"Activated currency {code.upper()}")


# ---------------------------------------------------------------------------
# General Settings (common ir.config_parameter shortcuts)
# ---------------------------------------------------------------------------


@app.command("settings")
def settings(ctx: typer.Context) -> None:
    """Show key Odoo configuration settings."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    keys = [
        "web.base.url",
        "report.url",
        "mail.catchall.domain",
        "mail.catchall.alias",
        "mail.default.from",
        "mail.bounce.alias",
        "database.uuid",
        "database.create_date",
        "auth_signup.invitation_scope",
        "auth_signup.reset_password",
        "base.login_cooldown_after",
        "base.login_cooldown_duration",
    ]

    rows = []
    json_data = {}
    for key in keys:
        result = c.search_read("ir.config_parameter", [("key", "=", key)], fields=["value"])
        val = result[0]["value"] if result else ""
        rows.append([key, val or "[dim]not set[/dim]"])
        json_data[key] = val or None

    out.table("Odoo Settings", [("Key", "cyan"), ("Value", "")], rows, [json_data])


@app.command("set-setting")
def setting_set(
    ctx: typer.Context,
    key: Annotated[str, typer.Argument(help="Setting key (e.g., web.base.url)")],
    value: Annotated[str, typer.Argument(help="Setting value")],
) -> None:
    """Set an Odoo configuration setting (ir.config_parameter)."""
    actx: AppContext = ctx.obj
    actx.client.execute_kw("ir.config_parameter", "set_param", [key, value])
    actx.output.success(f"{key} = {value}")


# ---------------------------------------------------------------------------
# Configuration Audit
# ---------------------------------------------------------------------------


def _get_param(client, key: str) -> str | None:
    """Get a single ir.config_parameter value."""
    try:
        result = client.search_read("ir.config_parameter", [("key", "=", key)], fields=["value"])
        return result[0]["value"] if result else None
    except RPCError:
        return None


def _safe_count(client, model: str, domain: list | None = None) -> int | None:
    """Search count that returns None if model doesn't exist."""
    try:
        return client.search_count(model, domain or [])
    except RPCError:
        return None


@app.command("audit")
def audit(ctx: typer.Context) -> None:
    """Audit configuration against best practices and score as percentage.

    Checks lock dates, default taxes, chart of accounts codes,
    web.base.url, backup cron, and currency rate freshness.

    Examples:
        kctl-odoo master-data audit
        kctl-odoo master-data audit --json
        kctl-odoo --profile production master-data audit
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    checks: list[tuple[str, bool, str]] = []  # (name, passed, detail)

    # 1. Lock dates set
    try:
        companies = c.search_read("res.company", [], fields=["id", "name", "fiscalyear_lock_date", "period_lock_date"])
        if companies:
            co = companies[0]
            fiscal_lock = co.get("fiscalyear_lock_date")
            period_lock = co.get("period_lock_date")
            has_lock = bool(fiscal_lock) or bool(period_lock)
            detail = f"Fiscal: {fiscal_lock or 'not set'}, Period: {period_lock or 'not set'}"
            checks.append(("Lock Dates", has_lock, detail))
        else:
            checks.append(("Lock Dates", False, "No company found"))
    except RPCError:
        checks.append(("Lock Dates", False, "Could not query"))

    # 2. Default taxes configured
    try:
        sale_taxes = c.search_count("account.tax", [("type_tax_use", "=", "sale")])
        purchase_taxes = c.search_count("account.tax", [("type_tax_use", "=", "purchase")])
        has_taxes = sale_taxes > 0 and purchase_taxes > 0
        checks.append(("Default Taxes", has_taxes, f"Sale: {sale_taxes}, Purchase: {purchase_taxes}"))
    except RPCError:
        checks.append(("Default Taxes", False, "account module not installed"))

    # 3. Chart of accounts has codes
    try:
        total_accounts = c.search_count("account.account", [])
        no_code = c.search_count("account.account", ["|", ("code", "=", False), ("code", "=", "")])
        all_have_codes = total_accounts > 0 and no_code == 0
        checks.append(("Account Codes", all_have_codes, f"{total_accounts} accounts, {no_code} without code"))
    except RPCError:
        checks.append(("Account Codes", False, "Could not query"))

    # 4. web.base.url
    base_url = _get_param(c, "web.base.url") or ""
    is_localhost = "localhost" in base_url or "127.0.0.1" in base_url
    if base_url and not is_localhost:
        checks.append(("web.base.url", True, base_url))
    elif not base_url:
        checks.append(("web.base.url", False, "Not set"))
    else:
        checks.append(("web.base.url", False, f"Points to localhost: {base_url}"))

    # 5. Backup cron exists and active
    try:
        backup_crons = c.search_count(
            "ir.cron",
            [("active", "=", True), ("name", "ilike", "backup")],
        )
        checks.append(("Backup Cron", backup_crons > 0, f"{backup_crons} active backup cron(s)"))
    except RPCError:
        checks.append(("Backup Cron", False, "Could not query"))

    # 6. Currency rates recent (within 7 days)
    try:
        cutoff_7d = (datetime.now(tz=UTC) - timedelta(days=7)).strftime("%Y-%m-%d")
        active_currencies = c.search_count("res.currency", [("active", "=", True)])
        if active_currencies > 1:
            recent_rates = c.search_count("res.currency.rate", [("name", ">=", cutoff_7d)])
            checks.append(
                (
                    "Currency Rates",
                    recent_rates > 0,
                    f"{recent_rates} rate(s) in last 7 days, {active_currencies} active currencies",
                )
            )
        else:
            checks.append(("Currency Rates", True, "Single currency (no rates needed)"))
    except RPCError:
        checks.append(("Currency Rates", True, "Could not query (non-critical)"))

    # 7. SMTP server configured
    smtp_count = _safe_count(c, "ir.mail_server", [("active", "=", True)])
    if smtp_count is not None:
        checks.append(("SMTP Server", smtp_count > 0, f"{smtp_count} active server(s)"))
    else:
        checks.append(("SMTP Server", False, "Could not query"))

    # 8. mail.catchall.domain
    catchall = _get_param(c, "mail.catchall.domain")
    checks.append(("Catchall Domain", bool(catchall), catchall or "Not set"))

    # Build output
    passed = sum(1 for _, p, _ in checks if p)
    total = len(checks)
    score_pct = round(passed / total * 100) if total else 0

    score_color = "green" if score_pct >= 80 else "yellow" if score_pct >= 50 else "red"

    rows = []
    json_checks = []
    for name, ok, detail in checks:
        status = "[green]PASS[/green]" if ok else "[red]FAIL[/red]"
        rows.append([name, status, detail])
        json_checks.append({"check": name, "passed": ok, "detail": detail})

    rows.append(["", "", ""])
    rows.append(
        [
            "[bold]Score[/bold]",
            f"[bold]{passed}/{total}[/bold]",
            f"[bold][{score_color}]{score_pct}%[/{score_color}][/bold]",
        ]
    )

    out.table(
        "Configuration Audit",
        [("Check", "cyan"), ("Status", ""), ("Detail", "dim")],
        rows,
        data_for_json=json_checks,
    )
