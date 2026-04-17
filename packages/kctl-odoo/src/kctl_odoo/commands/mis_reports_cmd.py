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
styles_app = typer.Typer(help="Manage MIS report styles (mis.report.style).")
kpis_app = typer.Typer(help="Manage KPIs on a template (mis.report.kpi).")
subkpis_app = typer.Typer(help="Manage sub-KPIs — adds columns within each KPI.")
queries_app = typer.Typer(help="Manage custom data-source queries (mis.report.query).")
subreports_app = typer.Typer(help="Manage embedded sub-reports (mis.report.subreport).")
app.add_typer(templates_app, name="templates")
app.add_typer(instances_app, name="instances")
app.add_typer(styles_app, name="styles")
app.add_typer(kpis_app, name="kpis")
app.add_typer(subkpis_app, name="subkpis")
app.add_typer(queries_app, name="queries")
app.add_typer(subreports_app, name="subreports")

_REPORT = "mis.report"
_KPI = "mis.report.kpi"
_STYLE = "mis.report.style"
_SUBKPI = "mis.report.subkpi"
_KPI_EXPR = "mis.report.kpi.expression"
_QUERY = "mis.report.query"
_SUBREPORT = "mis.report.subreport"
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


# ===================================================================
# STYLES — list / show / create / update / delete / recipes
# ===================================================================
#
# mis.report.style stores reusable styling rules. Every style field has a
# sibling `<name>_inherit` boolean flag (default True). When set to False,
# the field value overrides whatever style chain the KPI resolves. When
# True, the value is inherited from the report's default style. The CLI
# below automatically flips `_inherit` to False whenever you set the
# corresponding value — callers just pass the value and don't think
# about the inheritance plumbing.
#
# Available fields (verified against mis_builder 18.0.1.8.1):
#   - color           "#RRGGBB"        text color
#   - background_color "#RRGGBB"       cell background
#   - font_style      normal|italic
#   - font_weight     nornal|bold       NOTE: upstream typo "nornal"
#   - font_size       medium|xx-small|x-small|small|large|x-large|xx-large
#   - indent_level    integer           renders as text-indent: Xem
#   - prefix          string            prepended to value (e.g. "$")
#   - suffix          string            appended to value (e.g. "%")
#   - dp              integer           decimal places
#   - divider         "1"|"1e3"|"1e6"|"1e9"   value scaling
#   - hide_empty      boolean           suppress zero-value rows
#   - hide_always     boolean           always suppress this row


_STYLE_FIELDS = {
    "color": str,
    "background_color": str,
    "font_style": str,  # "normal" | "italic"
    "font_weight": str,  # "nornal" (sic) | "bold"
    "font_size": str,  # medium/xx-small/x-small/small/large/x-large/xx-large
    "indent_level": int,
    "prefix": str,
    "suffix": str,
    "dp": int,
    "divider": str,  # "1" | "1e3" | "1e6" | "1e9"
    "hide_empty": bool,
    "hide_always": bool,
}


def _style_vals(**kwargs):
    """Build a dict of {field: value, field_inherit: False} from kwargs."""
    vals = {}
    for key, value in kwargs.items():
        if key not in _STYLE_FIELDS or value is None:
            continue
        vals[key] = value
        vals[f"{key}_inherit"] = False
    return vals


@styles_app.command("list")
def styles_list(
    ctx: typer.Context,
    limit: Annotated[int, typer.Option("--limit", "-l")] = 100,
) -> None:
    """List all defined mis.report.style records."""
    actx: AppContext = ctx.obj
    out, c = actx.output, actx.client
    if not _require_mis(c, out):
        return
    try:
        records = c.search_read(
            _STYLE,
            domain=[],
            fields=[
                "id",
                "name",
                "font_weight",
                "font_style",
                "font_size",
                "indent_level",
                "color",
                "background_color",
                "prefix",
                "suffix",
                "dp",
                "divider",
            ],
            limit=limit,
            order="id",
        )
    except RPCError as e:
        out.error(f"Failed: {e}")
        raise typer.Exit(1) from e
    rows = []
    for r in records:
        rows.append(
            [
                str(r["id"]),
                r["name"],
                r.get("font_weight") or "",
                r.get("font_style") or "",
                str(r.get("indent_level") or ""),
                r.get("color") or "",
                r.get("prefix") or "",
                r.get("suffix") or "",
                str(r.get("dp") or ""),
            ]
        )
    out.table(
        f"Styles ({len(rows)})",
        [
            ("ID", "dim"),
            ("Name", "cyan"),
            ("Weight", ""),
            ("Style", ""),
            ("Indent", ""),
            ("Color", ""),
            ("Prefix", ""),
            ("Suffix", ""),
            ("DP", ""),
        ],
        rows,
    )


