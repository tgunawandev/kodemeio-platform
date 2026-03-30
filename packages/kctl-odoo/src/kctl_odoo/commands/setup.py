# Copyright 2026 Kodemeio
# License OPL-1

"""Setup wizard and implementation checklist for new Odoo deployments.

Provides guided workflows for new implementations:
- Interactive setup wizard
- Implementation checklist with status tracking
- Pre-flight validation
- Go-live smoke tests
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from kctl_odoo.core.bundles import (
    discover_profiles,
    get_default_install_dir,
    load_profile,
    resolve_profile_modules,
)
from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.setup_helpers import (
    CHECK_FUNCTIONS,
    CHECKLIST,
    read_dotenv,
    test_pg_connectivity,
)

app = typer.Typer(help="Implementation setup wizard and go-live tools.")
console = Console()


@app.command("checklist")
def checklist(
    ctx: typer.Context,
    category: Annotated[str | None, typer.Option("--category", "-c", help="Filter by category")] = None,
) -> None:
    """Run the implementation checklist against the Odoo instance.

    Validates infrastructure, modules, configuration, security, and operations.
    Shows pass/fail status with actionable fix commands for each item.
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    rows = []
    json_data = []
    passed = 0
    failed = 0

    for check_id, cat, description, fn_name in CHECKLIST:
        if category and cat.lower() != category.lower():
            continue

        fn = CHECK_FUNCTIONS[fn_name]
        try:
            ok, detail = fn(c)
        except Exception as e:
            ok, detail = False, f"Error: {e}"

        if ok:
            passed += 1
            status_str = "[green]PASS[/green]"
        else:
            failed += 1
            status_str = "[red]FAIL[/red]"

        rows.append([cat, description, status_str, detail[:80]])
        json_data.append(
            {
                "id": check_id,
                "category": cat,
                "description": description,
                "passed": ok,
                "detail": detail,
            }
        )

    total = passed + failed
    title = f"Implementation Checklist ({passed}/{total} passed)"
    if failed:
        title += f" - [red]{failed} issues[/red]"
    else:
        title += " - [green]all clear[/green]"

    out.table(
        title,
        [
            ("Category", "cyan"),
            ("Check", ""),
            ("Status", ""),
            ("Detail", "dim"),
        ],
        rows,
        json_data,
    )


@app.command("preflight")
def preflight(
    ctx: typer.Context,
    profile: Annotated[str | None, typer.Option("--profile", "-p", help="Deployment profile to verify")] = None,
    dir_path: Annotated[str | None, typer.Option("--dir", help="Install directory")] = None,
) -> None:
    """Pre-flight check before go-live.

    Runs the full checklist plus profile compliance verification.
    Returns exit code 1 if any critical check fails.
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    console.print("\n[bold]Pre-flight Check[/bold]\n")

    # Run all checklist items
    critical_fail = False
    results = []

    for check_id, cat, description, fn_name in CHECKLIST:
        fn = CHECK_FUNCTIONS[fn_name]
        try:
            ok, detail = fn(c)
        except Exception as e:
            ok, detail = False, str(e)

        icon = "[green]OK[/green]" if ok else "[red]FAIL[/red]"
        console.print(f"  {icon} {description}: {detail}")
        results.append({"id": check_id, "passed": ok, "detail": detail})

        if not ok and cat in ("Infrastructure", "Security"):
            critical_fail = True

    # Profile compliance
    if profile:
        install_dir = Path(dir_path) if dir_path else get_default_install_dir()
        if install_dir.is_dir():
            try:
                profile_path = None
                for prefix in ("profile-", ""):
                    for ext in (".yaml", ".yml"):
                        p = install_dir / f"{prefix}{profile}{ext}"
                        if p.exists():
                            profile_path = p
                            break

                if profile_path:
                    prof = load_profile(profile_path)
                    expected = resolve_profile_modules(prof, install_dir)
                    installed = c.search_read(
                        "ir.module.module",
                        domain=[("name", "in", expected), ("state", "=", "installed")],
                        fields=["name"],
                    )
                    installed_names = {m["name"] for m in installed}
                    missing = [m for m in expected if m not in installed_names]
                    pct = round(len(installed_names) * 100 / len(expected)) if expected else 100

                    if missing:
                        console.print(
                            f"\n  [red]FAIL[/red] Profile '{profile}': {pct}% compliant ({len(missing)} missing)"
                        )
                        for m in missing[:10]:
                            console.print(f"        - {m}")
                        if len(missing) > 10:
                            console.print(f"        ... and {len(missing) - 10} more")
                        critical_fail = True
                    else:
                        console.print(
                            f"\n  [green]OK[/green] Profile '{profile}': 100% compliant ({len(expected)} modules)"
                        )
            except Exception as e:
                console.print(f"\n  [yellow]WARN[/yellow] Profile check failed: {e}")

    passed = sum(1 for r in results if r["passed"])
    total = len(results)

    console.print(f"\n[bold]Result: {passed}/{total} checks passed[/bold]")

    if critical_fail:
        console.print("[red]CRITICAL issues found. Fix before go-live.[/red]")
        raise typer.Exit(1)
    elif passed < total:
        console.print("[yellow]Non-critical issues found. Review before go-live.[/yellow]")
    else:
        console.print("[green]All checks passed. Ready for go-live.[/green]")

    if actx.json_mode:
        out.raw_json(
            {
                "passed": passed,
                "total": total,
                "critical_fail": critical_fail,
                "results": results,
            }
        )


@app.command("quickstart")
def quickstart(ctx: typer.Context) -> None:
    """Show the recommended setup steps for a new Odoo implementation.

    Prints a step-by-step guide with the exact kctl-odoo commands to run.
    """
    console.print("""
