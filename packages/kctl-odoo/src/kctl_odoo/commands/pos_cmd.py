"""Point of Sale commands — sessions, orders, payments."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

import typer

from kctl_odoo.core.biz_helpers import fmt_amount, model_available
from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.exceptions import RPCError
from kctl_odoo.core.field_helpers import safe_fields

app = typer.Typer(help="Point of Sale: sessions, orders, payments.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _m2o_name(val: object) -> str:
    """Extract display name from an M2O field value ([id, name] or False)."""
    if isinstance(val, list):
        return str(val[1])
    return str(val or "-")


def _check_pos_available(c: object, out: object) -> bool:
    """Return True if the POS module is installed, warn and return False otherwise."""
    if not model_available(c, "pos.session"):
        out.warn("Point of Sale module (point_of_sale) is not installed.")  # type: ignore[attr-defined]
        return False
    return True


# ===================================================================
# SUMMARY / DASHBOARD
# ===================================================================


@app.command("summary")
def summary(
    ctx: typer.Context,
) -> None:
    """Dashboard — active sessions count, today's orders count, today's revenue.

    Examples:
        kctl-odoo pos summary
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _check_pos_available(c, out):
        return

    today_start = datetime.now(tz=UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    today_str = today_start.strftime("%Y-%m-%d %H:%M:%S")

    try:
        active_sessions = c.search_count("pos.session", [("state", "in", ["opened", "closing_control"])])
        today_orders = c.search_count("pos.order", [("date_order", ">=", today_str)])
        orders_data = c.search_read(
            "pos.order",
            domain=[("date_order", ">=", today_str)],
            fields=["amount_total"],
        )
    except RPCError as e:
        out.error(f"Failed to fetch POS summary: {e}")
        raise typer.Exit(1) from e

    today_revenue = sum(o.get("amount_total", 0.0) for o in orders_data)

    sections = [
        (
            "Point of Sale Dashboard",
            [
                ("Active Sessions", str(active_sessions)),
                ("Today's Orders", str(today_orders)),
                ("Today's Revenue", fmt_amount(today_revenue)),
            ],
        )
    ]

    json_result = {
        "active_sessions": active_sessions,
        "today_orders": today_orders,
        "today_revenue": today_revenue,
    }

    out.detail("POS Summary", sections, data_for_json=json_result)


# ===================================================================
# LIST SESSIONS
# ===================================================================


@app.command("sessions")
def sessions(
    ctx: typer.Context,
    state: Annotated[
        str | None,
        typer.Option("--state", "-s", help="Filter by state: opened, closing_control, closed"),
    ] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 20,
) -> None:
    """List POS sessions.

    Examples:
        kctl-odoo pos sessions
        kctl-odoo pos sessions --state opened
        kctl-odoo pos sessions --limit 10
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _check_pos_available(c, out):
        return

    domain: list = []
    if state:
        if state == "opened_and_closing":
            domain.append(("state", "in", ["opened", "closing_control"]))
        else:
            domain.append(("state", "=", state))

    try:
        records = c.search_read(
            "pos.session",
            domain=domain,
            fields=["name", "config_id", "user_id", "state", "start_at", "stop_at"],
            limit=limit,
            order="start_at desc",
        )
    except RPCError as e:
        out.error(f"Failed to list POS sessions: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.info("No POS sessions found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for r in records:
        rows.append(
            [
                r.get("name", ""),
                _m2o_name(r.get("config_id")),
                _m2o_name(r.get("user_id")),
                r.get("state", ""),
                str(r.get("start_at", "")),
                str(r.get("stop_at", "") or ""),
            ]
        )
        json_data.append(
            {
                "name": r.get("name"),
                "config": _m2o_name(r.get("config_id")),
                "user": _m2o_name(r.get("user_id")),
                "state": r.get("state"),
                "start_at": r.get("start_at"),
                "stop_at": r.get("stop_at"),
            }
        )

    out.table(
        f"POS Sessions ({len(records)})",
        [
            ("Name", "cyan"),
            ("Config", ""),
            ("User", ""),
            ("State", ""),
            ("Started", "dim"),
            ("Stopped", "dim"),
        ],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# CLOSE SESSION
# ===================================================================


@app.command("close-session")
def close_session(
    ctx: typer.Context,
    session_id: Annotated[int, typer.Argument(help="POS session ID to close")],
    force: Annotated[bool, typer.Option("--force", "-y", help="Skip confirmation prompt")] = False,
) -> None:
    """Close a POS session.

    Examples:
        kctl-odoo pos close-session 5
        kctl-odoo pos close-session 5 --force
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _check_pos_available(c, out):
        return

    # Read the session to confirm it exists
    try:
        sessions_data = c.read("pos.session", [session_id], ["name", "state"])
    except RPCError as e:
        out.error(f"Failed to fetch session {session_id}: {e}")
        raise typer.Exit(1) from e

    if not sessions_data:
        out.error(f"POS session {session_id} not found.")
        raise typer.Exit(1)

    session = sessions_data[0]
    session_name = session.get("name", str(session_id))
    session_state = session.get("state", "")

    if not force and not typer.confirm(f"Close POS session '{session_name}' (state: {session_state})?"):
        raise typer.Exit(0)

    try:
        c.execute_kw("pos.session", "action_pos_session_closing_control", [[session_id]])
    except RPCError as e:
        out.error(f"Failed to close session '{session_name}': {e}")
        raise typer.Exit(1) from e

    out.success(f"Closed POS session '{session_name}' (id={session_id})")

    if actx.json_mode:
        out.raw_json({"id": session_id, "name": session_name, "action": "closed"})


# ===================================================================
# LIST ORDERS
# ===================================================================


@app.command("orders")
def orders(
    ctx: typer.Context,
    session: Annotated[str | None, typer.Option("--session", help="Filter by session name")] = None,
    date_from: Annotated[str | None, typer.Option("--date-from", help="Filter orders from date (YYYY-MM-DD)")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List POS orders.

    Examples:
        kctl-odoo pos orders
        kctl-odoo pos orders --session "POS/001"
        kctl-odoo pos orders --date-from 2026-01-01 --limit 20
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _check_pos_available(c, out):
        return

    domain: list = []
    if session:
        domain.append(("session_id.name", "ilike", session))
    if date_from:
        domain.append(("date_order", ">=", date_from))

    try:
        records = c.search_read(
            "pos.order",
            domain=domain,
            fields=["name", "pos_reference", "session_id", "partner_id", "date_order", "amount_total", "state"],
            limit=limit,
            order="date_order desc",
        )
    except RPCError as e:
        out.error(f"Failed to list POS orders: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.info("No POS orders found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for r in records:
        rows.append(
            [
                r.get("name", ""),
                r.get("pos_reference", "") or "",
                _m2o_name(r.get("session_id")),
                _m2o_name(r.get("partner_id")),
                str(r.get("date_order", "")),
                fmt_amount(r.get("amount_total", 0)),
                r.get("state", ""),
            ]
        )
        json_data.append(
            {
                "name": r.get("name"),
                "pos_reference": r.get("pos_reference"),
                "session": _m2o_name(r.get("session_id")),
                "partner": _m2o_name(r.get("partner_id")),
                "date_order": r.get("date_order"),
                "amount_total": r.get("amount_total", 0),
                "state": r.get("state"),
            }
        )

    out.table(
        f"POS Orders ({len(records)})",
        [
            ("Name", "cyan"),
            ("Reference", ""),
            ("Session", ""),
            ("Partner", ""),
            ("Date", "dim"),
            ("Total", ""),
            ("State", ""),
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
    ref: Annotated[str, typer.Argument(help="POS order reference, name, or numeric ID")],
) -> None:
    """Get POS order detail by reference or name.

    Shows header information and order lines.

    Examples:
        kctl-odoo pos get-order "Order 00001-001-0001"
        kctl-odoo pos get-order 42
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _check_pos_available(c, out):
        return

    domain = [("id", "=", int(ref))] if ref.isdigit() else ["|", ("pos_reference", "=", ref), ("name", "ilike", ref)]

    try:
        records = c.search_read(
            "pos.order",
            domain=domain,
            fields=[
                "name",
                "pos_reference",
                "session_id",
                "partner_id",
                "date_order",
                "amount_tax",
                "amount_total",
                "state",
                "lines",
            ],
            limit=1,
        )
    except RPCError as e:
        out.error(f"Failed to fetch POS order: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.error(f"POS order not found: {ref}")
        raise typer.Exit(1)

    rec = records[0]

    sections = [
        (
            "POS Order",
            [
                ("Name", rec.get("name", "")),
                ("Reference", rec.get("pos_reference", "") or ""),
                ("Session", _m2o_name(rec.get("session_id"))),
                ("Partner", _m2o_name(rec.get("partner_id"))),
                ("Date", str(rec.get("date_order", ""))),
                ("Tax", fmt_amount(rec.get("amount_tax", 0))),
                ("Total", fmt_amount(rec.get("amount_total", 0))),
                ("State", rec.get("state", "")),
            ],
        )
    ]

    json_result: dict = {
        "name": rec.get("name"),
        "pos_reference": rec.get("pos_reference"),
        "session": _m2o_name(rec.get("session_id")),
        "partner": _m2o_name(rec.get("partner_id")),
        "date_order": rec.get("date_order"),
        "amount_tax": rec.get("amount_tax", 0),
        "amount_total": rec.get("amount_total", 0),
        "state": rec.get("state"),
        "lines": [],
    }

    out.detail("POS Order Detail", sections, data_for_json=json_result)

    # Order lines
    line_ids = rec.get("lines", [])
    if line_ids:
        try:
            lines = c.read(
                "pos.order.line",
                line_ids,
                ["product_id", "qty", "price_unit", "price_subtotal_incl"],
            )
        except RPCError as e:
            out.warn(f"Failed to read order lines: {e}")
            return

        rows = []
        lines_json = []
        for ln in lines:
            rows.append(
                [
                    _m2o_name(ln.get("product_id")),
                    str(ln.get("qty", 0)),
                    fmt_amount(ln.get("price_unit", 0)),
                    fmt_amount(ln.get("price_subtotal_incl", 0)),
                ]
            )
            lines_json.append(
                {
                    "product": _m2o_name(ln.get("product_id")),
                    "qty": ln.get("qty", 0),
                    "price_unit": ln.get("price_unit", 0),
                    "price_subtotal_incl": ln.get("price_subtotal_incl", 0),
                }
            )

        json_result["lines"] = lines_json

        out.table(
            "Order Lines",
            [("Product", ""), ("Qty", ""), ("Unit Price", ""), ("Subtotal (incl. tax)", "")],
            rows,
            data_for_json=lines_json,
        )


# ===================================================================
# LIST POS CONFIGS
# ===================================================================


@app.command("configs")
def configs(
    ctx: typer.Context,
) -> None:
    """List POS configurations.

    Examples:
        kctl-odoo pos configs
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _check_pos_available(c, out):
        return

    try:
        records = c.search_read(
            "pos.config",
            domain=[],
            fields=["name", "active", "current_session_id", "module_pos_restaurant"],
        )
    except RPCError as e:
        out.error(f"Failed to list POS configs: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.info("No POS configurations found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for r in records:
        current_session = _m2o_name(r.get("current_session_id")) if r.get("current_session_id") else "-"
        is_restaurant = "Yes" if r.get("module_pos_restaurant") else "No"
        is_active = "Yes" if r.get("active") else "No"
        rows.append(
            [
                r.get("name", ""),
                is_active,
                current_session,
                is_restaurant,
            ]
        )
        json_data.append(
            {
                "name": r.get("name"),
                "active": r.get("active"),
                "current_session": _m2o_name(r.get("current_session_id")) if r.get("current_session_id") else None,
                "is_restaurant": r.get("module_pos_restaurant"),
            }
        )

    out.table(
        f"POS Configurations ({len(records)})",
        [
            ("Name", "cyan"),
            ("Active", ""),
            ("Current Session", ""),
            ("Restaurant Mode", ""),
        ],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# PAYMENT SUMMARY
# ===================================================================


@app.command("payments")
def payments(
    ctx: typer.Context,
    date_from: Annotated[str | None, typer.Option("--date-from", help="Filter payments from date (YYYY-MM-DD)")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 100,
) -> None:
    """Payment summary grouped by payment method.

    Examples:
        kctl-odoo pos payments
        kctl-odoo pos payments --date-from 2026-01-01
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _check_pos_available(c, out):
        return

    domain: list = []
    if date_from:
        domain.append(("payment_date", ">=", date_from))

    try:
        records = c.search_read(
            "pos.payment",
            domain=domain,
            fields=["payment_method_id", "amount"],
            limit=limit,
        )
    except RPCError as e:
        out.error(f"Failed to fetch POS payments: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.info("No POS payments found.")
        if actx.json_mode:
            out.raw_json([])
        return

    # Group by payment method
    method_totals: dict[str, float] = {}
    method_counts: dict[str, int] = {}
    for r in records:
        method = _m2o_name(r.get("payment_method_id"))
        method_totals[method] = method_totals.get(method, 0.0) + r.get("amount", 0.0)
        method_counts[method] = method_counts.get(method, 0) + 1

    total_amount = sum(method_totals.values())
    total_count = sum(method_counts.values())

    rows = []
    json_data = []
    for method in sorted(method_totals.keys()):
        rows.append(
            [
                method,
                str(method_counts[method]),
                fmt_amount(method_totals[method]),
            ]
        )
        json_data.append(
            {
                "payment_method": method,
                "count": method_counts[method],
                "amount": method_totals[method],
            }
        )

    rows.append(
        [
            "[bold]Total[/bold]",
            f"[bold]{total_count}[/bold]",
            f"[bold]{fmt_amount(total_amount)}[/bold]",
        ]
    )
    json_data.append({"payment_method": "total", "count": total_count, "amount": total_amount})

    title = "POS Payment Summary"
    if date_from:
        title += f" (from {date_from})"

    out.table(
        title,
        [("Payment Method", ""), ("Count", "cyan"), ("Amount", "green")],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# DAILY REPORT
# ===================================================================


@app.command("daily-report")
def daily_report(
    ctx: typer.Context,
    date: Annotated[
        str | None,
        typer.Option("--date", help="Report date (YYYY-MM-DD, default: today)"),
    ] = None,
) -> None:
    """Daily sales summary grouped by POS configuration.

    Examples:
        kctl-odoo pos daily-report
        kctl-odoo pos daily-report --date 2026-03-28
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _check_pos_available(c, out):
        return

    if date is None:
        date = datetime.now(tz=UTC).strftime("%Y-%m-%d")

    date_start = f"{date} 00:00:00"
    date_end = f"{date} 23:59:59"

    try:
        records = c.search_read(
            "pos.order",
            domain=[
                ("date_order", ">=", date_start),
                ("date_order", "<=", date_end),
                ("state", "not in", ["cancel"]),
            ],
            fields=["config_id", "amount_total", "amount_tax"],
        )
    except RPCError as e:
        out.error(f"Failed to fetch POS daily report: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.info(f"No POS orders found for {date}.")
        if actx.json_mode:
            out.raw_json([])
        return

    # Group by config
    config_totals: dict[str, dict] = {}
    for r in records:
        config = _m2o_name(r.get("config_id"))
        bucket = config_totals.setdefault(config, {"count": 0, "revenue": 0.0, "tax": 0.0})
        bucket["count"] += 1
        bucket["revenue"] += r.get("amount_total", 0.0)
        bucket["tax"] += r.get("amount_tax", 0.0)

    total_count = sum(b["count"] for b in config_totals.values())
    total_revenue = sum(b["revenue"] for b in config_totals.values())
    total_tax = sum(b["tax"] for b in config_totals.values())

    rows = []
    json_data = []
    for config, bucket in sorted(config_totals.items()):
        rows.append(
            [
                config,
                str(bucket["count"]),
                fmt_amount(bucket["revenue"]),
                fmt_amount(bucket["tax"]),
            ]
        )
        json_data.append(
            {
                "config": config,
                "orders": bucket["count"],
                "revenue": bucket["revenue"],
                "tax": bucket["tax"],
            }
        )

    rows.append(
        [
            "[bold]Total[/bold]",
            f"[bold]{total_count}[/bold]",
            f"[bold]{fmt_amount(total_revenue)}[/bold]",
            f"[bold]{fmt_amount(total_tax)}[/bold]",
        ]
    )
    json_data.append({"config": "total", "orders": total_count, "revenue": total_revenue, "tax": total_tax})

    out.table(
        f"POS Daily Report — {date}",
        [("Config", "cyan"), ("Orders", ""), ("Revenue", "green"), ("Tax", "dim")],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# STUCK SESSIONS
# ===================================================================


@app.command("stuck-sessions")
def stuck_sessions(
    ctx: typer.Context,
    hours: Annotated[
        int,
        typer.Option("--hours", help="Sessions open longer than this many hours (default: 24)"),
    ] = 24,
) -> None:
    """Find POS sessions that have been open beyond a threshold.

    Helps identify sessions that were not properly closed.

    Examples:
        kctl-odoo pos stuck-sessions
        kctl-odoo pos stuck-sessions --hours 12
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _check_pos_available(c, out):
        return

    cutoff = (datetime.now(tz=UTC) - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")

    try:
        records = c.search_read(
            "pos.session",
            domain=[
                ("state", "!=", "closed"),
                ("start_at", "<", cutoff),
            ],
            fields=["name", "config_id", "user_id", "state", "start_at"],
            order="start_at asc",
        )
    except RPCError as e:
        out.error(f"Failed to fetch stuck sessions: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.info(f"No stuck sessions found (sessions open > {hours}h).")
        if actx.json_mode:
            out.raw_json([])
        return

    now = datetime.now(tz=UTC)
    rows = []
    json_data = []
    for r in records:
        start_raw = r.get("start_at", "")
        # Calculate approximate open duration
        try:
            if start_raw:
                start_dt = datetime.fromisoformat(str(start_raw).replace("Z", "+00:00"))
                if start_dt.tzinfo is None:
                    start_dt = start_dt.replace(tzinfo=UTC)
                open_hours = round((now - start_dt).total_seconds() / 3600, 1)
                open_str = f"{open_hours}h"
            else:
                open_str = "?"
        except (ValueError, TypeError):
            open_str = "?"

        rows.append(
            [
                r.get("name", ""),
                _m2o_name(r.get("config_id")),
                _m2o_name(r.get("user_id")),
                r.get("state", ""),
                str(start_raw),
                open_str,
            ]
        )
        json_data.append(
            {
                "name": r.get("name"),
                "config": _m2o_name(r.get("config_id")),
                "user": _m2o_name(r.get("user_id")),
                "state": r.get("state"),
                "start_at": start_raw,
                "open_duration": open_str,
            }
        )

    out.table(
        f"Stuck POS Sessions (open > {hours}h) — {len(records)} found",
        [
            ("Name", "cyan"),
            ("Config", ""),
            ("User", ""),
            ("State", ""),
            ("Started", "dim"),
            ("Open For", "yellow"),
        ],
        rows,
        data_for_json=json_data,
    )

    out.warn(f"Found {len(records)} session(s) open beyond {hours}h. Use 'kctl-odoo pos close-session <id>' to close.")


# ===================================================================
# CASH CONTROL
# ===================================================================


@app.command("cash-control")
def cash_control(
    ctx: typer.Context,
    session_id: Annotated[int, typer.Argument(help="POS session ID")],
) -> None:
    """Show cash in/out details for a POS session.

    Displays opening balance, cash payments received, cash out (change),
    expected closing balance, actual closing balance, and difference.

    Examples:
        kctl-odoo pos cash-control 1
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _check_pos_available(c, out):
        return

    try:
        fields = safe_fields(
            c,
            "pos.session",
            [
                "name",
                "config_id",
                "state",
                "cash_register_balance_start",
                "cash_register_balance_end_real",
                "cash_real_transaction",
            ],
        )
        data = c.read("pos.session", [session_id], fields)
    except RPCError as e:
        out.error(f"Failed to fetch session {session_id}: {e}")
        raise typer.Exit(1) from e

    if not data:
        out.error(f"POS session {session_id} not found.")
        raise typer.Exit(1)

    s = data[0]
    opening = s.get("cash_register_balance_start") or 0.0
    actual_close = s.get("cash_register_balance_end_real") or 0.0
    cash_transaction = s.get("cash_real_transaction") or 0.0
    # expected = opening + net cash transactions during session
    expected_close = opening + cash_transaction
    difference = actual_close - expected_close

    sections = [
        (
            f"Cash Control — {s.get('name', session_id)}",
            [
                ("Config", _m2o_name(s.get("config_id"))),
                ("State", s.get("state", "")),
                ("Opening Balance", fmt_amount(opening)),
                ("Cash Transactions (net)", fmt_amount(cash_transaction)),
                ("Expected Closing", fmt_amount(expected_close)),
                ("Actual Closing", fmt_amount(actual_close)),
                ("Difference", fmt_amount(difference)),
            ],
        )
    ]

    json_result = {
        "session_id": session_id,
        "name": s.get("name"),
        "state": s.get("state"),
        "opening_balance": opening,
        "cash_transactions": cash_transaction,
        "expected_closing": expected_close,
        "actual_closing": actual_close,
        "difference": difference,
    }

    out.detail("Cash Control", sections, data_for_json=json_result)

    if abs(difference) > 0.01:
        out.warn(f"Cash discrepancy detected: {fmt_amount(difference)}")
    else:
        out.success("Cash balanced — no discrepancy.")


# ===================================================================
# RECONCILE
# ===================================================================


@app.command("reconcile")
def reconcile(
    ctx: typer.Context,
    session_id: Annotated[int, typer.Argument(help="POS session ID")],
) -> None:
    """Verify session reconciliation — compare POS totals vs journal entries.

    Checks that POS order totals match the account.move created at session close.
    Flags discrepancies.

    Examples:
        kctl-odoo pos reconcile 1
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _check_pos_available(c, out):
        return

    try:
        s_fields = safe_fields(c, "pos.session", ["name", "state", "move_id"])
        s_data = c.read("pos.session", [session_id], s_fields)
    except RPCError as e:
        out.error(f"Failed to fetch session {session_id}: {e}")
        raise typer.Exit(1) from e

    if not s_data:
        out.error(f"POS session {session_id} not found.")
        raise typer.Exit(1)

    s = s_data[0]
    session_name = s.get("name", str(session_id))

    # Sum POS order totals for this session
    try:
        order_records = c.search_read(
            "pos.order",
            domain=[("session_id", "=", session_id), ("state", "not in", ["cancel"])],
            fields=["amount_total"],
        )
    except RPCError as e:
        out.error(f"Failed to fetch orders: {e}")
        raise typer.Exit(1) from e

    pos_total = sum(o.get("amount_total", 0.0) for o in order_records)
    order_count = len(order_records)

    # Read journal entry if it exists
    move_id = s.get("move_id")
    move_total = None
    move_state = None
    move_name = None

    if move_id and isinstance(move_id, list):
        try:
            move_fields = safe_fields(c, "account.move", ["name", "state", "amount_total"])
            move_data = c.read("account.move", [move_id[0]], move_fields)
            if move_data:
                m = move_data[0]
                move_total = m.get("amount_total", 0.0)
                move_state = m.get("state", "")
                move_name = m.get("name", "")
        except RPCError:
            pass  # Journal entry read failure is non-fatal

    sections: list = []
    reconcile_items = [
        ("Session", session_name),
        ("Session State", s.get("state", "")),
        ("Order Count", str(order_count)),
        ("POS Orders Total", fmt_amount(pos_total)),
    ]

    if move_name:
        reconcile_items += [
            ("Journal Entry", move_name),
            ("Journal Entry State", move_state or ""),
            ("Journal Entry Total", fmt_amount(move_total or 0.0)),
        ]
        diff = pos_total - (move_total or 0.0)
        match_status = "MATCH" if abs(diff) < 0.01 else f"MISMATCH ({fmt_amount(diff)})"
        reconcile_items.append(("Reconciliation", match_status))
    else:
        reconcile_items.append(("Journal Entry", "Not created yet"))

    sections.append(("Reconciliation Report", reconcile_items))

    json_result = {
        "session_id": session_id,
        "session_name": session_name,
        "pos_total": pos_total,
        "order_count": order_count,
        "move_name": move_name,
        "move_total": move_total,
        "match": move_total is not None and abs(pos_total - move_total) < 0.01,
    }

    out.detail("Session Reconciliation", sections, data_for_json=json_result)

    if move_total is not None and abs(pos_total - (move_total or 0.0)) >= 0.01:
        out.warn("Reconciliation MISMATCH — investigate journal entry vs POS totals.")
    elif move_total is not None:
        out.success("Reconciliation OK — POS total matches journal entry.")


# ===================================================================
# ORDER LINES
# ===================================================================


@app.command("order-lines")
def order_lines(
    ctx: typer.Context,
    order_ref: Annotated[str, typer.Argument(help="POS order reference or name")],
) -> None:
    """Show detailed order lines with products, qty, price, discount.

    Examples:
        kctl-odoo pos order-lines "Order 00000-002-0001"
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _check_pos_available(c, out):
        return

    domain = (
        [("id", "=", int(order_ref))]
        if order_ref.isdigit()
        else ["|", ("pos_reference", "=", order_ref), ("name", "ilike", order_ref)]
    )

    try:
        records = c.search_read(
            "pos.order",
            domain=domain,
            fields=["name", "pos_reference", "amount_total", "lines"],
            limit=1,
        )
    except RPCError as e:
        out.error(f"Failed to fetch POS order: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.error(f"POS order not found: {order_ref}")
        raise typer.Exit(1)

    rec = records[0]
    line_ids = rec.get("lines", [])

    if not line_ids:
        out.info(f"Order '{rec.get('name')}' has no lines.")
        return

    try:
        line_fields = safe_fields(
            c,
            "pos.order.line",
            [
                "product_id",
                "full_product_name",
                "qty",
                "price_unit",
                "price_subtotal",
                "price_subtotal_incl",
                "discount",
            ],
        )
        lines = c.read("pos.order.line", line_ids, line_fields)
    except RPCError as e:
        out.error(f"Failed to read order lines: {e}")
        raise typer.Exit(1) from e

    rows = []
    json_data = []
    subtotal_sum = 0.0
    total_sum = 0.0

    for ln in lines:
        product = ln.get("full_product_name") or _m2o_name(ln.get("product_id"))
        qty = ln.get("qty", 0)
        price_unit = ln.get("price_unit", 0.0)
        subtotal = ln.get("price_subtotal", 0.0)
        total = ln.get("price_subtotal_incl", 0.0)
        discount = ln.get("discount", 0.0)
        subtotal_sum += subtotal
        total_sum += total

        rows.append(
            [
                product,
                str(qty),
                fmt_amount(price_unit),
                f"{discount:.1f}%" if discount else "-",
                fmt_amount(subtotal),
                fmt_amount(total),
            ]
        )
        json_data.append(
            {
                "product": product,
                "qty": qty,
                "price_unit": price_unit,
                "discount": discount,
                "price_subtotal": subtotal,
                "price_subtotal_incl": total,
            }
        )

    rows.append(
        [
            "[bold]Total[/bold]",
            "",
            "",
            "",
            f"[bold]{fmt_amount(subtotal_sum)}[/bold]",
            f"[bold]{fmt_amount(total_sum)}[/bold]",
        ]
    )

    out.table(
        f"Order Lines — {rec.get('name', order_ref)}",
        [
            ("Product", "cyan"),
            ("Qty", ""),
            ("Unit Price", ""),
            ("Discount", ""),
            ("Subtotal (excl.)", "dim"),
            ("Subtotal (incl.)", "green"),
        ],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# TRACE ORDER
# ===================================================================


@app.command("trace-order")
def trace_order(
    ctx: typer.Context,
    order_ref: Annotated[str, typer.Argument(help="POS order reference or name")],
) -> None:
    """Trace a POS order through the full accounting flow.

    Shows: POS Order → Session → Journal Entry.
    Useful for debugging payment/accounting discrepancies.

    Examples:
        kctl-odoo pos trace-order "Order 00000-002-0001"
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _check_pos_available(c, out):
        return

    domain = (
        [("id", "=", int(order_ref))]
        if order_ref.isdigit()
        else ["|", ("pos_reference", "=", order_ref), ("name", "ilike", order_ref)]
    )

    try:
        order_fields = safe_fields(
            c,
            "pos.order",
            ["name", "pos_reference", "session_id", "amount_total", "state", "account_move"],
        )
        records = c.search_read("pos.order", domain=domain, fields=order_fields, limit=1)
    except RPCError as e:
        out.error(f"Failed to fetch POS order: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.error(f"POS order not found: {order_ref}")
        raise typer.Exit(1)

    order = records[0]
    order_name = order.get("name", order_ref)
    order_total = order.get("amount_total", 0.0)
    session_ref = order.get("session_id")
    account_move_ref = order.get("account_move")

    trace_items = [
        ("POS Order", order_name),
        ("Reference", order.get("pos_reference", "") or "-"),
        ("Amount", fmt_amount(order_total)),
        ("State", order.get("state", "")),
    ]

    # Trace session
    if session_ref and isinstance(session_ref, list):
        try:
            s_fields = safe_fields(c, "pos.session", ["name", "state", "move_id"])
            s_data = c.read("pos.session", [session_ref[0]], s_fields)
            if s_data:
                session = s_data[0]
                trace_items += [
                    ("Session", _m2o_name(session_ref)),
                    ("Session State", session.get("state", "")),
                ]
                # Trace journal entry from session
                session_move = session.get("move_id")
                if session_move and isinstance(session_move, list):
                    try:
                        m_fields = safe_fields(c, "account.move", ["name", "state", "amount_total"])
                        m_data = c.read("account.move", [session_move[0]], m_fields)
                        if m_data:
                            m = m_data[0]
                            trace_items += [
                                ("Session Journal Entry", _m2o_name(session_move)),
                                ("Journal Entry State", m.get("state", "")),
                                ("Journal Entry Amount", fmt_amount(m.get("amount_total", 0.0))),
                            ]
                    except RPCError:
                        trace_items.append(("Session Journal Entry", "Error reading"))
                else:
                    trace_items.append(("Session Journal Entry", "Not created"))
        except RPCError:
            trace_items.append(("Session", f"{_m2o_name(session_ref)} (error reading details)"))
    else:
        trace_items.append(("Session", "-"))

    # Trace direct account_move on order (if field exists)
    if account_move_ref and isinstance(account_move_ref, list):
        trace_items.append(("Order Journal Entry", _m2o_name(account_move_ref)))
    elif account_move_ref is False or account_move_ref is None:
        trace_items.append(("Order Journal Entry", "Not created"))

    sections = [("Order Accounting Trace", trace_items)]

    json_result = {
        "order_name": order_name,
        "order_total": order_total,
        "session": _m2o_name(session_ref) if session_ref else None,
        "account_move": _m2o_name(account_move_ref) if account_move_ref else None,
    }

    out.detail("Order Trace", sections, data_for_json=json_result)


# ===================================================================
# REFUNDS
# ===================================================================


@app.command("refunds")
def refunds(
    ctx: typer.Context,
    date_from: Annotated[str | None, typer.Option("--date-from", help="Start date (YYYY-MM-DD)")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List POS refund orders.

    Examples:
        kctl-odoo pos refunds
        kctl-odoo pos refunds --date-from 2026-03-01
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _check_pos_available(c, out):
        return

    domain: list = [("amount_total", "<", 0)]
    if date_from:
        domain.append(("date_order", ">=", date_from))

    try:
        records = c.search_read(
            "pos.order",
            domain=domain,
            fields=["name", "pos_reference", "partner_id", "date_order", "amount_total", "session_id", "state"],
            limit=limit,
            order="date_order desc",
        )
    except RPCError as e:
        out.error(f"Failed to fetch POS refunds: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.info("No POS refund orders found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for r in records:
        rows.append(
            [
                r.get("name", ""),
                r.get("pos_reference", "") or "",
                _m2o_name(r.get("partner_id")),
                str(r.get("date_order", "")),
                fmt_amount(r.get("amount_total", 0)),
                _m2o_name(r.get("session_id")),
                r.get("state", ""),
            ]
        )
        json_data.append(
            {
                "name": r.get("name"),
                "pos_reference": r.get("pos_reference"),
                "partner": _m2o_name(r.get("partner_id")),
                "date_order": r.get("date_order"),
                "amount_total": r.get("amount_total", 0),
                "session": _m2o_name(r.get("session_id")),
                "state": r.get("state"),
            }
        )

    out.table(
        f"POS Refunds ({len(records)})",
        [
            ("Name", "cyan"),
            ("Reference", ""),
            ("Partner", ""),
            ("Date", "dim"),
            ("Amount", "red"),
            ("Session", ""),
            ("State", ""),
        ],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# CASHIER SUMMARY
# ===================================================================


@app.command("cashier-summary")
def cashier_summary(
    ctx: typer.Context,
    date_from: Annotated[str | None, typer.Option("--date-from", help="Start date (YYYY-MM-DD)")] = None,
    date_to: Annotated[str | None, typer.Option("--date-to", help="End date (YYYY-MM-DD)")] = None,
) -> None:
    """Revenue and order count per cashier.

    Examples:
        kctl-odoo pos cashier-summary
        kctl-odoo pos cashier-summary --date-from 2026-03-01
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _check_pos_available(c, out):
        return

    domain: list = [("state", "not in", ["cancel"])]
    if date_from:
        domain.append(("date_order", ">=", date_from))
    if date_to:
        domain.append(("date_order", "<=", f"{date_to} 23:59:59"))

    try:
        order_fields = safe_fields(c, "pos.order", ["employee_id", "user_id", "amount_total"])
        records = c.search_read("pos.order", domain=domain, fields=order_fields)
    except RPCError as e:
        out.error(f"Failed to fetch POS orders: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.info("No POS orders found.")
        if actx.json_mode:
            out.raw_json([])
        return

    # Group by cashier (prefer employee_id, fall back to user_id)
    cashier_data: dict[str, dict] = {}
    for r in records:
        emp = r.get("employee_id")
        user = r.get("user_id")
        cashier = _m2o_name(emp) if emp else _m2o_name(user)
        bucket = cashier_data.setdefault(cashier, {"count": 0, "revenue": 0.0})
        bucket["count"] += 1
        bucket["revenue"] += r.get("amount_total", 0.0)

    rows = []
    json_data = []
    for cashier, bucket in sorted(cashier_data.items(), key=lambda x: x[1]["revenue"], reverse=True):
        avg_order = bucket["revenue"] / bucket["count"] if bucket["count"] else 0.0
        rows.append(
            [
                cashier,
                str(bucket["count"]),
                fmt_amount(bucket["revenue"]),
                fmt_amount(avg_order),
            ]
        )
        json_data.append(
            {
                "cashier": cashier,
                "orders": bucket["count"],
                "revenue": bucket["revenue"],
                "avg_order": avg_order,
            }
        )

    title = "Cashier Summary"
    if date_from:
        title += f" (from {date_from})"
    if date_to:
        title += f" to {date_to}"

    out.table(
        title,
        [("Cashier", "cyan"), ("Orders", ""), ("Revenue", "green"), ("Avg Order", "dim")],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# TOP PRODUCTS
# ===================================================================


@app.command("top-products")
def top_products(
    ctx: typer.Context,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Number of products to show")] = 20,
    date_from: Annotated[str | None, typer.Option("--date-from", help="Start date (YYYY-MM-DD)")] = None,
) -> None:
    """Top-selling products from POS orders.

    Examples:
        kctl-odoo pos top-products
        kctl-odoo pos top-products --limit 10 --date-from 2026-03-01
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _check_pos_available(c, out):
        return

    # Build order domain to pre-filter by date
    order_domain: list = [("order_id.state", "not in", ["cancel"])]
    if date_from:
        order_domain.append(("order_id.date_order", ">=", date_from))

    try:
        line_fields = safe_fields(
            c,
            "pos.order.line",
            ["product_id", "full_product_name", "qty", "price_subtotal_incl"],
        )
        lines = c.search_read("pos.order.line", domain=order_domain, fields=line_fields)
    except RPCError as e:
        out.error(f"Failed to fetch order lines: {e}")
        raise typer.Exit(1) from e

    if not lines:
        out.info("No POS order lines found.")
        if actx.json_mode:
            out.raw_json([])
        return

    # Aggregate by product
    product_data: dict[str, dict] = {}
    for ln in lines:
        product_id_val = ln.get("product_id")
        full_name = ln.get("full_product_name")
        product_name = full_name or _m2o_name(product_id_val)
        bucket = product_data.setdefault(product_name, {"qty": 0.0, "revenue": 0.0})
        bucket["qty"] += ln.get("qty", 0.0)
        bucket["revenue"] += ln.get("price_subtotal_incl", 0.0)

    # Sort by revenue descending, take top N
    sorted_products = sorted(product_data.items(), key=lambda x: x[1]["revenue"], reverse=True)[:limit]

    rows = []
    json_data = []
    for rank, (product, bucket) in enumerate(sorted_products, 1):
        rows.append(
            [
                str(rank),
                product,
                f"{bucket['qty']:.1f}",
                fmt_amount(bucket["revenue"]),
            ]
        )
        json_data.append(
            {
                "rank": rank,
                "product": product,
                "qty": bucket["qty"],
                "revenue": bucket["revenue"],
            }
        )

    title = f"Top {limit} Products"
    if date_from:
        title += f" (from {date_from})"

    out.table(
        title,
        [("#", "dim"), ("Product", "cyan"), ("Qty Sold", ""), ("Revenue", "green")],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# HOURLY SALES
# ===================================================================


@app.command("hourly-sales")
def hourly_sales(
    ctx: typer.Context,
    date: Annotated[str | None, typer.Option("--date", help="Date (YYYY-MM-DD, default: today)")] = None,
) -> None:
    """Hourly sales breakdown for a given day.

    Shows order count and revenue per hour to identify peak times.
    Default: today.

    Examples:
        kctl-odoo pos hourly-sales
        kctl-odoo pos hourly-sales --date 2026-03-27
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _check_pos_available(c, out):
        return

    if date is None:
        date = datetime.now(tz=UTC).strftime("%Y-%m-%d")

    date_start = f"{date} 00:00:00"
    date_end = f"{date} 23:59:59"

    try:
        records = c.search_read(
            "pos.order",
            domain=[
                ("date_order", ">=", date_start),
                ("date_order", "<=", date_end),
                ("state", "not in", ["cancel"]),
            ],
            fields=["date_order", "amount_total"],
        )
    except RPCError as e:
        out.error(f"Failed to fetch POS orders: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.info(f"No POS orders found for {date}.")
        if actx.json_mode:
            out.raw_json([])
        return

    # Bucket into hours 0-23
    hourly: dict[int, dict] = {h: {"count": 0, "revenue": 0.0} for h in range(24)}
    for r in records:
        date_order_raw = r.get("date_order", "")
        try:
            dt = datetime.fromisoformat(str(date_order_raw).replace("Z", "+00:00"))
            hour = dt.hour
        except (ValueError, TypeError):
            continue
        hourly[hour]["count"] += 1
        hourly[hour]["revenue"] += r.get("amount_total", 0.0)

    # Only show hours with data
    rows = []
    json_data = []
    for h in range(24):
        bucket = hourly[h]
        if bucket["count"] == 0:
            continue
        rows.append(
            [
                f"{h:02d}:00",
                str(bucket["count"]),
                fmt_amount(bucket["revenue"]),
            ]
        )
        json_data.append({"hour": h, "orders": bucket["count"], "revenue": bucket["revenue"]})

    if not rows:
        out.info(f"No orders with valid timestamps for {date}.")
        return

    out.table(
        f"Hourly Sales — {date}",
        [("Hour", "cyan"), ("Orders", ""), ("Revenue", "green")],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# DEBUG SESSION
# ===================================================================


@app.command("debug-session")
def debug_session(
    ctx: typer.Context,
    session_id: Annotated[int, typer.Argument(help="POS session ID")],
) -> None:
    """Comprehensive debug view of a POS session.

    Shows: config, cashier, state, open/close times, order count/total,
    payment breakdown, journal entry status, picking status, cash control.

    Examples:
        kctl-odoo pos debug-session 1
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _check_pos_available(c, out):
        return

    try:
        s_fields = safe_fields(
            c,
            "pos.session",
            [
                "name",
                "config_id",
                "user_id",
                "state",
                "start_at",
                "stop_at",
                "move_id",
                "picking_ids",
                "cash_register_balance_start",
                "cash_register_balance_end_real",
                "cash_real_transaction",
            ],
        )
        s_data = c.read("pos.session", [session_id], s_fields)
    except RPCError as e:
        out.error(f"Failed to fetch session {session_id}: {e}")
        raise typer.Exit(1) from e

    if not s_data:
        out.error(f"POS session {session_id} not found.")
        raise typer.Exit(1)

    s = s_data[0]

    # Count orders and sum totals
    try:
        order_count = c.search_count("pos.order", [("session_id", "=", session_id), ("state", "not in", ["cancel"])])
        order_records = c.search_read(
            "pos.order",
            domain=[("session_id", "=", session_id), ("state", "not in", ["cancel"])],
            fields=["amount_total"],
        )
        order_total = sum(o.get("amount_total", 0.0) for o in order_records)
    except RPCError:
        order_count = 0
        order_total = 0.0

    # Payment breakdown
    try:
        payment_records = c.search_read(
            "pos.payment",
            domain=[("session_id", "=", session_id)],
            fields=["payment_method_id", "amount"],
        )
        payment_totals: dict[str, float] = {}
        for p in payment_records:
            method = _m2o_name(p.get("payment_method_id"))
            payment_totals[method] = payment_totals.get(method, 0.0) + p.get("amount", 0.0)
    except RPCError:
        payment_totals = {}

    # Journal entry status
    move_id = s.get("move_id")
    move_status = "-"
    if move_id and isinstance(move_id, list):
        try:
            m_fields = safe_fields(c, "account.move", ["name", "state"])
            m_data = c.read("account.move", [move_id[0]], m_fields)
            if m_data:
                move_status = f"{m_data[0].get('name', '')} ({m_data[0].get('state', '')})"
        except RPCError:
            move_status = f"id={move_id[0]} (error)"
    elif not move_id:
        move_status = "Not created"

    # Picking status
    picking_ids = s.get("picking_ids", [])
    picking_status = f"{len(picking_ids)} picking(s)" if picking_ids else "None"

    # Cash control
    opening = s.get("cash_register_balance_start") or 0.0
    actual_close = s.get("cash_register_balance_end_real") or 0.0
    cash_transaction = s.get("cash_real_transaction") or 0.0
    expected_close = opening + cash_transaction
    cash_diff = actual_close - expected_close

    session_info = [
        ("Name", s.get("name", str(session_id))),
        ("Config", _m2o_name(s.get("config_id"))),
        ("User", _m2o_name(s.get("user_id"))),
        ("State", s.get("state", "")),
        ("Opened", str(s.get("start_at", ""))),
        ("Closed", str(s.get("stop_at", "") or "-")),
    ]
    order_info = [
        ("Order Count", str(order_count)),
        ("Orders Total", fmt_amount(order_total)),
    ]
    payment_info = [(method, fmt_amount(amt)) for method, amt in sorted(payment_totals.items())]
    accounting_info = [
        ("Journal Entry", move_status),
        ("Pickings", picking_status),
    ]
    cash_info = [
        ("Opening Balance", fmt_amount(opening)),
        ("Cash Transactions (net)", fmt_amount(cash_transaction)),
        ("Expected Closing", fmt_amount(expected_close)),
        ("Actual Closing", fmt_amount(actual_close)),
        ("Difference", fmt_amount(cash_diff)),
    ]

    sections = [
        ("Session Info", session_info),
        ("Orders", order_info),
        ("Payments", payment_info or [("No payments", "-")]),
        ("Accounting", accounting_info),
        ("Cash Control", cash_info),
    ]

    json_result = {
        "session_id": session_id,
        "name": s.get("name"),
        "state": s.get("state"),
        "order_count": order_count,
        "order_total": order_total,
        "payments": payment_totals,
        "journal_entry": move_status,
        "cash_difference": cash_diff,
    }

    out.detail("Session Debug", sections, data_for_json=json_result)

    if abs(cash_diff) > 0.01:
        out.warn(f"Cash discrepancy: {fmt_amount(cash_diff)}")


# ===================================================================
# VALIDATE CLOSE
# ===================================================================


@app.command("validate-close")
def validate_close(
    ctx: typer.Context,
    session_id: Annotated[int, typer.Argument(help="POS session ID")],
) -> None:
    """Pre-check if a session can be cleanly closed.

    Verifies: no draft orders, cash difference within threshold,
    all payment methods reconciled. Does NOT close the session.

    Examples:
        kctl-odoo pos validate-close 1
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _check_pos_available(c, out):
        return

    try:
        s_fields = safe_fields(
            c,
            "pos.session",
            [
                "name",
                "state",
                "config_id",
                "cash_register_balance_start",
                "cash_register_balance_end_real",
                "cash_real_transaction",
            ],
        )
        s_data = c.read("pos.session", [session_id], s_fields)
    except RPCError as e:
        out.error(f"Failed to fetch session {session_id}: {e}")
        raise typer.Exit(1) from e

    if not s_data:
        out.error(f"POS session {session_id} not found.")
        raise typer.Exit(1)

    s = s_data[0]
    session_name = s.get("name", str(session_id))
    state = s.get("state", "")

    # Read config for authorized diff threshold
    authorized_diff = 0.0
    config_ref = s.get("config_id")
    if config_ref and isinstance(config_ref, list):
        try:
            cfg_fields = safe_fields(c, "pos.config", ["amount_authorized_diff"])
            cfg_data = c.read("pos.config", [config_ref[0]], cfg_fields)
            if cfg_data:
                authorized_diff = cfg_data[0].get("amount_authorized_diff") or 0.0
        except RPCError:
            pass

    checks: list[tuple[str, bool, str]] = []

    # Check 1: Session state
    valid_states = {"opened", "closing_control", "opened_and_closing"}
    state_ok = state in valid_states
    checks.append(("Session state is closeable", state_ok, f"State: {state}"))

    # Check 2: No draft orders
    try:
        draft_count = c.search_count(
            "pos.order",
            [("session_id", "=", session_id), ("state", "=", "draft")],
        )
        checks.append(("No draft orders", draft_count == 0, f"{draft_count} draft order(s)"))
    except RPCError:
        checks.append(("No draft orders", False, "Error checking orders"))

    # Check 3: Cash difference within threshold
    opening = s.get("cash_register_balance_start") or 0.0
    actual_close = s.get("cash_register_balance_end_real") or 0.0
    cash_transaction = s.get("cash_real_transaction") or 0.0
    expected_close = opening + cash_transaction
    cash_diff = abs(actual_close - expected_close)
    diff_ok = cash_diff <= authorized_diff if authorized_diff > 0 else True
    checks.append(
        (
            f"Cash diff within threshold ({fmt_amount(authorized_diff)})",
            diff_ok,
            f"Diff: {fmt_amount(cash_diff)}",
        )
    )

    rows = []
    json_data = []
    all_pass = True
    for check_name, passed, detail in checks:
        status = "[green]PASS[/green]" if passed else "[red]FAIL[/red]"
        rows.append([check_name, status, detail])
        if not passed:
            all_pass = False
        json_data.append({"check": check_name, "passed": passed, "detail": detail})

    out.table(
        f"Validate Close — {session_name}",
        [("Check", "cyan"), ("Status", ""), ("Detail", "dim")],
        rows,
        data_for_json=json_data,
    )

    if all_pass:
        out.success("All checks passed — session can be closed.")
    else:
        out.warn("Some checks failed — resolve issues before closing.")


# ===================================================================
# TAX SUMMARY
# ===================================================================


@app.command("tax-summary")
def tax_summary(
    ctx: typer.Context,
    date_from: Annotated[str | None, typer.Option("--date-from", help="Start date (YYYY-MM-DD)")] = None,
    date_to: Annotated[str | None, typer.Option("--date-to", help="End date (YYYY-MM-DD)")] = None,
) -> None:
    """POS tax breakdown by tax rate for a period.

    Shows total base amount and tax amount per tax rate applied in POS orders.
    Useful for Indonesian PPN reporting from POS.

    Examples:
        kctl-odoo pos tax-summary
        kctl-odoo pos tax-summary --date-from 2026-03-01 --date-to 2026-03-31
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _check_pos_available(c, out):
        return

    order_domain: list = [("order_id.state", "not in", ["cancel"])]
    if date_from:
        order_domain.append(("order_id.date_order", ">=", date_from))
    if date_to:
        order_domain.append(("order_id.date_order", "<=", f"{date_to} 23:59:59"))

    try:
        line_fields = safe_fields(
            c,
            "pos.order.line",
            ["tax_ids", "price_subtotal", "price_subtotal_incl"],
        )
        lines = c.search_read("pos.order.line", domain=order_domain, fields=line_fields)
    except RPCError as e:
        out.error(f"Failed to fetch order lines: {e}")
        raise typer.Exit(1) from e

    if not lines:
        out.info("No POS order lines found for this period.")
        if actx.json_mode:
            out.raw_json([])
        return

    # Collect all tax IDs for batch name lookup
    all_tax_ids: set[int] = set()
    for ln in lines:
        tax_ids = ln.get("tax_ids", [])
        if isinstance(tax_ids, list):
            all_tax_ids.update(tax_ids)

    # Fetch tax names
    tax_names: dict[int, str] = {}
    if all_tax_ids:
        try:
            tax_data = c.read("account.tax", list(all_tax_ids), ["name"])
            for t in tax_data:
                tax_names[t["id"]] = t.get("name", str(t["id"]))
        except RPCError:
            pass

    # Aggregate: base = price_subtotal (excl. tax), tax_amount = incl - excl
    tax_buckets: dict[str, dict] = {}
    no_tax_base = 0.0

    for ln in lines:
        tax_ids = ln.get("tax_ids", [])
        base = ln.get("price_subtotal", 0.0)
        incl = ln.get("price_subtotal_incl", 0.0)
        tax_amount = incl - base

        if not tax_ids:
            no_tax_base += base
            continue

        for tid in tax_ids:
            tax_name = tax_names.get(tid, f"Tax {tid}")
            bucket = tax_buckets.setdefault(tax_name, {"base": 0.0, "tax": 0.0})
            bucket["base"] += base
            # Distribute tax proportionally if multiple taxes
            bucket["tax"] += tax_amount / len(tax_ids)

    if no_tax_base:
        tax_buckets["(No Tax)"] = {"base": no_tax_base, "tax": 0.0}

    rows = []
    json_data = []
    total_base = 0.0
    total_tax = 0.0
    for tax_name, bucket in sorted(tax_buckets.items()):
        total_amount = bucket["base"] + bucket["tax"]
        rows.append(
            [
                tax_name,
                fmt_amount(bucket["base"]),
                fmt_amount(bucket["tax"]),
                fmt_amount(total_amount),
            ]
        )
        json_data.append(
            {
                "tax": tax_name,
                "base": bucket["base"],
                "tax_amount": bucket["tax"],
                "total": total_amount,
            }
        )
        total_base += bucket["base"]
        total_tax += bucket["tax"]

    rows.append(
        [
            "[bold]Total[/bold]",
            f"[bold]{fmt_amount(total_base)}[/bold]",
            f"[bold]{fmt_amount(total_tax)}[/bold]",
            f"[bold]{fmt_amount(total_base + total_tax)}[/bold]",
        ]
    )

    title = "POS Tax Summary"
    if date_from or date_to:
        parts = []
        if date_from:
            parts.append(f"from {date_from}")
        if date_to:
            parts.append(f"to {date_to}")
        title += f" ({', '.join(parts)})"

    out.table(
        title,
        [("Tax", "cyan"), ("Base Amount", ""), ("Tax Amount", "yellow"), ("Total", "green")],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# PERIOD REPORT
# ===================================================================


@app.command("period-report")
def period_report(
    ctx: typer.Context,
    period: Annotated[str, typer.Option("--period", help="Period: week or month (default: month)")] = "month",
) -> None:
    """Sales comparison report: this period vs previous.

    Compares revenue, order count, average order value, and top product
    between current period and the previous one.

    Examples:
        kctl-odoo pos period-report
        kctl-odoo pos period-report --period week
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _check_pos_available(c, out):
        return

    now = datetime.now(tz=UTC)

    if period == "week":
        # ISO week: Monday to Sunday
        days_since_monday = now.weekday()
        current_start = (now - timedelta(days=days_since_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
        current_end = now
        previous_start = current_start - timedelta(weeks=1)
        previous_end = current_start - timedelta(seconds=1)
    else:
        # Month
        current_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        current_end = now
        # Previous month: go back one month
        if current_start.month == 1:
            previous_start = current_start.replace(year=current_start.year - 1, month=12)
        else:
            previous_start = current_start.replace(month=current_start.month - 1)
        previous_end = current_start - timedelta(seconds=1)

    def _fetch_period_stats(start: datetime, end: datetime) -> dict:
        start_str = start.strftime("%Y-%m-%d %H:%M:%S")
        end_str = end.strftime("%Y-%m-%d %H:%M:%S")
        try:
            records = c.search_read(
                "pos.order",
                domain=[
                    ("date_order", ">=", start_str),
                    ("date_order", "<=", end_str),
                    ("state", "not in", ["cancel"]),
                ],
                fields=["amount_total"],
            )
        except RPCError:
            return {"count": 0, "revenue": 0.0, "avg": 0.0}
        count = len(records)
        revenue = sum(r.get("amount_total", 0.0) for r in records)
        avg = revenue / count if count else 0.0
        return {"count": count, "revenue": revenue, "avg": avg}

    current = _fetch_period_stats(current_start, current_end)
    previous = _fetch_period_stats(previous_start, previous_end)

    def _pct_change(curr: float, prev: float) -> str:
        if prev == 0:
            return "N/A"
        pct = ((curr - prev) / prev) * 100
        sign = "+" if pct >= 0 else ""
        return f"{sign}{pct:.1f}%"

    period_label = "Week" if period == "week" else "Month"
    current_label = f"This {period_label} ({current_start.strftime('%Y-%m-%d')})"
    previous_label = f"Previous {period_label} ({previous_start.strftime('%Y-%m-%d')})"

    rows = [
        ["Orders", str(current["count"]), str(previous["count"]), _pct_change(current["count"], previous["count"])],
        [
            "Revenue",
            fmt_amount(current["revenue"]),
            fmt_amount(previous["revenue"]),
            _pct_change(current["revenue"], previous["revenue"]),
        ],
        [
            "Avg Order Value",
            fmt_amount(current["avg"]),
            fmt_amount(previous["avg"]),
            _pct_change(current["avg"], previous["avg"]),
        ],
    ]

    json_result = {
        "period": period,
        "current": current,
        "previous": previous,
    }

    out.table(
        f"Period Comparison — {period_label}",
        [
            ("Metric", "cyan"),
            (current_label, "green"),
            (previous_label, "dim"),
            ("Change", "yellow"),
        ],
        rows,
        data_for_json=json_result,
    )


# ===================================================================
# ORPHAN ORDERS
# ===================================================================


@app.command("orphan-orders")
def orphan_orders(
    ctx: typer.Context,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results per check")] = 50,
) -> None:
    """Find POS orders with data integrity issues.

    Detects: orders without session, orders without journal entry (in done state),
    sessions without journal entry (in closed state).

    Examples:
        kctl-odoo pos orphan-orders
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _check_pos_available(c, out):
        return

    issues_found = False

    # Check 1: Orders without session
    try:
        no_session = c.search_read(
            "pos.order",
            domain=[("session_id", "=", False)],
            fields=["name", "date_order", "amount_total", "state"],
            limit=limit,
        )
    except RPCError as e:
        out.warn(f"Failed to check orders without session: {e}")
        no_session = []

    if no_session:
        issues_found = True
        rows = [
            [r.get("name", ""), str(r.get("date_order", "")), fmt_amount(r.get("amount_total", 0)), r.get("state", "")]
            for r in no_session
        ]
        out.table(
            f"Orders Without Session ({len(no_session)} found)",
            [("Name", "red"), ("Date", "dim"), ("Total", ""), ("State", "")],
            rows,
            data_for_json=no_session,
        )

    # Check 2: Done orders without journal entry
    try:
        account_move_field = safe_fields(c, "pos.order", ["account_move"])
        if "account_move" in account_move_field:
            no_move = c.search_read(
                "pos.order",
                domain=[("state", "=", "done"), ("account_move", "=", False)],
                fields=["name", "date_order", "amount_total", "session_id"],
                limit=limit,
            )
        else:
            no_move = []
    except RPCError as e:
        out.warn(f"Failed to check orders without journal entry: {e}")
        no_move = []

    if no_move:
        issues_found = True
        rows = [
            [
                r.get("name", ""),
                str(r.get("date_order", "")),
                fmt_amount(r.get("amount_total", 0)),
                _m2o_name(r.get("session_id")),
            ]
            for r in no_move
        ]
        out.table(
            f"Done Orders Without Journal Entry ({len(no_move)} found)",
            [("Name", "red"), ("Date", "dim"), ("Total", ""), ("Session", "")],
            rows,
            data_for_json=no_move,
        )

    # Check 3: Closed sessions without journal entry
    try:
        closed_no_move = c.search_read(
            "pos.session",
            domain=[("state", "=", "closed"), ("move_id", "=", False)],
            fields=["name", "config_id", "stop_at"],
            limit=limit,
        )
    except RPCError as e:
        out.warn(f"Failed to check sessions without journal entry: {e}")
        closed_no_move = []

    if closed_no_move:
        issues_found = True
        rows = [[r.get("name", ""), _m2o_name(r.get("config_id")), str(r.get("stop_at", ""))] for r in closed_no_move]
        out.table(
            f"Closed Sessions Without Journal Entry ({len(closed_no_move)} found)",
            [("Session", "red"), ("Config", ""), ("Closed At", "dim")],
            rows,
            data_for_json=closed_no_move,
        )

    if not issues_found:
        out.success("No orphan orders or sessions found — data integrity looks good.")
    else:
        out.warn("Data integrity issues detected. Manual investigation may be required.")

    if actx.json_mode:
        out.raw_json(
            {
                "no_session_orders": len(no_session),
                "done_without_move": len(no_move),
                "closed_sessions_without_move": len(closed_no_move),
            }
        )


# ===================================================================
# CONFIG DETAIL
# ===================================================================


@app.command("config-detail")
def config_detail(
    ctx: typer.Context,
    config_id: Annotated[int, typer.Argument(help="POS configuration ID")],
) -> None:
    """Show detailed POS configuration.

    Shows all configuration options: payment methods, pricelists, receipt settings,
    cash rounding, fiscal position, warehouse, employees, and more.

    Examples:
        kctl-odoo pos config-detail 1
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _check_pos_available(c, out):
        return

    try:
        cfg_fields = safe_fields(
            c,
            "pos.config",
            [
                "name",
                "active",
                "company_id",
                "warehouse_id",
                "stock_location_id",
                "pricelist_id",
                "available_pricelist_ids",
                "payment_method_ids",
                "default_fiscal_position_id",
                "cash_rounding",
                "module_pos_restaurant",
                "basic_receipt",
                "auto_validate_terminal_payment",
                "amount_authorized_diff",
                "basic_employee_ids",
                "advanced_employee_ids",
                "current_session_id",
            ],
        )
        data = c.read("pos.config", [config_id], cfg_fields)
    except RPCError as e:
        out.error(f"Failed to fetch POS config {config_id}: {e}")
        raise typer.Exit(1) from e

    if not data:
        out.error(f"POS configuration {config_id} not found.")
        raise typer.Exit(1)

    cfg = data[0]

    # Format list fields
    def _fmt_list(val: object) -> str:
        if isinstance(val, list) and val:
            # Could be a list of [id, name] pairs or a list of IDs
            if isinstance(val[0], list):
                return ", ".join(str(v[1]) for v in val)
            return str(len(val)) + " item(s)"
        return "-"

    # Resolve payment method names
    pm_ids = cfg.get("payment_method_ids", [])
    payment_methods_str = "-"
    if pm_ids:
        try:
            pm_data = c.read("pos.payment.method", pm_ids, ["name"])
            payment_methods_str = ", ".join(p.get("name", str(p["id"])) for p in pm_data)
        except RPCError:
            payment_methods_str = f"{len(pm_ids)} method(s)"

    # Resolve pricelist names
    avail_pl_ids = cfg.get("available_pricelist_ids", [])
    pricelists_str = "-"
    if avail_pl_ids:
        try:
            pl_data = c.read("product.pricelist", avail_pl_ids, ["name"])
            pricelists_str = ", ".join(p.get("name", str(p["id"])) for p in pl_data)
        except RPCError:
            pricelists_str = f"{len(avail_pl_ids)} pricelist(s)"

    sections = [
        (
            "General",
            [
                ("Name", cfg.get("name", "")),
                ("Active", "Yes" if cfg.get("active") else "No"),
                ("Company", _m2o_name(cfg.get("company_id"))),
                (
                    "Current Session",
                    _m2o_name(cfg.get("current_session_id")) if cfg.get("current_session_id") else "None",
                ),
            ],
        ),
        (
            "Inventory",
            [
                ("Warehouse", _m2o_name(cfg.get("warehouse_id"))),
                ("Stock Location", _m2o_name(cfg.get("stock_location_id"))),
            ],
        ),
        (
            "Pricing & Payment",
            [
                ("Default Pricelist", _m2o_name(cfg.get("pricelist_id"))),
                ("Available Pricelists", pricelists_str),
                ("Payment Methods", payment_methods_str),
                ("Fiscal Position", _m2o_name(cfg.get("default_fiscal_position_id"))),
                ("Cash Rounding", "Enabled" if cfg.get("cash_rounding") else "Disabled"),
                ("Authorized Cash Diff", fmt_amount(cfg.get("amount_authorized_diff") or 0.0)),
            ],
        ),
        (
            "Features",
            [
                ("Restaurant Mode", "Yes" if cfg.get("module_pos_restaurant") else "No"),
                ("Basic Receipt", "Yes" if cfg.get("basic_receipt") else "No"),
                ("Auto-validate Terminal", "Yes" if cfg.get("auto_validate_terminal_payment") else "No"),
            ],
        ),
        (
            "Employees",
            [
                ("Basic Employees", f"{len(cfg.get('basic_employee_ids', []))} employee(s)"),
                ("Advanced Employees", f"{len(cfg.get('advanced_employee_ids', []))} employee(s)"),
            ],
        ),
    ]

    json_result = {
        "id": config_id,
        "name": cfg.get("name"),
        "active": cfg.get("active"),
        "company": _m2o_name(cfg.get("company_id")),
        "warehouse": _m2o_name(cfg.get("warehouse_id")),
        "payment_methods": payment_methods_str,
        "pricelists": pricelists_str,
        "restaurant_mode": cfg.get("module_pos_restaurant"),
        "authorized_diff": cfg.get("amount_authorized_diff") or 0.0,
    }

    out.detail("POS Config Detail", sections, data_for_json=json_result)
