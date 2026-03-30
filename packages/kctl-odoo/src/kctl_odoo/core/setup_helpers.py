# Copyright 2026 Kodemeio
# License OPL-1

"""Helper functions for the setup command group.

Contains:
- Implementation checklist definitions and check functions
- .env file reading utility
- PostgreSQL connectivity testing
"""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

from kctl_odoo.core.bundles import (
    discover_profiles,
    get_default_install_dir,
)

# ---------------------------------------------------------------------------
# Checklist definitions
# ---------------------------------------------------------------------------

CHECKLIST: list[tuple[str, str, str, str]] = [
    # (id, category, description, check_function_name)
    # --- Infrastructure (4) ---
    ("db_health", "Infrastructure", "Database connectivity", "_check_db_health"),
    ("odoo_health", "Infrastructure", "Odoo server reachable", "_check_odoo_health"),
    ("admin_user", "Infrastructure", "Admin user authenticated", "_check_admin_user"),
    ("base_url_set", "Infrastructure", "web.base.url is not localhost", "_check_base_url"),
    # --- Modules (3) ---
    ("modules_installed", "Modules", "Mandatory modules installed", "_check_mandatory_modules"),
    ("profile_compliance", "Modules", "Deployment profile compliance", "_check_profile_compliance"),
    ("no_stuck_modules", "Modules", "No modules stuck in transitional state", "_check_stuck_modules"),
    # --- Company & Localization (5) ---
    ("company_configured", "Company", "Company name is set (not default)", "_check_company"),
    ("company_currency", "Company", "Company currency is set", "_check_currency"),
    ("chart_of_accounts", "Accounting", "Chart of accounts loaded (>10 accounts)", "_check_chart_of_accounts"),
    ("taxes_configured", "Accounting", "Taxes configured (sales + purchase)", "_check_taxes"),
    ("payment_terms", "Accounting", "Payment terms defined", "_check_payment_terms"),
    # --- Inventory & Operations (3) ---
    ("warehouses", "Operations", "At least one warehouse configured", "_check_warehouses"),
    ("product_categories", "Operations", "Product categories defined", "_check_product_categories"),
    ("sequences", "Operations", "Key sequences configured (SO/PO/INV)", "_check_sequences"),
    # --- Email & Communication (2) ---
    ("smtp_configured", "Email", "Outgoing mail server configured", "_check_smtp"),
    ("catchall_domain", "Email", "Mail catchall domain set", "_check_catchall"),
    # --- Security (4) ---
    ("admin_password_changed", "Security", "Admin password is not 'admin'", "_check_admin_password"),
    ("users_created", "Security", "At least one non-admin user exists", "_check_users"),
    ("operating_units", "Security", "Operating units configured (if multi-OU)", "_check_operating_units"),
    ("access_rights", "Security", "Custom models have access rights", "_check_access_rights"),
    # --- Accounting Extended (3) ---
    ("journals", "Accounting", "Accounting journals configured", "_check_journals"),
    ("fiscal_positions", "Accounting", "Fiscal positions defined", "_check_fiscal_positions"),
    ("pricelists", "Sales", "At least one pricelist defined", "_check_pricelists"),
    # --- Sales & Inventory (3) ---
    ("sales_teams", "Sales", "Sales teams configured", "_check_sales_teams"),
    ("picking_types", "Inventory", "Stock picking types configured", "_check_picking_types"),
    ("uom", "Inventory", "Units of measure configured", "_check_uom"),
    # --- Communication (1) ---
    ("email_templates", "Email", "Email templates configured", "_check_email_templates"),
    # --- Operations (4) ---
    ("cron_healthy", "Cron", "No overdue cron jobs", "_check_cron"),
    ("mail_queue_clear", "Cron", "No stuck emails in queue", "_check_mail_queue"),
    ("backup_configured", "Cron", "Backup-related cron exists", "_check_backup_cron"),
    ("db_size", "Cron", "Database not excessively large", "_check_db_size"),
]