@styles_app.command("show")
def styles_show(
    ctx: typer.Context,
    style_id: Annotated[int, typer.Argument(help="Style ID")],
) -> None:
    """Show every field on a style with its inherit flag."""
    actx: AppContext = ctx.obj
    out, c = actx.output, actx.client
    if not _require_mis(c, out):
        return
    fields_list = ["name"] + list(_STYLE_FIELDS.keys()) + [f"{k}_inherit" for k in _STYLE_FIELDS]
    try:
        [rec] = c.read(_STYLE, [style_id], fields_list)
    except RPCError as e:
        out.error(f"Failed: {e}")
        raise typer.Exit(1) from e
    rows = [["name", str(rec["name"]), ""]]
    for f in _STYLE_FIELDS:
        value = rec.get(f)
        inherit = rec.get(f"{f}_inherit", True)
        rows.append([f, str(value) if value not in (None, False, "") else "—", "inherit" if inherit else "override"])
    out.table(
        f"Style id={style_id} ({rec['name']})",
        [("Field", "cyan"), ("Value", ""), ("Mode", "dim")],
        rows,
    )


@styles_app.command("create")
def styles_create(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", "-n", help="Style name")],
    color: Annotated[str | None, typer.Option("--color", help="Text color #RRGGBB")] = None,
    background_color: Annotated[str | None, typer.Option("--bg", help="Background color #RRGGBB")] = None,
    font_style: Annotated[str | None, typer.Option("--font-style", help="normal|italic")] = None,
    font_weight: Annotated[str | None, typer.Option("--font-weight", help="nornal(sic)|bold — UPSTREAM TYPO")] = None,
    font_size: Annotated[
        str | None, typer.Option("--font-size", help="medium|xx-small|x-small|small|large|x-large|xx-large")
    ] = None,
    indent: Annotated[int | None, typer.Option("--indent", help="indent_level (integer em units)")] = None,
    prefix: Annotated[str | None, typer.Option("--prefix", help="Prepended text (e.g. $)")] = None,
    suffix: Annotated[str | None, typer.Option("--suffix", help="Appended text (e.g. %)")] = None,
    dp: Annotated[int | None, typer.Option("--dp", help="Decimal places")] = None,
    divider: Annotated[str | None, typer.Option("--divider", help="Value scale: 1|1e3|1e6|1e9")] = None,
    hide_empty: Annotated[bool, typer.Option("--hide-empty", help="Hide zero-value rows")] = False,
) -> None:
    """Create a mis.report.style with only the fields you specify.

    Any field you don't pass stays inherited from the parent chain.

    Example:
        kctl-odoo mis-reports styles create \\
            --name "Subtotal" --font-weight bold --indent 0
    """
    actx: AppContext = ctx.obj
    out, c = actx.output, actx.client
    if not _require_mis(c, out):
        return
    vals = {"name": name}
    vals.update(
        _style_vals(
            color=color,
            background_color=background_color,
            font_style=font_style,
            font_weight=font_weight,
            font_size=font_size,
            indent_level=indent,
            prefix=prefix,
            suffix=suffix,
            dp=dp,
            divider=divider,
            hide_empty=hide_empty if hide_empty else None,
        )
    )
    try:
        new_id = c.create(_STYLE, vals)
        out.success(f"Created style id={new_id}: {name}")
    except RPCError as e:
        out.error(f"Failed: {e}")
        raise typer.Exit(1) from e


