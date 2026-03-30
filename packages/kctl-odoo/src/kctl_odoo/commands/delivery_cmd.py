"""Delivery / logistics operations commands — tracking, performance, returns."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

import typer

from kctl_odoo.core.biz_helpers import model_available
from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.exceptions import RPCError
from kctl_odoo.core.field_helpers import safe_fields

app = typer.Typer(help="Delivery & logistics: tracking, performance, returns.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _m2o_name(val: object) -> str:
    """Extract display name from an M2O field value ([id, name] or False)."""
    if isinstance(val, list):
        return str(val[1])
    return str(val or "-")


# ===================================================================
# LIST
# ===================================================================


@app.command("list")
def list_deliveries(
    ctx: typer.Context,
    state: Annotated[
        str | None, typer.Option("--state", "-s", help="Filter by state: draft, confirmed, assigned, done, cancel")
    ] = None,
    carrier: Annotated[str | None, typer.Option("--carrier", help="Filter by carrier name")] = None,
    date_from: Annotated[str | None, typer.Option("--date-from", help="From date (YYYY-MM-DD)")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List outgoing deliveries.

    Examples:
        kctl-odoo delivery list
        kctl-odoo delivery list --state assigned
        kctl-odoo delivery list --carrier "JNE" --date-from 2025-01-01
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    domain: list = [("picking_type_code", "=", "outgoing")]
    if state:
        domain.append(("state", "=", state))
    if carrier:
        domain.append(("carrier_id.name", "ilike", carrier))
    if date_from:
        domain.append(("scheduled_date", ">=", date_from))

    fields = safe_fields(
        c,
        "stock.picking",
        ["display_name", "partner_id", "scheduled_date", "state", "carrier_id", "origin"],
    )

    try:
        records = c.search_read("stock.picking", domain, fields, limit=limit)  # type: ignore[attr-defined]
    except RPCError as e:
        out.error(f"Failed to list deliveries: {e}")
        raise typer.Exit(1)

    if not records:
        out.info("No deliveries found.")
        return

    if actx.json_mode:
        out.raw_json(records)
        return

    rows = [
        [
            r.get("display_name", "-"),
            _m2o_name(r.get("partner_id", False)),
            (r.get("scheduled_date", "-") or "-")[:16],
            r.get("state", "-"),
            _m2o_name(r.get("carrier_id", False)),
            r.get("origin") or "-",
        ]
        for r in records
    ]

    out.table(
        f"Deliveries ({len(rows)})",
        [
            ("Reference", ""),
            ("Partner", "dim"),
            ("Scheduled", ""),
            ("State", ""),
            ("Carrier", "dim"),
            ("Origin", "dim"),
        ],
        rows,
    )


# ===================================================================
# TRACKING
# ===================================================================


@app.command("tracking")
def tracking(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Delivery reference (e.g. WH/OUT/00001)")],
) -> None:
    """Show delivery tracking detail by reference.

    Examples:
        kctl-odoo delivery tracking WH/OUT/00001
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    detail_fields = [
        "name",
        "partner_id",
        "state",
        "scheduled_date",
        "date_done",
        "carrier_id",
        "carrier_tracking_ref",
        "weight",
        "origin",
        "move_line_ids",
    ]
    fields = safe_fields(c, "stock.picking", detail_fields)

    try:
        records = c.search_read("stock.picking", [("name", "=", name)], fields, limit=1)  # type: ignore[attr-defined]
    except RPCError as e:
        out.error(f"Failed to fetch delivery: {e}")
        raise typer.Exit(1)

    if not records:
        out.error(f"Delivery not found: {name}")
        raise typer.Exit(1)

    r = records[0]
    move_line_count = len(r.get("move_line_ids", []))

    if actx.json_mode:
        out.raw_json({**r, "move_line_count": move_line_count})
        return

    rows = [
        ["Reference", r.get("name", "-")],
        ["Partner", _m2o_name(r.get("partner_id", False))],
        ["State", r.get("state", "-")],
        ["Scheduled Date", (r.get("scheduled_date") or "-")[:16]],
        ["Done Date", (r.get("date_done") or "-")[:16]],
        ["Carrier", _m2o_name(r.get("carrier_id", False))],
        ["Tracking Ref", r.get("carrier_tracking_ref") or "-"],
        ["Weight", f"{r.get('weight', 0)} kg"],
        ["Origin", r.get("origin") or "-"],
        ["Move Lines", str(move_line_count)],
    ]

    out.table(
        f"Delivery: {name}",
        [("Field", ""), ("Value", "")],
        rows,
    )