[bold cyan]Kodemeio Odoo 18 — New Implementation Quickstart[/bold cyan]

[bold]Step 1: Choose your deployment profile[/bold]
  kctl-odoo profiles list                          # See available profiles
  kctl-odoo profiles show manufacturing            # Review modules included

[bold]Step 2: Start the environment[/bold]
  kctl-odoo setup init                             # Interactive .env setup
  kctl-odoo local build                            # Build Docker image
  kctl-odoo local up                               # Start Odoo

[bold]Step 3: Verify installation[/bold]
  kctl-odoo -p dev troubleshoot check               # Check server health
  kctl-odoo -p dev deploy status                   # View installed modules
  kctl-odoo -p dev setup checklist                 # Run implementation checklist

[bold]Step 4: Configure company[/bold]
  kctl-odoo -p dev companies update 1 --name "PT Your Company" --email "info@company.com"
  kctl-odoo -p dev server params-set web.base.url https://erp.company.com

[bold]Step 5: Configure email[/bold]
  kctl-odoo -p dev server mail-outgoing-add \\
    --name "Production SMTP" --host smtp.gmail.com --port 587 \\
    --user "noreply@company.com" --password "app-password" --encryption starttls
  kctl-odoo -p dev server mail-outgoing-test 1

[bold]Step 6: Create users[/bold]
  kctl-odoo -p dev users create admin2 --name "IT Admin" --email "admin@company.com"
  kctl-odoo -p dev security add-to-group admin2 base.group_system
  kctl-odoo -p dev users create user1 --name "Sales Rep" --email "sales@company.com"
  kctl-odoo -p dev security add-to-group user1 sales_team.group_sale_salesman

[bold]Step 7: Import data[/bold]
  kctl-odoo -p dev import records res.partner partners.csv
  kctl-odoo -p dev import records product.template products.csv

[bold]Step 8: Test[/bold]
  kctl-odoo -p dev setup checklist                 # Re-run checklist
  kctl-odoo -p dev setup preflight --profile manufacturing  # Full pre-flight

[bold]Step 9: Deploy to production[/bold]
  cp .env .env.production                          # Production credentials
  ./scripts/host/deploy/deploy.sh --env .env.production

[bold]Step 10: Go-live verification[/bold]
  kctl-odoo -p production troubleshoot check
  kctl-odoo -p production setup preflight --profile manufacturing
  kctl-odoo -p production deploy verify manufacturing