@styles_app.command("update")
def styles_update(
    ctx: typer.Context,
    style_id: Annotated[int, typer.Argument(help="Style ID")],
    name: Annotated[str | None, typer.Option("--name")] = None,
    color: Annotated[str | None, typer.Option("--color")] = None,
    background_color: Annotated[str | None, typer.Option("--bg")] = None,
    font_style: Annotated[str | None, typer.Option("--font-style")] = None,
    font_weight: Annotated[str | None, typer.Option("--font-weight")] = None,
    font_size: Annotated[str | None, typer.Option("--font-size")] = None,
    indent: Annotated[int | None, typer.Option("--indent")] = None,
    prefix: Annotated[str | None, typer.Option("--prefix")] = None,
    suffix: Annotated[str | None, typer.Option("--suffix")] = None,
    dp: Annotated[int | None, typer.Option("--dp")] = None,
    divider: Annotated[str | None, typer.Option("--divider")] = None,
) -> None:
    """Update one or more fields on an existing style."""
    actx: AppContext = ctx.obj
    out, c = actx.output, actx.client
    if not _require_mis(c, out):
        return
    vals = {}
    if name is not None:
        vals["name"] = name
    vals.update(
        _style_vals(
            color=color,
            background_color=background_color,
            font_style=font_style,
            font_weight=font_weight,
            font_size=font_size,
            indent_level=indent,
            prefix=prefix,
            suffix=suffix,
            dp=dp,
            divider=divider,
        )
    )
    if not vals:
        out.warn("No fields to update.")
        return
    try:
        c.write(_STYLE, [style_id], vals)
        out.success(f"Updated style {style_id}.")
    except RPCError as e:
        out.error(f"Failed: {e}")
        raise typer.Exit(1) from e


@styles_app.command("delete")
def styles_delete(
    ctx: typer.Context,
    style_id: Annotated[int, typer.Argument(help="Style ID")],
    yes: Annotated[bool, typer.Option("--yes", "-y")] = False,
) -> None:
    """Delete a style (fails if any KPI references it)."""
    actx: AppContext = ctx.obj
    out, c = actx.output, actx.client
    if not _require_mis(c, out):
        return
    if not yes and not typer.confirm(f"Delete style {style_id}?"):
        return
    try:
        c.unlink(_STYLE, [style_id])
        out.success(f"Deleted style {style_id}.")
    except RPCError as e:
        out.error(f"Failed: {e}")
        raise typer.Exit(1) from e


@styles_app.command("create-psak-set")
def styles_create_psak_set(
    ctx: typer.Context,
) -> None:
    """Bulk-create the 7 styles the PSAK recipe needs.

    Creates: PSAK Section (bold indent 0), PSAK Subtotal (bold indent 0),
    PSAK Subheader (bold indent 2), PSAK Grand Total (bold indent 0),
    PSAK Child L1/L2/L3 (indent 1/2/3, normal weight). Assigns names
    verbatim so the PSAK template can reference them predictably.
    """
    actx: AppContext = ctx.obj
    out, c = actx.output, actx.client
    if not _require_mis(c, out):
        return
    recipes = [
        ("PSAK Section", {"font_weight": "bold", "indent_level": 0}),
        ("PSAK Subtotal", {"font_weight": "bold", "indent_level": 0}),
        ("PSAK Subheader", {"font_weight": "bold", "indent_level": 2}),
        ("PSAK Grand Total", {"font_weight": "bold", "indent_level": 0}),
        ("PSAK Child L1", {"indent_level": 1}),
        ("PSAK Child L2", {"indent_level": 2}),
        ("PSAK Child L3", {"indent_level": 3}),
    ]
    created = []
    for name, overrides in recipes:
        try:
            vals = {"name": name}
            vals.update(_style_vals(**overrides))
            new_id = c.create(_STYLE, vals)
            created.append((new_id, name))
        except RPCError as e:
            out.error(f"Failed to create {name}: {e}")
            continue
    out.success(f"Created {len(created)} PSAK styles.")
    out.table(
        "Created",
        [("ID", "dim"), ("Name", "cyan")],
        [[str(i), n] for i, n in created],
    )


# ===================================================================
# KPIs — add / update / remove / set-style / describe
# ===================================================================


_KPI_TYPES = {"num": "Numeric", "pct": "Percentage", "str": "String"}
_KPI_COMPARE = {"diff": "Difference", "pct": "Percentage", "none": "None"}
_KPI_ACCUM = {"sum": "Sum", "avg": "Average", "none": "None"}


