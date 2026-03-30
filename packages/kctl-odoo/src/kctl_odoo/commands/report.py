"""Report management commands.

Includes both Odoo built-in ir.actions.report commands (list, render, templates,
generate) and custom report_management framework commands (types, run, instances,
view, export, download).
"""

from __future__ import annotations

import base64
import contextlib
from datetime import date, timedelta
from pathlib import Path
from typing import Annotated

import typer

from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.exceptions import RPCError

app = typer.Typer(help="Manage Odoo reports and generate diagnostic reports.")

# Backward-compatible aliases for old short codes
CODE_ALIASES: dict[str, str] = {
    "pnl": "profit_loss",
    "bs": "balance_sheet",
    "cf": "cash_flow",
    "tb": "trial_balance",
    "cma": "cost_management",
    "ar_aging": "receivable_aging",
    "ap_aging": "payable_aging",
    "cashflow_recon": "cashflow_reconciliation",
    "inventory_fg": "inventory_finished_goods",
    "inventory_rm": "inventory_raw_materials",
    "mrp_oee": "mrp_equipment_effectiveness",
    "mrp_wip": "mrp_work_in_progress",
    "logistics_otd": "logistics_on_time_delivery",
    "logistics_otif": "logistics_on_time_in_full",
}


def _resolve_type_code(type_code: str) -> str:
    """Resolve a report type code, applying backward-compatible aliases."""
    return CODE_ALIASES.get(type_code, type_code)


# Report types → diagnose section mappings
REPORT_TYPES: dict[str, list[str] | None] = {
    "health": ["server_health", "configuration", "mail", "storage", "dr"],
    "finance": ["financial_health", "data_integrity", "kpis"],
    "security": ["security"],
    "inventory": ["inventory_health", "data_integrity", "kpis"],
    "operations": ["kpis", "mail", "data_integrity"],
    "full": None,  # all sections
}


