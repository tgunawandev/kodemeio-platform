"""Report drill-route CRUD (cross-report drill edges).

Wraps the ``report.type.drill.route`` model — declares where a click on a
row in one report type navigates: another report type, a list view, or an
``ir.actions.act_window`` xmlid. Lets operators wire inter-report navigation
without XML data + module upgrade.

Mounted under ``kctl-odoo report drill-route``.
"""

from __future__ import annotations

import json
from typing import Annotated

import typer

from kctl_odoo.core.biz_helpers import model_available
from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.exceptions import RPCError

app = typer.Typer(help="Report drill-route (cross-report navigation) CRUD.")


_WRITABLE = (
    "name",
    "sequence",
    "source_type_id",
    "target_kind",
    "target_type_id",
    "target_model",
    "target_action",
    "param_map",
    "domain_override",
    "applies_to_row_kind",
)


def _require_module(c, out) -> bool:
    if not model_available(c, "report.type.drill.route"):
        out.warn("report.type.drill.route not available. Install: kctl-odoo modules install report_management")
        return False
    return True


def _resolve_type_id(c, code: str) -> int | None:
    ids = c.search("report.type.registry", [("code", "=", code)], limit=1)
    return ids[0] if ids else None


def _resolve_route_id(c, source_code: str, name: str) -> int | None:
    src_id = _resolve_type_id(c, source_code)
    if src_id is None:
        return None
    ids = c.search(
        "report.type.drill.route",
        [("source_type_id", "=", src_id), ("name", "=", name)],
        limit=1,
    )
    return ids[0] if ids else None


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
def list_routes(
    ctx: typer.Context,
    source: Annotated[
        str | None,
        typer.Option("--source", "-s", help="Filter by source report-type code"),
    ] = None,
) -> None:
    """List drill routes."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    if not _require_module(c, out):
        raise typer.Exit(1)

    domain: list = []
    if source:
        src_id = _resolve_type_id(c, source)
        if src_id is None:
            out.error(f"Source report type not found: {source}")
            raise typer.Exit(1)
        domain.append(("source_type_id", "=", src_id))

    rows = c.search_read(
        "report.type.drill.route",
        domain=domain,
        fields=[
            "id",
            "name",
            "sequence",
            "source_type_id",
            "target_kind",
            "target_type_id",
            "target_model",
            "target_action",
            "applies_to_row_kind",
        ],
        order="source_type_id, sequence",
    )
    if not rows:
        out.info("No drill routes found.")
        if actx.json_mode:
            out.raw_json([])
        return

    table_rows = [
        [
            str(r["id"]),
            (r["source_type_id"][1] if isinstance(r.get("source_type_id"), list) else "-"),
            (r.get("name") or "")[:28],
            r.get("target_kind") or "-",
            (
                (r["target_type_id"][1] if isinstance(r.get("target_type_id"), list) else "-")
                if r.get("target_kind") == "report"
                else (r.get("target_model") or "-")
            ),
            r.get("applies_to_row_kind") or "-",
            str(r.get("sequence") or ""),
        ]
        for r in rows
    ]
    out.table(
        f"Drill Routes ({len(rows)})",
        [
            ("ID", "dim"),
            ("Source", "cyan"),
            ("Name", ""),
            ("Kind", ""),
            ("Target", ""),
            ("Rows", ""),
            ("Seq", "dim"),
        ],
        table_rows,
        data_for_json=rows,
    )


# ---------------------------------------------------------------------------
# show
# ---------------------------------------------------------------------------
@app.command("show")
def show_route(
    ctx: typer.Context,
    source: Annotated[str, typer.Argument(help="Source report-type code")],
    name: Annotated[str, typer.Argument(help="Route name")],
) -> None:
    """Show one drill route in detail."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    if not _require_module(c, out):
        raise typer.Exit(1)

    rid = _resolve_route_id(c, source, name)
    if rid is None:
        out.error(f"Route not found: source={source} name={name}")
        raise typer.Exit(1)
    (rec,) = c.read(
        "report.type.drill.route",
        [rid],
        [
            "id",
            "name",
            "sequence",
            "source_type_id",
            "target_kind",
            "target_type_id",
            "target_model",
            "target_action",
            "param_map",
            "domain_override",
            "applies_to_row_kind",
        ],
    )
    if actx.json_mode:
        out.raw_json(rec)
        return
    print(json.dumps(rec, indent=2, ensure_ascii=False, default=str))


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------
@app.command("create")
def create_route(
    ctx: typer.Context,
    source: Annotated[str, typer.Argument(help="Source report-type code")],
    name: Annotated[str, typer.Argument(help="Route name (unique per source)")],
    kind: Annotated[
        str,
        typer.Option("--kind", help="report / list"),
    ] = "report",
    target_type: Annotated[
        str | None,
        typer.Option("--target-type", help="Target report-type code (when --kind=report)"),
    ] = None,
    target_model: Annotated[
        str | None,
        typer.Option("--target-model", help="Target model (when --kind=list), e.g. 'account.move.line'"),
    ] = None,
    target_action: Annotated[
        str | None,
        typer.Option("--action", help="Optional ir.actions.act_window xmlid override"),
    ] = None,
    param_map: Annotated[
        str,
        typer.Option("--params", help='JSON mapping of drill_context keys, e.g. \'{"account_ids":"account_id"}\''),
    ] = "{}",
    applies_to: Annotated[
        str,
        typer.Option("--applies-to", help="any / line / subtotal / header"),
    ] = "line",
    sequence: Annotated[int, typer.Option("--sequence", help="Route priority (lower first)")] = 10,
) -> None:
    """Create a new drill route.

    Examples:

    \b
        # P&L -> journal items list
        kctl-odoo report drill-route create profit_loss "P&L to JE" \\
            --kind list --target-model account.move.line \\
            --params '{"account_ids":"account_id","date_from":"date_from","date_to":"date_to"}'

    \b
        # Balance Sheet -> Trial Balance (drill to another report)
        kctl-odoo report drill-route create balance_sheet "BS to TB" \\
            --kind report --target-type trial_balance
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    if not _require_module(c, out):
        raise typer.Exit(1)

    src_id = _resolve_type_id(c, source)
    if src_id is None:
        out.error(f"Source report type not found: {source}")
        raise typer.Exit(1)

    if _resolve_route_id(c, source, name) is not None:
        out.error(f"Route already exists: source={source} name={name}. Use `update` to modify.")
        raise typer.Exit(1)

    vals: dict = {
        "source_type_id": src_id,
        "name": name,
        "target_kind": kind,
        "applies_to_row_kind": applies_to,
        "sequence": sequence,
        "param_map": param_map,
    }
    if kind == "report":
        if not target_type:
            out.error("--target-type is required when --kind=report")
            raise typer.Exit(1)
        tgt_id = _resolve_type_id(c, target_type)
        if tgt_id is None:
            out.error(f"Target report type not found: {target_type}")
            raise typer.Exit(1)
        vals["target_type_id"] = tgt_id
    else:  # list
        if not target_model:
            out.error("--target-model is required when --kind=list")
            raise typer.Exit(1)
        vals["target_model"] = target_model
        if target_action:
            vals["target_action"] = target_action

    try:
        res = c.execute_kw("report.type.drill.route", "create", [vals])
    except RPCError as exc:
        out.error(f"Create failed: {exc}")
        raise typer.Exit(1) from exc
    new_id = res[0] if isinstance(res, list) else res
    out.success(f"Created report.type.drill.route source={source} name={name!r} id={new_id}")
    if actx.json_mode:
        out.raw_json({"source": source, "name": name, "id": new_id})


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------
@app.command("update")
def update_route(
    ctx: typer.Context,
    source: Annotated[str, typer.Argument(help="Source report-type code")],
    name: Annotated[str, typer.Argument(help="Route name")],
    set_: Annotated[
        list[str],
        typer.Option("--set", "-s", help="field=value (repeatable)"),
    ],
) -> None:
    """Update fields on a drill route."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    if not _require_module(c, out):
        raise typer.Exit(1)

    rid = _resolve_route_id(c, source, name)
    if rid is None:
        out.error(f"Route not found: source={source} name={name}")
        raise typer.Exit(1)

    vals = _parse_kv(set_)
    if not vals:
        out.error("No fields to update.")
        raise typer.Exit(1)

    try:
        c.execute_kw("report.type.drill.route", "write", [[rid], vals])
    except RPCError as exc:
        out.error(f"Update failed: {exc}")
        raise typer.Exit(1) from exc
    out.success(f"Updated report.type.drill.route id={rid}: {', '.join(vals.keys())}")
    if actx.json_mode:
        out.raw_json({"id": rid, "updated": list(vals.keys())})


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------
@app.command("delete")
def delete_route(
    ctx: typer.Context,
    source: Annotated[str, typer.Argument(help="Source report-type code")],
    name: Annotated[str, typer.Argument(help="Route name")],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation")] = False,
) -> None:
    """Delete a drill route."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client
    if not _require_module(c, out):
        raise typer.Exit(1)

    rid = _resolve_route_id(c, source, name)
    if rid is None:
        out.error(f"Route not found: source={source} name={name}")
        raise typer.Exit(1)

    if not yes and not typer.confirm(f"Delete route {source!r}/{name!r}?"):
        raise typer.Exit(0)

    c.execute_kw("report.type.drill.route", "unlink", [[rid]])
    out.success(f"Deleted report.type.drill.route source={source} name={name!r}")
    if actx.json_mode:
        out.raw_json({"source": source, "name": name, "id": rid, "deleted": True})