@kpis_app.command("add")
def kpis_add(
    ctx: typer.Context,
    template: Annotated[int, typer.Option("--template", "-t", help="Template (mis.report) ID")],
    name: Annotated[str, typer.Option("--name", "-n", help="Internal name (snake_case, used in expressions)")],
    description: Annotated[str, typer.Option("--description", "-d", help="Display label")],
    expression: Annotated[
        str, typer.Option("--expression", "-e", help="MIS expression (e.g. balp[('account_type','=','income')][])")
    ],
    sequence: Annotated[int, typer.Option("--sequence", "-s", help="Row order")] = 100,
    style: Annotated[int | None, typer.Option("--style", help="mis.report.style ID for this row")] = None,
    expand: Annotated[bool, typer.Option("--expand", help="Display detail by account")] = False,
    expand_style: Annotated[int | None, typer.Option("--expand-style", help="Style ID for expanded child rows")] = None,
    kpi_type: Annotated[str, typer.Option("--type", help="num|pct|str")] = "num",
    compare: Annotated[str, typer.Option("--compare", help="diff|pct|none")] = "diff",
    accumulation: Annotated[str, typer.Option("--accumulation", help="sum|avg|none")] = "sum",
) -> None:
    """Add a KPI (row) to an existing template."""
    actx: AppContext = ctx.obj
    out, c = actx.output, actx.client
    if not _require_mis(c, out):
        return
    vals = {
        "report_id": template,
        "name": name,
        "description": description,
        "expression": expression,
        "sequence": sequence,
        "auto_expand_accounts": expand,
        "type": kpi_type,
        "compare_method": compare,
        "accumulation_method": accumulation,
    }
    if style:
        vals["style_id"] = style
    if expand_style:
        vals["auto_expand_accounts_style_id"] = expand_style
    try:
        new_id = c.create(_KPI, vals)
        out.success(f"Added KPI id={new_id} ({description}) to template {template}.")
    except RPCError as e:
        out.error(f"Failed: {e}")
        raise typer.Exit(1) from e


@kpis_app.command("update")
def kpis_update(
    ctx: typer.Context,
    kpi_id: Annotated[int, typer.Argument(help="KPI ID")],
    description: Annotated[str | None, typer.Option("--description", "-d")] = None,
    expression: Annotated[str | None, typer.Option("--expression", "-e")] = None,
    sequence: Annotated[int | None, typer.Option("--sequence", "-s")] = None,
    style: Annotated[int | None, typer.Option("--style", help="Style for row")] = None,
    expand: Annotated[bool | None, typer.Option("--expand/--no-expand")] = None,
    expand_style: Annotated[int | None, typer.Option("--expand-style")] = None,
) -> None:
    """Update one or more fields on an existing KPI."""
    actx: AppContext = ctx.obj
    out, c = actx.output, actx.client
    if not _require_mis(c, out):
        return
    vals: dict = {}
    if description is not None:
        vals["description"] = description
    if expression is not None:
        vals["expression"] = expression
    if sequence is not None:
        vals["sequence"] = sequence
    if style is not None:
        vals["style_id"] = style
    if expand is not None:
        vals["auto_expand_accounts"] = expand
    if expand_style is not None:
        vals["auto_expand_accounts_style_id"] = expand_style
    if not vals:
        out.warn("No fields to update.")
        return
    try:
        c.write(_KPI, [kpi_id], vals)
        out.success(f"Updated KPI {kpi_id}.")
    except RPCError as e:
        out.error(f"Failed: {e}")
        raise typer.Exit(1) from e


@kpis_app.command("set-style")
def kpis_set_style(
    ctx: typer.Context,
    kpi_id: Annotated[int, typer.Argument(help="KPI ID")],
    style: Annotated[int, typer.Option("--style", help="Style ID to apply")],
    expand_style: Annotated[int | None, typer.Option("--expand-style", help="Style ID for expanded children")] = None,
) -> None:
    """Shortcut for setting style + expand-style on a KPI."""
    kpis_update.callback(  # type: ignore[attr-defined]
        ctx,
        kpi_id=kpi_id,
        description=None,
        expression=None,
        sequence=None,
        style=style,
        expand=None,
        expand_style=expand_style,
    )


