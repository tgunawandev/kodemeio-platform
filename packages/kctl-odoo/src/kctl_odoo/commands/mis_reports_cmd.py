"""MIS Builder helpers — templates, instances, and the pre-built PSAK recipe.

MIS Builder's data model splits a report into three objects:

    mis.report              the TEMPLATE (KPI structure, shared across tenants)
    mis.report.kpi          one LINE inside a template (expression + style)
    mis.report.instance     a COMPUTED RUN of the template (company, period)

Creating either from the web UI is a click-marathon. These commands collapse
the common flows into a single invocation — most importantly the
`templates create-psak` recipe that produces an Indonesian PSAK / Accurate-
compatible P&L hierarchy (Pendapatan → BPP → Laba Kotor → Beban Operasional
→ Pendapatan Operasional → Non-Operasional → Laba Bersih) in one shot.
"""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_odoo.core.biz_helpers import model_available
from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.exceptions import RPCError

app = typer.Typer(help="MIS Builder templates + computed instances.")
templates_app = typer.Typer(help="Manage MIS report templates (mis.report).")
instances_app = typer.Typer(help="Manage MIS report instances (mis.report.instance).")
app.add_typer(templates_app, name="templates")
app.add_typer(instances_app, name="instances")

_REPORT = "mis.report"
_KPI = "mis.report.kpi"
_INSTANCE = "mis.report.instance"
_PERIOD = "mis.report.instance.period"
_HINT = "MIS Builder module (mis_builder) is not installed."


def _m2o_name(val: object) -> str:
    if isinstance(val, list) and len(val) >= 2:
        return str(val[1])
    return str(val or "-")


def _require_mis(c, out) -> bool:
    if not model_available(c, _REPORT):
        out.warn(_HINT)
        return False
    return True


# ===================================================================
# TEMPLATES — list / show / create-psak / clone / delete
# ===================================================================


