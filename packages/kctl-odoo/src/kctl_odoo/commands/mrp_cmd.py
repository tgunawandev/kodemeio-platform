"""Manufacturing operations commands — production orders, BOMs, work centers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

import typer

from kctl_odoo.core.biz_helpers import model_available
from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.exceptions import RPCError
from kctl_odoo.core.field_helpers import safe_fields

app = typer.Typer(help="Manufacturing: production orders, BOMs, work centers.")

_MRP_MODEL = "mrp.production"
_MRP_HINT = "Manufacturing module (mrp) is not installed."


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _m2o_name(val: object) -> str:
    """Extract display name from an M2O field value ([id, name] or False)."""
    if isinstance(val, list):
        return str(val[1])
    return str(val or "")


def _resolve(c: object, model: str, field: str, value: str, label: str) -> tuple[int, str]:
    """Resolve a record by numeric ID or name search.

    Returns (id, display_name).  Raises ``typer.BadParameter`` when not found.
    """
    if value.isdigit():
        recs = c.read(model, [int(value)], ["id", "display_name"])  # type: ignore[attr-defined]
    else:
        recs = c.search_read(  # type: ignore[attr-defined]
            model, [(field, "=", value)], ["id", "display_name"], limit=1
        )
    if not recs:
        raise typer.BadParameter(f"{label} not found: {value}")
    return recs[0]["id"], recs[0].get("display_name", str(recs[0]["id"]))


# ===================================================================
# SUMMARY / DASHBOARD
# ===================================================================


@app.command("summary")
def summary(
    ctx: typer.Context,
) -> None:
    """Manufacturing dashboard — MOs by state count.

    Examples:
        kctl-odoo mrp summary
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _MRP_MODEL):
        out.warn(_MRP_HINT)
        return

    states = ["draft", "confirmed", "progress", "to_close", "done", "cancel"]
    state_labels = {
        "draft": "Draft",
        "confirmed": "Confirmed",
        "progress": "In Progress",
        "to_close": "To Close",
        "done": "Done",
        "cancel": "Cancelled",
    }

    try:
        groups = c.read_group(  # type: ignore[attr-defined]
            _MRP_MODEL,
            domain=[],
            fields=["state"],
            groupby=["state"],
        )
    except RPCError as e:
        out.error(f"Failed to fetch MO summary: {e}")
        raise typer.Exit(1) from e

    buckets: dict[str, int] = {}
    for g in groups:
        st = g.get("state", "unknown")
        buckets[st] = g.get("state_count", g.get("__count", 0))

    total = sum(buckets.values())

    rows = []
    json_data: list[dict] = []
    for st in states:
        count = buckets.get(st, 0)
        if count == 0:
            continue
        rows.append([state_labels.get(st, st), str(count)])
        json_data.append({"state": st, "label": state_labels.get(st, st), "count": count})

    rows.append(["[bold]Total[/bold]", f"[bold]{total}[/bold]"])
    json_data.append({"state": "total", "label": "Total", "count": total})

    out.table(
        "Manufacturing Summary",
        [("State", ""), ("Count", "cyan")],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# LIST ORDERS
# ===================================================================


@app.command("orders")
def orders(
    ctx: typer.Context,
    state: Annotated[
        str | None,
        typer.Option("--state", "-s", help="Filter by state: draft, confirmed, progress, done, cancel"),
    ] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List manufacturing orders with key fields.

    Examples:
        kctl-odoo mrp orders
        kctl-odoo mrp orders --state confirmed --limit 20
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _MRP_MODEL):
        out.warn(_MRP_HINT)
        return

    domain: list = []
    if state:
        domain.append(("state", "=", state))

    try:
        records = c.search_read(
            _MRP_MODEL,
            domain=domain,
            fields=["name", "product_id", "product_qty", "state", "date_start"],
            limit=limit,
            order="date_start desc",
        )
    except RPCError as e:
        out.error(f"Failed to list manufacturing orders: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.info("No manufacturing orders found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for r in records:
        rows.append(
            [
                r["name"],
                _m2o_name(r.get("product_id")),
                str(r.get("product_qty", 0)),
                r.get("state", ""),
                str(r.get("date_start", "")),
            ]
        )
        json_data.append(
            {
                "name": r["name"],
                "product": _m2o_name(r.get("product_id")),
                "product_qty": r.get("product_qty", 0),
                "state": r.get("state"),
                "date_start": r.get("date_start"),
            }
        )

    out.table(
        f"Manufacturing Orders ({len(records)})",
        [
            ("Name", "cyan"),
            ("Product", ""),
            ("Qty", ""),
            ("State", ""),
            ("Date Start", "dim"),
        ],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# GET ORDER DETAIL
# ===================================================================


@app.command("get-order")
def get_order(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="MO name (e.g. WH/MO/00001) or numeric ID")],
) -> None:
    """Get manufacturing order detail by name or ID.

    Shows header information and component lines (move_raw_ids).

    Examples:
        kctl-odoo mrp get-order WH/MO/00001
        kctl-odoo mrp get-order 42
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _MRP_MODEL):
        out.warn(_MRP_HINT)
        return

    domain = [("id", "=", int(name))] if name.isdigit() else [("name", "=", name)]

    try:
        records = c.search_read(
            _MRP_MODEL,
            domain=domain,
            fields=[
                "name",
                "product_id",
                "product_qty",
                "state",
                "date_start",
                "date_finished",
                "bom_id",
                "workcenter_id",
                "move_raw_ids",
            ],
            limit=1,
        )
    except RPCError as e:
        out.error(f"Failed to fetch MO: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.error(f"Manufacturing order not found: {name}")
        raise typer.Exit(1)

    rec = records[0]

    header_sections = [
        (
            "Manufacturing Order",
            [
                ("Name", rec["name"]),
                ("Product", _m2o_name(rec.get("product_id"))),
                ("Qty", str(rec.get("product_qty", 0))),
                ("State", rec.get("state", "")),
                ("Date Start", str(rec.get("date_start", ""))),
                ("Date Finished", str(rec.get("date_finished", ""))),
                ("BOM", _m2o_name(rec.get("bom_id"))),
                ("Work Center", _m2o_name(rec.get("workcenter_id"))),
            ],
        )
    ]

    json_result: dict = {
        "name": rec["name"],
        "product": _m2o_name(rec.get("product_id")),
        "product_qty": rec.get("product_qty", 0),
        "state": rec.get("state"),
        "date_start": rec.get("date_start"),
        "date_finished": rec.get("date_finished"),
        "bom": _m2o_name(rec.get("bom_id")),
        "components": [],
    }

    out.detail("Manufacturing Order Detail", header_sections, data_for_json=json_result)

    # Components (move_raw_ids)
    move_ids = rec.get("move_raw_ids", [])
    if move_ids:
        try:
            moves = c.read(
                "stock.move",
                move_ids,
                ["product_id", "product_uom_qty", "quantity", "state"],
            )
        except RPCError as e:
            out.warn(f"Failed to read components: {e}")
            return

        rows = []
        components_json = []
        for mv in moves:
            rows.append(
                [
                    _m2o_name(mv.get("product_id")),
                    str(mv.get("product_uom_qty", 0)),
                    str(mv.get("quantity", 0)),
                    mv.get("state", ""),
                ]
            )
            components_json.append(
                {
                    "product": _m2o_name(mv.get("product_id")),
                    "demand": mv.get("product_uom_qty", 0),
                    "done": mv.get("quantity", 0),
                    "state": mv.get("state"),
                }
            )

        json_result["components"] = components_json

        out.table(
            "Components",
            [("Product", ""), ("Demand", ""), ("Done", ""), ("State", "")],
            rows,
            data_for_json=components_json,
        )


# ===================================================================
# LIST BOMS
# ===================================================================


@app.command("boms")
def boms(
    ctx: typer.Context,
    product: Annotated[str | None, typer.Option("--product", help="Filter by product name")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List bills of materials.

    Examples:
        kctl-odoo mrp boms
        kctl-odoo mrp boms --product "Finished Goods"
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, "mrp.bom"):
        out.warn(_MRP_HINT)
        return

    domain: list = []
    if product:
        domain.append(("product_tmpl_id.name", "ilike", product))

    try:
        records = c.search_read(
            "mrp.bom",
            domain=domain,
            fields=["product_tmpl_id", "product_qty", "type", "code"],
            limit=limit,
        )
    except RPCError as e:
        out.error(f"Failed to list BOMs: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.info("No BOMs found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for r in records:
        rows.append(
            [
                str(r["id"]),
                _m2o_name(r.get("product_tmpl_id")),
                str(r.get("product_qty", 0)),
                r.get("type", ""),
                str(r.get("code", "")),
            ]
        )
        json_data.append(
            {
                "id": r["id"],
                "product": _m2o_name(r.get("product_tmpl_id")),
                "product_qty": r.get("product_qty", 0),
                "type": r.get("type"),
                "code": r.get("code"),
            }
        )

    out.table(
        f"Bills of Materials ({len(records)})",
        [
            ("ID", "dim"),
            ("Product", "cyan"),
            ("Qty", ""),
            ("Type", ""),
            ("Code", "dim"),
        ],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# BOM DETAIL
# ===================================================================


@app.command("bom-detail")
def bom_detail(
    ctx: typer.Context,
    bom_id: Annotated[int, typer.Argument(help="BOM ID")],
) -> None:
    """Show BOM detail with component lines.

    Examples:
        kctl-odoo mrp bom-detail 5
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, "mrp.bom"):
        out.warn(_MRP_HINT)
        return

    try:
        records = c.read(
            "mrp.bom",
            [bom_id],
            ["product_tmpl_id", "product_qty", "type", "code", "bom_line_ids"],
        )
    except RPCError as e:
        out.error(f"Failed to fetch BOM {bom_id}: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.error(f"BOM not found: {bom_id}")
        raise typer.Exit(1)

    rec = records[0]

    header_sections = [
        (
            "Bill of Materials",
            [
                ("ID", str(rec["id"])),
                ("Product", _m2o_name(rec.get("product_tmpl_id"))),
                ("Qty", str(rec.get("product_qty", 0))),
                ("Type", rec.get("type", "")),
                ("Code", str(rec.get("code", ""))),
            ],
        )
    ]

    json_result: dict = {
        "id": rec["id"],
        "product": _m2o_name(rec.get("product_tmpl_id")),
        "product_qty": rec.get("product_qty", 0),
        "type": rec.get("type"),
        "code": rec.get("code"),
        "lines": [],
    }

    out.detail("BOM Detail", header_sections, data_for_json=json_result)

    line_ids = rec.get("bom_line_ids", [])
    if line_ids:
        try:
            lines = c.read(
                "mrp.bom.line",
                line_ids,
                ["product_id", "product_qty", "product_uom_id"],
            )
        except RPCError as e:
            out.warn(f"Failed to read BOM lines: {e}")
            return

        rows = []
        lines_json = []
        for ln in lines:
            rows.append(
                [
                    _m2o_name(ln.get("product_id")),
                    str(ln.get("product_qty", 0)),
                    _m2o_name(ln.get("product_uom_id")),
                ]
            )
            lines_json.append(
                {
                    "product": _m2o_name(ln.get("product_id")),
                    "qty": ln.get("product_qty", 0),
                    "uom": _m2o_name(ln.get("product_uom_id")),
                }
            )

        json_result["lines"] = lines_json

        out.table(
            "BOM Lines",
            [("Product", ""), ("Qty", ""), ("UoM", "dim")],
            rows,
            data_for_json=lines_json,
        )


# ===================================================================
# WORK CENTERS
# ===================================================================


@app.command("workcenters")
def workcenters(
    ctx: typer.Context,
) -> None:
    """List work centers.

    Examples:
        kctl-odoo mrp workcenters
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, "mrp.workcenter"):
        out.warn(_MRP_HINT)
        return

    try:
        records = c.search_read(
            "mrp.workcenter",
            domain=[],
            fields=["name", "code", "active", "time_efficiency", "capacity"],
        )
    except RPCError as e:
        out.error(f"Failed to list work centers: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.info("No work centers found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for r in records:
        rows.append(
            [
                r.get("name", ""),
                str(r.get("code", "")),
                "Yes" if r.get("active") else "No",
                f"{r.get('time_efficiency', 100):.0f}%",
                str(r.get("capacity", 1)),
            ]
        )
        json_data.append(
            {
                "name": r.get("name"),
                "code": r.get("code"),
                "active": r.get("active"),
                "time_efficiency": r.get("time_efficiency"),
                "capacity": r.get("capacity"),
            }
        )

    out.table(
        f"Work Centers ({len(records)})",
        [
            ("Name", "cyan"),
            ("Code", "dim"),
            ("Active", ""),
            ("Efficiency", ""),
            ("Capacity", ""),
        ],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# WORK ORDERS
# ===================================================================


@app.command("workorders")
def workorders(
    ctx: typer.Context,
    state: Annotated[
        str | None,
        typer.Option("--state", "-s", help="Filter by state: pending, ready, progress, done, cancel"),
    ] = None,
    workcenter: Annotated[str | None, typer.Option("--workcenter", help="Filter by work center name")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List work orders.

    Examples:
        kctl-odoo mrp workorders
        kctl-odoo mrp workorders --state ready
        kctl-odoo mrp workorders --workcenter "Assembly"
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, "mrp.workorder"):
        out.warn(_MRP_HINT)
        return

    domain: list = []
    if state:
        domain.append(("state", "=", state))
    if workcenter:
        domain.append(("workcenter_id.name", "ilike", workcenter))

    try:
        records = c.search_read(
            "mrp.workorder",
            domain=domain,
            fields=["name", "production_id", "workcenter_id", "state", "duration"],
            limit=limit,
            order="id desc",
        )
    except RPCError as e:
        out.error(f"Failed to list work orders: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.info("No work orders found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for r in records:
        rows.append(
            [
                r.get("name", ""),
                _m2o_name(r.get("production_id")),
                _m2o_name(r.get("workcenter_id")),
                r.get("state", ""),
                f"{r.get('duration', 0):.1f}",
            ]
        )
        json_data.append(
            {
                "name": r.get("name"),
                "production": _m2o_name(r.get("production_id")),
                "workcenter": _m2o_name(r.get("workcenter_id")),
                "state": r.get("state"),
                "duration": r.get("duration", 0),
            }
        )

    out.table(
        f"Work Orders ({len(records)})",
        [
            ("Name", "cyan"),
            ("MO", ""),
            ("Work Center", ""),
            ("State", ""),
            ("Duration (min)", "dim"),
        ],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# PLANNING
# ===================================================================


@app.command("planning")
def planning(
    ctx: typer.Context,
    days: Annotated[int, typer.Option("--days", help="Upcoming days window")] = 7,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """Upcoming manufacturing orders (confirmed or in progress) by scheduled date.

    Examples:
        kctl-odoo mrp planning
        kctl-odoo mrp planning --days 14
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _MRP_MODEL):
        out.warn(_MRP_HINT)
        return

    now = datetime.now(tz=UTC)
    cutoff = (now + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

    domain: list = [
        ("state", "in", ["confirmed", "progress"]),
        ("date_start", "!=", False),
        ("date_start", "<=", cutoff),
    ]

    try:
        records = c.search_read(
            _MRP_MODEL,
            domain=domain,
            fields=["name", "product_id", "product_qty", "state", "date_start"],
            limit=limit,
            order="date_start asc",
        )
    except RPCError as e:
        out.error(f"Failed to fetch planning: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.info(f"No upcoming MOs in the next {days} day(s).")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for r in records:
        rows.append(
            [
                r["name"],
                _m2o_name(r.get("product_id")),
                str(r.get("product_qty", 0)),
                r.get("state", ""),
                str(r.get("date_start", "")),
            ]
        )
        json_data.append(
            {
                "name": r["name"],
                "product": _m2o_name(r.get("product_id")),
                "product_qty": r.get("product_qty", 0),
                "state": r.get("state"),
                "date_start": r.get("date_start"),
            }
        )

    out.table(
        f"Upcoming MOs — next {days} day(s) ({len(records)})",
        [
            ("Name", "cyan"),
            ("Product", ""),
            ("Qty", ""),
            ("State", ""),
            ("Date Start", "dim"),
        ],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# STUCK ORDERS
# ===================================================================


@app.command("stuck")
def stuck(
    ctx: typer.Context,
    days: Annotated[int, typer.Option("--days", help="Threshold: MOs started more than N days ago")] = 7,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """Manufacturing orders stuck beyond threshold (confirmed/in progress, overdue).

    Examples:
        kctl-odoo mrp stuck
        kctl-odoo mrp stuck --days 14
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _MRP_MODEL):
        out.warn(_MRP_HINT)
        return

    now = datetime.now(tz=UTC)
    cutoff = (now - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

    domain: list = [
        ("state", "in", ["confirmed", "progress"]),
        ("date_start", "!=", False),
        ("date_start", "<", cutoff),
    ]

    try:
        records = c.search_read(
            _MRP_MODEL,
            domain=domain,
            fields=["name", "product_id", "product_qty", "state", "date_start"],
            limit=limit,
            order="date_start asc",
        )
    except RPCError as e:
        out.error(f"Failed to fetch stuck MOs: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.info(f"No stuck MOs found (>{days} days).")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for r in records:
        rows.append(
            [
                r["name"],
                _m2o_name(r.get("product_id")),
                str(r.get("product_qty", 0)),
                r.get("state", ""),
                str(r.get("date_start", "")),
            ]
        )
        json_data.append(
            {
                "name": r["name"],
                "product": _m2o_name(r.get("product_id")),
                "product_qty": r.get("product_qty", 0),
                "state": r.get("state"),
                "date_start": r.get("date_start"),
            }
        )

    out.table(
        f"Stuck MOs (>{days} days) — {len(records)} found",
        [
            ("Name", "cyan"),
            ("Product", ""),
            ("Qty", ""),
            ("State", ""),
            ("Date Start", "dim"),
        ],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# CONFIRM MO
# ===================================================================


@app.command("confirm")
def confirm(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="MO name (e.g. WH/MO/00001) or numeric ID")],
    force: Annotated[bool, typer.Option("--force", "-y", help="Skip confirmation prompt")] = False,
) -> None:
    """Confirm a draft manufacturing order.

    Examples:
        kctl-odoo mrp confirm WH/MO/00001
        kctl-odoo mrp confirm WH/MO/00001 --force
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _MRP_MODEL):
        out.warn(_MRP_HINT)
        return

    try:
        mo_id, mo_display = _resolve(c, _MRP_MODEL, "name", name, "MO")
    except typer.BadParameter as e:
        out.error(str(e))
        raise typer.Exit(1) from e

    if not force and not typer.confirm(f"Confirm MO {mo_display}?"):
        raise typer.Exit(0)

    try:
        c.execute_kw(_MRP_MODEL, "button_confirm", [[mo_id]])  # type: ignore[attr-defined]
    except RPCError as e:
        out.error(f"Failed to confirm {mo_display}: {e}")
        raise typer.Exit(1) from e

    out.success(f"Confirmed MO {mo_display}")

    if actx.json_mode:
        out.raw_json({"id": mo_id, "name": mo_display, "action": "confirmed"})


# ===================================================================
# MARK MO DONE
# ===================================================================


@app.command("done")
def done(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="MO name (e.g. WH/MO/00001) or numeric ID")],
    force: Annotated[bool, typer.Option("--force", "-y", help="Skip confirmation prompt")] = False,
) -> None:
    """Mark a manufacturing order as done.

    Examples:
        kctl-odoo mrp done WH/MO/00001
        kctl-odoo mrp done WH/MO/00001 --force
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _MRP_MODEL):
        out.warn(_MRP_HINT)
        return

    try:
        mo_id, mo_display = _resolve(c, _MRP_MODEL, "name", name, "MO")
    except typer.BadParameter as e:
        out.error(str(e))
        raise typer.Exit(1) from e

    if not force and not typer.confirm(f"Mark MO {mo_display} as done?"):
        raise typer.Exit(0)

    try:
        c.execute_kw(_MRP_MODEL, "button_mark_done", [[mo_id]])  # type: ignore[attr-defined]
    except RPCError as e:
        out.error(f"Failed to mark {mo_display} as done: {e}")
        raise typer.Exit(1) from e

    out.success(f"Marked MO {mo_display} as done")

    if actx.json_mode:
        out.raw_json({"id": mo_id, "name": mo_display, "action": "done"})


# ===================================================================
# CREATE MANUFACTURING ORDER
# ===================================================================


@app.command("create-order")
def create_order(
    ctx: typer.Context,
    product: Annotated[str, typer.Argument(help="Product name or numeric ID")],
    qty: Annotated[float, typer.Option("--qty", "-q", help="Production quantity")] = 1.0,
    bom: Annotated[str | None, typer.Option("--bom", help="BOM reference or numeric ID (optional)")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview without creating")] = False,
) -> None:
    """Create a manufacturing order.

    Resolves product by name or numeric ID. If --bom is given, resolves
    the BOM by ID or reference code; otherwise Odoo picks the default BOM.

    Examples:
        kctl-odoo mrp create-order "Finished Product" --qty 100
        kctl-odoo mrp create-order 42 --qty 5 --bom 3
        kctl-odoo mrp create-order "Widget A" --qty 50 --dry-run
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _MRP_MODEL):
        out.warn(_MRP_HINT)
        return

    # Resolve product (product.product)
    try:
        prod_id, prod_display = _resolve(c, "product.product", "name", product, "Product")
    except typer.BadParameter as e:
        out.error(str(e))
        raise typer.Exit(1) from e

    # Resolve BOM if provided
    bom_id: int | None = None
    bom_display = ""
    if bom is not None:
        try:
            bom_id, bom_display = _resolve(c, "mrp.bom", "code", bom, "BOM")
        except typer.BadParameter as e:
            out.error(str(e))
            raise typer.Exit(1) from e

    vals: dict = {
        "product_id": prod_id,
        "product_qty": qty,
    }
    if bom_id is not None:
        vals["bom_id"] = bom_id

    summary = {
        "product": prod_display,
        "qty": qty,
        "bom": bom_display or "(default)",
    }

    if dry_run:
        out.info("Dry run — manufacturing order will NOT be created.")
        out.detail(
            "Manufacturing Order Preview",
            [
                (
                    "New MO",
                    [
                        ("Product", prod_display),
                        ("Qty", str(qty)),
                        ("BOM", bom_display or "(default — Odoo selects)"),
                    ],
                )
            ],
            data_for_json=summary,
        )
        return

    try:
        mo_id = c.create(_MRP_MODEL, vals)
    except RPCError as e:
        out.error(f"Failed to create manufacturing order: {e}")
        raise typer.Exit(1) from e

    # Read back the name
    try:
        created = c.read(_MRP_MODEL, [mo_id], ["name"])
        mo_name = created[0]["name"] if created else str(mo_id)
    except RPCError:
        mo_name = str(mo_id)

    out.success(f"Created manufacturing order {mo_name} (id={mo_id}) for {prod_display} x{qty}")

    if actx.json_mode:
        out.raw_json({"id": mo_id, "name": mo_name, **summary})