@kpis_app.command("delete")
def kpis_delete(
    ctx: typer.Context,
    kpi_id: Annotated[int, typer.Argument(help="KPI ID")],
    yes: Annotated[bool, typer.Option("--yes", "-y")] = False,
) -> None:
    """Delete a KPI from its template."""
    actx: AppContext = ctx.obj
    out, c = actx.output, actx.client
    if not _require_mis(c, out):
        return
    if not yes and not typer.confirm(f"Delete KPI {kpi_id}?"):
        return
    try:
        c.unlink(_KPI, [kpi_id])
        out.success(f"Deleted KPI {kpi_id}.")
    except RPCError as e:
        out.error(f"Failed: {e}")
        raise typer.Exit(1) from e


@app.command("describe")
def describe(ctx: typer.Context) -> None:
    """Print a field-level reference for every MIS Builder model.

    What you can set, what the selection values mean, and where MIS
    Builder emits which CSS — handy when you're wiring a template by
    hand and don't want to dig through the OCA source.
    """
    actx: AppContext = ctx.obj
    out = actx.output
    out.info(
        "\n[bold cyan]mis.report.kpi[/]  — one row on the report\n"
        "  name                            snake_case; referenced from other KPI expressions\n"
        "  description                     human-facing label (shown in the row)\n"
        "  expression                      MIS expression: balp[domain][subdomain] or KPI arithmetic\n"
        "  multi                           True → expressions come from expression_ids (one per subkpi)\n"
        "  auto_expand_accounts            True → render one child row per matching account\n"
        "  auto_expand_accounts_style_id   style applied to those child rows (indent goes here)\n"
        "  style_id                        style for this KPI's own row\n"
        "  style_expression                Python condition that swaps style at render (advanced)\n"
        "  type                            num | pct | str\n"
        "  compare_method                  diff | pct | none     (only matters in comparison columns)\n"
        "  accumulation_method             sum | avg | none     (how values combine across sub-periods)\n"
        "  sequence                        row order\n"
        "  budgetable                      True → appears in budget vs actual comparison\n"
        "\n[bold cyan]mis.report.style[/] — reusable styling block, applied via style_id\n"
        "  Every field has a sibling <field>_inherit flag. Set it to False when you want the value\n"
        "  to override the inherited chain. The kctl-odoo styles create/update commands flip this\n"
        "  automatically based on what you pass.\n"
        "  color / background_color        #RRGGBB hex\n"
        "  font_style                      normal | italic\n"
        "  font_weight                     nornal (upstream typo!) | bold\n"
        "  font_size                       medium | xx-small | x-small | small | large | x-large | xx-large\n"
        "  indent_level                    integer → emits inline style='text-indent: Xem'\n"
        "  prefix / suffix                 string wrapped around the value (e.g. '$', '%')\n"
        "  dp                              decimal places\n"
        "  divider                         '1' | '1e3' | '1e6' | '1e9'  scales numeric output\n"
        "  hide_empty                      True → suppress zero rows\n"
        "  hide_always                     True → never render\n"
        "\n[bold cyan]mis.report.instance.period[/] — a column on the report\n"
        "  mode                            fix | relative | date_range | none\n"
        "  source                          actuals | actuals_alt | cmpcol | sumcol\n"
        "  manual_date_from / manual_date_to   for mode=fix\n"
        "  date_range_id                   for mode=date_range (links a date.range record)\n"
        "  comparison_column_ids           for source=cmpcol (other period this one compares to)\n"
        "  source_aml_model_name           default 'account.move.line' — the drill-down source\n"
        "\nExamples:\n"
        "  [dim]# Build a PSAK P&L template from scratch:[/]\n"
        "  kctl-odoo mis-reports styles create-psak-set\n"
        "  kctl-odoo mis-reports templates create-psak --name 'P&L PSAK'\n"
        "  kctl-odoo mis-reports instances create \\\n"
        "      --name 'P&L Co.A FY2026' --template <ID> --company <ID> \\\n"
        "      --from 2026-01-01 --to 2026-12-31\n"
    )


# ===================================================================
# SUBKPIs — column dimension across all KPIs (e.g. "Nilai" + "% dari Omset")
# ===================================================================
#
# When a report declares sub-KPIs, every KPI row renders once per sub-KPI as
# separate columns. This is MIS Builder's mechanism for multi-column layouts
# like Accurate's "Value" + "% of Revenue" dual-column view.
#
# Data model: mis.report.subkpi defines a column. Each KPI then gets multiple
# mis.report.kpi.expression records (one per subkpi) — set kpi.multi=True and
# populate expression_ids. Setting `multi=False` reverts to single-column mode
# where the `expression` char field is used directly.


