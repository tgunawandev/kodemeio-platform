"""Report type registry CRUD.

Wraps the ``report.type.registry`` model shipped with ``report_management``.
Lets operators add, tweak, or retire report types on the fly in production
without editing ``data/report.type.registry.csv`` + module upgrade.

Mounted under ``kctl-odoo report type``.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Annotated

import typer

from kctl_odoo.core.biz_helpers import model_available
from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.exceptions import RPCError

app = typer.Typer(help="Report type registry: create/update report types via CLI (no UI).")


_WRITABLE_FIELDS = (
    "name",
    "code",
    "sequence",
    "active",
    "category",
    "date_mode",
    "column_template",
    "expand_mode",
    "handler_model",
    "dynamic_lines",
    "render_mode",
    "chart_type",
    "chart_config",
    "applicable_display_options",
    "root_type_id",
    "default_drill_route_id",
)

_LIST_FIELDS = (
    "id",
    "code",
    "name",
    "category",
    "date_mode",
    "expand_mode",
    "handler_model",
    "active",
    "is_variant",
    "variant_count",
)


def _require_report_management(c, out) -> bool:
    if not model_available(c, "report.type.registry"):
        out.warn("report.type.registry model not available. Install with: kctl-odoo modules install report_management")
        return False
    return True


def _resolve_type_id(c, code: str) -> int | None:
    ids = c.search("report.type.registry", [("code", "=", code)], limit=1)
    return ids[0] if ids else None


def _parse_kv(pairs: list[str] | None) -> dict:
    """Parse ``--set key=value`` options into a dict. JSON-decodes values when possible.

    Examples:
        --set sequence=30 --set active=true --set chart_config='{"color":"red"}'
    """
    out: dict = {}
    if not pairs:
        return out
    for raw in pairs:
        if "=" not in raw:
            raise typer.BadParameter(f"Expected key=value, got {raw!r}")
        key, _, val = raw.partition("=")
        key = key.strip()
        if key not in _WRITABLE_FIELDS:
            raise typer.BadParameter(f"Unknown field {key!r}. Writable fields: {', '.join(_WRITABLE_FIELDS)}")
        val = val.strip()
        try:
            out[key] = json.loads(val)
        except ValueError:
            out[key] = val
    return out


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------
@app.command("list")
def list_types(
    ctx: typer.Context,
    category: Annotated[
        str | None,
        typer.Option("--category", "-c", help="Filter by category (financial/aging/management/custom)"),
    ] = None,
    handler: Annotated[
        str | None,
        typer.Option("--handler", "-h", help="Filter by handler_model prefix"),
    ] = None,
    active_only: Annotated[
        bool,
        typer.Option("--active-only/--all", help="Hide archived types"),
    ] = True,
) -> None:
    """List report types on the connected tenant."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    if not _require_report_management(c, out):
        raise typer.Exit(1)

    domain: list = []
    if category:
        domain.append(("category", "=", category))
    if handler:
        domain.append(("handler_model", "=like", f"{handler}%"))
    if active_only:
        domain.append(("active", "=", True))

    rows = c.search_read(
        "report.type.registry",
        domain=domain,
        fields=list(_LIST_FIELDS),
        order="category, sequence, name",
    )
    if not rows:
        out.info("No report types found.")
        if actx.json_mode:
            out.raw_json([])
        return

    table_rows = [
        [
            str(r["id"]),
            r.get("code") or "-",
            (r.get("name") or "")[:36],
            r.get("category") or "-",
            r.get("date_mode") or "-",
            r.get("expand_mode") or "-",
            (r.get("handler_model") or "").rsplit(".", 1)[-1][:18],
            "✓" if r.get("active") else "✗",
            "V" if r.get("is_variant") else "",
            str(r.get("variant_count") or "") if r.get("variant_count") else "",
        ]
        for r in rows
    ]
    out.table(
        f"Report Types ({len(rows)})",
        [
            ("ID", "dim"),
            ("Code", "cyan"),
            ("Name", ""),
            ("Cat", ""),
            ("Date", ""),
            ("Expand", ""),
            ("Handler", "dim"),
            ("Act", ""),
            ("Var", "dim"),
            ("#Variants", "dim"),
        ],
        table_rows,
        data_for_json=rows,
    )