@templates_app.command("list")
def templates_list(
    ctx: typer.Context,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List MIS report templates.

    Example: kctl-odoo mis-reports templates list
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    if not _require_mis(c, out):
        return

    try:
        records = c.search_read(_REPORT, domain=[], fields=["id", "name"], limit=limit, order="id")
    except RPCError as e:
        out.error(f"Failed to list templates: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.info("No MIS report templates found.")
        return

    rows = [[str(r["id"]), r["name"]] for r in records]
    out.table(
        f"MIS templates ({len(rows)})",
        [("ID", "dim"), ("Name", "cyan")],
        rows,
    )


@templates_app.command("show")
def templates_show(
    ctx: typer.Context,
    report_id: Annotated[int, typer.Argument(help="Template ID")],
) -> None:
    """Show template structure (KPI list with expressions + styles)."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    if not _require_mis(c, out):
        return

    try:
        [rec] = c.read(_REPORT, [report_id], ["name"])
        kpis = c.search_read(
            _KPI,
            domain=[("report_id", "=", report_id)],
            fields=[
                "id",
                "sequence",
                "name",
                "description",
                "expression",
                "auto_expand_accounts",
                "style_id",
            ],
            order="sequence, id",
        )
    except RPCError as e:
        out.error(f"Failed: {e}")
        raise typer.Exit(1) from e

    out.info(f"Template: {rec['name']} (id={report_id}) — {len(kpis)} KPIs")
    rows = []
    for k in kpis:
        rows.append(
            [
                str(k["sequence"]),
                k["name"],
                k.get("description") or "",
                (k.get("expression") or "")[:50],
                "Y" if k.get("auto_expand_accounts") else "",
                _m2o_name(k.get("style_id")),
            ]
        )
    out.table(
        f"KPIs ({len(rows)})",
        [
            ("Seq", "dim"),
            ("Name", "cyan"),
            ("Description", ""),
            ("Expression", ""),
            ("Expand", ""),
            ("Style", ""),
        ],
        rows,
    )


@templates_app.command("delete")
def templates_delete(
    ctx: typer.Context,
    report_id: Annotated[int, typer.Argument(help="Template ID")],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation")] = False,
) -> None:
    """Delete a MIS report template (fails if instances reference it)."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    if not _require_mis(c, out):
        return

    if not yes:
        confirm = typer.confirm(f"Delete template {report_id}? (instances may break)")
        if not confirm:
            out.info("Aborted.")
            return

    try:
        c.unlink(_REPORT, [report_id])
        out.success(f"Deleted template {report_id}.")
    except RPCError as e:
        out.error(f"Failed: {e}")
        raise typer.Exit(1) from e


@templates_app.command("clone")
def templates_clone(
    ctx: typer.Context,
    source_id: Annotated[int, typer.Argument(help="Source template ID")],
    name: Annotated[str, typer.Option("--name", "-n", help="New template name")],
) -> None:
    """Clone a template (copies all KPIs)."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    if not _require_mis(c, out):
        return

    try:
        new_id = c.execute_kw(_REPORT, "copy", [source_id], {"default": {"name": name}})
        out.success(f"Cloned template {source_id} → {new_id} ({name}).")
    except RPCError as e:
        out.error(f"Failed: {e}")
        raise typer.Exit(1) from e


# ---- PSAK recipe ----------------------------------------------------
# Pre-built P&L structure that matches Accurate ERP's "Laba/Rugi (Standar)"
# export. Account-type + code-prefix filters assume a standard Indonesian
# PSAK chart of accounts:
#   4xxx → income            (Pendapatan)
#   5xxx → expense_direct_cost (BPP)
#   6xxx → expense            (Beban Operasional)
#   7xxx/9xxx → expense       (Beban Non Operasional — "everything else")
#   8xxx → income_other       (Pendapatan Non Operasional)

_PSAK_KPIS = [
    # (name, description, expression, sequence, auto_expand, style_id)
    ("pendapatan", "PENDAPATAN", "-balp[('account_type','=','income')][]", 10, True, 2),
    ("total_pendapatan", "Jumlah Pendapatan", "pendapatan", 20, False, 2),
    ("bpp", "BEBAN POKOK PENJUALAN", "balp[('account_type','=','expense_direct_cost')][]", 30, True, 2),
    ("total_bpp", "Jumlah Beban Pokok Penjualan", "bpp", 40, False, 2),
    ("laba_kotor", "LABA KOTOR", "total_pendapatan - total_bpp", 50, False, 2),
    ("opex", "BEBAN OPERASIONAL", "balp[('account_type','=','expense'),('code','=like','6%')][]", 60, True, 2),
    ("total_opex", "Jumlah Beban Operasional", "opex", 70, False, 2),
    ("pendapatan_op", "PENDAPATAN OPERASIONAL", "laba_kotor - total_opex", 80, False, 2),
    ("nonop_inc", "Pendapatan Non Operasional", "-balp[('account_type','=','income_other')][]", 90, True, 4),
    ("total_nonop_inc", "Jumlah Pendapatan Non Operasional", "nonop_inc", 100, False, 4),
    # Non-op expense = all expense minus OPEX (avoids domain NOT operator)
    (
        "nonop_exp",
        "Beban Non Operasional",
        "balp[('account_type','in',('expense','expense_depreciation'))][] - opex",
        110,
        False,
        4,
    ),
    ("total_nonop_exp", "Jumlah Beban Non Operasional", "nonop_exp", 120, False, 4),
    ("total_nonop", "Jumlah Pendapatan dan Beban Non Operasional", "total_nonop_inc - total_nonop_exp", 130, False, 2),
    ("laba_bersih", "LABA BERSIH", "pendapatan_op + total_nonop", 140, False, 2),
]


@templates_app.command("create-psak")
def templates_create_psak(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", "-n", help="Template name")] = "P&L Akurat PSAK",
) -> None:
    """Create an Indonesian PSAK / Accurate-style P&L template.

    Ships a 14-KPI hierarchy that mirrors Accurate ERP's "Laba/Rugi (Standar)"
    layout — Pendapatan, BPP, Laba Kotor, Beban Operasional, Pendapatan
    Operasional, Non-Operasional, Laba Bersih. Uses account_type + code
    prefix filters (6% for operating expense).
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    if not _require_mis(c, out):
        return

    kpi_ids = [
        (
            0,
            0,
            {
                "name": k[0],
                "description": k[1],
                "expression": k[2],
                "sequence": k[3],
                "auto_expand_accounts": k[4],
                "style_id": k[5],
                "type": "num",
                "compare_method": "diff",
            },
        )
        for k in _PSAK_KPIS
    ]

    try:
        new_id = c.create(_REPORT, {"name": name, "kpi_ids": kpi_ids})
        out.success(f"Created PSAK template: {name} (id={new_id}) with {len(_PSAK_KPIS)} KPIs.")
        out.info(
            "Next: kctl-odoo mis-reports instances create --template "
            f"{new_id} --company <ID> --name <...> --from YYYY-MM-DD --to YYYY-MM-DD"
        )
    except RPCError as e:
        out.error(f"Failed: {e}")
        raise typer.Exit(1) from e


# ===================================================================
# INSTANCES — list / show / create / compute / delete
# ===================================================================


@instances_app.command("list")
def instances_list(
    ctx: typer.Context,
    template: Annotated[int | None, typer.Option("--template", "-t", help="Filter by template ID")] = None,
    company: Annotated[int | None, typer.Option("--company", "-c", help="Filter by company ID")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List MIS report instances."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    if not _require_mis(c, out):
        return

    domain = []
    if template:
        domain.append(("report_id", "=", template))
    if company:
        domain.append(("company_id", "=", company))

    try:
        records = c.search_read(
            _INSTANCE,
            domain=domain,
            fields=["id", "name", "report_id", "company_id", "currency_id", "target_move"],
            limit=limit,
            order="id desc",
        )
    except RPCError as e:
        out.error(f"Failed: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.info("No instances found.")
        return

    rows = [
        [
            str(r["id"]),
            r["name"],
            _m2o_name(r.get("report_id")),
            _m2o_name(r.get("company_id")),
            _m2o_name(r.get("currency_id")),
            r.get("target_move") or "",
        ]
        for r in records
    ]
    out.table(
        f"Instances ({len(rows)})",
        [
            ("ID", "dim"),
            ("Name", "cyan"),
            ("Template", ""),
            ("Company", ""),
            ("Currency", ""),
            ("Target", ""),
        ],
        rows,
    )


@instances_app.command("create")
def instances_create(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", "-n", help="Instance name")],
    template: Annotated[int, typer.Option("--template", "-t", help="Template (mis.report) ID")],
    company: Annotated[int, typer.Option("--company", "-c", help="Company ID")],
    date_from: Annotated[str, typer.Option("--from", help="Period start YYYY-MM-DD")],
    date_to: Annotated[str, typer.Option("--to", help="Period end YYYY-MM-DD")],
    period_name: Annotated[str, typer.Option("--period-name", help="Period label")] = "Period",
    target_move: Annotated[str, typer.Option("--target", help="posted|all")] = "posted",
    currency: Annotated[
        int | None, typer.Option("--currency", help="Currency ID (defaults to company currency)")
    ] = None,
) -> None:
    """Create a MIS report instance with a single fixed-date period.

    Example:
        kctl-odoo -p tpp-odoo-erp mis-reports instances create \\
            --name 'P&L Sumber FY 2026' --template 6 --company 2 \\
            --from 2026-01-01 --to 2026-12-31
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    if not _require_mis(c, out):
        return

    vals: dict = {
        "name": name,
        "report_id": template,
        "company_id": company,
        "target_move": target_move,
        "comparison_mode": False,
    }
    if currency:
        vals["currency_id"] = currency

    try:
        new_id = c.create(_INSTANCE, vals)
        # The instance auto-creates a "Default" period; rewrite its dates.
        [inst] = c.read(_INSTANCE, [new_id], ["period_ids"])
        period_ids = inst.get("period_ids") or []
        if period_ids:
            c.write(
                _PERIOD,
                period_ids,
                {
                    "name": period_name,
                    "mode": "fix",
                    "manual_date_from": date_from,
                    "manual_date_to": date_to,
                    "source": "actuals",
                    "source_aml_model_name": "account.move.line",
                },
            )
        out.success(f"Created instance {name} (id={new_id}) — period {date_from} → {date_to}.")
        out.info(f"Compute: kctl-odoo mis-reports instances compute {new_id}")
    except RPCError as e:
        out.error(f"Failed: {e}")
        raise typer.Exit(1) from e


@instances_app.command("compute")
def instances_compute(
    ctx: typer.Context,
    instance_id: Annotated[int, typer.Argument(help="Instance ID")],
) -> None:
    """Compute an instance and print the result as a table."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    if not _require_mis(c, out):
        return

    try:
        data = c.execute_kw(_INSTANCE, "compute", [[instance_id]])
    except RPCError as e:
        out.error(f"Compute failed: {e}")
        raise typer.Exit(1) from e

    if actx.json_mode:
        import json as _json

        print(_json.dumps(data, indent=2, default=str))
        return

    col_labels = [c.get("label", "") for c in (data.get("header") or [{}])[-1].get("cols", [])]
    columns = [("Label", "cyan")] + [(lbl or "", "") for lbl in col_labels]
    rows = []
    for r in data.get("body", []):
        label = r.get("label", "")
        cells = [c.get("val_r", "") for c in (r.get("cells") or [])]
        rows.append([label] + cells)
    out.table(f"Instance {instance_id} ({len(rows)} rows)", columns, rows)


@instances_app.command("delete")
def instances_delete(
    ctx: typer.Context,
    instance_id: Annotated[int, typer.Argument(help="Instance ID")],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation")] = False,
) -> None:
    """Delete a MIS report instance."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    if not _require_mis(c, out):
        return

    if not yes:
        confirm = typer.confirm(f"Delete instance {instance_id}?")
        if not confirm:
            out.info("Aborted.")
            return

    try:
        c.unlink(_INSTANCE, [instance_id])
        out.success(f"Deleted instance {instance_id}.")
    except RPCError as e:
        out.error(f"Failed: {e}")
        raise typer.Exit(1) from e
