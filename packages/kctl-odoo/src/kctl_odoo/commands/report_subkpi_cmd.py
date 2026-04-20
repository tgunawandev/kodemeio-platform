"""Report subkpi (formula column) CRUD.

Wraps the ``report.subkpi`` model — declarative formula columns that get
evaluated against each row's existing numeric values (e.g. Variance %,
Budget/Actual ratio). Lets operators add, modify, or drop formula columns
on a template without UI clicks.

Mounted under ``kctl-odoo report subkpi``.
"""

from __future__ import annotations

import json
from typing import Annotated

import typer

from kctl_odoo.core.biz_helpers import model_available
from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.exceptions import RPCError

app = typer.Typer(help="Report formula-column (subkpi) CRUD.")


_WRITABLE = ("name", "code", "formula", "display_format", "sequence")


def _require_module(c, out) -> bool:
    if not model_available(c, "report.subkpi"):
        out.warn("report.subkpi not available. Install: kctl-odoo modules install report_management")
        return False
    return True


def _resolve_template_id(c, template_code: str) -> int | None:
    ids = c.search("report.template", [("code", "=", template_code)], limit=1)
    return ids[0] if ids else None


def _resolve_subkpi_id(c, template_code: str, subkpi_code: str) -> tuple[int | None, int | None]:
    tpl_id = _resolve_template_id(c, template_code)
    if tpl_id is None:
        return None, None
    ids = c.search("report.subkpi", [("template_id", "=", tpl_id), ("code", "=", subkpi_code)], limit=1)
    return tpl_id, (ids[0] if ids else None)


