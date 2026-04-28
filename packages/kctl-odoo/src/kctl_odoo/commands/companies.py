"""Company management commands."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Annotated

import typer

from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.resolve import resolve_id

app = typer.Typer(help="Manage Odoo companies.")


def _resolve_company_id(client: object, identifier: str) -> int:
    """Resolve company ID from numeric ID or name."""
    return resolve_id(client, "res.company", identifier, ilike=True, label="Company")  # type: ignore[arg-type]


@app.command("list")
def list_(
    ctx: typer.Context,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 80,
) -> None:
    """List companies."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    companies = c.search_read(
        "res.company",
        domain=[],
        fields=["id", "name", "email", "phone", "currency_id", "parent_id"],
        limit=limit,
        order="id",
    )

    rows = []
    json_data = []
    for co in companies:
        currency = co.get("currency_id")
        currency_name = currency[1] if isinstance(currency, list) else str(currency or "-")
        parent = co.get("parent_id")
        parent_name = parent[1] if isinstance(parent, list) else str(parent or "-") if parent else "-"

        rows.append(
            [
                str(co["id"]),
                co["name"],
                co.get("email") or "-",
                co.get("phone") or "-",
                currency_name,
                parent_name,
            ]
        )
        json_data.append(
            {
                "id": co["id"],
                "name": co["name"],
                "email": co.get("email"),
                "phone": co.get("phone"),
                "currency": currency_name,
                "parent": parent_name,
            }
        )

    out.table(
        f"Companies ({len(companies)})",
        [("ID", "cyan"), ("Name", ""), ("Email", "dim"), ("Phone", "dim"), ("Currency", ""), ("Parent", "dim")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def get(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="Company ID or name")],
) -> None:
    """Get company details."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    company_id = _resolve_company_id(c, identifier)
    records = c.read(
        "res.company",
        [company_id],
        fields=[
            "id",
            "name",
            "email",
            "phone",
            "website",
            "vat",
            "currency_id",
            "parent_id",
            "child_ids",
            "street",
            "city",
            "zip",
            "country_id",
            "create_date",
            "write_date",
        ],
    )

    if not records:
        out.error(f"Company not found: {identifier}")
        raise typer.Exit(1)

    co = records[0]
    currency = co.get("currency_id")
    currency_name = currency[1] if isinstance(currency, list) else str(currency or "-")
    parent = co.get("parent_id")
    parent_name = parent[1] if isinstance(parent, list) else "-" if not parent else str(parent)
    country = co.get("country_id")
    country_name = country[1] if isinstance(country, list) else str(country or "-")

    sections = [
        (
            "Company Info",
            [
                ("ID", str(co["id"])),
                ("Name", co["name"]),
                ("Email", co.get("email") or "-"),
                ("Phone", co.get("phone") or "-"),
                ("Website", co.get("website") or "-"),
                ("VAT", co.get("vat") or "-"),
                ("Currency", currency_name),
                ("Parent", parent_name),
                ("Children", str(len(co.get("child_ids", [])))),
            ],
        ),
        (
            "Address",
            [
                ("Street", co.get("street") or "-"),
                ("City", co.get("city") or "-"),
                ("ZIP", co.get("zip") or "-"),
                ("Country", country_name),
            ],
        ),
        (
            "Dates",
            [
                ("Created", str(co.get("create_date", ""))),
                ("Updated", str(co.get("write_date", ""))),
            ],
        ),
    ]

    out.detail(f"Company: {co['name']}", sections, data_for_json=co)


@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", "-n", help="Company name")],
    email: Annotated[str | None, typer.Option("--email", help="Email")] = None,
    currency: Annotated[str | None, typer.Option("--currency", help="Currency code (e.g. USD, EUR)")] = None,
    parent: Annotated[str | None, typer.Option("--parent", help="Parent company ID or name")] = None,
) -> None:
    """Create a new company."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    vals: dict = {"name": name}
    if email:
        vals["email"] = email
    if currency:
        currency_ids = c.search("res.currency", [("name", "=", currency.upper())])
        if not currency_ids:
            out.error(f"Currency not found: {currency}")
            raise typer.Exit(1)
        vals["currency_id"] = currency_ids[0]
    if parent:
        vals["parent_id"] = _resolve_company_id(c, parent)

    company_id = c.create("res.company", vals)
    out.success(f"Created company '{name}' (ID: {company_id})")