# ---------------------------------------------------------------------------
# show
# ---------------------------------------------------------------------------
@app.command("show")
def show_type(
    ctx: typer.Context,
    code: Annotated[str, typer.Argument(help="Report type code")],
) -> None:
    """Show one report type in detail (all fields as JSON)."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    if not _require_report_management(c, out):
        raise typer.Exit(1)

    type_id = _resolve_type_id(c, code)
    if type_id is None:
        out.error(f"Report type not found: {code}")
        raise typer.Exit(1)

    fields = (
        *_LIST_FIELDS,
        "column_template",
        "render_mode",
        "chart_config",
        "applicable_display_options",
        "dynamic_lines",
        "root_type_id",
        "variant_ids",
        "default_drill_route_id",
        "drill_route_ids",
    )
    (rec,) = c.read("report.type.registry", [type_id], list(fields))
    if actx.json_mode:
        out.raw_json(rec)
        return
    print(json.dumps(rec, indent=2, ensure_ascii=False, default=str))


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------
@app.command("create")
def create_type(
    ctx: typer.Context,
    code: Annotated[str, typer.Argument(help="Unique code (e.g. margin_by_product)")],
    name: Annotated[str, typer.Argument(help='Display name (e.g. "Margin Analysis by Product")')],
    category: Annotated[
        str,
        typer.Option("--category", help="financial/aging/management/custom"),
    ] = "custom",
    handler: Annotated[
        str,
        typer.Option("--handler", help="handler_model (model name of the handler class)"),
    ] = "report.handler.base",
    date_mode: Annotated[
        str,
        typer.Option("--date-mode", help="period / cumulative / as_of"),
    ] = "period",
    expand_mode: Annotated[
        str,
        typer.Option("--expand-mode", help="accounts / partners / none"),
    ] = "accounts",
    column_template: Annotated[
        str,
        typer.Option("--columns", help="standard / trial_balance / aging_buckets"),
    ] = "standard",
    dynamic_lines: Annotated[
        bool,
        typer.Option("--dynamic-lines/--no-dynamic-lines"),
    ] = False,
    sequence: Annotated[int, typer.Option("--sequence", help="Menu order")] = 10,
    root: Annotated[
        str | None,
        typer.Option("--root", help="Parent report-type code; creates this as a variant"),
    ] = None,
    set_: Annotated[
        list[str] | None,
        typer.Option("--set", help="Additional fields as key=value (repeatable)"),
    ] = None,
) -> None:
    """Create a new report type.

    Examples:

    \b
        kctl-odoo report type create margin_by_product "Margin by Product" \\
            --handler report.handler.sales --date-mode period --expand-mode none

    \b
        kctl-odoo report type create bs_abridged "Balance Sheet (Abridged)" \\
            --root balance_sheet --category financial \\
            --set applicable_display_options=show_totals_only
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    if not _require_report_management(c, out):
        raise typer.Exit(1)

    if _resolve_type_id(c, code) is not None:
        out.error(f"Report type already exists: {code}. Use `report type update {code}` to modify.")
        raise typer.Exit(1)

    vals: dict = {
        "code": code,
        "name": name,
        "category": category,
        "handler_model": handler,
        "date_mode": date_mode,
        "expand_mode": expand_mode,
        "column_template": column_template,
        "dynamic_lines": dynamic_lines,
        "sequence": sequence,
    }
    if root:
        root_id = _resolve_type_id(c, root)
        if root_id is None:
            out.error(f"Root type not found: {root}")
            raise typer.Exit(1)
        vals["root_type_id"] = root_id
    vals.update(_parse_kv(set_))

    try:
        res = c.execute_kw("report.type.registry", "create", [vals])
    except RPCError as exc:
        out.error(f"Create failed: {exc}")
        raise typer.Exit(1) from exc

    new_id = res[0] if isinstance(res, list) else res
    out.success(f"Created report.type.registry code={code!r} id={new_id}")
    if actx.json_mode:
        out.raw_json({"code": code, "id": new_id})


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------
@app.command("update")
def update_type(
    ctx: typer.Context,
    code: Annotated[str, typer.Argument(help="Report type code to update")],
    set_: Annotated[
        list[str],
        typer.Option("--set", "-s", help="field=value (repeatable). See `show` for writable fields."),
    ],
) -> None:
    """Update fields on a report type.

    Examples:

    \b
        kctl-odoo report type update margin_by_product --set sequence=5 --set active=true
        kctl-odoo report type update pnl --set name='"Profit & Loss (custom)"'
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    if not _require_report_management(c, out):
        raise typer.Exit(1)

    type_id = _resolve_type_id(c, code)
    if type_id is None:
        out.error(f"Report type not found: {code}")
        raise typer.Exit(1)

    vals = _parse_kv(set_)
    if not vals:
        out.error("No fields to update — pass at least one --set key=value.")
        raise typer.Exit(1)

    try:
        c.execute_kw("report.type.registry", "write", [[type_id], vals])
    except RPCError as exc:
        out.error(f"Update failed: {exc}")
        raise typer.Exit(1) from exc

    out.success(f"Updated report.type.registry code={code!r} id={type_id}: {', '.join(vals.keys())}")
    if actx.json_mode:
        out.raw_json({"code": code, "id": type_id, "updated": list(vals.keys())})


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------
@app.command("delete")
def delete_type(
    ctx: typer.Context,
    code: Annotated[str, typer.Argument(help="Report type code to delete")],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation")] = False,
) -> None:
    """Delete a report type by code.

    Blocked if templates reference the type — archive (``--set active=false``)
    those templates first or reassign them.
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    if not _require_report_management(c, out):
        raise typer.Exit(1)

    type_id = _resolve_type_id(c, code)
    if type_id is None:
        out.error(f"Report type not found: {code}")
        raise typer.Exit(1)

    tpl_count = len(c.search("report.template", [("report_type", "=", code)]))
    if tpl_count and not yes:
        out.warn(f"{tpl_count} report.template record(s) reference {code!r}. Pass --yes to force.")
        raise typer.Exit(1)

    if not yes and not typer.confirm(f"Delete report type {code!r}?"):
        raise typer.Exit(0)

    try:
        c.execute_kw("report.type.registry", "unlink", [[type_id]])
    except RPCError as exc:
        out.error(f"Delete failed: {exc}")
        raise typer.Exit(1) from exc

    out.success(f"Deleted report.type.registry code={code!r} id={type_id}")
    if actx.json_mode:
        out.raw_json({"code": code, "id": type_id, "deleted": True})