def _parse_kv(pairs: list[str] | None) -> dict:
    out: dict = {}
    for raw in pairs or []:
        if "=" not in raw:
            raise typer.BadParameter(f"Expected key=value, got {raw!r}")
        key, _, val = raw.partition("=")
        key = key.strip()
        if key not in _WRITABLE:
            raise typer.BadParameter(f"Unknown field {key!r}. Writable: {', '.join(_WRITABLE)}")
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
def list_subkpis(
    ctx: typer.Context,
    template: Annotated[
        str | None,
        typer.Option("--template", "-t", help="Filter by template code"),
    ] = None,
) -> None:
    """List subkpi (formula) columns, optionally filtered by template code."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    if not _require_module(c, out):
        raise typer.Exit(1)

    domain: list = []
    if template:
        tpl_id = _resolve_template_id(c, template)
        if tpl_id is None:
            out.error(f"Template not found: {template}")
            raise typer.Exit(1)
        domain.append(("template_id", "=", tpl_id))

    rows = c.search_read(
        "report.subkpi",
        domain=domain,
        fields=["id", "template_id", "name", "code", "formula", "display_format", "sequence"],
        order="template_id, sequence, id",
    )
    if not rows:
        out.info("No subkpis found.")
        if actx.json_mode:
            out.raw_json([])
        return

    table_rows = [
        [
            str(r["id"]),
            (r["template_id"][1] if isinstance(r.get("template_id"), list) else "-"),
            r.get("code") or "-",
            (r.get("name") or "")[:28],
            (r.get("formula") or "")[:40],
            r.get("display_format") or "-",
            str(r.get("sequence") or ""),
        ]
        for r in rows
    ]
    out.table(
        f"SubKPIs ({len(rows)})",
        [
            ("ID", "dim"),
            ("Template", "cyan"),
            ("Code", "cyan"),
            ("Name", ""),
            ("Formula", ""),
            ("Format", ""),
            ("Seq", "dim"),
        ],
        table_rows,
        data_for_json=rows,
    )


# ---------------------------------------------------------------------------
# show
# ---------------------------------------------------------------------------
@app.command("show")
def show_subkpi(
    ctx: typer.Context,
    template: Annotated[str, typer.Argument(help="Template code")],
    code: Annotated[str, typer.Argument(help="SubKPI code within the template")],
) -> None:
    """Show one subkpi in detail."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    if not _require_module(c, out):
        raise typer.Exit(1)

    _, sub_id = _resolve_subkpi_id(c, template, code)
    if sub_id is None:
        out.error(f"SubKPI not found: template={template} code={code}")
        raise typer.Exit(1)
    (rec,) = c.read(
        "report.subkpi",
        [sub_id],
        ["id", "template_id", "name", "code", "formula", "display_format", "sequence"],
    )
    if actx.json_mode:
        out.raw_json(rec)
        return
    print(json.dumps(rec, indent=2, ensure_ascii=False, default=str))


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------
@app.command("create")
def create_subkpi(
    ctx: typer.Context,
    template: Annotated[str, typer.Argument(help="Template code the subkpi belongs to")],
    code: Annotated[str, typer.Argument(help="Column key (unique within the template)")],
    name: Annotated[str, typer.Argument(help='Display header (e.g. "Variance %")')],
    formula: Annotated[str, typer.Argument(help='Python expr over row cols, e.g. "(actual-budget)/budget*100"')],
    display_format: Annotated[
        str,
        typer.Option("--format", help="number / percent / ratio"),
    ] = "number",
    sequence: Annotated[int, typer.Option("--sequence", help="Column order (lower = leftmost)")] = 10,
) -> None:
    """Create a new subkpi (formula column) on a template.

    Example:

    \b
        kctl-odoo report subkpi create pnl_management var_pct "Variance %" \\
            "(actual - budget) / budget * 100 if budget else 0" \\
            --format percent

    The server-side engine renders the formula with a sandboxed safe_eval;
    if it fails (NameError on an unknown column, ZeroDivisionError, etc.)
    the row shows an em-dash instead of crashing the report.
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    if not _require_module(c, out):
        raise typer.Exit(1)

    tpl_id = _resolve_template_id(c, template)
    if tpl_id is None:
        out.error(f"Template not found: {template}")
        raise typer.Exit(1)

    existing = c.search("report.subkpi", [("template_id", "=", tpl_id), ("code", "=", code)], limit=1)
    if existing:
        out.error(f"SubKPI already exists: template={template} code={code}. Use `update` to modify.")
        raise typer.Exit(1)

    vals = {
        "template_id": tpl_id,
        "code": code,
        "name": name,
        "formula": formula,
        "display_format": display_format,
        "sequence": sequence,
    }
    try:
        res = c.execute_kw("report.subkpi", "create", [vals])
    except RPCError as exc:
        out.error(f"Create failed: {exc}")
        raise typer.Exit(1) from exc
    new_id = res[0] if isinstance(res, list) else res
    out.success(f"Created report.subkpi template={template} code={code!r} id={new_id}")
    if actx.json_mode:
        out.raw_json({"template": template, "code": code, "id": new_id})


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------
@app.command("update")
def update_subkpi(
    ctx: typer.Context,
    template: Annotated[str, typer.Argument(help="Template code")],
    code: Annotated[str, typer.Argument(help="SubKPI code")],
    set_: Annotated[
        list[str],
        typer.Option("--set", "-s", help="field=value (repeatable)"),
    ],
) -> None:
    """Update fields on a subkpi.

    Example:

    \b
        kctl-odoo report subkpi update pnl_management var_pct \\
            --set sequence=5 --set 'formula="(actual-prior_year)/prior_year*100"'
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    if not _require_module(c, out):
        raise typer.Exit(1)

    _, sub_id = _resolve_subkpi_id(c, template, code)
    if sub_id is None:
        out.error(f"SubKPI not found: template={template} code={code}")
        raise typer.Exit(1)

    vals = _parse_kv(set_)
    if not vals:
        out.error("No fields to update.")
        raise typer.Exit(1)

    try:
        c.execute_kw("report.subkpi", "write", [[sub_id], vals])
    except RPCError as exc:
        out.error(f"Update failed: {exc}")
        raise typer.Exit(1) from exc
    out.success(f"Updated report.subkpi id={sub_id}: {', '.join(vals.keys())}")
    if actx.json_mode:
        out.raw_json({"id": sub_id, "updated": list(vals.keys())})


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------
@app.command("delete")
def delete_subkpi(
    ctx: typer.Context,
    template: Annotated[str, typer.Argument(help="Template code")],
    code: Annotated[str, typer.Argument(help="SubKPI code")],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation")] = False,
) -> None:
    """Delete a subkpi column."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    if not _require_module(c, out):
        raise typer.Exit(1)

    _, sub_id = _resolve_subkpi_id(c, template, code)
    if sub_id is None:
        out.error(f"SubKPI not found: template={template} code={code}")
        raise typer.Exit(1)

    if not yes and not typer.confirm(f"Delete subkpi {template}/{code}?"):
        raise typer.Exit(0)

    c.execute_kw("report.subkpi", "unlink", [[sub_id]])
    out.success(f"Deleted report.subkpi template={template} code={code!r}")
    if actx.json_mode:
        out.raw_json({"template": template, "code": code, "id": sub_id, "deleted": True})