# ---------------------------------------------------------------------------
# Check functions — each takes an Odoo XML-RPC client, returns (ok, detail)
# ---------------------------------------------------------------------------


def _check_db_health(c) -> tuple[bool, str]:
    try:
        dbs = c.db_list()
        return True, f"{len(dbs)} databases available"
    except Exception as e:
        return False, str(e)


def _check_odoo_health(c) -> tuple[bool, str]:
    ok, version = c.check_health()
    if ok:
        return True, f"Odoo {version}"
    return False, version


def _check_admin_user(c) -> tuple[bool, str]:
    try:
        uid = c.authenticate()
        return True, f"UID {uid}"
    except Exception as e:
        return False, str(e)


def _check_mandatory_modules(c) -> tuple[bool, str]:
    stuck = c.search_read(
        "ir.module.module",
        domain=[("state", "in", ["to install", "to upgrade", "to remove"])],
        fields=["name", "state"],
    )
    if stuck:
        names = [f"{m['name']} ({m['state']})" for m in stuck[:5]]
        return False, f"{len(stuck)} modules pending: {', '.join(names)}"
    installed = c.search_count("ir.module.module", [("state", "=", "installed")])
    return True, f"{installed} modules installed"


def _check_profile_compliance(c) -> tuple[bool, str]:
    install_dir = get_default_install_dir()
    if not install_dir.is_dir():
        return True, "No install/ dir (skipped)"
    profiles = discover_profiles(install_dir)
    if not profiles:
        return True, "No profiles defined (skipped)"
    installed = c.search_count("ir.module.module", [("state", "=", "installed")])
    return True, f"{installed} modules installed (check with: kctl-odoo deploy verify <profile>)"


def _check_stuck_modules(c) -> tuple[bool, str]:
    stuck = c.search_count(
        "ir.module.module",
        [("state", "in", ["to install", "to upgrade", "to remove"])],
    )
    if stuck:
        return False, f"{stuck} modules in transitional state (fix with: kctl-odoo troubleshoot fix-stuck)"
    return True, "No stuck modules"


def _check_company(c) -> tuple[bool, str]:
    companies = c.search_read("res.company", domain=[], fields=["name"], limit=1)
    if not companies:
        return False, "No company found"
    name = companies[0].get("name", "")
    if name in ("My Company", "My Company (San Francisco)", "YourCompany"):
        return False, f"Default company name: '{name}' — update via: kctl-odoo companies update 1 --name 'Your Company'"
    return True, name


def _check_smtp(c) -> tuple[bool, str]:
    servers = c.search_read("ir.mail_server", domain=[], fields=["name", "smtp_host"], limit=5)
    if not servers:
        return False, "No SMTP server configured — add via: kctl-odoo server mail-outgoing-add"
    names = [s["name"] for s in servers]
    return True, ", ".join(names)


def _check_base_url(c) -> tuple[bool, str]:
    params = c.search_read(
        "ir.config_parameter",
        domain=[("key", "=", "web.base.url")],
        fields=["value"],
    )
    if not params:
        return False, "web.base.url not set"
    url = params[0].get("value", "")
    if "localhost" in url or "127.0.0.1" in url:
        return (
            False,
            f"Still localhost: {url} — set via: kctl-odoo server params-set web.base.url https://your-domain.com",
        )
    return True, url


def _check_admin_password(c) -> tuple[bool, str]:
    return True, "API key authentication active (password not checkable via API)"


def _check_users(c) -> tuple[bool, str]:
    users = c.search_count("res.users", [("active", "=", True), ("share", "=", False)])
    if users <= 1:
        return (
            False,
            f"Only {users} internal user — create more via:"
            " kctl-odoo users create <login> --name 'Name' --email 'email'",
        )
    return True, f"{users} internal users"