# ===================================================================
# PERFORMANCE
# ===================================================================


@app.command("performance")
def performance(
    ctx: typer.Context,
    days: Annotated[int, typer.Option("--days", "-d", help="Number of days to analyze")] = 30,
) -> None:
    """On-time delivery performance report.

    Compares scheduled_date vs date_done for completed deliveries.

    Examples:
        kctl-odoo delivery performance
        kctl-odoo delivery performance --days 7
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    since = (datetime.now(tz=UTC) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

    domain: list = [
        ("picking_type_code", "=", "outgoing"),
        ("state", "=", "done"),
        ("date_done", ">=", since),
    ]
    fields = safe_fields(c, "stock.picking", ["name", "scheduled_date", "date_done"])

    try:
        records = c.search_read("stock.picking", domain, fields, limit=0)  # type: ignore[attr-defined]
    except RPCError as e:
        out.error(f"Failed to fetch deliveries: {e}")
        raise typer.Exit(1)

    total = len(records)
    if total == 0:
        out.info(f"No completed deliveries in the last {days} days.")
        return

    on_time = 0
    late = 0
    total_delay_hours = 0.0

    for r in records:
        sched = r.get("scheduled_date")
        done = r.get("date_done")
        if not sched or not done:
            on_time += 1  # Can't determine, count as on-time
            continue

        # Parse dates
        try:
            sched_dt = datetime.fromisoformat(str(sched).replace("Z", "+00:00"))
            done_dt = datetime.fromisoformat(str(done).replace("Z", "+00:00"))
            # Make naive if needed
            if sched_dt.tzinfo is None:
                sched_dt = sched_dt.replace(tzinfo=UTC)
            if done_dt.tzinfo is None:
                done_dt = done_dt.replace(tzinfo=UTC)

            delay = (done_dt - sched_dt).total_seconds() / 3600
            if delay <= 0:
                on_time += 1
            else:
                late += 1
                total_delay_hours += delay
        except (ValueError, TypeError):
            on_time += 1  # Can't parse, count as on-time

    on_time_pct = (on_time / total * 100) if total > 0 else 0
    avg_delay = (total_delay_hours / late) if late > 0 else 0

    if actx.json_mode:
        out.raw_json(
            {
                "period_days": days,
                "total": total,
                "on_time": on_time,
                "late": late,
                "on_time_pct": round(on_time_pct, 1),
                "avg_delay_hours": round(avg_delay, 1),
            }
        )
        return

    rows = [
        ["Period", f"Last {days} days"],
        ["Total Deliveries", str(total)],
        ["On-Time", str(on_time)],
        ["Late", str(late)],
        ["On-Time %", f"{on_time_pct:.1f}%"],
        ["Avg Delay", f"{avg_delay:.1f} hours"],
    ]

    out.table(
        "Delivery Performance",
        [("Metric", ""), ("Value", "")],
        rows,
    )


# ===================================================================
# RETURNS
# ===================================================================


@app.command("returns")
def returns(
    ctx: typer.Context,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List return pickings (origin contains 'Return').

    Examples:
        kctl-odoo delivery returns
        kctl-odoo delivery returns --limit 20
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    domain: list = [("origin", "ilike", "Return")]
    fields = safe_fields(
        c,
        "stock.picking",
        ["display_name", "partner_id", "scheduled_date", "state", "origin"],
    )

    try:
        records = c.search_read("stock.picking", domain, fields, limit=limit)  # type: ignore[attr-defined]
    except RPCError as e:
        out.error(f"Failed to list returns: {e}")
        raise typer.Exit(1)

    if not records:
        out.info("No return pickings found.")
        return

    if actx.json_mode:
        out.raw_json(records)
        return

    rows = [
        [
            r.get("display_name", "-"),
            _m2o_name(r.get("partner_id", False)),
            (r.get("scheduled_date", "-") or "-")[:16],
            r.get("state", "-"),
            r.get("origin") or "-",
        ]
        for r in records
    ]

    out.table(
        f"Return Pickings ({len(rows)})",
        [("Reference", ""), ("Partner", "dim"), ("Scheduled", ""), ("State", ""), ("Origin", "dim")],
        rows,
    )


# ===================================================================
# CARRIERS
# ===================================================================


@app.command("carriers")
def carriers(
    ctx: typer.Context,
) -> None:
    """List configured delivery carriers.

    Examples:
        kctl-odoo delivery carriers
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, "delivery.carrier"):
        out.info("Delivery module not installed. Install with: kctl-odoo modules install delivery")
        return

    fields = safe_fields(
        c,
        "delivery.carrier",
        ["display_name", "delivery_type", "fixed_price", "active"],
    )

    try:
        records = c.search_read("delivery.carrier", [], fields)  # type: ignore[attr-defined]
    except RPCError as e:
        out.error(f"Failed to list carriers: {e}")
        raise typer.Exit(1)

    if not records:
        out.info("No carriers configured.")
        return

    if actx.json_mode:
        out.raw_json(records)
        return

    rows = [
        [
            r.get("display_name", "-"),
            r.get("delivery_type", "-"),
            f"{r.get('fixed_price', 0):,.2f}",
            "Yes" if r.get("active", True) else "No",
        ]
        for r in records
    ]

    out.table(
        f"Delivery Carriers ({len(rows)})",
        [("Name", ""), ("Type", ""), ("Fixed Price", ""), ("Active", "")],
        rows,
    )