# ---------------------------------------------------------------------------
# export-csv
# ---------------------------------------------------------------------------
@app.command("export-csv")
def export_csv(
    ctx: typer.Context,
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Output file path (stdout if omitted)"),
    ] = None,
    active_only: Annotated[
        bool,
        typer.Option("--active-only/--all", help="Only export active types"),
    ] = True,
) -> None:
    """Dump the registry as CSV — same schema as ``data/report.type.registry.csv``."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    if not _require_report_management(c, out):
        raise typer.Exit(1)

    domain: list = [("active", "=", True)] if active_only else []
    rows = c.search_read(
        "report.type.registry",
        domain=domain,
        fields=list(_WRITABLE_FIELDS),
        order="category, sequence, name",
    )

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(_WRITABLE_FIELDS), extrasaction="ignore")
    writer.writeheader()
    for r in rows:
        flat = {k: ("" if r.get(k) in (None, False) and k != "active" else r.get(k)) for k in _WRITABLE_FIELDS}
        for k in ("root_type_id", "default_drill_route_id"):
            v = r.get(k)
            flat[k] = v[0] if isinstance(v, list) and v else ""
        if isinstance(flat.get("chart_config"), (dict, list)):
            flat["chart_config"] = json.dumps(flat["chart_config"])
        writer.writerow(flat)

    csv_text = buf.getvalue()
    if output:
        output.write_text(csv_text, encoding="utf-8")
        out.success(f"Wrote {len(rows)} types to {output}")
        if actx.json_mode:
            out.raw_json({"count": len(rows), "file": str(output)})
    else:
        print(csv_text, end="")


# ---------------------------------------------------------------------------
# handlers — convenience listing
# ---------------------------------------------------------------------------
@app.command("handlers")
def list_handlers(ctx: typer.Context) -> None:
    """List every model with name prefix ``report.handler.*`` (available handler classes)."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    if not _require_report_management(c, out):
        raise typer.Exit(1)

    rows = c.search_read(
        "ir.model",
        domain=[("model", "=like", "report.handler.%")],
        fields=["id", "model", "name"],
        order="model",
    )
    if not rows:
        out.info("No handler models found.")
        return
    out.table(
        f"Available handlers ({len(rows)})",
        [("Model", "cyan"), ("Name", "")],
        [[r["model"], r.get("name") or "-"] for r in rows],
        data_for_json=rows,
    )