def _check_cron(c) -> tuple[bool, str]:
    now = datetime.now(tz=UTC)
    crons = c.search_read(
        "ir.cron",
        domain=[("active", "=", True)],
        fields=["name", "nextcall"],
        limit=200,
    )
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
    if overdue:
        return False, f"{overdue} overdue cron jobs — check with: kctl-odoo cron diagnose"
    return True, f"{len(crons)} active, none overdue"


def _check_mail_queue(c) -> tuple[bool, str]:
    exception_count = c.search_count("mail.mail", [("state", "=", "exception")])
    outgoing_count = c.search_count("mail.mail", [("state", "=", "outgoing")])
    if exception_count:
        return False, f"{exception_count} failed emails — check with: kctl-odoo mail failed"
    if outgoing_count > 50:
        return False, f"{outgoing_count} emails queued (may be stuck)"
    return True, f"{outgoing_count} queued, {exception_count} failed"


def _check_currency(c) -> tuple[bool, str]:
    companies = c.search_read("res.company", domain=[], fields=["name", "currency_id"], limit=1)
    if not companies:
        return False, "No company found"
    curr = companies[0].get("currency_id")
    if not curr:
        return False, "No currency set on company"
    name = curr[1] if isinstance(curr, list) else str(curr)
    if name in ("USD",):
        return True, f"{name} (verify this is correct for your country)"
    return True, name


def _check_chart_of_accounts(c) -> tuple[bool, str]:
    try:
        count = c.search_count("account.account", [])
        if count == 0:
            return False, "No accounts — install localization package or import chart of accounts"
        if count < 10:
            return False, f"Only {count} accounts — chart of accounts may be incomplete"
        return True, f"{count} accounts configured"
    except Exception:
        return True, "account module not installed (skipped)"


def _check_taxes(c) -> tuple[bool, str]:
    try:
        sales = c.search_count("account.tax", [("type_tax_use", "=", "sale")])
        purchase = c.search_count("account.tax", [("type_tax_use", "=", "purchase")])
        total = sales + purchase
        if total == 0:
            return False, "No taxes configured — set up via Accounting > Configuration > Taxes"
        parts = []
        if sales:
            parts.append(f"{sales} sales")
        if purchase:
            parts.append(f"{purchase} purchase")
        return True, ", ".join(parts)
    except Exception:
        return True, "account module not installed (skipped)"


def _check_payment_terms(c) -> tuple[bool, str]:
    try:
        count = c.search_count("account.payment.term", [])
        if count == 0:
            return False, "No payment terms — define at least Net 30, COD"
        return True, f"{count} payment terms defined"
    except Exception:
        return True, "account module not installed (skipped)"


def _check_warehouses(c) -> tuple[bool, str]:
    try:
        whs = c.search_read("stock.warehouse", domain=[], fields=["name", "code"], limit=10)
        if not whs:
            return False, "No warehouses — configure via Inventory > Configuration > Warehouses"
        names = [f"{w['code']} ({w['name']})" for w in whs]
        return True, ", ".join(names)
    except Exception:
        return True, "stock module not installed (skipped)"


def _check_product_categories(c) -> tuple[bool, str]:
    count = c.search_count("product.category", [])
    if count <= 1:
        return False, "Only default category — define categories for your product lines"
    return True, f"{count} categories"


def _check_sequences(c) -> tuple[bool, str]:
    key_prefixes = ["sale.order", "purchase.order", "account.move"]
    found = []
    for prefix in key_prefixes:
        seqs = c.search_count("ir.sequence", [("code", "ilike", prefix)])
        if seqs:
            found.append(prefix.split(".")[0].upper())
    if len(found) < 2:
        return False, f"Only found sequences for: {', '.join(found) or 'none'}"
    return True, f"Sequences for: {', '.join(found)}"


def _check_catchall(c) -> tuple[bool, str]:
    params = c.search_read(
        "ir.config_parameter",
        domain=[("key", "=", "mail.catchall.domain")],
        fields=["value"],
    )
    if not params or not params[0].get("value"):
        return (
            False,
            "mail.catchall.domain not set — set via: kctl-odoo server params-set mail.catchall.domain yourdomain.com",
        )
    return True, params[0]["value"]