# ===================================================================
# PENDING
# ===================================================================


@app.command("pending")
def pending(
    ctx: typer.Context,
    days: Annotated[int, typer.Option("--days", "-d", help="Days overdue threshold")] = 3,
) -> None:
    """List deliveries pending beyond threshold days.

    Shows outgoing deliveries in 'assigned' or 'confirmed' state with
    scheduled_date older than today - N days.

    Examples:
        kctl-odoo delivery pending
        kctl-odoo delivery pending --days 7
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    cutoff = (datetime.now(tz=UTC) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

    domain: list = [
        ("picking_type_code", "=", "outgoing"),
        ("state", "in", ["assigned", "confirmed"]),
        ("scheduled_date", "<", cutoff),
    ]
    fields = safe_fields(
        c,
        "stock.picking",
        ["display_name", "partner_id", "scheduled_date", "state", "origin"],
    )

    try:
        records = c.search_read("stock.picking", domain, fields, limit=200)  # type: ignore[attr-defined]
    except RPCError as e:
        out.error(f"Failed to fetch pending deliveries: {e}")
        raise typer.Exit(1)

    if not records:
        out.info(f"No deliveries pending beyond {days} days.")
        return

    if actx.json_mode:
        out.raw_json(records)
        return

    rows = [
        [
            r.get("display_name", "-"),
            _m2o_name(r.get("partner_id", False)),
            (r.get("scheduled_date", "-") or "-")[:16],
            r.get("state", "-"),
            r.get("origin") or "-",
        ]
        for r in records
    ]

    out.table(
        f"Pending Deliveries (>{days} days, {len(rows)} found)",
        [("Reference", ""), ("Partner", "dim"), ("Scheduled", ""), ("State", ""), ("Origin", "dim")],
        rows,
    )