@subkpis_app.command("list")
def subkpis_list(
    ctx: typer.Context,
    template: Annotated[int, typer.Option("--template", "-t", help="Template ID")],
) -> None:
    """List sub-KPIs on a template (columns that apply across every KPI)."""
    actx: AppContext = ctx.obj
    out, c = actx.output, actx.client
    if not _require_mis(c, out):
        return
    try:
        records = c.search_read(
            _SUBKPI,
            domain=[("report_id", "=", template)],
            fields=["id", "sequence", "name", "description"],
            order="sequence, id",
        )
    except RPCError as e:
        out.error(f"Failed: {e}")
        raise typer.Exit(1) from e
    if not records:
        out.info("No sub-KPIs on this template (single-column mode).")
        return
    rows = [[str(r["id"]), str(r["sequence"]), r["name"], r.get("description") or ""] for r in records]
    out.table(
        f"Sub-KPIs on template {template} ({len(rows)})",
        [("ID", "dim"), ("Seq", "dim"), ("Name", "cyan"), ("Description", "")],
        rows,
    )


@subkpis_app.command("add")
def subkpis_add(
    ctx: typer.Context,
    template: Annotated[int, typer.Option("--template", "-t")],
    name: Annotated[str, typer.Option("--name", "-n", help="snake_case identifier")],
    description: Annotated[str, typer.Option("--description", "-d", help="Display label")],
    sequence: Annotated[int, typer.Option("--sequence", "-s")] = 10,
) -> None:
    """Add a sub-KPI column to a template.

    Remember: after adding sub-KPIs you must set kpi.multi=True on each KPI
    and populate one expression per sub-KPI — or the KPI won't compute.
    """
    actx: AppContext = ctx.obj
    out, c = actx.output, actx.client
    if not _require_mis(c, out):
        return
    try:
        new_id = c.create(
            _SUBKPI,
            {
                "report_id": template,
                "name": name,
                "description": description,
                "sequence": sequence,
            },
        )
        out.success(f"Added sub-KPI id={new_id} ({description}) to template {template}.")
    except RPCError as e:
        out.error(f"Failed: {e}")
        raise typer.Exit(1) from e


@subkpis_app.command("delete")
def subkpis_delete(
    ctx: typer.Context,
    subkpi_id: Annotated[int, typer.Argument(help="Sub-KPI ID")],
    yes: Annotated[bool, typer.Option("--yes", "-y")] = False,
) -> None:
    """Delete a sub-KPI (cascades to all kpi.expression records using it)."""
    actx: AppContext = ctx.obj
    out, c = actx.output, actx.client
    if not _require_mis(c, out):
        return
    if not yes and not typer.confirm(f"Delete sub-KPI {subkpi_id}?"):
        return
    try:
        c.unlink(_SUBKPI, [subkpi_id])
        out.success(f"Deleted sub-KPI {subkpi_id}.")
    except RPCError as e:
        out.error(f"Failed: {e}")
        raise typer.Exit(1) from e


@subkpis_app.command("set-expression")
def subkpis_set_expression(
    ctx: typer.Context,
    kpi_id: Annotated[int, typer.Argument(help="KPI ID")],
    subkpi_id: Annotated[int, typer.Option("--subkpi", help="Sub-KPI ID")],
    expression: Annotated[str, typer.Option("--expression", "-e", help="MIS expression for this cell")],
) -> None:
    """Set the expression for a specific (KPI × sub-KPI) cell.

    Multi-column KPIs store one mis.report.kpi.expression record per
    sub-KPI. This command upserts the row — create if missing, update if
    present — and flips kpi.multi=True automatically.
    """
    actx: AppContext = ctx.obj
    out, c = actx.output, actx.client
    if not _require_mis(c, out):
        return
    try:
        existing = c.search_read(
            _KPI_EXPR,
            domain=[("kpi_id", "=", kpi_id), ("subkpi_id", "=", subkpi_id)],
            fields=["id"],
        )
        if existing:
            c.write(_KPI_EXPR, [existing[0]["id"]], {"name": expression})
        else:
            c.create(_KPI_EXPR, {"kpi_id": kpi_id, "subkpi_id": subkpi_id, "name": expression})
        c.write(_KPI, [kpi_id], {"multi": True})
        out.success(f"KPI {kpi_id} × sub-KPI {subkpi_id} → {expression}")
    except RPCError as e:
        out.error(f"Failed: {e}")
        raise typer.Exit(1) from e