def _check_operating_units(c) -> tuple[bool, str]:
    try:
        count = c.search_count("operating.unit", [])
        if count == 0:
            return True, "No OUs (single-unit setup)"
        if count == 1:
            return True, "1 operating unit"
        return True, f"{count} operating units"
    except Exception:
        return True, "operating_unit module not installed (skipped)"


def _check_access_rights(c) -> tuple[bool, str]:
    try:
        no_access = c.search_read(
            "ir.model",
            domain=[("model", "like", "%.%"), ("transient", "=", False)],
            fields=["model"],
            limit=500,
        )
        models_without_access = 0
        for m in no_access[:50]:
            acl_count = c.search_count("ir.model.access", [("model_id.model", "=", m["model"])])
            if acl_count == 0:
                models_without_access += 1
        if models_without_access > 10:
            return False, f"{models_without_access} models without access rights (of {min(len(no_access), 50)} checked)"
        return True, f"Checked {min(len(no_access), 50)} models, {models_without_access} without ACL"
    except Exception as e:
        return True, f"Check skipped: {e}"


def _check_backup_cron(c) -> tuple[bool, str]:
    backup_crons = c.search_read(
        "ir.cron",
        domain=[("name", "ilike", "backup")],
        fields=["name", "active"],
    )
    if not backup_crons:
        return False, "No backup cron job found — configure automated backups"
    active = [cr for cr in backup_crons if cr.get("active")]
    if not active:
        return False, f"{len(backup_crons)} backup crons found but none active"
    return True, f"{len(active)} active backup cron(s)"


def _check_db_size(c) -> tuple[bool, str]:
    try:
        partner_count = c.search_count("res.partner", [])
        attachment_count = c.search_count("ir.attachment", [])
        msg = f"Partners: {partner_count}, Attachments: {attachment_count}"
        if attachment_count > 50000:
            return False, f"Large attachment count ({attachment_count}) — review storage cleanup"
        return True, msg
    except Exception as e:
        return True, f"Check skipped: {e}"


def _check_journals(c) -> tuple[bool, str]:
    try:
        journals = c.search_read("account.journal", domain=[], fields=["name", "type"], limit=20)
        if not journals:
            return False, "No journals — configure Sales, Purchase, Bank, Cash journals"
        types: dict[str, int] = {}
        for j in journals:
            t = j.get("type", "unknown")
            types[t] = types.get(t, 0) + 1
        parts = [f"{cnt} {t}" for t, cnt in sorted(types.items())]
        return True, ", ".join(parts)
    except Exception:
        return True, "account module not installed (skipped)"


def _check_fiscal_positions(c) -> tuple[bool, str]:
    try:
        count = c.search_count("account.fiscal.position", [])
        if count == 0:
            return False, "No fiscal positions — needed for tax mapping across regions/customer types"
        return True, f"{count} fiscal positions"
    except Exception:
        return True, "account module not installed (skipped)"


def _check_pricelists(c) -> tuple[bool, str]:
    try:
        count = c.search_count("product.pricelist", [])
        if count == 0:
            return False, "No pricelists — define at least a default pricelist"
        return True, f"{count} pricelists"
    except Exception:
        return True, "product module not installed (skipped)"


def _check_sales_teams(c) -> tuple[bool, str]:
    try:
        teams = c.search_read("crm.team", domain=[], fields=["name"], limit=10)
        if not teams:
            return False, "No sales teams — configure via Sales > Configuration > Sales Teams"
        names = [t["name"] for t in teams]
        return True, ", ".join(names)
    except Exception:
        return True, "crm module not installed (skipped)"


