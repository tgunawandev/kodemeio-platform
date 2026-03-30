"""Data quality: duplicates, completeness, orphans."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.exceptions import RPCError

app = typer.Typer(help="Data quality: duplicates, completeness, orphans.")


def _m2o_name(val):
    if isinstance(val, list):
        return str(val[1])
    return str(val or "-")


@app.command("duplicates")
def duplicates(
    ctx: typer.Context,
    model: Annotated[str, typer.Argument(help="Model to check (e.g. res.partner)")],
    field: Annotated[str, typer.Option("--field", "-f", help="Field to group by for duplicate detection")] = "name",
    limit: Annotated[int, typer.Option("--limit", "-l", help="Maximum duplicate groups to show")] = 50,
) -> None:
    """Find duplicate records grouped by a field.

    Uses read_group to detect records sharing the same field value.

    Examples:
        kctl-odoo data-quality duplicates res.partner
        kctl-odoo data-quality duplicates res.partner --field email
        kctl-odoo data-quality duplicates product.template --field name --limit 20
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    try:
        groups = c.execute_kw(
            model,
            "read_group",
            [[], [field], [field]],
            {"orderby": f"{field}_count desc", "limit": limit + 10},
        )
    except RPCError as e:
        out.error(f"Failed to read_group on '{model}' by '{field}': {e}")
        raise typer.Exit(1) from e
    except Exception as e:
        out.error(f"Unexpected error reading '{model}': {e}")
        raise typer.Exit(1) from e

    count_key = f"{field}_count"
    dups = [g for g in groups if g.get(count_key, 0) > 1]
    dups = dups[:limit]

    if not dups:
        out.success(f"No duplicates found in '{model}' by field '{field}'.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    result_data = []
    for g in dups:
        field_val = g.get(field)
        if isinstance(field_val, list):
            display_val = str(field_val[1])
        elif field_val is False or field_val is None:
            display_val = "(empty)"
        else:
            display_val = str(field_val)
        count = g.get(count_key, 0)
        rows.append([display_val[:60], str(count)])
        result_data.append({"value": display_val, "count": count})

    out.table(
        f"Duplicates in {model} by {field} ({len(dups)} groups)",
        [("Value", "cyan"), ("Count", "red")],
        rows,
        data_for_json=result_data,
    )

    if actx.json_mode:
        out.raw_json(result_data)


@app.command("completeness")
def completeness(
    ctx: typer.Context,
    model: Annotated[str, typer.Argument(help="Model to check (e.g. res.partner)")],
    fields: Annotated[str | None, typer.Option("--fields", "-f", help="Comma-separated field names to check")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Records to sample for completeness check")] = 100,
) -> None:
    """Check field completeness (fill rates) for a model.

    Samples records and calculates what percentage of values are non-empty per field.

    Examples:
        kctl-odoo data-quality completeness res.partner
        kctl-odoo data-quality completeness res.partner --fields name,email,phone,vat
        kctl-odoo data-quality completeness product.template --limit 200
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Determine which fields to check
    if fields:
        check_fields = [f.strip() for f in fields.split(",") if f.strip()]
    else:
        # Default fields per model
        defaults: dict[str, list[str]] = {
            "res.partner": ["name", "email", "phone", "mobile", "street", "city", "zip", "country_id", "vat"],
            "product.template": ["name", "description", "categ_id", "list_price", "default_code", "barcode"],
            "product.product": ["name", "default_code", "barcode", "categ_id"],
            "hr.employee": ["name", "work_email", "job_id", "department_id", "coach_id", "parent_id"],
            "account.move": ["name", "partner_id", "invoice_date", "invoice_date_due", "ref"],
            "sale.order": ["name", "partner_id", "date_order", "user_id", "team_id"],
        }
        check_fields = defaults.get(model, ["name"])

    try:
        records = c.search_read(
            model,
            domain=[],
            fields=check_fields,
            limit=limit,
            order="id desc",
        )
    except RPCError as e:
        out.error(f"Failed to read '{model}': {e}")
        raise typer.Exit(1) from e
    except Exception as e:
        out.error(f"Unexpected error reading '{model}': {e}")
        raise typer.Exit(1) from e

    if not records:
        out.info(f"No records found in '{model}'.")
        if actx.json_mode:
            out.raw_json([])
        return

    total = len(records)
    result_data = []
    rows = []

    for field_name in check_fields:
        filled = 0
        for rec in records:
            val = rec.get(field_name)
            if val is not False and val is not None and val != "" and val != []:
                filled += 1
        pct = round(filled / total * 100, 1) if total > 0 else 0.0
        pct_str = f"{pct}%"
        # Color by fill rate
        if pct >= 90:
            pct_display = f"[green]{pct_str}[/green]"
        elif pct >= 60:
            pct_display = f"[yellow]{pct_str}[/yellow]"
        else:
            pct_display = f"[red]{pct_str}[/red]"
        rows.append([field_name, str(filled), str(total), pct_display])
        result_data.append({"field": field_name, "filled": filled, "total": total, "pct": pct})

    out.table(
        f"Field Completeness: {model} (sample: {total} records)",
        [("Field", "cyan"), ("Filled", ""), ("Total", "dim"), ("Fill Rate", "")],
        rows,
        data_for_json=result_data,
    )

    if actx.json_mode:
        out.raw_json(result_data)


@app.command("orphans")
def orphans(
    ctx: typer.Context,
    model: Annotated[str, typer.Option("--model", "-m", help="Model to check for orphans")] = "res.partner",
) -> None:
    """Check for common orphan record patterns.

    Checks for:
    - Partners with no related records (invoices, orders, etc.)
    - Products with no sales or moves
    - Custom model check per model type.

    Examples:
        kctl-odoo data-quality orphans
        kctl-odoo data-quality orphans --model product.template
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    checks: list[tuple[str, str, list]] = []

    if model == "res.partner":
        checks = [
            ("Partners with no invoices", "res.partner", [("invoice_ids", "=", False)]),
            ("Partners with no sale orders", "res.partner", [("sale_order_ids", "=", False)]),
            ("Partners with no purchase orders", "res.partner", [("purchase_order_ids", "=", False)]),
            (
                "Partners with no contacts (companies only)",
                "res.partner",
                [("is_company", "=", True), ("child_ids", "=", False)],
            ),
        ]
    elif model in ("product.template", "product.product"):
        checks = [
            (
                "Products with no sale order lines",
                "product.template",
                [("sale_ok", "=", True), ("invoice_ids", "=", False)],
            ),
            ("Products with no stock moves", "product.template", [("type", "=", "consu")]),
        ]
    elif model == "hr.employee":
        checks = [
            ("Employees with no department", "hr.employee", [("department_id", "=", False)]),
            ("Employees with no job position", "hr.employee", [("job_id", "=", False)]),
            ("Employees with no manager", "hr.employee", [("parent_id", "=", False), ("active", "=", True)]),
        ]
    else:
        # Generic: check for records with empty name
        checks = [
            (f"{model} with empty name", model, [("name", "=", False)]),
            (f"{model} with empty name (blank)", model, [("name", "=", "")]),
        ]

    rows = []
    result_data = []

    for description, check_model, domain in checks:
        try:
            count = c.search_count(check_model, domain)
            level = "[red]" if count > 0 else "[green]"
            level_end = "[/red]" if count > 0 else "[/green]"
            rows.append([description, f"{level}{count}{level_end}"])
            result_data.append({"check": description, "model": check_model, "count": count})
        except (RPCError, Exception):
            rows.append([description, "[dim]N/A[/dim]"])
            result_data.append({"check": description, "model": check_model, "count": -1})

    out.table(
        f"Orphan Check: {model}",
        [("Check", "cyan"), ("Count", "")],
        rows,
        data_for_json=result_data,
    )

    if actx.json_mode:
        out.raw_json(result_data)


@app.command("validate")
def validate(
    ctx: typer.Context,
    model: Annotated[str, typer.Argument(help="Model to validate (e.g. res.partner)")],
    rules: Annotated[
        str | None, typer.Option("--rules", "-r", help="Comma-separated rules: required,email,phone (default: all)")
    ] = None,
) -> None:
    """Run basic data validation rules on a model.

    Checks required fields, email format on email fields, phone format on phone fields.

    Examples:
        kctl-odoo data-quality validate res.partner
        kctl-odoo data-quality validate res.partner --rules required,email
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    run_rules = {"required", "email", "phone"}
    if rules:
        run_rules = {r.strip() for r in rules.split(",") if r.strip()}

    # Per-model validation definitions
    validations: dict[str, dict] = {
        "res.partner": {
            "required": [("name", "=", False)],
            "email_fields": ["email"],
            "phone_fields": ["phone", "mobile"],
        },
        "hr.employee": {
            "required": [("name", "=", False)],
            "email_fields": ["work_email"],
            "phone_fields": ["mobile_phone", "work_phone"],
        },
        "res.users": {
            "required": [("name", "=", False)],
            "email_fields": ["email"],
            "phone_fields": [],
        },
        "product.template": {
            "required": [("name", "=", False)],
            "email_fields": [],
            "phone_fields": [],
        },
    }

    model_rules = validations.get(
        model,
        {
            "required": [("name", "=", False)],
            "email_fields": [],
            "phone_fields": [],
        },
    )

    rows = []
    result_data = []

    if "required" in run_rules:
        try:
            count = c.search_count(model, model_rules.get("required", [("name", "=", False)]))
            status = "[green]PASS[/green]" if count == 0 else "[red]FAIL[/red]"
            rows.append(["required.name", status, str(count) + " violations"])
            result_data.append({"rule": "required.name", "pass": count == 0, "violations": count})
        except (RPCError, Exception) as e:
            rows.append(["required.name", "[dim]N/A[/dim]", str(e)[:40]])
            result_data.append({"rule": "required.name", "pass": None, "violations": -1})

    if "email" in run_rules:
        for ef in model_rules.get("email_fields", []):
            try:
                # Check for invalid email format: no @ sign
                count = c.search_count(
                    model,
                    [(ef, "not like", "@"), (ef, "!=", False), (ef, "!=", "")],
                )
                status = "[green]PASS[/green]" if count == 0 else "[red]FAIL[/red]"
                rows.append([f"email.format.{ef}", status, str(count) + " invalid"])
                result_data.append({"rule": f"email.format.{ef}", "pass": count == 0, "violations": count})
            except (RPCError, Exception) as e:
                rows.append([f"email.format.{ef}", "[dim]N/A[/dim]", str(e)[:40]])
                result_data.append({"rule": f"email.format.{ef}", "pass": None, "violations": -1})

    if "phone" in run_rules:
        for pf in model_rules.get("phone_fields", []):
            try:
                # Check for phone numbers that are too short
                count = c.search_count(
                    model,
                    [(pf, "!=", False), (pf, "!=", "")],
                )
                rows.append([f"phone.present.{pf}", "[green]PASS[/green]", f"{count} with value"])
                result_data.append({"rule": f"phone.present.{pf}", "pass": True, "count": count})
            except (RPCError, Exception) as e:
                rows.append([f"phone.present.{pf}", "[dim]N/A[/dim]", str(e)[:40]])
                result_data.append({"rule": f"phone.present.{pf}", "pass": None, "violations": -1})

    if not rows:
        out.warn(f"No validation rules applicable for '{model}' with rules: {', '.join(run_rules)}")
        return

    out.table(
        f"Validation Results: {model}",
        [("Rule", "cyan"), ("Status", ""), ("Detail", "dim")],
        rows,
        data_for_json=result_data,
    )

    if actx.json_mode:
        out.raw_json(result_data)


@app.command("report")
def report(
    ctx: typer.Context,
    category: Annotated[str, typer.Option("--category", "-c", help="Category: master, operations, all")] = "all",
) -> None:
    """Combined data quality scorecard.

    Runs duplicate checks, completeness checks and orphan counts for common models.
    Categories: master (partners, products), operations (orders, invoices), all.

    Examples:
        kctl-odoo data-quality report
        kctl-odoo data-quality report --category master
        kctl-odoo data-quality report --category operations
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    master_checks = [
        ("Partner duplicates (name)", "res.partner", "name"),
        ("Partner duplicates (email)", "res.partner", "email"),
        ("Product duplicates (name)", "product.template", "name"),
    ]

    operations_checks = [
        ("Sale Order duplicates (name)", "sale.order", "name"),
        ("Invoice duplicates (name)", "account.move", "name"),
    ]

    if category == "master":
        checks_to_run = master_checks
    elif category == "operations":
        checks_to_run = operations_checks
    else:
        checks_to_run = master_checks + operations_checks

    rows = []
    result_data = []

    for description, check_model, group_field in checks_to_run:
        try:
            groups = c.execute_kw(
                check_model,
                "read_group",
                [[], [group_field], [group_field]],
                {"orderby": f"{group_field}_count desc", "limit": 200},
            )
            count_key = f"{group_field}_count"
            dup_groups = [g for g in groups if g.get(count_key, 0) > 1]
            dup_count = len(dup_groups)
            total_dups = sum(g.get(count_key, 0) - 1 for g in dup_groups)
            status = "[green]CLEAN[/green]" if dup_count == 0 else "[red]DUPS[/red]"
            rows.append([description, status, str(dup_count) + " groups", str(total_dups) + " extra"])
            result_data.append(
                {
                    "check": description,
                    "model": check_model,
                    "field": group_field,
                    "dup_groups": dup_count,
                    "extra_records": total_dups,
                }
            )
        except (RPCError, Exception):
            rows.append([description, "[dim]N/A[/dim]", "-", "-"])
            result_data.append({"check": description, "model": check_model, "field": group_field, "error": True})

    # Orphan counts
    orphan_checks: list[tuple[str, str, list]] = [
        ("Partners no invoices", "res.partner", [("invoice_ids", "=", False)]),
        ("Partners no orders", "res.partner", [("sale_order_ids", "=", False)]),
    ]
    if category in ("master", "all"):
        for desc, chk_model, domain in orphan_checks:
            try:
                count = c.search_count(chk_model, domain)
                status = "[green]CLEAN[/green]" if count == 0 else "[yellow]WARN[/yellow]"
                rows.append([desc, status, str(count), "-"])
                result_data.append({"check": desc, "model": chk_model, "count": count})
            except (RPCError, Exception):
                rows.append([desc, "[dim]N/A[/dim]", "-", "-"])
                result_data.append({"check": desc, "model": chk_model, "error": True})

    out.table(
        f"Data Quality Scorecard ({category})",
        [("Check", "cyan"), ("Status", ""), ("Groups/Count", ""), ("Detail", "dim")],
        rows,
        data_for_json=result_data,
    )

    if actx.json_mode:
        out.raw_json(result_data)