# ===================================================================
# QUERIES — arbitrary data sources (beyond account.move.line)
# ===================================================================
#
# A query fetches records from any Odoo model, filtered by a domain, and
# aggregates a field across the reporting period. Useful when a KPI needs
# data from outside the accounting module (CRM leads, inventory moves,
# HR timesheets, etc.). Once declared, reference the query from a KPI
# expression using the query's name.


@queries_app.command("list")
def queries_list(
    ctx: typer.Context,
    template: Annotated[int, typer.Option("--template", "-t")],
) -> None:
    """List custom data-source queries on a template."""
    actx: AppContext = ctx.obj
    out, c = actx.output, actx.client
    if not _require_mis(c, out):
        return
    try:
        records = c.search_read(
            _QUERY,
            domain=[("report_id", "=", template)],
            fields=["id", "name", "model_id", "field_names", "aggregate", "date_field", "domain"],
            order="name",
        )
    except RPCError as e:
        out.error(f"Failed: {e}")
        raise typer.Exit(1) from e
    if not records:
        out.info("No queries defined.")
        return
    rows = []
    for r in records:
        rows.append(
            [
                str(r["id"]),
                r["name"],
                _m2o_name(r.get("model_id")),
                r.get("field_names") or "",
                r.get("aggregate") or "",
                _m2o_name(r.get("date_field")),
                (r.get("domain") or "")[:40],
            ]
        )
    out.table(
        f"Queries on template {template} ({len(rows)})",
        [
            ("ID", "dim"),
            ("Name", "cyan"),
            ("Model", ""),
            ("Fields", ""),
            ("Aggregate", ""),
            ("Date Field", ""),
            ("Domain", ""),
        ],
        rows,
    )


@queries_app.command("add")
def queries_add(
    ctx: typer.Context,
    template: Annotated[int, typer.Option("--template", "-t")],
    name: Annotated[str, typer.Option("--name", "-n", help="snake_case — referenced in KPI expressions")],
    model: Annotated[str, typer.Option("--model", "-m", help="Odoo model (e.g. sale.order)")],
    fields_: Annotated[str, typer.Option("--fields", "-f", help="Comma-separated field names to fetch")],
    date_field: Annotated[str, typer.Option("--date-field", help="Date/datetime field for period filter")],
    aggregate: Annotated[str | None, typer.Option("--aggregate", help="sum | avg | min | max")] = None,
    domain: Annotated[str | None, typer.Option("--domain", help="Additional filter, e.g. \"[('state','=','sale')]\"")] = None,
    company_field: Annotated[str | None, typer.Option("--company-field", help="Company field name for multi-company isolation")] = None,
) -> None:
    """Add a custom query to a template.

    Resolves --model, --fields, --date-field, --company-field from their
    string names to the underlying ir.model / ir.model.fields IDs.

    Example (sale orders per period):
        kctl-odoo mis-reports queries add \\
            --template 6 --name sales --model sale.order \\
            --fields amount_total --date-field date_order \\
            --aggregate sum --domain "[('state','in',('sale','done'))]"
    """
    actx: AppContext = ctx.obj
    out, c = actx.output, actx.client
    if not _require_mis(c, out):
        return
    try:
        [model_rec] = c.search_read(
            "ir.model", domain=[("model", "=", model)], fields=["id"], limit=1
        ) or [None]
        if not model_rec:
            out.error(f"Model {model!r} not found.")
            raise typer.Exit(1)
        field_names = [f.strip() for f in fields_.split(",") if f.strip()]
        field_recs = c.search_read(
            "ir.model.fields",
            domain=[("model_id", "=", model_rec["id"]), ("name", "in", field_names)],
            fields=["id", "name"],
        )
        [date_rec] = c.search_read(
            "ir.model.fields",
            domain=[("model_id", "=", model_rec["id"]), ("name", "=", date_field)],
            fields=["id"],
            limit=1,
        ) or [None]
        if not date_rec:
            out.error(f"Date field {model}.{date_field} not found.")
            raise typer.Exit(1)
        vals: dict = {
            "report_id": template,
            "name": name,
            "model_id": model_rec["id"],
            "field_ids": [(6, 0, [f["id"] for f in field_recs])],
            "date_field": date_rec["id"],
        }
        if aggregate:
            vals["aggregate"] = aggregate
        if domain:
            vals["domain"] = domain
        if company_field:
            [cf] = c.search_read(
                "ir.model.fields",
                domain=[("model_id", "=", model_rec["id"]), ("name", "=", company_field)],
                fields=["id"],
                limit=1,
            ) or [None]
            if cf:
                vals["company_field_id"] = cf["id"]
        new_id = c.create(_QUERY, vals)
        out.success(f"Added query id={new_id} ({name}) — {model}.{','.join(field_names)} by {date_field}")
    except RPCError as e:
        out.error(f"Failed: {e}")
        raise typer.Exit(1) from e