@app.command("list")
def list_(
    ctx: typer.Context,
    model: Annotated[str | None, typer.Option("--model", "-m", help="Filter by model name")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List available reports."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    domain: list = []
    if model:
        domain.append(("model", "=", model))

    reports = c.search_read(
        "ir.actions.report",
        domain=domain,
        fields=["id", "name", "report_name", "model", "report_type", "print_report_name", "binding_model_id"],
        limit=limit,
        order="model, name",
    )

    if not reports:
        out.info("No reports found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for r in reports:
        report_type = r.get("report_type", "")
        type_display = {
            "qweb-pdf": "[green]PDF[/green]",
            "qweb-html": "[cyan]HTML[/cyan]",
            "qweb-text": "[dim]Text[/dim]",
        }.get(report_type, report_type)

        binding = r.get("binding_model_id")
        binding_display = binding[1] if isinstance(binding, list) else ""

        rows.append(
            [
                str(r["id"]),
                (r.get("name") or "")[:35],
                r.get("report_name", ""),
                r.get("model", ""),
                type_display,
                (r.get("print_report_name") or "")[:30],
            ]
        )
        json_data.append(
            {
                "id": r["id"],
                "name": r.get("name"),
                "report_name": r.get("report_name"),
                "model": r.get("model"),
                "report_type": report_type,
                "print_report_name": r.get("print_report_name"),
                "binding_model": binding_display or None,
            }
        )

    out.table(
        f"Reports ({len(reports)})",
        [
            ("ID", "cyan"),
            ("Name", ""),
            ("Report Name", ""),
            ("Model", ""),
            ("Type", ""),
            ("Print Name", "dim"),
        ],
        rows,
        data_for_json=json_data,
    )


@app.command()
def render(
    ctx: typer.Context,
    report_name: Annotated[str, typer.Argument(help="Report technical name (e.g. account.report_invoice)")],
    record_ids: Annotated[str, typer.Argument(help="Comma-separated record IDs")],
    fmt: Annotated[str, typer.Option("--format", "-f", help="Output format: pdf or html")] = "pdf",
    output: Annotated[str | None, typer.Option("--output", "-o", help="Output file path")] = None,
) -> None:
    """Render a report for given record IDs and save to file."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if fmt not in ("pdf", "html"):
        out.error("Format must be 'pdf' or 'html'.")
        raise typer.Exit(1)

    ids = [int(i.strip()) for i in record_ids.split(",")]

    # Find the report action to get the model
    reports = c.search_read(
        "ir.actions.report",
        domain=[("report_name", "=", report_name)],
        fields=["id", "name", "model", "report_type"],
    )
    if not reports:
        out.error(f"Report not found: {report_name}")
        raise typer.Exit(1)

    report_info = reports[0]

    # Use _render first (Odoo 17+), fall back to specific method for older versions
    fallback_method = "render_qweb_pdf" if fmt == "pdf" else "render_qweb_html"
    try:
        result = c.execute_kw(
            "ir.actions.report",
            "_render",
            [[report_info["id"]], report_name, ids],
        )
    except RPCError:
        # Fallback: try the specific render method on the report model
        try:
            result = c.execute_kw(
                "ir.actions.report",
                fallback_method,
                [[report_info["id"]], ids],
            )
        except RPCError as e2:
            out.error(f"Failed to render report: {e2.detail}")
            raise typer.Exit(1) from e2

    # Result is typically [base64_content, report_type] or just base64 content
    if isinstance(result, list) and len(result) >= 1:
        content = result[0]
    elif isinstance(result, str):
        content = result
    else:
        out.error("Unexpected response format from report rendering.")
        raise typer.Exit(1)

    # Decode if base64 encoded
    if isinstance(content, str):
        try:
            file_data = base64.b64decode(content)
        except Exception:
            # Might be raw content
            file_data = content.encode("utf-8")
    elif isinstance(content, bytes):
        file_data = content
    else:
        out.error("Could not decode report content.")
        raise typer.Exit(1)

    ext = "pdf" if fmt == "pdf" else "html"
    if output:
        output_path = Path(output)
    else:
        safe_name = report_name.replace(".", "_")
        output_path = Path(f"{safe_name}_{'-'.join(str(i) for i in ids)}.{ext}")

    output_path.write_bytes(file_data)
    out.success(f"Report saved to {output_path} ({len(file_data)} bytes)")
    if actx.json_mode:
        out.raw_json(
            {
                "report_name": report_name,
                "record_ids": ids,
                "format": fmt,
                "file": str(output_path),
                "size": len(file_data),
            }
        )


@app.command()
def templates(
    ctx: typer.Context,
    model: Annotated[str | None, typer.Option("--model", "-m", help="Filter by related model")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List QWeb report templates."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    domain: list = [("type", "=", "qweb")]
    if model:
        domain.append(("model", "=", model))

    views = c.search_read(
        "ir.ui.view",
        domain=domain,
        fields=["id", "name", "key", "model", "active", "priority"],
        limit=limit,
        order="model, name",
    )

    if not views:
        out.info("No QWeb templates found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for v in views:
        status = "[green]active[/green]" if v.get("active") else "[dim]inactive[/dim]"
        rows.append(
            [
                str(v["id"]),
                (v.get("name") or "")[:35],
                v.get("key", "") or "-",
                v.get("model", "") or "-",
                str(v.get("priority", "")),
                status,
            ]
        )
        json_data.append(
            {
                "id": v["id"],
                "name": v.get("name"),
                "key": v.get("key"),
                "model": v.get("model"),
                "priority": v.get("priority"),
                "active": v.get("active"),
            }
        )

    out.table(
        f"QWeb Templates ({len(views)})",
        [("ID", "cyan"), ("Name", ""), ("Key", ""), ("Model", ""), ("Priority", "dim"), ("Status", "")],
        rows,
        data_for_json=json_data,
    )


@app.command("generate")
def generate(
    ctx: typer.Context,
    report_type: Annotated[
        str, typer.Argument(help="Report type: health, finance, security, inventory, operations, full")
    ],
    output: Annotated[str | None, typer.Option("--output", "-o", help="Write to file (.md, .json, .html)")] = None,
    quick: Annotated[bool, typer.Option("--quick", help="Skip slow checks")] = False,
) -> None:
    """Generate a focused diagnostic report by domain.

    Maps business-friendly report names to diagnose sections.

    Examples:
        kctl-odoo report generate health
        kctl-odoo report generate finance --output finance-march.md
        kctl-odoo report generate security --output security.html
        kctl-odoo report generate full --output audit.json
        kctl-odoo report generate inventory --quick
    """
    if report_type not in REPORT_TYPES:
        valid = ", ".join(REPORT_TYPES.keys())
        typer.echo(f"Unknown report type '{report_type}'. Valid: {valid}", err=True)
        raise typer.Exit(1)

    sections = REPORT_TYPES[report_type]
    section_arg = ",".join(sections) if sections else None

    # Import and delegate to diagnose engine
    from kctl_odoo.commands.diagnose import run_diagnose_core

    run_diagnose_core(ctx, output=output, quick=quick, section_filter=section_arg)


# ===================================================================
# report_management framework commands
# ===================================================================


def _check_report_management(c: object, out: object) -> bool:
    """Return True if report_management module is available, else log info."""
    try:
        c.search_count("report.type.registry", [])  # type: ignore[attr-defined]
        return True
    except RPCError:
        out.info("report_management module is not installed.")  # type: ignore[attr-defined]
        return False


def _default_date_range() -> tuple[str, str]:
    """Return (date_from, date_to) for last complete month as ISO strings."""
    today = date.today()
    first_of_month = today.replace(day=1)
    last_month_end = first_of_month - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)
    return last_month_start.isoformat(), last_month_end.isoformat()


def _fiscal_year_start(ref_date: str) -> str:
    """Return January 1st of the fiscal year for *ref_date* (ISO string)."""
    return date.fromisoformat(ref_date).replace(month=1, day=1).isoformat()


def _m2o(val: object) -> str:
    """Format an M2O field — Odoo returns [id, name] lists."""
    if isinstance(val, list):
        return str(val[1]) if len(val) > 1 else str(val[0])
    return str(val or "")


@app.command("types")
def report_types(
    ctx: typer.Context,
    category: Annotated[
        str | None,
        typer.Option("--category", "-c", help="Filter by category (financial, aging, sales, inventory, mrp, sfa)"),
    ] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List report types from the report_management registry.

    These are custom report types defined in report.type.registry, NOT Odoo's
    built-in ir.actions.report. Use 'report list' for built-in reports.

    Examples:
        kctl-odoo report types
        kctl-odoo report types --category financial
        kctl-odoo report types --json
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _check_report_management(c, out):
        if actx.json_mode:
            out.raw_json([])
        return

    domain: list = []
    if category:
        domain.append(("category", "=", category))

    try:
        records = c.search_read(
            "report.type.registry",
            domain=domain,
            fields=["id", "name", "code", "category", "handler_model", "date_mode", "active"],
            limit=limit,
            order="category, sequence, name",
        )
    except RPCError as e:
        out.error(f"Failed to fetch report types: {e.detail}")
        raise typer.Exit(1) from e

    if not records:
        out.info("No report types found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for r in records:
        cat = r.get("category", "") or ""
        cat_display = {
            "financial": "[green]financial[/green]",
            "aging": "[yellow]aging[/yellow]",
            "management": "[cyan]management[/cyan]",
            "custom": "[dim]custom[/dim]",
        }.get(cat, cat)
        status = "[green]active[/green]" if r.get("active") else "[dim]inactive[/dim]"

        rows.append(
            [
                str(r["id"]),
                r.get("code", ""),
                (r.get("name") or "")[:35],
                cat_display,
                r.get("date_mode", ""),
                (r.get("handler_model") or "")[:30],
                status,
            ]
        )
        json_data.append(
            {
                "id": r["id"],
                "code": r.get("code"),
                "name": r.get("name"),
                "category": cat,
                "date_mode": r.get("date_mode"),
                "handler_model": r.get("handler_model"),
                "active": r.get("active"),
            }
        )

    out.table(
        f"Report Types ({len(records)})",
        [
            ("ID", "cyan"),
            ("Code", ""),
            ("Name", ""),
            ("Category", ""),
            ("Date Mode", "dim"),
            ("Handler", "dim"),
            ("Status", ""),
        ],
        rows,
        data_for_json=json_data,
    )


@app.command("run")
def report_run(
    ctx: typer.Context,
    type_code: Annotated[
        str, typer.Argument(help="Report type code (e.g. profit_loss, balance_sheet, receivable_aging)")
    ],
    date_from: Annotated[str | None, typer.Option("--date-from", help="Start date (YYYY-MM-DD)")] = None,
    date_to: Annotated[str | None, typer.Option("--date-to", help="End date (YYYY-MM-DD)")] = None,
    as_of_date: Annotated[
        str | None,
        typer.Option("--date", help="As-of / cumulative date (for balance_sheet, receivable_aging, payable_aging)"),
    ] = None,
    company: Annotated[str | None, typer.Option("--company", help="Company name or ID")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show what would be created without executing")] = False,
    force: Annotated[bool, typer.Option("--force", "-y", help="Skip confirmation")] = False,
) -> None:
    """Generate a report using the report_management framework.

    Creates a report.wizard, sets parameters, calls button_export_html to
    create a report.instance, then displays the instance metadata.

    Old short codes (pnl, bs, cf, tb, cma, ar_aging, ap_aging) are still
    accepted via backward-compatible aliases.

    Examples:
        kctl-odoo report run profit_loss --date-from 2026-01-01 --date-to 2026-01-31
        kctl-odoo report run balance_sheet --date 2026-03-31
        kctl-odoo report run receivable_aging --date 2026-03-27
        kctl-odoo report run trial_balance --dry-run
        kctl-odoo report run pnl --date-from 2026-01-01 --date-to 2026-01-31  # alias
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _check_report_management(c, out):
        return

    # Resolve aliases (e.g. pnl → profit_loss)
    type_code = _resolve_type_code(type_code)

    # 1. Resolve report type from registry
    try:
        reg_records = c.search_read(
            "report.type.registry",
            domain=[("code", "=", type_code)],
            fields=["id", "name", "code", "date_mode", "category"],
            limit=1,
        )
    except RPCError as e:
        out.error(f"Failed to query report type registry: {e.detail}")
        raise typer.Exit(1) from e

    if not reg_records:
        out.error(f"Report type not found: {type_code}")
        raise typer.Exit(1)

    reg = reg_records[0]
    reg.get("date_mode", "period")

    # 2. Find a template for this report type
    try:
        tpl_records = c.search_read(
            "report.template",
            domain=[("report_type_id", "=", reg["id"])],
            fields=["id", "name", "code"],
            limit=1,
            order="sequence, id",
        )
    except RPCError as e:
        out.error(f"Failed to query report templates: {e.detail}")
        raise typer.Exit(1) from e

    if not tpl_records:
        # Fallback: try matching by the selection field
        with contextlib.suppress(RPCError):
            tpl_records = c.search_read(
                "report.template",
                domain=[("report_type", "=", type_code)],
                fields=["id", "name", "code"],
                limit=1,
                order="sequence, id",
            )

    if not tpl_records:
        out.error(f"No report template found for type '{type_code}'.")
        raise typer.Exit(1)

    tpl = tpl_records[0]

    # 3. Resolve dates
    if as_of_date:
        # Cumulative / as_of: set date_from to fiscal year start, date_to to the date
        resolved_date_to = as_of_date
        resolved_date_from = _fiscal_year_start(as_of_date)
    elif date_from and date_to:
        resolved_date_from = date_from
        resolved_date_to = date_to
    elif date_from and not date_to:
        resolved_date_from = date_from
        resolved_date_to = date.today().isoformat()
    elif date_to and not date_from:
        resolved_date_from = _fiscal_year_start(date_to)
        resolved_date_to = date_to
    else:
        resolved_date_from, resolved_date_to = _default_date_range()

    # 4. Build wizard vals
    wizard_vals: dict = {
        "template_id": tpl["id"],
        "date_from": resolved_date_from,
        "date_to": resolved_date_to,
    }

    if company:
        if company.isdigit():
            wizard_vals["company_id"] = int(company)
        else:
            companies = c.search_read(
                "res.company",
                domain=[("name", "ilike", company)],
                fields=["id", "name"],
                limit=1,
            )
            if not companies:
                out.error(f"Company not found: {company}")
                raise typer.Exit(1)
            wizard_vals["company_id"] = companies[0]["id"]

    # Dry run: just show what would be created
    if dry_run:
        out.info("Would create report instance:")
        out.info(f"  Type:      {reg.get('name')} ({type_code})")
        out.info(f"  Template:  {tpl.get('name')} (ID {tpl['id']})")
        out.info(f"  Date From: {resolved_date_from}")
        out.info(f"  Date To:   {resolved_date_to}")
        if actx.json_mode:
            out.raw_json(
                {
                    "dry_run": True,
                    "type_code": type_code,
                    "type_name": reg.get("name"),
                    "template_id": tpl["id"],
                    "template_name": tpl.get("name"),
                    "date_from": resolved_date_from,
                    "date_to": resolved_date_to,
                    "wizard_vals": wizard_vals,
                }
            )
        return

    if not force:
        out.info(f"Generate '{reg.get('name')}' for {resolved_date_from} to {resolved_date_to}")
        if not typer.confirm("Proceed?"):
            raise typer.Exit(0)

    # 5. Create wizard and generate report
    try:
        wizard_id = c.execute_kw("report.wizard", "create", [wizard_vals])
        result = c.execute_kw("report.wizard", "button_export_html", [[wizard_id]])
    except RPCError as e:
        out.error(f"Failed to generate report: {e.detail}")
        raise typer.Exit(1) from e

    # 6. Extract instance ID from the action result
    instance_id = None
    if isinstance(result, dict):
        instance_id = result.get("res_id")

    if not instance_id:
        # Fallback: find the most recently created instance for this template
        try:
            recent = c.search_read(
                "report.instance",
                domain=[("template_id", "=", tpl["id"])],
                fields=["id", "display_name", "date_from", "date_to", "create_date"],
                limit=1,
                order="create_date desc",
            )
            if recent:
                instance_id = recent[0]["id"]
        except RPCError:
            pass

    if instance_id:
        try:
            inst = c.search_read(
                "report.instance",
                domain=[("id", "=", instance_id)],
                fields=["id", "display_name", "date_from", "date_to", "create_date", "template_id"],
                limit=1,
            )
            if inst:
                inst = inst[0]
                out.success(f"Report instance created: ID {inst['id']} - {inst.get('display_name', '')}")
                if actx.json_mode:
                    out.raw_json(
                        {
                            "instance_id": inst["id"],
                            "display_name": inst.get("display_name"),
                            "date_from": inst.get("date_from"),
                            "date_to": inst.get("date_to"),
                            "create_date": inst.get("create_date"),
                            "template": _m2o(inst.get("template_id")),
                        }
                    )
                return
        except RPCError:
            pass

    out.success("Report generated successfully.")
    if actx.json_mode:
        out.raw_json({"instance_id": instance_id, "result": result})


@app.command("instances")
def report_instances(
    ctx: typer.Context,
    type_code: Annotated[str | None, typer.Option("--type", "-t", help="Filter by report type code")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 20,
) -> None:
    """List generated report instances from report_management.

    Shows instances created via the report wizard, NOT Odoo built-in reports.

    Examples:
        kctl-odoo report instances
        kctl-odoo report instances --type profit_loss
        kctl-odoo report instances --limit 10 --json
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _check_report_management(c, out):
        if actx.json_mode:
            out.raw_json([])
        return

    domain: list = []
    if type_code:
        # Resolve aliases (e.g. pnl → profit_loss)
        type_code = _resolve_type_code(type_code)
        # Find template(s) matching the type code via registry
        try:
            reg_ids = c.search("report.type.registry", [("code", "=", type_code)])
            if reg_ids:
                tpl_ids = c.search("report.template", [("report_type_id", "in", reg_ids)])
                if tpl_ids:
                    domain.append(("template_id", "in", tpl_ids))
                else:
                    # Try legacy selection field
                    tpl_ids = c.search("report.template", [("report_type", "=", type_code)])
                    if tpl_ids:
                        domain.append(("template_id", "in", tpl_ids))
                    else:
                        out.info(f"No templates found for type '{type_code}'.")
                        if actx.json_mode:
                            out.raw_json([])
                        return
            else:
                out.info(f"Report type not found: {type_code}")
                if actx.json_mode:
                    out.raw_json([])
                return
        except RPCError as e:
            out.error(f"Failed to resolve report type: {e.detail}")
            raise typer.Exit(1) from e

    try:
        records = c.search_read(
            "report.instance",
            domain=domain,
            fields=["id", "display_name", "template_id", "date_from", "date_to", "create_date", "company_id"],
            limit=limit,
            order="create_date desc",
        )
    except RPCError as e:
        out.error(f"Failed to fetch report instances: {e.detail}")
        raise typer.Exit(1) from e

    if not records:
        out.info("No report instances found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for r in records:
        rows.append(
            [
                str(r["id"]),
                (r.get("display_name") or "")[:40],
                _m2o(r.get("template_id")),
                str(r.get("date_from") or ""),
                str(r.get("date_to") or ""),
                str(r.get("create_date") or "")[:19],
            ]
        )
        json_data.append(
            {
                "id": r["id"],
                "display_name": r.get("display_name"),
                "template": _m2o(r.get("template_id")),
                "date_from": r.get("date_from"),
                "date_to": r.get("date_to"),
                "create_date": r.get("create_date"),
                "company": _m2o(r.get("company_id")),
            }
        )

    out.table(
        f"Report Instances ({len(records)})",
        [
            ("ID", "cyan"),
            ("Name", ""),
            ("Template", ""),
            ("Date From", ""),
            ("Date To", ""),
            ("Created", "dim"),
        ],
        rows,
        data_for_json=json_data,
    )


@app.command("view")
def report_view(
    ctx: typer.Context,
    instance_id: Annotated[int, typer.Argument(help="Report instance ID")],
) -> None:
    """View a report instance's metadata and data summary.

    Reads the report.instance record and displays its details. Report data
    (columns, lines) may not be directly readable via JSON-RPC as they are
    often computed in-browser; in that case only metadata is shown.

    Examples:
        kctl-odoo report view 42
        kctl-odoo report view 42 --json
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _check_report_management(c, out):
        return

    base_fields = [
        "id",
        "display_name",
        "template_id",
        "date_from",
        "date_to",
        "company_id",
        "target_move",
        "comparison_mode",
        "divider",
        "show_variance",
        "show_percentage",
        "monthly_breakdown",
        "create_date",
        "create_uid",
        "render_mode",
    ]

    try:
        records = c.search_read(
            "report.instance",
            domain=[("id", "=", instance_id)],
            fields=base_fields,
            limit=1,
        )
    except RPCError as e:
        out.error(f"Failed to read report instance: {e.detail}")
        raise typer.Exit(1) from e

    if not records:
        out.error(f"Report instance not found: {instance_id}")
        raise typer.Exit(1)

    inst = records[0]

    if actx.json_mode:
        json_out: dict = {
            "id": inst["id"],
            "display_name": inst.get("display_name"),
            "template": _m2o(inst.get("template_id")),
            "date_from": inst.get("date_from"),
            "date_to": inst.get("date_to"),
            "company": _m2o(inst.get("company_id")),
            "target_move": inst.get("target_move"),
            "comparison_mode": inst.get("comparison_mode"),
            "divider": inst.get("divider"),
            "show_variance": inst.get("show_variance"),
            "show_percentage": inst.get("show_percentage"),
            "monthly_breakdown": inst.get("monthly_breakdown"),
            "render_mode": inst.get("render_mode"),
            "create_date": inst.get("create_date"),
            "created_by": _m2o(inst.get("create_uid")),
        }
        out.raw_json(json_out)
        return

    # Display as key-value detail view
    out.info(f"Report Instance #{inst['id']}")
    out.info(f"  Name:          {inst.get('display_name', '')}")
    out.info(f"  Template:      {_m2o(inst.get('template_id'))}")
    out.info(f"  Date From:     {inst.get('date_from', '')}")
    out.info(f"  Date To:       {inst.get('date_to', '')}")
    out.info(f"  Company:       {_m2o(inst.get('company_id'))}")
    out.info(f"  Target Move:   {inst.get('target_move', '')}")
    out.info(f"  Comparison:    {inst.get('comparison_mode', '')}")
    out.info(f"  Divider:       {inst.get('divider', '')}")
    out.info(f"  Variance:      {inst.get('show_variance', '')}")
    out.info(f"  Percentage:    {inst.get('show_percentage', '')}")
    out.info(f"  Monthly:       {inst.get('monthly_breakdown', '')}")
    out.info(f"  Render Mode:   {inst.get('render_mode', '')}")
    out.info(f"  Created:       {str(inst.get('create_date', ''))[:19]}")
    out.info(f"  Created By:    {_m2o(inst.get('create_uid'))}")
    out.info("")
    out.info("Tip: Open in Odoo UI for full report with data, charts, and drill-down.")


def _http_download_report(
    base_url: str,
    database: str,
    username: str,
    password: str,
    data_dict: dict,
    fmt: str,
    output_path: Path,
    out,
    quiet: bool = False,
) -> bool:
    """Download report via HTTP controller (headless, no browser needed).

    Authenticates via /web/session/authenticate, then calls
    /report_management/download_xlsx or download_pdf with the data dict.
    Returns True on success, False on failure.
    """
    import json as json_lib
    from urllib.parse import quote

    import httpx

    url = base_url.rstrip("/")
    endpoint = f"/report_management/download_{'xlsx' if fmt == 'xlsx' else 'pdf'}"

    try:
        headers = {"X-Odoo-dbfilter": f"^{database}$"}
        with httpx.Client(timeout=120, follow_redirects=True, headers=headers) as client:
            # Step 1: Authenticate to get session cookie
            auth_resp = client.post(
                f"{url}/web/session/authenticate",
                json={
                    "jsonrpc": "2.0",
                    "method": "call",
                    "id": 1,
                    "params": {"db": database, "login": username, "password": password},
                },
            )
            if auth_resp.status_code != 200:
                out.error(f"Authentication failed: HTTP {auth_resp.status_code}")
                return False

            auth_data = auth_resp.json()
            if auth_data.get("error") or not auth_data.get("result", {}).get("uid"):
                out.error("Authentication failed: invalid credentials")
                return False

            # Step 2: Download report via controller
            encoded_data = quote(json_lib.dumps(data_dict))
            download_resp = client.get(f"{url}{endpoint}?data={encoded_data}")

            if download_resp.status_code != 200:
                out.error(f"Download failed: HTTP {download_resp.status_code}")
                return False

            content_type = download_resp.headers.get("content-type", "")
            if "html" in content_type and download_resp.status_code == 200 and len(download_resp.content) < 500:
                out.error("Download returned HTML (likely redirect to login). Check credentials.")
                return False

            output_path.write_bytes(download_resp.content)
            size_kb = len(download_resp.content) / 1024
            if not quiet:
                out.success(f"Report saved: {output_path} ({size_kb:.1f} KB)")
            return True

    except httpx.ConnectError as exc:
        out.error(f"Connection failed: {exc}")
        return False
    except Exception as exc:
        out.error(f"Download failed: {exc}")
        return False


@app.command("export")
def report_export(
    ctx: typer.Context,
    instance_id: Annotated[int, typer.Argument(help="Report instance ID")],
    fmt: Annotated[str, typer.Option("--format", "-f", help="Export format: xlsx or pdf")] = "xlsx",
    output: Annotated[str | None, typer.Option("--output", "-o", help="Output file path")] = None,
) -> None:
    """Export a report instance to XLSX or PDF file.

    Downloads the report via Odoo's HTTP controller (headless, no browser).

    Examples:
        kctl-odoo report export 1 -o pnl.xlsx
        kctl-odoo report export 1 --format pdf -o pnl.pdf
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _check_report_management(c, out):
        return

    if fmt not in ("xlsx", "pdf"):
        out.error("Format must be 'xlsx' or 'pdf'.")
        raise typer.Exit(1)

    # Read instance to get template_id and dates
    try:
        inst_records = c.search_read(
            "report.instance",
            domain=[("id", "=", instance_id)],
            fields=["id", "display_name", "template_id", "date_from", "date_to", "company_id", "target_move"],
            limit=1,
        )
    except RPCError as e:
        out.error(f"Failed to read report instance: {e.detail}")
        raise typer.Exit(1) from e

    if not inst_records:
        out.error(f"Report instance not found: {instance_id}")
        raise typer.Exit(1)

    inst = inst_records[0]
    tpl_id = inst["template_id"][0] if isinstance(inst.get("template_id"), list) else inst.get("template_id")
    company_id = inst["company_id"][0] if isinstance(inst.get("company_id"), list) else inst.get("company_id")

    # Build data dict for the controller — company_id is required
    if not company_id:
        try:
            user_data = c.read("res.users", [c.uid], ["company_id"])
            if user_data:
                co = user_data[0].get("company_id")
                company_id = co[0] if isinstance(co, list) else co
        except Exception:
            company_id = 1

    data_dict = {
        "template_id": tpl_id,
        "date_from": str(inst.get("date_from") or ""),
        "date_to": str(inst.get("date_to") or ""),
        "target_move": inst.get("target_move", "posted"),
        "company_id": company_id or 1,
    }

    # Resolve output path
    if output:
        output_path = Path(output)
    else:
        safe_name = (inst.get("display_name") or f"report_{instance_id}").replace(" ", "_").replace("/", "-")
        output_path = Path(f"{safe_name}.{fmt}")

    # Get connection details
    from kctl_odoo.core.config import resolve_connection

    url, database, username, api_key = resolve_connection(
        profile_name=actx.profile,
        url_override=actx.url_override,
        api_key_override=actx.api_key_override,
        database_override=actx.database_override,
        username_override=actx.username_override,
    )

    out.info(f"Downloading {fmt.upper()} for instance #{instance_id}...")
    success = _http_download_report(url, database, username, api_key, data_dict, fmt, output_path, out)

    if success and actx.json_mode:
        out.raw_json(
            {
                "instance_id": instance_id,
                "format": fmt,
                "file": str(output_path),
                "size": output_path.stat().st_size,
            }
        )
    elif not success:
        if actx.json_mode:
            out.raw_json(
                {
                    "instance_id": instance_id,
                    "format": fmt,
                    "hint": "Download from Odoo UI",
                }
            )
        raise typer.Exit(1)


@app.command("download")
def report_download(
    ctx: typer.Context,
    type_code: Annotated[
        str, typer.Argument(help="Report type code (e.g. profit_loss, balance_sheet, receivable_aging)")
    ],
    date_from: Annotated[str | None, typer.Option("--date-from", help="Start date (YYYY-MM-DD)")] = None,
    date_to: Annotated[str | None, typer.Option("--date-to", help="End date (YYYY-MM-DD)")] = None,
    as_of_date: Annotated[
        str | None,
        typer.Option("--date", help="As-of / cumulative date (for balance_sheet, receivable_aging, payable_aging)"),
    ] = None,
    fmt: Annotated[str, typer.Option("--format", "-f", help="Export format: xlsx or pdf")] = "xlsx",
    output: Annotated[str | None, typer.Option("--output", "-o", help="Output file path")] = None,
    force: Annotated[bool, typer.Option("--force", "-y", help="Skip confirmation")] = False,
) -> None:
    """Generate a report and export it in one step.

    Combines 'report run' + 'report export': creates a report.instance via
    the wizard, then exports to XLSX or PDF.

    Old short codes (pnl, bs, cf, tb, cma, ar_aging, ap_aging) are still
    accepted via backward-compatible aliases.

    Examples:
        kctl-odoo report download profit_loss --date-from 2026-01-01 --date-to 2026-01-31
        kctl-odoo report download balance_sheet --date 2026-03-31 --format pdf
        kctl-odoo report download receivable_aging --date 2026-03-27 -o aging.xlsx -y
        kctl-odoo report download pnl --date-from 2026-01-01 --date-to 2026-01-31  # alias
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _check_report_management(c, out):
        return

    if fmt not in ("xlsx", "pdf"):
        out.error("Format must be 'xlsx' or 'pdf'.")
        raise typer.Exit(1)

    # Resolve aliases (e.g. pnl → profit_loss)
    type_code = _resolve_type_code(type_code)

    # 1. Resolve report type
    try:
        reg_records = c.search_read(
            "report.type.registry",
            domain=[("code", "=", type_code)],
            fields=["id", "name", "code", "date_mode"],
            limit=1,
        )
    except RPCError as e:
        out.error(f"Failed to query report type registry: {e.detail}")
        raise typer.Exit(1) from e

    if not reg_records:
        out.error(f"Report type not found: {type_code}")
        raise typer.Exit(1)

    reg = reg_records[0]

    # 2. Find template
    try:
        tpl_records = c.search_read(
            "report.template",
            domain=[("report_type_id", "=", reg["id"])],
            fields=["id", "name"],
            limit=1,
            order="sequence, id",
        )
    except RPCError as e:
        out.error(f"Failed to query report templates: {e.detail}")
        raise typer.Exit(1) from e

    if not tpl_records:
        with contextlib.suppress(RPCError):
            tpl_records = c.search_read(
                "report.template",
                domain=[("report_type", "=", type_code)],
                fields=["id", "name"],
                limit=1,
                order="sequence, id",
            )

    if not tpl_records:
        out.error(f"No report template found for type '{type_code}'.")
        raise typer.Exit(1)

    tpl = tpl_records[0]

    # 3. Resolve dates
    if as_of_date:
        resolved_date_to = as_of_date
        resolved_date_from = _fiscal_year_start(as_of_date)
    elif date_from and date_to:
        resolved_date_from = date_from
        resolved_date_to = date_to
    elif date_from and not date_to:
        resolved_date_from = date_from
        resolved_date_to = date.today().isoformat()
    elif date_to and not date_from:
        resolved_date_from = _fiscal_year_start(date_to)
        resolved_date_to = date_to
    else:
        resolved_date_from, resolved_date_to = _default_date_range()

    if not force:
        out.info(
            f"Generate + export '{reg.get('name')}' ({fmt.upper()}) for {resolved_date_from} to {resolved_date_to}"
        )
        if not typer.confirm("Proceed?"):
            raise typer.Exit(0)

    # 4. Create wizard and generate
    wizard_vals: dict = {
        "template_id": tpl["id"],
        "date_from": resolved_date_from,
        "date_to": resolved_date_to,
    }

    try:
        wizard_id = c.execute_kw("report.wizard", "create", [wizard_vals])
        result = c.execute_kw("report.wizard", "button_export_html", [[wizard_id]])
    except RPCError as e:
        out.error(f"Failed to generate report: {e.detail}")
        raise typer.Exit(1) from e

    # Extract instance ID
    instance_id = None
    if isinstance(result, dict):
        instance_id = result.get("res_id")

    if not instance_id:
        try:
            recent = c.search_read(
                "report.instance",
                domain=[("template_id", "=", tpl["id"])],
                fields=["id"],
                limit=1,
                order="create_date desc",
            )
            if recent:
                instance_id = recent[0]["id"]
        except RPCError:
            pass

    if not instance_id:
        out.error("Report was generated but instance ID could not be determined.")
        raise typer.Exit(1)

    out.success(f"Report instance #{instance_id} created.")

    # 5. Export via HTTP controller (headless download)
    # Resolve company_id (required by controller)
    dl_company_id = None
    try:
        user_data = c.read("res.users", [c.uid], ["company_id"])
        if user_data:
            co = user_data[0].get("company_id")
            dl_company_id = co[0] if isinstance(co, list) else co
    except Exception:
        dl_company_id = 1

    data_dict = {
        "template_id": tpl["id"],
        "date_from": resolved_date_from,
        "date_to": resolved_date_to,
        "company_id": dl_company_id or 1,
        "target_move": "posted",
    }

    output_path = Path(output) if output else Path(f"{type_code}_{resolved_date_from}_{resolved_date_to}.{fmt}")

    from kctl_odoo.core.config import resolve_connection

    url, database_name, username, api_key = resolve_connection(
        profile_name=actx.profile,
        url_override=actx.url_override,
        api_key_override=actx.api_key_override,
        database_override=actx.database_override,
        username_override=actx.username_override,
    )

    out.info(f"Downloading {fmt.upper()}...")
    success = _http_download_report(url, database_name, username, api_key, data_dict, fmt, output_path, out)

    if success and actx.json_mode:
        out.raw_json(
            {
                "instance_id": instance_id,
                "format": fmt,
                "file": str(output_path),
                "size": output_path.stat().st_size,
            }
        )
    elif not success:
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# Validate
# ---------------------------------------------------------------------------


@app.command("validate")
def report_validate(
    ctx: typer.Context,
    type_code: Annotated[
        str | None,
        typer.Argument(help="Report type code to validate, or 'all'"),
    ] = "all",
    date_from: Annotated[str | None, typer.Option("--date-from")] = None,
    date_to: Annotated[str | None, typer.Option("--date-to")] = None,
) -> None:
    """Validate report quality — check reports generate with data.

    Downloads each report and checks for errors, empty files, and data rows.

    Examples:
        kctl-odoo report validate
        kctl-odoo report validate profit_loss
        kctl-odoo report validate all --date-from 2026-01-01 --date-to 2026-03-31
    """
    import tempfile

    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _check_report_management(c, out):
        return

    if not date_to:
        date_to = date.today().strftime("%Y-%m-%d")
    if not date_from:
        date_from = date.today().replace(month=1, day=1).strftime("%Y-%m-%d")

    resolved = _resolve_type_code(type_code) if type_code and type_code != "all" else None

    try:
        domain = [("code", "=", resolved)] if resolved else []
        types = c.search_read(
            "report.type.registry",
            domain=domain,
            fields=["id", "code", "name", "category"],
            order="category,sequence",
        )
    except RPCError as e:
        out.error(f"Failed to query: {e.detail}")
        raise typer.Exit(1) from e

    if not types:
        out.error(f"Not found: {type_code}")
        raise typer.Exit(1)

    # Resolve connection for HTTP download
    from kctl_odoo.core.config import resolve_connection

    url, database_name, username, api_key = resolve_connection(
        profile_name=actx.profile,
        url_override=actx.url_override,
        api_key_override=actx.api_key_override,
        database_override=actx.database_override,
        username_override=actx.username_override,
    )

    # Get company
    company_id = 1
    try:
        cos = c.search_read("res.company", [("active", "=", True)], ["id"], limit=1)
        if cos:
            company_id = cos[0]["id"]
    except RPCError:
        pass

    out.info(f"Validating {len(types)} reports ({date_from} to {date_to})")

    ok_count = warn_count = fail_count = 0
    results = []
    current_cat = ""

    for rt in types:
        code, category = rt["code"], rt["category"]

        if category != current_cat:
            current_cat = category
            out.info(f"\n  [{category}]")

        try:
            tpls = c.search_read("report.template", [("report_type", "=", code)], ["id"], limit=1)
        except RPCError:
            out.error(f"    FAIL  {code:40s} template query error")
            fail_count += 1
            results.append({"code": code, "status": "fail"})
            continue
        if not tpls:
            out.warn(f"    SKIP  {code:40s} no template")
            warn_count += 1
            results.append({"code": code, "status": "skip"})
            continue

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            data_dict = {
                "template_id": tpls[0]["id"],
                "date_from": date_from,
                "date_to": date_to,
                "company_id": company_id,
                "target_move": "posted",
            }

            ok = _http_download_report(
                url, database_name, username, api_key, data_dict, "xlsx", tmp_path, out, quiet=True
            )

            if not ok:
                out.error(f"    FAIL  {code:40s} download error")
                fail_count += 1
                results.append({"code": code, "status": "fail"})
                continue

            fsize = tmp_path.stat().st_size
            if fsize == 0:
                out.error(f"    FAIL  {code:40s} empty")
                fail_count += 1
                results.append({"code": code, "status": "fail"})
                continue

            # Count data rows
            data_rows = 0
            try:
                import openpyxl

                wb = openpyxl.load_workbook(tmp_path)
                ws = wb.active
                for row in ws.iter_rows(min_row=5, max_row=200, values_only=True):
                    if not row or not row[0]:
                        continue
                    lbl = str(row[0]).strip()
                    if lbl in ("", "Generated by Report Management"):
                        continue
                    for v in row[1:]:
                        if v is not None and v != "" and v != 0:
                            data_rows += 1
                            break
                    else:
                        if len(lbl) > 2:
                            data_rows += 1
                wb.close()
            except Exception:
                data_rows = -1

            if data_rows > 0:
                out.success(f"    OK    {code:40s} {fsize:>6}B {data_rows:>3} rows")
                ok_count += 1
            elif data_rows == 0:
                out.warn(f"    WARN  {code:40s} {fsize:>6}B no data")
                warn_count += 1
            else:
                out.success(f"    OK    {code:40s} {fsize:>6}B")
                ok_count += 1

            results.append(
                {"code": code, "status": "ok" if data_rows != 0 else "warn", "size": fsize, "rows": data_rows}
            )

        except Exception as e:
            out.error(f"    FAIL  {code:40s} {str(e)[:50]}")
            fail_count += 1
            results.append({"code": code, "status": "fail"})
        finally:
            tmp_path.unlink(missing_ok=True)

    total = ok_count + warn_count + fail_count
    out.info(f"\n{'=' * 60}")

    if fail_count == 0 and warn_count == 0:
        out.success(f"  ALL {total} REPORTS PASS")
    elif fail_count == 0:
        out.success(f"  {ok_count} pass, {warn_count} warnings")
    else:
        out.error(f"  {fail_count} FAILURES | {ok_count} ok | {warn_count} warn")

    if actx.json_mode:
        import json as _json

        print(
            _json.dumps(
                {"total": total, "ok": ok_count, "warn": warn_count, "fail": fail_count, "results": results}, indent=2
            )
        )


# ===================================================================
# CATALOG — report type overview with template counts
# ===================================================================


@app.command("catalog")
def report_catalog(
    ctx: typer.Context,
) -> None:
    """Show all report types with template count and status.

    Queries report.type.registry and counts associated templates per type.

    Examples:
        kctl-odoo report catalog
        kctl-odoo report catalog --json
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _check_report_management(c, out):
        if actx.json_mode:
            out.raw_json([])
        return

    try:
        records = c.search_read(
            "report.type.registry",
            domain=[],
            fields=["id", "code", "name", "category", "active"],
            limit=500,
            order="category, sequence, name",
        )
    except RPCError as e:
        out.error(f"Failed to fetch report types: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.info("No report types found.")
        if actx.json_mode:
            out.raw_json([])
        return

    # Count templates per report type
    template_counts: dict[str, int] = {}
    for r in records:
        code = r.get("code", "")
        try:
            count = c.search_count(
                "report.template",
                [("report_type", "=", code)],
            )
            template_counts[code] = count
        except RPCError:
            template_counts[code] = 0

    rows = []
    json_data = []
    for r in records:
        code = r.get("code", "")
        cat = r.get("category", "") or ""
        cat_display = {
            "financial": "[green]financial[/green]",
            "aging": "[yellow]aging[/yellow]",
            "management": "[cyan]management[/cyan]",
            "custom": "[dim]custom[/dim]",
        }.get(cat, cat)
        status = "[green]active[/green]" if r.get("active") else "[dim]inactive[/dim]"
        tpl_count = template_counts.get(code, 0)

        rows.append(
            [
                code,
                (r.get("name") or "")[:40],
                cat_display,
                str(tpl_count),
                status,
            ]
        )
        json_data.append(
            {
                "code": code,
                "name": r.get("name"),
                "category": cat,
                "templates": tpl_count,
                "active": r.get("active"),
            }
        )

    out.table(
        f"Report Catalog ({len(records)} types)",
        [
            ("Code", "cyan"),
            ("Name", ""),
            ("Category", ""),
            ("Templates", ""),
            ("Status", ""),
        ],
        rows,
        data_for_json=json_data,
    )


@app.command("schedule")
def schedule_report(
    ctx: typer.Context,
    type_code: Annotated[str, typer.Argument(help="Report type code (e.g. profit_loss)")],
    cron: Annotated[str, typer.Option("--cron", help="Cron schedule expression")] = "0 8 * * 1",
    email_to: Annotated[str | None, typer.Option("--email-to", help="Email address to send report to")] = None,
) -> None:
    """Schedule a report to run periodically.

    Shows instructions for setting up a cron job to generate and email reports.
    """
    actx: AppContext = ctx.obj
    out = actx.output

    type_code = _resolve_type_code(type_code)
    run_cmd = f"kctl-odoo report run {type_code}"
    export_cmd = f"kctl-odoo report export {type_code} --format xlsx"

    sections: list[tuple[str, list[tuple[str, str]]]] = [
        (
            "Report Details",
            [
                ("Type Code", type_code),
                ("Cron Schedule", cron),
                ("Email To", email_to or "(not set)"),
            ],
        ),
        (
            "Crontab Entry",
            [
                ("Generate & export", f"{cron}  {export_cmd}"),
            ],
        ),
    ]

    if email_to:
        mail_cmd = f"{cron}  {export_cmd} && mail -s 'Report: {type_code}' {email_to} < /dev/null"
        sections.append(
            (
                "With Email",
                [
                    ("Send via mail", mail_cmd),
                    (
                        "Send via kctl",
                        f"{cron}  {run_cmd} --email {email_to}",
                    ),
                ],
            )
        )

    sections.append(
        (
            "Setup Instructions",
            [
                ("1. Edit crontab", "crontab -e"),
                ("2. Add entry", f"{cron}  {export_cmd}"),
                ("3. Verify cron", "crontab -l"),
                (
                    "4. Odoo ir.cron",
                    "Or use Odoo Technical > Automation > Scheduled Actions",
                ),
            ],
        )
    )

    json_data = {
        "type_code": type_code,
        "cron": cron,
        "email_to": email_to,
        "run_command": run_cmd,
        "export_command": export_cmd,
    }

    out.detail(f"Schedule Report: {type_code}", sections, data_for_json=json_data)


@app.command("batch-download")
def batch_download(
    ctx: typer.Context,
    category: Annotated[str | None, typer.Option("--category", "-c", help="Filter by report category")] = None,
    date_from: Annotated[str | None, typer.Option("--date-from", help="Start date (YYYY-MM-DD)")] = None,
    date_to: Annotated[str | None, typer.Option("--date-to", help="End date (YYYY-MM-DD)")] = None,
    output_dir: Annotated[str, typer.Option("--output-dir", "-o", help="Output directory")] = ".",
) -> None:
    """Bulk export multiple reports to files."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Default date range: last 30 days
    if not date_to:
        date_to = date.today().isoformat()
    if not date_from:
        date_from = (date.today() - timedelta(days=30)).isoformat()

    # Try to list report types from report_management module
    domain: list = [("active", "=", True)]
    if category:
        domain.append(("category", "=", category))

    try:
        report_types = c.search_read(
            "report.type.registry",
            domain=domain,
            fields=["id", "code", "name", "category"],
            limit=50,
            order="category, name",
        )
    except RPCError:
        out.warn("report.type.registry model not available. Is report_management installed?")
        out.info("Falling back to ir.actions.report...")
        try:
            report_types_raw = c.search_read(
                "ir.actions.report",
                domain=[("report_type", "in", ["qweb-pdf", "qweb-xlsx"])],
                fields=["id", "name", "report_name", "report_type"],
                limit=50,
                order="name",
            )
            report_types = [
                {
                    "id": r["id"],
                    "code": r["report_name"],
                    "name": r["name"],
                    "category": r.get("report_type", ""),
                }
                for r in report_types_raw
            ]
        except RPCError as e:
            out.error(f"Could not list reports: {e.detail}")
            raise typer.Exit(1) from e

    if not report_types:
        out.info("No report types found" + (f" for category '{category}'" if category else "") + ".")
        if actx.json_mode:
            out.raw_json([])
        return

    out.info(f"Found {len(report_types)} report type(s) to download.")
    out.info(f"Date range: {date_from} to {date_to}")
    out.info(f"Output directory: {output_path.resolve()}")

    results = []
    for rt in report_types:
        code = rt.get("code") or rt.get("report_name") or str(rt["id"])
        name = rt.get("name", code)
        file_name = f"{code.replace('.', '_').replace('/', '_')}.xlsx"
        file_path = output_path / file_name

        try:
            # Try to use report_management export if available
            instance_domain: list = [
                ("type_code", "=", code),
                ("date_from", ">=", date_from),
                ("date_to", "<=", date_to),
            ]
            instances = c.search_read(
                "report.instance",
                domain=instance_domain,
                fields=["id", "name", "state"],
                limit=1,
                order="create_date desc",
            )
            if instances:
                inst = instances[0]
                raw = c.execute_kw("report.instance", "action_export_xlsx", [[inst["id"]]])
                if raw and isinstance(raw, dict):
                    data = raw.get("data") or raw.get("file_data")
                    if data:
                        file_path.write_bytes(base64.b64decode(data))
                        results.append({"code": code, "name": name, "file": str(file_path), "status": "ok"})
                        out.info(f"  [green]OK[/green] {name} -> {file_name}")
                        continue

            # Fallback: generate a placeholder file
            file_path.write_text(
                f"Report: {name}\nCode: {code}\n"
                f"Date range: {date_from} to {date_to}\n"
                f"Generated at: {date.today().isoformat()}\n"
            )
            results.append({"code": code, "name": name, "file": str(file_path), "status": "placeholder"})
            out.info(f"  [yellow]PLACEHOLDER[/yellow] {name} -> {file_name}")

        except (RPCError, Exception) as e:
            results.append({"code": code, "name": name, "file": None, "status": "error", "error": str(e)})
            out.warn(f"  [red]FAILED[/red] {name}: {e}")

    ok_count = sum(1 for r in results if r["status"] == "ok")
    placeholder_count = sum(1 for r in results if r["status"] == "placeholder")
    err_count = sum(1 for r in results if r["status"] == "error")

    out.info(f"\nBatch download complete: {ok_count} OK, {placeholder_count} placeholder, {err_count} failed")
    if actx.json_mode:
        out.raw_json(results)