@app.command()
def update(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="Company ID or name")],
    name: Annotated[str | None, typer.Option("--name", "-n", help="New name")] = None,
    email: Annotated[str | None, typer.Option("--email", help="Email")] = None,
    phone: Annotated[str | None, typer.Option("--phone", help="Phone")] = None,
    website: Annotated[str | None, typer.Option("--website", help="Website")] = None,
) -> None:
    """Update a company."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    company_id = _resolve_company_id(c, identifier)
    vals: dict = {}
    if name is not None:
        vals["name"] = name
    if email is not None:
        vals["email"] = email
    if phone is not None:
        vals["phone"] = phone
    if website is not None:
        vals["website"] = website

    if not vals:
        out.warn("No fields to update")
        return

    c.write("res.company", [company_id], vals)
    out.success(f"Updated company {identifier} (ID: {company_id})")


@app.command()
def users(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="Company ID or name")],
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 80,
) -> None:
    """List users belonging to a company."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    company_id = _resolve_company_id(c, identifier)
    company_data = c.read("res.company", [company_id], fields=["name"])
    company_name = company_data[0]["name"] if company_data else str(company_id)

    user_records = c.search_read(
        "res.users",
        domain=[("company_ids", "in", [company_id])],
        fields=["id", "login", "name", "email", "active", "company_id"],
        limit=limit,
        order="login",
    )

    rows = []
    json_data = []
    for u in user_records:
        current_co = u.get("company_id")
        is_current = current_co[0] == company_id if isinstance(current_co, list) else False
        status = "[green]active[/green]" if u.get("active") else "[red]inactive[/red]"
        current_label = "[cyan]current[/cyan]" if is_current else ""

        rows.append([str(u["id"]), u["login"], u["name"], u.get("email") or "-", status, current_label])
        json_data.append(
            {
                "id": u["id"],
                "login": u["login"],
                "name": u["name"],
                "email": u.get("email"),
                "active": u.get("active"),
                "is_current_company": is_current,
            }
        )

    out.table(
        f"Users in '{company_name}' ({len(user_records)})",
        [("ID", "cyan"), ("Login", ""), ("Name", ""), ("Email", "dim"), ("Status", ""), ("Current Co.", "")],
        rows,
        data_for_json=json_data,
    )