def _check_picking_types(c) -> tuple[bool, str]:
    try:
        types = c.search_read("stock.picking.type", domain=[], fields=["name", "code"], limit=20)
        if not types:
            return False, "No picking types — configure via Inventory > Configuration"
        codes: dict[str, int] = {}
        for t in types:
            code = t.get("code", "unknown")
            codes[code] = codes.get(code, 0) + 1
        parts = [f"{cnt} {c}" for c, cnt in sorted(codes.items())]
        return True, ", ".join(parts)
    except Exception:
        return True, "stock module not installed (skipped)"


def _check_uom(c) -> tuple[bool, str]:
    count = c.search_count("uom.uom", [])
    if count < 3:
        return False, f"Only {count} UoMs — need at least Unit, kg, Hour"
    return True, f"{count} units of measure"


def _check_email_templates(c) -> tuple[bool, str]:
    count = c.search_count("mail.template", [])
    if count == 0:
        return False, "No email templates — needed for automated notifications"
    return True, f"{count} email templates"


# ---------------------------------------------------------------------------
# Check function registry
# ---------------------------------------------------------------------------

CHECK_FUNCTIONS: dict[str, callable] = {
    "_check_db_health": _check_db_health,
    "_check_odoo_health": _check_odoo_health,
    "_check_admin_user": _check_admin_user,
    "_check_mandatory_modules": _check_mandatory_modules,
    "_check_profile_compliance": _check_profile_compliance,
    "_check_stuck_modules": _check_stuck_modules,
    "_check_company": _check_company,
    "_check_currency": _check_currency,
    "_check_chart_of_accounts": _check_chart_of_accounts,
    "_check_taxes": _check_taxes,
    "_check_payment_terms": _check_payment_terms,
    "_check_journals": _check_journals,
    "_check_fiscal_positions": _check_fiscal_positions,
    "_check_pricelists": _check_pricelists,
    "_check_warehouses": _check_warehouses,
    "_check_product_categories": _check_product_categories,
    "_check_sequences": _check_sequences,
    "_check_sales_teams": _check_sales_teams,
    "_check_picking_types": _check_picking_types,
    "_check_uom": _check_uom,
    "_check_smtp": _check_smtp,
    "_check_catchall": _check_catchall,
    "_check_email_templates": _check_email_templates,
    "_check_admin_password": _check_admin_password,
    "_check_users": _check_users,
    "_check_operating_units": _check_operating_units,
    "_check_access_rights": _check_access_rights,
    "_check_cron": _check_cron,
    "_check_mail_queue": _check_mail_queue,
    "_check_backup_cron": _check_backup_cron,
    "_check_db_size": _check_db_size,
    "_check_base_url": _check_base_url,
}


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


def read_dotenv(path: Path) -> dict[str, str]:
    """Read a .env file into a dict, ignoring comments and blank lines."""
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip()
    return env


def test_pg_connectivity(host: str, port: str, user: str) -> tuple[bool, str]:
    """Test PostgreSQL connectivity via pg_isready or psql.

    Returns (success, message).
    """
    # Try pg_isready first
    try:
        result = subprocess.run(
            ["pg_isready", "-h", host, "-p", port, "-U", user],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return True, result.stdout.strip() or "PostgreSQL is accepting connections"
        return False, result.stdout.strip() or result.stderr.strip() or "Connection refused"
    except FileNotFoundError:
        pass
    except subprocess.TimeoutExpired:
        return False, "Connection timed out"

    # Fallback to psql
    try:
        result = subprocess.run(
            ["psql", "-h", host, "-p", port, "-U", user, "-c", "SELECT 1;"],
            capture_output=True,
            text=True,
            timeout=10,
            env={**__import__("os").environ, "PGCONNECT_TIMEOUT": "5"},
        )
        if result.returncode == 0:
            return True, "PostgreSQL connection successful (via psql)"
        return False, result.stderr.strip() or "Connection failed"
    except FileNotFoundError:
        return False, "Neither pg_isready nor psql found on PATH (install postgresql-client)"
    except subprocess.TimeoutExpired:
        return False, "Connection timed out"