[dim]For the full guide: docs/admin/initial-setup.md[/dim]
""")


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------


@app.command("init")
def init() -> None:
    """Interactive setup wizard -- prompts for .env values and writes .env file.

    Asks for database connection, admin password, HTTP port, and optional
    deployment profile. Tests PostgreSQL connectivity before writing the file.

    Examples:
        kctl-odoo setup init
    """
    from kctl_odoo.core.utils import find_project_root

    console.print("\n[bold cyan]Kodemeio Odoo 18 — Environment Setup[/bold cyan]\n")

    env_path = find_project_root() / ".env"
    if env_path.exists():
        overwrite = typer.confirm(f".env already exists at {env_path}. Overwrite?", default=False)
        if not overwrite:
            console.print("[yellow]Aborted.[/yellow]")
            raise typer.Exit(0)

    # Discover available profiles
    install_dir = get_default_install_dir()
    profile_names: list[str] = []
    if install_dir.is_dir():
        profiles = discover_profiles(install_dir)
        profile_names = [p.name for p in profiles]

    # Interactive prompts
    console.print("[bold]Database Configuration[/bold]")
    pghost = typer.prompt("  PGHOST", default="localhost")
    pgport = typer.prompt("  PGPORT", default="5432")
    pguser = typer.prompt("  PGUSER", default="odoo")
    pgpassword = typer.prompt("  PGPASSWORD", hide_input=True)
    pgdatabase = typer.prompt("  PGDATABASE", default="odoo")

    console.print("\n[bold]Odoo Configuration[/bold]")
    admin_passwd = typer.prompt("  ODOO_ADMIN_PASSWD (master password)", hide_input=True)
    http_port = typer.prompt("  ODOO_HTTP_PORT", default="8069")

    deploy_profile = ""
    if profile_names:
        console.print(f"\n  Available profiles: {', '.join(profile_names)}")
        deploy_profile = typer.prompt(
            "  ODOO_DEPLOY_PROFILE (press Enter to skip)",
            default="",
        )
        if deploy_profile and deploy_profile not in profile_names:
            console.print(f"[yellow]WARN[/yellow] Profile '{deploy_profile}' not found in install/")

    # Test PostgreSQL connectivity
    console.print("\n[bold]Testing PostgreSQL connectivity...[/bold]")
    ok, msg = test_pg_connectivity(pghost, pgport, pguser)
    if ok:
        console.print(f"  [green]OK[/green] {msg}")
    else:
        console.print(f"  [yellow]WARN[/yellow] {msg}")
        proceed = typer.confirm("  PostgreSQL is not reachable. Write .env anyway?", default=True)
        if not proceed:
            console.print("[yellow]Aborted.[/yellow]")
            raise typer.Exit(1)

    # Build .env content
    lines = [
        "# =============================================================================",
        "# Odoo 18 - Environment Configuration",
        "# =============================================================================",
        "# Generated by: kctl-odoo setup init",
        "",
        "# Project",
        "COMPOSE_PROJECT_NAME=kodemeio-odoo",
        "TENANT=local",
        "DOMAIN=localhost",
        "",
        "# Database",
        f"PGHOST={pghost}",
        f"PGPORT={pgport}",
        f"PGUSER={pguser}",
        f"PGPASSWORD={pgpassword}",
        f"PGDATABASE={pgdatabase}",
        "ODOO_DB_MAXCONN=64",
        "",
        "# Odoo",
        f"ODOO_ADMIN_PASSWD={admin_passwd}",
        f"ODOO_HTTP_PORT={http_port}",
        f"ODOO_LONGPOLLING_PORT={int(http_port) + 3}",
        "ODOO_WORKERS=0",
        "ODOO_MAX_CRON_THREADS=1",
        "ODOO_PROXY_MODE=False",
        "ODOO_DEV_MODE=reload,qweb,xml",
        "ODOO_SERVER_WIDE_MODULES=base,web,bus,bus_alt_connection,session_db",
        "",
    ]

    if deploy_profile:
        lines.extend(
            [
                "# Deployment Profile",
                f"ODOO_DEPLOY_PROFILE={deploy_profile}",
                "",
            ]
        )

    env_path.write_text("\n".join(lines) + "\n")
    console.print(f"\n[green]OK[/green] Wrote {env_path}")
    console.print("[dim]Next: kctl-odoo local build && kctl-odoo local up[/dim]")


# ---------------------------------------------------------------------------
# Check DB
# ---------------------------------------------------------------------------


@app.command("check-db")
def check_db() -> None:
    """Test PostgreSQL connectivity using configured .env values.

    Reads PGHOST/PGPORT/PGUSER/PGPASSWORD from environment or .env file and
    attempts to connect via pg_isready.

    Examples:
        kctl-odoo setup check-db
    """
    import os

    # Load from .env if present
    from kctl_odoo.core.utils import find_project_root

    env_path = find_project_root() / ".env"
    dotenv_vals = read_dotenv(env_path)

    pghost = os.environ.get("PGHOST", dotenv_vals.get("PGHOST", "localhost"))
    pgport = os.environ.get("PGPORT", dotenv_vals.get("PGPORT", "5432"))
    pguser = os.environ.get("PGUSER", dotenv_vals.get("PGUSER", "odoo"))

    console.print("[bold]PostgreSQL Connectivity Check[/bold]")
    console.print(f"  Host: {pghost}")
    console.print(f"  Port: {pgport}")
    console.print(f"  User: {pguser}")

    if env_path.exists():
        console.print(f"  Source: {env_path}")
    else:
        console.print("  Source: environment variables (no .env found)")

    console.print()

    ok, msg = test_pg_connectivity(pghost, pgport, pguser)
    if ok:
        console.print(f"[green]OK[/green] {msg}")
    else:
        console.print(f"[red]FAIL[/red] {msg}")
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# Smoke Test
# ---------------------------------------------------------------------------


@app.command("smoke-test")
def smoke_test(
    ctx: typer.Context,
) -> None:
    """Smoke-test key HTTP endpoints on the Odoo instance.

    Tests health, login page, database selector, JSON-RPC authentication,
    and a basic search_read on res.partner.

    Examples:
        kctl-odoo -p dev setup smoke-test
    """
    import httpx

    actx: AppContext = ctx.obj
    out = actx.output

    # Derive base URL from the client config
    c = actx.client
    base_url = c._base_url  # noqa: SLF001

    results: list[dict] = []
    passed = 0
    failed = 0

    def _record(name: str, ok: bool, detail: str) -> None:
        nonlocal passed, failed
        if ok:
            passed += 1
        else:
            failed += 1
        results.append({"test": name, "passed": ok, "detail": detail})

    http = httpx.Client(timeout=15, follow_redirects=True)

    # 1. GET /web/health
    try:
        resp = http.get(f"{base_url}/web/health")
        ok = resp.status_code == 200
        _record("GET /web/health", ok, f"HTTP {resp.status_code}")
    except Exception as e:
        _record("GET /web/health", False, str(e))

    # 2. GET /web/login
    try:
        resp = http.get(f"{base_url}/web/login")
        ok = resp.status_code == 200
        _record("GET /web/login", ok, f"HTTP {resp.status_code}")
    except Exception as e:
        _record("GET /web/login", False, str(e))

    # 3. GET /web/database/selector
    try:
        resp = http.get(f"{base_url}/web/database/selector")
        ok = resp.status_code in (200, 303)
        detail = f"HTTP {resp.status_code}"
        if resp.status_code == 303:
            detail += f" -> {resp.headers.get('location', '?')}"
        _record("GET /web/database/selector", ok, detail)
    except Exception as e:
        _record("GET /web/database/selector", False, str(e))

    # 4. JSON-RPC authenticate
    try:
        uid = c.authenticate()
        _record("JSON-RPC authenticate", True, f"UID {uid}")
    except Exception as e:
        _record("JSON-RPC authenticate", False, str(e))

    # 5. search_read res.partner
    try:
        partners = c.search_read("res.partner", domain=[], fields=["name"], limit=1)
        ok = isinstance(partners, list)
        count = len(partners) if ok else 0
        _record("search_read res.partner", ok, f"Returned {count} record(s)")
    except Exception as e:
        _record("search_read res.partner", False, str(e))

    http.close()

    # Output results
    rows = []
    for r in results:
        status = "[green]PASS[/green]" if r["passed"] else "[red]FAIL[/red]"
        rows.append([r["test"], status, r["detail"]])

    title = f"Smoke Test ({passed}/{passed + failed} passed)"
    if failed:
        title += f" - [red]{failed} failed[/red]"
    else:
        title += " - [green]all clear[/green]"

    out.table(
        title,
        [
            ("Endpoint", "cyan"),
            ("Status", ""),
            ("Detail", "dim"),
        ],
        rows,
        results,
    )

    if failed:
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# Audit — deep master data and configuration analysis
# ---------------------------------------------------------------------------


@app.command("audit")
def audit(ctx: typer.Context) -> None:
    """Deep audit of master data, configuration, and business readiness.

    Goes beyond the checklist to provide a comprehensive inventory of all
    configured master data: companies, currencies, chart of accounts,
    taxes, payment terms, warehouses, operating units, users, groups,
    sequences, fiscal positions, and more.

    Use this to understand what's configured vs what still needs setup.
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    json_data: dict = {}

    def _safe_count(model: str, domain: list | None = None) -> int:
        try:
            return c.search_count(model, domain or [])
        except Exception:
            return -1

    def _safe_read(model: str, domain: list | None = None, fields: list | None = None, limit: int = 100) -> list:
        try:
            return c.search_read(model, domain=domain or [], fields=fields or ["name"], limit=limit)
        except Exception:
            return []

    console.print("\n[bold cyan]Master Data & Configuration Audit[/bold cyan]\n")

    # --- Company ---
    companies = _safe_read("res.company", fields=["name", "currency_id", "country_id", "vat", "email", "phone"])
    console.print("[bold]Companies[/bold]")
    for comp in companies:
        curr = comp.get("currency_id", [None, "?"])
        country = comp.get("country_id", [None, "?"])
        curr_name = curr[1] if isinstance(curr, list) else str(curr or "?")
        country_name = country[1] if isinstance(country, list) else str(country or "Not set")
        console.print(
            f"  {comp['name']} — Currency: {curr_name}, Country: {country_name},"
            f" VAT: {comp.get('vat') or '[red]Not set[/red]'},"
            f" Email: {comp.get('email') or '[red]Not set[/red]'}"
        )
    json_data["companies"] = companies

    # --- Chart of Accounts ---
    account_count = _safe_count("account.account")
    console.print(f"\n[bold]Chart of Accounts[/bold]: {account_count} accounts")
    if account_count > 0:
        account_types = _safe_read("account.account", fields=["account_type"], limit=500)
        type_counts: dict[str, int] = {}
        for a in account_types:
            at = a.get("account_type", "unknown")
            type_counts[at] = type_counts.get(at, 0) + 1
        for at, cnt in sorted(type_counts.items(), key=lambda x: -x[1]):
            console.print(f"  {at}: {cnt}")
        json_data["chart_of_accounts"] = {"total": account_count, "by_type": type_counts}
    elif account_count == 0:
        console.print("  [red]No accounts! Load a localization package or import chart of accounts.[/red]")
        json_data["chart_of_accounts"] = {"total": 0}

    # --- Taxes ---
    console.print("\n[bold]Taxes[/bold]")
    sales_taxes = _safe_read(
        "account.tax", domain=[("type_tax_use", "=", "sale")], fields=["name", "amount", "amount_type"]
    )
    purchase_taxes = _safe_read(
        "account.tax", domain=[("type_tax_use", "=", "purchase")], fields=["name", "amount", "amount_type"]
    )
    if sales_taxes:
        console.print(f"  Sales ({len(sales_taxes)}):")
        for t in sales_taxes[:10]:
            console.print(f"    {t['name']} — {t.get('amount', '?')}% ({t.get('amount_type', '?')})")
    else:
        console.print("  [red]No sales taxes configured![/red]")
    if purchase_taxes:
        console.print(f"  Purchase ({len(purchase_taxes)}):")
        for t in purchase_taxes[:10]:
            console.print(f"    {t['name']} — {t.get('amount', '?')}% ({t.get('amount_type', '?')})")
    else:
        console.print("  [red]No purchase taxes configured![/red]")
    json_data["taxes"] = {"sales": len(sales_taxes), "purchase": len(purchase_taxes)}

    # --- Payment Terms ---
    terms = _safe_read("account.payment.term", fields=["name"])
    console.print(f"\n[bold]Payment Terms[/bold]: {len(terms)}")
    for t in terms:
        console.print(f"  {t['name']}")
    json_data["payment_terms"] = [t["name"] for t in terms]

    # --- Fiscal Positions ---
    fp_count = _safe_count("account.fiscal.position")
    console.print(f"\n[bold]Fiscal Positions[/bold]: {fp_count}")
    if fp_count == 0:
        console.print("  [yellow]None configured — needed for tax mapping across regions[/yellow]")
    json_data["fiscal_positions"] = fp_count

    # --- Warehouses ---
    warehouses = _safe_read("stock.warehouse", fields=["name", "code"])
    console.print(f"\n[bold]Warehouses[/bold]: {len(warehouses)}")
    for w in warehouses:
        console.print(f"  {w.get('code', '?')} — {w['name']}")
    json_data["warehouses"] = [{"name": w["name"], "code": w.get("code")} for w in warehouses]

    # --- Operating Units ---
    ous = _safe_read("operating.unit", fields=["name", "code"])
    if ous or _safe_count("operating.unit") >= 0:
        console.print(f"\n[bold]Operating Units[/bold]: {len(ous)}")
        for ou in ous:
            console.print(f"  {ou.get('code', '?')} — {ou['name']}")
        json_data["operating_units"] = [{"name": ou["name"], "code": ou.get("code")} for ou in ous]

    # --- Users ---
    users = _safe_read(
        "res.users", domain=[("active", "=", True), ("share", "=", False)], fields=["login", "name", "groups_id"]
    )
    console.print(f"\n[bold]Internal Users[/bold]: {len(users)}")
    for u in users:
        groups = u.get("groups_id", [])
        console.print(f"  {u.get('login', '?')} — {u['name']} ({len(groups)} groups)")
    json_data["users"] = [
        {"login": u.get("login"), "name": u["name"], "groups": len(u.get("groups_id", []))} for u in users
    ]

    # --- Product Categories ---
    cats = _safe_read("product.category", fields=["complete_name"])
    console.print(f"\n[bold]Product Categories[/bold]: {len(cats)}")
    for cat in cats[:15]:
        console.print(f"  {cat.get('complete_name', cat.get('name', '?'))}")
    if len(cats) > 15:
        console.print(f"  ... and {len(cats) - 15} more")
    json_data["product_categories"] = len(cats)

    # --- Currencies ---
    currencies = _safe_read("res.currency", domain=[("active", "=", True)], fields=["name", "symbol"])
    console.print(f"\n[bold]Active Currencies[/bold]: {len(currencies)}")
    for cur in currencies:
        console.print(f"  {cur['name']} ({cur.get('symbol', '?')})")
    json_data["currencies"] = [c["name"] for c in currencies]

    # --- Bank Accounts ---
    banks = _safe_read("res.partner.bank", fields=["acc_number", "bank_id"])
    console.print(f"\n[bold]Bank Accounts[/bold]: {len(banks)}")
    for b in banks:
        bank_name = b.get("bank_id", [None, "?"])
        bname = bank_name[1] if isinstance(bank_name, list) else str(bank_name or "?")
        console.print(f"  {b.get('acc_number', '?')} — {bname}")
    json_data["bank_accounts"] = len(banks)

    # --- Journals ---
    journals = _safe_read("account.journal", fields=["name", "type", "code"])
    if journals:
        console.print(f"\n[bold]Accounting Journals[/bold]: {len(journals)}")
        for j in journals:
            console.print(f"  {j.get('code', '?')} — {j['name']} ({j.get('type', '?')})")
        json_data["journals"] = [{"name": j["name"], "type": j.get("type"), "code": j.get("code")} for j in journals]

    # --- Pricelists ---
    pricelists = _safe_read("product.pricelist", fields=["name", "currency_id"])
    console.print(f"\n[bold]Pricelists[/bold]: {len(pricelists)}")
    if pricelists:
        for pl in pricelists:
            curr = pl.get("currency_id", [None, "?"])
            cname = curr[1] if isinstance(curr, list) else str(curr or "?")
            console.print(f"  {pl['name']} ({cname})")
    else:
        console.print("  [yellow]None configured — needed for customer pricing strategies[/yellow]")
    json_data["pricelists"] = len(pricelists)

    # --- Sales Teams ---
    teams = _safe_read("crm.team", fields=["name"])
    if teams:
        console.print(f"\n[bold]Sales Teams[/bold]: {len(teams)}")
        for t in teams:
            console.print(f"  {t['name']}")
        json_data["sales_teams"] = [t["name"] for t in teams]

    # --- Stock Locations ---
    locations = _safe_read(
        "stock.location", domain=[("usage", "in", ["internal", "transit"])], fields=["complete_name", "usage"]
    )
    console.print(f"\n[bold]Stock Locations[/bold]: {len(locations)} (internal + transit)")
    for loc in locations[:15]:
        console.print(f"  {loc.get('complete_name', '?')} [{loc.get('usage', '?')}]")
    if len(locations) > 15:
        console.print(f"  ... and {len(locations) - 15} more")
    json_data["stock_locations"] = len(locations)

    # --- Picking Types ---
    picking_types = _safe_read("stock.picking.type", fields=["name", "code", "warehouse_id"])
    if picking_types:
        console.print(f"\n[bold]Picking Types[/bold]: {len(picking_types)}")
        for pt in picking_types:
            wh = pt.get("warehouse_id", [None, "?"])
            wh_name = wh[1] if isinstance(wh, list) else str(wh or "?")
            console.print(f"  {pt['name']} ({pt.get('code', '?')}) — {wh_name}")
        json_data["picking_types"] = len(picking_types)

    # --- UoM ---
    uom_cats = _safe_read("uom.category", fields=["name"])
    uom_count = _safe_count("uom.uom")
    console.print(f"\n[bold]Units of Measure[/bold]: {uom_count} UoMs in {len(uom_cats)} categories")
    for cat in uom_cats:
        console.print(f"  {cat['name']}")
    json_data["uom"] = {"units": uom_count, "categories": len(uom_cats)}

    # --- Email Templates ---
    templates = _safe_read("mail.template", fields=["name", "model_id"], limit=20)
    console.print(f"\n[bold]Email Templates[/bold]: {len(templates)}")
    for t in templates[:10]:
        model = t.get("model_id", [None, "?"])
        mname = model[1] if isinstance(model, list) else str(model or "?")
        console.print(f"  {t['name']} ({mname})")
    if len(templates) > 10:
        console.print(f"  ... and {len(templates) - 10} more")
    json_data["email_templates"] = len(templates)

    # --- Incoterms ---
    incoterms_count = _safe_count("account.incoterms")
    if incoterms_count >= 0:
        console.print(f"\n[bold]Incoterms[/bold]: {incoterms_count}")
        json_data["incoterms"] = incoterms_count

    # --- Working Hours ---
    calendars = _safe_read("resource.calendar", fields=["name"])
    if calendars:
        console.print(f"\n[bold]Working Hours / Calendars[/bold]: {len(calendars)}")
        for cal in calendars:
            console.print(f"  {cal['name']}")
        json_data["working_calendars"] = len(calendars)

    # --- Key System Parameters ---
    key_params = [
        "web.base.url",
        "report.url",
        "mail.catchall.domain",
        "mail.default.from",
        "database.uuid",
        "database.create_date",
    ]
    console.print("\n[bold]Key System Parameters[/bold]")
    params_data = {}
    for key in key_params:
        result = _safe_read("ir.config_parameter", domain=[("key", "=", key)], fields=["value"])
        val = result[0]["value"] if result else "[red]Not set[/red]"
        console.print(f"  {key} = {val}")
        params_data[key] = result[0]["value"] if result else None
    json_data["system_parameters"] = params_data

    # --- Summary ---
    console.print(f"\n{'=' * 60}")
    console.print("[bold]Audit Summary[/bold]")
    issues = []
    if account_count < 10:
        issues.append("Chart of accounts incomplete (< 10 accounts)")
    if not sales_taxes:
        issues.append("No sales taxes configured")
    if not purchase_taxes:
        issues.append("No purchase taxes configured")
    if not terms:
        issues.append("No payment terms defined")
    if not journals:
        issues.append("No accounting journals configured")
    if fp_count == 0:
        issues.append("No fiscal positions (needed for tax mapping)")
    if not pricelists:
        issues.append("No pricelists configured")
    if not banks:
        issues.append("No bank accounts configured")
    if not params_data.get("mail.catchall.domain"):
        issues.append("mail.catchall.domain not set")
    if not params_data.get("report.url"):
        issues.append("report.url not set (needed for PDF generation)")
    if uom_count < 3:
        issues.append("Too few units of measure (need Unit, kg, Hour minimum)")
    base_url = params_data.get("web.base.url", "")
    if base_url and ("localhost" in base_url or "127.0.0.1" in base_url):
        issues.append(f"web.base.url still points to localhost: {base_url}")

    if issues:
        console.print(f"\n[yellow]{len(issues)} issues to address:[/yellow]")
        for i, issue in enumerate(issues, 1):
            console.print(f"  {i}. {issue}")
    else:
        console.print("\n[green]All master data looks good.[/green]")

    if actx.json_mode:
        json_data["issues"] = issues
        out.raw_json(json_data)