@app.command("switch")
def switch_company(
    ctx: typer.Context,
    user_id: Annotated[int, typer.Argument(help="User ID")],
    company_id: Annotated[int, typer.Argument(help="Target company ID")],
) -> None:
    """Switch a user's current company."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Verify user exists
    user_data = c.read("res.users", [user_id], fields=["login", "company_ids"])
    if not user_data:
        out.error(f"User not found: {user_id}")
        raise typer.Exit(1)

    # Verify company is in user's allowed companies
    allowed = user_data[0].get("company_ids", [])
    if company_id not in allowed:
        out.error(f"Company {company_id} is not in user's allowed companies: {allowed}")
        raise typer.Exit(1)

    c.write("res.users", [user_id], {"company_id": company_id})
    out.success(f"Switched user {user_data[0]['login']} (ID: {user_id}) to company ID {company_id}")


def _run_setup(
    c: object,
    out: object,
    *,
    name: str,
    template_id: int,
    street: str | None = None,
    city: str | None = None,
    phone: str | None = None,
    email: str | None = None,
    npwp: str | None = None,
    warehouse_prefix: str | None = None,
    skip_warehouses: bool = False,
    skip_fiscal_positions: bool = False,
    skip_extra_journals: bool = False,
    skip_report_formats: bool = False,
    dry_run: bool = False,
) -> dict | None:
    """Call CompanyOnboardingService.provision() via JSON-RPC."""
    # Verify company_onboarding module is installed
    installed = c.search(
        "ir.module.module",
        [("name", "=", "company_onboarding"), ("state", "=", "installed")],
    )
    if not installed:
        out.error("Module 'company_onboarding' is not installed. Install it first.")
        raise typer.Exit(1)

    company_vals = {"name": name}
    if street:
        company_vals["street"] = street
    if city:
        company_vals["city"] = city
    if phone:
        company_vals["phone"] = phone
    if email:
        company_vals["email"] = email
    if npwp:
        company_vals["npwp"] = npwp
    if warehouse_prefix:
        company_vals["warehouse_code_prefix"] = warehouse_prefix

    options = {
        "clone_fiscal_positions": not skip_fiscal_positions,
        "clone_warehouses": not skip_warehouses,
        "clone_extra_journals": not skip_extra_journals,
        "clone_report_formats": not skip_report_formats,
    }

    if dry_run:
        out.info(f"[DRY RUN] Would create company '{name}' from template ID {template_id}")
        out.info(f"  Options: {options}")
        return None

    result = c.execute_kw(
        "company.onboarding.wizard",
        "action_provision_from_cli",
        [company_vals, template_id, options],
    )

    # Display results
    out.success(f"Created company '{result['company_name']}' (ID: {result['company_id']})")
    for step in result.get("steps", []):
        icon = {"ok": "✓", "skipped": "⊘", "error": "✗"}.get(step["status"], "?")
        style = "green" if step["status"] == "ok" else ("yellow" if step["status"] == "skipped" else "red")
        out.console.print(f"  [{style}]{icon}[/{style}] {step['name']}: {step['detail']}")

    out.console.print()
    out.console.print("[dim]Next steps:[/dim]")
    out.console.print("  1. Assign users:  kctl-odoo roles assign <login> --roles finance_user")
    out.console.print("  2. Configure bank: Settings → Companies → Giro/Cek Accounts")
    out.console.print("  3. Set tax office: Settings → Companies → Tax Settings")

    return result


@app.command()
def setup(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", "-n", help="Company name")],
    template: Annotated[str, typer.Option("--template", "-t", help="Template company ID or name")],
    street: Annotated[str | None, typer.Option(help="Street address")] = None,
    city: Annotated[str | None, typer.Option(help="City")] = None,
    phone: Annotated[str | None, typer.Option(help="Phone")] = None,
    email: Annotated[str | None, typer.Option(help="Email")] = None,
    npwp: Annotated[str | None, typer.Option(help="NPWP (Indonesian Tax ID)")] = None,
    warehouse_prefix: Annotated[
        str | None, typer.Option("--warehouse-prefix", help="3-char warehouse code prefix")
    ] = None,
    skip_warehouses: Annotated[bool, typer.Option("--skip-warehouses", help="Skip warehouse cloning")] = False,
    skip_fiscal_positions: Annotated[
        bool, typer.Option("--skip-fiscal-positions", help="Skip fiscal position cloning")
    ] = False,
    skip_extra_journals: Annotated[
        bool, typer.Option("--skip-extra-journals", help="Skip extra journal cloning")
    ] = False,
    skip_report_formats: Annotated[
        bool, typer.Option("--skip-report-formats", help="Skip report format provisioning")
    ] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview without creating")] = False,
) -> None:
    """Create and provision a new company from a template.

    Installs l10n_id CoA (journals + taxes), then clones warehouses, fiscal
    positions, extra journals, and report formats from the template company.

    Requires the company_onboarding module to be installed.

    Examples:
        kctl-odoo companies setup --name "CV Baru Import" --template 2
        kctl-odoo companies setup -n "CV Baru" -t "CV Sumber Pangan" --npwp "01.234.567.8-901.000"
        kctl-odoo companies setup -n "CV Test" -t 2 --skip-warehouses --dry-run
    """
    actx: AppContext = ctx.obj
    template_id = _resolve_company_id(actx.client, template)

    _run_setup(
        actx.client,
        actx.output,
        name=name,
        template_id=template_id,
        street=street,
        city=city,
        phone=phone,
        email=email,
        npwp=npwp,
        warehouse_prefix=warehouse_prefix,
        skip_warehouses=skip_warehouses,
        skip_fiscal_positions=skip_fiscal_positions,
        skip_extra_journals=skip_extra_journals,
        skip_report_formats=skip_report_formats,
        dry_run=dry_run,
    )


@app.command("setup-batch")
def setup_batch(
    ctx: typer.Context,
    csv_file: Annotated[Path, typer.Argument(help="CSV file with columns: name,street,city,npwp,warehouse_prefix")],
    template: Annotated[str, typer.Option("--template", "-t", help="Template company ID or name")],
    skip_warehouses: Annotated[bool, typer.Option("--skip-warehouses", help="Skip warehouse cloning")] = False,
    skip_report_formats: Annotated[
        bool, typer.Option("--skip-report-formats", help="Skip report format provisioning")
    ] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview without creating")] = False,
) -> None:
    """Batch-create companies from a CSV file.

    CSV format (header required):
        name,street,city,npwp,warehouse_prefix
        CV Baru Import,Jl. Raya 1,Surabaya,01.234.567.8-901.000,BRI
        CV Lain Import,Jl. Lain 2,Jakarta,02.345.678.9-012.000,LNI

    Requires the company_onboarding module to be installed.

    Examples:
        kctl-odoo companies setup-batch companies.csv --template 2
        kctl-odoo companies setup-batch companies.csv -t "CV Sumber Pangan" --dry-run
    """
    actx: AppContext = ctx.obj
    out = actx.output

    if not csv_file.exists():
        out.error(f"File not found: {csv_file}")
        raise typer.Exit(1)

    template_id = _resolve_company_id(actx.client, template)

    with csv_file.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        out.warn("CSV file is empty")
        return

    out.info(f"Processing {len(rows)} companies from {csv_file.name}")
    out.console.print()

    created, failed = 0, 0
    for i, row in enumerate(rows, 1):
        company_name = row.get("name", "").strip()
        if not company_name:
            out.warn(f"Row {i}: skipping — empty name")
            continue

        out.console.rule(f"[bold]{i}/{len(rows)}: {company_name}")
        try:
            result = _run_setup(
                actx.client,
                out,
                name=company_name,
                template_id=template_id,
                street=row.get("street", "").strip() or None,
                city=row.get("city", "").strip() or None,
                phone=row.get("phone", "").strip() or None,
                email=row.get("email", "").strip() or None,
                npwp=row.get("npwp", "").strip() or None,
                warehouse_prefix=row.get("warehouse_prefix", "").strip() or None,
                skip_warehouses=skip_warehouses,
                skip_report_formats=skip_report_formats,
                dry_run=dry_run,
            )
            if result:
                created += 1
        except (typer.Exit, Exception) as exc:
            out.error(f"Failed: {company_name} — {exc}")
            failed += 1

        out.console.print()

    out.console.rule("[bold]Summary")
    out.info(f"Created: {created}, Failed: {failed}, Total: {len(rows)}")


@app.command("bootstrap-baseline")
def bootstrap_baseline(
    ctx: typer.Context,
    company: Annotated[str, typer.Argument(help="Company ID or name (template or existing)")],
    all_companies: Annotated[bool, typer.Option("--all", help="Run on every company")] = False,
) -> None:
    """Retro-fit baseline setup on existing companies.

    Idempotent. For each target company, ensures:
      - At least one stock.warehouse exists (creates HDQ if missing)
      - At least one operating.unit exists (creates HDQ if missing — OCA optional)
      - Bank journals have default_account_id set

    Used to backfill the template company and pre-existing companies that
    were created before company_onboarding was installed. Calls
    company.onboarding.service.bootstrap_baseline() server-side, which uses
    sudo() to bypass the stock_request and operating_unit access groups.

    Examples:
        kctl-odoo companies bootstrap-baseline 338
        kctl-odoo companies bootstrap-baseline _TEMPLATE_TPP_IMPORT
        kctl-odoo companies bootstrap-baseline --all _
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    installed = c.search(
        "ir.module.module",
        [("name", "=", "company_onboarding"), ("state", "=", "installed")],
    )
    if not installed:
        out.error("Module 'company_onboarding' is not installed.")
        raise typer.Exit(1)

    if all_companies:
        ids = [r["id"] for r in c.search_read("res.company", [], fields=["id"], order="id")]
    else:
        ids = [_resolve_company_id(c, company)]

    rows = []
    json_data = []
    for cid in ids:
        comp = c.read("res.company", [cid], fields=["id", "name"])
        cname = comp[0]["name"] if comp else f"id={cid}"
        try:
            result = c.execute_kw(
                "company.onboarding.wizard",
                "action_bootstrap_baseline_from_cli",
                [cid],
            )
            status = result.get("status", "?") if isinstance(result, dict) else "?"
            detail = result.get("detail", "") if isinstance(result, dict) else str(result)
        except Exception as e:
            status = "error"
            detail = str(e)
        rows.append([str(cid), cname, status, detail])
        json_data.append({"id": cid, "name": cname, "status": status, "detail": detail})
        icon = {"ok": "[green]OK[/green]", "error": "[red]ERR[/red]"}.get(status, status)
        out.console.print(f"  {icon} [{cid}] {cname}: {detail}")

    if actx.json_mode:
        out.raw_json(json_data)