@queries_app.command("delete")
def queries_delete(
    ctx: typer.Context,
    query_id: Annotated[int, typer.Argument(help="Query ID")],
    yes: Annotated[bool, typer.Option("--yes", "-y")] = False,
) -> None:
    """Delete a query from its template."""
    actx: AppContext = ctx.obj
    out, c = actx.output, actx.client
    if not _require_mis(c, out):
        return
    if not yes and not typer.confirm(f"Delete query {query_id}?"):
        return
    try:
        c.unlink(_QUERY, [query_id])
        out.success(f"Deleted query {query_id}.")
    except RPCError as e:
        out.error(f"Failed: {e}")
        raise typer.Exit(1) from e


# ===================================================================
# SUBREPORTS — embed one report inside another
# ===================================================================
#
# A subreport pulls the KPIs from report B and renders them inline inside
# report A. Useful for factoring common blocks (a department P&L) into a
# shared template that's composed into a consolidated view.


@subreports_app.command("list")
def subreports_list(
    ctx: typer.Context,
    template: Annotated[int, typer.Option("--template", "-t")],
) -> None:
    """List subreports embedded in a template."""
    actx: AppContext = ctx.obj
    out, c = actx.output, actx.client
    if not _require_mis(c, out):
        return
    try:
        records = c.search_read(
            _SUBREPORT,
            domain=[("report_id", "=", template)],
            fields=["id", "name", "subreport_id"],
            order="name",
        )
    except RPCError as e:
        out.error(f"Failed: {e}")
        raise typer.Exit(1) from e
    if not records:
        out.info("No subreports on this template.")
        return
    rows = [[str(r["id"]), r["name"], _m2o_name(r.get("subreport_id"))] for r in records]
    out.table(
        f"Subreports on template {template} ({len(rows)})",
        [("ID", "dim"), ("Name", "cyan"), ("Embeds template", "")],
        rows,
    )


@subreports_app.command("add")
def subreports_add(
    ctx: typer.Context,
    template: Annotated[int, typer.Option("--template", "-t", help="Parent template ID")],
    subtemplate: Annotated[int, typer.Option("--subtemplate", "-s", help="Template ID to embed")],
    name: Annotated[str, typer.Option("--name", "-n", help="Name of the subreport block")],
) -> None:
    """Embed one template inside another as a subreport block."""
    actx: AppContext = ctx.obj
    out, c = actx.output, actx.client
    if not _require_mis(c, out):
        return
    try:
        new_id = c.create(
            _SUBREPORT,
            {"report_id": template, "subreport_id": subtemplate, "name": name},
        )
        out.success(f"Embedded template {subtemplate} in {template} as {name} (id={new_id}).")
    except RPCError as e:
        out.error(f"Failed: {e}")
        raise typer.Exit(1) from e


@subreports_app.command("delete")
def subreports_delete(
    ctx: typer.Context,
    subreport_id: Annotated[int, typer.Argument(help="Subreport link ID")],
    yes: Annotated[bool, typer.Option("--yes", "-y")] = False,
) -> None:
    """Remove a subreport embedding (doesn't delete the underlying template)."""
    actx: AppContext = ctx.obj
    out, c = actx.output, actx.client
    if not _require_mis(c, out):
        return
    if not yes and not typer.confirm(f"Remove subreport link {subreport_id}?"):
        return
    try:
        c.unlink(_SUBREPORT, [subreport_id])
        out.success(f"Removed subreport link {subreport_id}.")
    except RPCError as e:
        out.error(f"Failed: {e}")
        raise typer.Exit(1) from e