# ===================================================================
# MANUFACTURING ORDER COST BREAKDOWN
# ===================================================================


@app.command("costs")
def costs(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="MO name (e.g. WH/MO/00001) or numeric ID")],
) -> None:
    """Show manufacturing order cost breakdown — planned vs actual.

    Reads component stock moves to calculate planned and actual costs
    based on product standard price.

    Examples:
        kctl-odoo mrp costs MO/00001
        kctl-odoo mrp costs 42
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _MRP_MODEL):
        out.warn(_MRP_HINT)
        return

    domain = [("id", "=", int(name))] if name.isdigit() else [("name", "=", name)]

    try:
        records = c.search_read(
            _MRP_MODEL,
            domain=domain,
            fields=["name", "product_id", "product_qty", "qty_producing", "move_raw_ids"],
            limit=1,
        )
    except RPCError as e:
        out.error(f"Failed to fetch MO: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.error(f"Manufacturing order not found: {name}")
        raise typer.Exit(1)

    rec = records[0]
    mo_name = rec["name"]
    move_ids = rec.get("move_raw_ids", [])

    header_sections = [
        (
            "Manufacturing Order",
            [
                ("Name", mo_name),
                ("Product", _m2o_name(rec.get("product_id"))),
                ("Planned Qty", str(rec.get("product_qty", 0))),
                ("Qty Producing", str(rec.get("qty_producing", 0))),
            ],
        )
    ]
    json_result: dict = {
        "name": mo_name,
        "product": _m2o_name(rec.get("product_id")),
        "product_qty": rec.get("product_qty", 0),
        "qty_producing": rec.get("qty_producing", 0),
        "components": [],
    }

    out.detail("MO Cost Breakdown", header_sections, data_for_json=json_result)

    if not move_ids:
        out.info("No component moves found.")
        return

    try:
        move_fields = safe_fields(
            c,
            "stock.move",
            ["product_id", "product_uom_qty", "quantity", "state"],
        )
        moves = c.read("stock.move", move_ids, move_fields)
    except RPCError as e:
        out.warn(f"Failed to read components: {e}")
        return

    # Collect product IDs to batch-read standard prices
    prod_ids = [mv["product_id"][0] for mv in moves if isinstance(mv.get("product_id"), list)]
    std_prices: dict[int, float] = {}
    if prod_ids:
        try:
            prods = c.read("product.product", list(set(prod_ids)), ["id", "standard_price"])
            std_prices = {p["id"]: p.get("standard_price", 0.0) for p in prods}
        except RPCError:
            pass  # Continue without prices

    rows = []
    components_json = []
    total_planned = 0.0
    total_actual = 0.0

    for mv in moves:
        prod_name = _m2o_name(mv.get("product_id"))
        prod_id = mv["product_id"][0] if isinstance(mv.get("product_id"), list) else 0
        planned_qty = mv.get("product_uom_qty", 0.0)
        actual_qty = mv.get("quantity", 0.0)
        unit_cost = std_prices.get(prod_id, 0.0)
        planned_cost = planned_qty * unit_cost
        actual_cost = actual_qty * unit_cost
        total_planned += planned_cost
        total_actual += actual_cost

        rows.append(
            [
                prod_name,
                f"{planned_qty:.2f}",
                f"{actual_qty:.2f}",
                f"{unit_cost:,.2f}",
                f"{planned_cost:,.2f}",
                f"{actual_cost:,.2f}",
            ]
        )
        components_json.append(
            {
                "product": prod_name,
                "planned_qty": planned_qty,
                "actual_qty": actual_qty,
                "unit_cost": unit_cost,
                "planned_cost": planned_cost,
                "actual_cost": actual_cost,
            }
        )

    # Totals row
    rows.append(
        [
            "[bold]TOTAL[/bold]",
            "",
            "",
            "",
            f"[bold]{total_planned:,.2f}[/bold]",
            f"[bold]{total_actual:,.2f}[/bold]",
        ]
    )
    json_result["components"] = components_json
    json_result["total_planned_cost"] = total_planned
    json_result["total_actual_cost"] = total_actual

    out.table(
        f"Component Costs — {mo_name}",
        [
            ("Component", ""),
            ("Planned Qty", ""),
            ("Actual Qty", ""),
            ("Unit Cost", "dim"),
            ("Planned Cost", "cyan"),
            ("Actual Cost", "green"),
        ],
        rows,
        data_for_json=components_json,
    )


# ===================================================================
# BOM COST CALCULATION
# ===================================================================


@app.command("bom-cost")
def bom_cost(
    ctx: typer.Context,
    bom_id: Annotated[int, typer.Argument(help="BOM ID")],
) -> None:
    """Calculate BOM cost from component standard prices.

    Reads each BOM line and multiplies quantity by the product's
    standard price to give a total BOM manufacturing cost estimate.

    Examples:
        kctl-odoo mrp bom-cost 1
        kctl-odoo mrp bom-cost 5
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, "mrp.bom"):
        out.warn(_MRP_HINT)
        return

    try:
        records = c.read(
            "mrp.bom",
            [bom_id],
            ["product_tmpl_id", "product_qty", "type", "code", "bom_line_ids"],
        )
    except RPCError as e:
        out.error(f"Failed to fetch BOM {bom_id}: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.error(f"BOM not found: {bom_id}")
        raise typer.Exit(1)

    rec = records[0]
    line_ids = rec.get("bom_line_ids", [])

    header_sections = [
        (
            "Bill of Materials",
            [
                ("ID", str(rec["id"])),
                ("Product", _m2o_name(rec.get("product_tmpl_id"))),
                ("Qty", str(rec.get("product_qty", 0))),
                ("Type", rec.get("type", "")),
                ("Code", str(rec.get("code", ""))),
            ],
        )
    ]
    json_result: dict = {
        "id": rec["id"],
        "product": _m2o_name(rec.get("product_tmpl_id")),
        "product_qty": rec.get("product_qty", 0),
        "lines": [],
        "total_cost": 0.0,
    }

    out.detail("BOM Cost", header_sections, data_for_json=json_result)

    if not line_ids:
        out.info("No BOM lines found.")
        return

    try:
        lines = c.read(
            "mrp.bom.line",
            line_ids,
            ["product_id", "product_qty", "product_uom_id"],
        )
    except RPCError as e:
        out.warn(f"Failed to read BOM lines: {e}")
        return

    # Batch-read standard prices
    prod_ids = [ln["product_id"][0] for ln in lines if isinstance(ln.get("product_id"), list)]
    std_prices: dict[int, float] = {}
    if prod_ids:
        try:
            prods = c.read("product.product", list(set(prod_ids)), ["id", "standard_price"])
            std_prices = {p["id"]: p.get("standard_price", 0.0) for p in prods}
        except RPCError:
            pass

    rows = []
    lines_json = []
    total_cost = 0.0

    for ln in lines:
        prod_name = _m2o_name(ln.get("product_id"))
        prod_id = ln["product_id"][0] if isinstance(ln.get("product_id"), list) else 0
        qty = ln.get("product_qty", 0.0)
        uom = _m2o_name(ln.get("product_uom_id"))
        unit_cost = std_prices.get(prod_id, 0.0)
        line_cost = qty * unit_cost
        total_cost += line_cost

        rows.append(
            [
                prod_name,
                f"{qty:.2f}",
                uom,
                f"{unit_cost:,.2f}",
                f"{line_cost:,.2f}",
            ]
        )
        lines_json.append(
            {
                "product": prod_name,
                "qty": qty,
                "uom": uom,
                "unit_cost": unit_cost,
                "line_cost": line_cost,
            }
        )

    rows.append(
        [
            "[bold]TOTAL[/bold]",
            "",
            "",
            "",
            f"[bold]{total_cost:,.2f}[/bold]",
        ]
    )
    json_result["lines"] = lines_json
    json_result["total_cost"] = total_cost

    out.table(
        f"BOM Cost — id={bom_id}",
        [
            ("Component", ""),
            ("Qty", ""),
            ("UoM", "dim"),
            ("Unit Cost", "dim"),
            ("Line Cost", "cyan"),
        ],
        rows,
        data_for_json=lines_json,
    )

    out.info(f"Total BOM cost: {total_cost:,.2f}")


# ===================================================================
# START WORK ORDER
# ===================================================================


@app.command("start-workorder")
def start_workorder(
    ctx: typer.Context,
    workorder_id: Annotated[int, typer.Argument(help="Work order ID")],
    force: Annotated[bool, typer.Option("--force", "-y", help="Skip confirmation prompt")] = False,
) -> None:
    """Start a work order (set to in progress).

    Calls ``button_start`` on the mrp.workorder record.

    Examples:
        kctl-odoo mrp start-workorder 1
        kctl-odoo mrp start-workorder 7 --force
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, "mrp.workorder"):
        out.warn(_MRP_HINT)
        return

    if not force and not typer.confirm(f"Start work order id={workorder_id}?"):
        raise typer.Exit(0)

    try:
        c.execute_kw("mrp.workorder", "button_start", [[workorder_id]])
    except RPCError as e:
        out.error(f"Failed to start work order {workorder_id}: {e}")
        raise typer.Exit(1) from e

    out.success(f"Started work order id={workorder_id}")

    if actx.json_mode:
        out.raw_json({"id": workorder_id, "action": "started"})


# ===================================================================
# FINISH WORK ORDER
# ===================================================================


@app.command("finish-workorder")
def finish_workorder(
    ctx: typer.Context,
    workorder_id: Annotated[int, typer.Argument(help="Work order ID")],
    force: Annotated[bool, typer.Option("--force", "-y", help="Skip confirmation prompt")] = False,
) -> None:
    """Finish a work order (mark as done).

    Calls ``button_finish`` on the mrp.workorder record.

    Examples:
        kctl-odoo mrp finish-workorder 1
        kctl-odoo mrp finish-workorder 7 --force
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, "mrp.workorder"):
        out.warn(_MRP_HINT)
        return

    if not force and not typer.confirm(f"Finish work order id={workorder_id}?"):
        raise typer.Exit(0)

    try:
        c.execute_kw("mrp.workorder", "button_finish", [[workorder_id]])
    except RPCError as e:
        out.error(f"Failed to finish work order {workorder_id}: {e}")
        raise typer.Exit(1) from e

    out.success(f"Finished work order id={workorder_id}")

    if actx.json_mode:
        out.raw_json({"id": workorder_id, "action": "finished"})
