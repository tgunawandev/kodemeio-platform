"""Sales operations commands — orders, deliveries, invoicing."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

import typer

from kctl_odoo.core.biz_helpers import fmt_amount, model_available, module_hint, period_domain
from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.exceptions import RPCError

app = typer.Typer(help="Sales operations: orders, deliveries, invoicing.")


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
            model, [(field, "ilike", value)], ["id", "display_name"], limit=1
        )
    if not recs:
        raise typer.BadParameter(f"{label} not found: {value}")
    return recs[0]["id"], recs[0].get("display_name", str(recs[0]["id"]))


def _fmt_amount(amount: float) -> str:
    """Format a monetary amount with thousands separator."""
    if amount >= 0:
        return f"{amount:,.2f}"
    return f"-{abs(amount):,.2f}"


# ===================================================================
# LIST ORDERS
# ===================================================================


@app.command("orders")
def orders(
    ctx: typer.Context,
    state: Annotated[
        str | None, typer.Option("--state", "-s", help="Filter by state: draft, sale, done, cancel")
    ] = None,
    partner: Annotated[str | None, typer.Option("--partner", help="Filter by partner name")] = None,
    date_from: Annotated[str | None, typer.Option("--date-from", help="From date (YYYY-MM-DD)")] = None,
    date_to: Annotated[str | None, typer.Option("--date-to", help="To date (YYYY-MM-DD)")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List sale orders with key fields.

    Examples:
        kctl-odoo sales orders
        kctl-odoo sales orders --state sale --limit 20
        kctl-odoo sales orders --partner "PT Maju"
        kctl-odoo sales orders --date-from 2025-01-01 --date-to 2025-01-31
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    domain: list = []
    if state:
        domain.append(("state", "=", state))
    if partner:
        domain.append(("partner_id.name", "ilike", partner))
    if date_from:
        domain.append(("date_order", ">=", date_from))
    if date_to:
        domain.append(("date_order", "<=", date_to))

    try:
        records = c.search_read(
            "sale.order",
            domain=domain,
            fields=["name", "partner_id", "date_order", "amount_total", "state", "invoice_status"],
            limit=limit,
            order="date_order desc",
        )
    except RPCError as e:
        out.error(f"Failed to list sale orders: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.info("No sale orders found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for r in records:
        rows.append(
            [
                r["name"],
                _m2o_name(r.get("partner_id")),
                str(r.get("date_order", "")),
                _fmt_amount(r.get("amount_total", 0)),
                r.get("state", ""),
                r.get("invoice_status", ""),
            ]
        )
        json_data.append(
            {
                "name": r["name"],
                "partner": _m2o_name(r.get("partner_id")),
                "date_order": r.get("date_order"),
                "amount_total": r.get("amount_total", 0),
                "state": r.get("state"),
                "invoice_status": r.get("invoice_status"),
            }
        )

    out.table(
        f"Sale Orders ({len(records)})",
        [
            ("Name", "cyan"),
            ("Partner", ""),
            ("Date", "dim"),
            ("Total", ""),
            ("State", ""),
            ("Invoice", ""),
        ],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# ORDER DETAIL
# ===================================================================


@app.command("get-order")
def order_get(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Sale order name (e.g. S00001) or numeric ID")],
) -> None:
    """Get sale order detail by name or ID.

    Shows header information and order lines.

    Examples:
        kctl-odoo sales get-order S00001
        kctl-odoo sales get-order 42
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Resolve the order
    domain = [("id", "=", int(name))] if name.isdigit() else [("name", "=", name)]

    try:
        records = c.search_read(
            "sale.order",
            domain=domain,
            fields=[
                "name",
                "partner_id",
                "date_order",
                "amount_untaxed",
                "amount_tax",
                "amount_total",
                "state",
                "invoice_status",
                "order_line",
            ],
            limit=1,
        )
    except RPCError as e:
        out.error(f"Failed to fetch sale order: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.error(f"Sale order not found: {name}")
        raise typer.Exit(1)

    rec = records[0]

    # Header
    header_sections = [
        (
            "Sale Order",
            [
                ("Name", rec["name"]),
                ("Partner", _m2o_name(rec.get("partner_id"))),
                ("Date", str(rec.get("date_order", ""))),
                ("Untaxed", _fmt_amount(rec.get("amount_untaxed", 0))),
                ("Tax", _fmt_amount(rec.get("amount_tax", 0))),
                ("Total", _fmt_amount(rec.get("amount_total", 0))),
                ("State", rec.get("state", "")),
                ("Invoice Status", rec.get("invoice_status", "")),
            ],
        )
    ]

    json_result = {
        "name": rec["name"],
        "partner": _m2o_name(rec.get("partner_id")),
        "date_order": rec.get("date_order"),
        "amount_untaxed": rec.get("amount_untaxed", 0),
        "amount_tax": rec.get("amount_tax", 0),
        "amount_total": rec.get("amount_total", 0),
        "state": rec.get("state"),
        "invoice_status": rec.get("invoice_status"),
        "lines": [],
    }

    out.detail("Sale Order Detail", header_sections, data_for_json=json_result)

    # Order lines
    line_ids = rec.get("order_line", [])
    if line_ids:
        try:
            lines = c.read(
                "sale.order.line",
                line_ids,
                ["product_id", "product_uom_qty", "price_unit", "price_subtotal"],
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
                    str(ln.get("product_uom_qty", 0)),
                    _fmt_amount(ln.get("price_unit", 0)),
                    _fmt_amount(ln.get("price_subtotal", 0)),
                ]
            )
            lines_json.append(
                {
                    "product": _m2o_name(ln.get("product_id")),
                    "qty": ln.get("product_uom_qty", 0),
                    "price_unit": ln.get("price_unit", 0),
                    "price_subtotal": ln.get("price_subtotal", 0),
                }
            )

        json_result["lines"] = lines_json

        out.table(
            "Order Lines",
            [("Product", ""), ("Qty", ""), ("Unit Price", ""), ("Subtotal", "")],
            rows,
            data_for_json=lines_json,
        )


# ===================================================================
# CREATE ORDER
# ===================================================================


@app.command("create-order")
def order_create(
    ctx: typer.Context,
    partner_name: Annotated[str, typer.Option("--partner", help="Partner name or ID")],
    product_name: Annotated[str, typer.Option("--product", help="Product name or ID")],
    qty: Annotated[float, typer.Option("--qty", help="Quantity")] = 1.0,
    price: Annotated[
        float | None, typer.Option("--price", help="Unit price (uses product list price if omitted)")
    ] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview without creating")] = False,
    force: Annotated[bool, typer.Option("--force", "-y", help="Skip confirmation prompt")] = False,
) -> None:
    """Create a sale order with one line.

    Resolves partner and product by name.  Uses product list price if
    ``--price`` is not specified.

    Examples:
        kctl-odoo sales create-order --partner "PT Maju" --product "Widget" --qty 10
        kctl-odoo sales create-order --partner 5 --product 12 --qty 5 --price 100
        kctl-odoo sales create-order --partner "PT Maju" --product "Widget" --dry-run
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    try:
        partner_id, partner_display = _resolve(c, "res.partner", "name", partner_name, "Partner")
        product_id, product_display = _resolve(c, "product.product", "name", product_name, "Product")
    except typer.BadParameter as e:
        out.error(str(e))
        raise typer.Exit(1) from e

    # If no price given, fetch list price from product
    if price is None:
        try:
            prod_data = c.read("product.product", [product_id], ["list_price"])
            price = prod_data[0].get("list_price", 0.0) if prod_data else 0.0
        except RPCError:
            price = 0.0

    line_vals = {
        "product_id": product_id,
        "product_uom_qty": qty,
        "price_unit": price,
    }

    order_vals = {
        "partner_id": partner_id,
        "order_line": [(0, 0, line_vals)],
    }

    summary = {
        "partner": partner_display,
        "product": product_display,
        "qty": qty,
        "price_unit": price,
        "line_total": qty * price,
    }

    if dry_run:
        out.info("Dry run — order will NOT be created.")
        out.detail(
            "Sale Order Preview",
            [
                (
                    "Order",
                    [
                        ("Partner", partner_display),
                        ("Product", product_display),
                        ("Qty", str(qty)),
                        ("Unit Price", _fmt_amount(price)),
                        ("Line Total", _fmt_amount(qty * price)),
                    ],
                )
            ],
            data_for_json=summary,
        )
        return

    if not force:
        out.info(f"Create SO: partner={partner_display}, product={product_display}, qty={qty}, price={price}")
        if not typer.confirm("Create this sale order?"):
            raise typer.Exit(0)

    try:
        order_id = c.create("sale.order", order_vals)
    except RPCError as e:
        out.error(f"Failed to create sale order: {e}")
        raise typer.Exit(1) from e

    # Re-read to get the generated name
    try:
        created = c.read("sale.order", [order_id], ["name"])
        order_name = created[0]["name"] if created else str(order_id)
    except RPCError:
        order_name = str(order_id)

    out.success(f"Created sale order {order_name} (id={order_id})")

    if actx.json_mode:
        out.raw_json({"id": order_id, "name": order_name, **summary})


# ===================================================================
# CONFIRM ORDER
# ===================================================================


@app.command("confirm-order")
def order_confirm(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Sale order name (e.g. S00001) or numeric ID")],
    force: Annotated[bool, typer.Option("--force", "-y", help="Skip confirmation prompt")] = False,
) -> None:
    """Confirm a draft sale order.

    Examples:
        kctl-odoo sales confirm-order S00001
        kctl-odoo sales confirm-order S00001 --force
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    try:
        order_id, order_display = _resolve(c, "sale.order", "name", name, "Sale Order")
    except typer.BadParameter as e:
        out.error(str(e))
        raise typer.Exit(1) from e

    if not force and not typer.confirm(f"Confirm sale order {order_display}?"):
        raise typer.Exit(0)

    try:
        c.execute_kw("sale.order", "action_confirm", [[order_id]])
    except RPCError as e:
        out.error(f"Failed to confirm {order_display}: {e}")
        raise typer.Exit(1) from e

    out.success(f"Confirmed sale order {order_display}")

    if actx.json_mode:
        out.raw_json({"id": order_id, "name": order_display, "action": "confirmed"})


# ===================================================================
# LIST DELIVERIES
# ===================================================================


@app.command("deliveries")
def deliveries(
    ctx: typer.Context,
    state: Annotated[str | None, typer.Option("--state", "-s", help="Filter by state: assigned, done, waiting")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List outgoing deliveries (sale-related stock pickings).

    Examples:
        kctl-odoo sales deliveries
        kctl-odoo sales deliveries --state assigned
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    domain: list = [("picking_type_code", "=", "outgoing")]
    if state:
        domain.append(("state", "=", state))

    try:
        records = c.search_read(
            "stock.picking",
            domain=domain,
            fields=["name", "partner_id", "scheduled_date", "state", "origin"],
            limit=limit,
            order="scheduled_date desc",
        )
    except RPCError as e:
        out.error(f"Failed to list deliveries: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.info("No outgoing deliveries found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for r in records:
        rows.append(
            [
                r["name"],
                _m2o_name(r.get("partner_id")),
                str(r.get("scheduled_date", "")),
                r.get("state", ""),
                str(r.get("origin", "")),
            ]
        )
        json_data.append(
            {
                "name": r["name"],
                "partner": _m2o_name(r.get("partner_id")),
                "scheduled_date": r.get("scheduled_date"),
                "state": r.get("state"),
                "origin": r.get("origin"),
            }
        )

    out.table(
        f"Outgoing Deliveries ({len(records)})",
        [
            ("Name", "cyan"),
            ("Partner", ""),
            ("Scheduled", "dim"),
            ("State", ""),
            ("Origin", ""),
        ],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# VALIDATE DELIVERY
# ===================================================================


@app.command("validate-delivery")
def delivery_validate(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Delivery order name (e.g. WH/OUT/00001) or numeric ID")],
    force: Annotated[bool, typer.Option("--force", "-y", help="Skip confirmation prompt")] = False,
) -> None:
    """Validate an outgoing delivery picking.

    Examples:
        kctl-odoo sales validate-delivery WH/OUT/00001
        kctl-odoo sales validate-delivery WH/OUT/00001 --force
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    try:
        pick_id, pick_display = _resolve(c, "stock.picking", "name", name, "Delivery")
    except typer.BadParameter as e:
        out.error(str(e))
        raise typer.Exit(1) from e

    if not force and not typer.confirm(f"Validate delivery {pick_display}?"):
        raise typer.Exit(0)

    try:
        c.execute_kw("stock.picking", "button_validate", [[pick_id]])
    except RPCError as e:
        out.error(f"Failed to validate {pick_display}: {e}")
        raise typer.Exit(1) from e

    out.success(f"Validated delivery {pick_display}")

    if actx.json_mode:
        out.raw_json({"id": pick_id, "name": pick_display, "action": "validated"})


# ===================================================================
# SUMMARY / DASHBOARD
# ===================================================================


@app.command("summary")
def sales_summary(
    ctx: typer.Context,
    period: Annotated[str, typer.Option("--period", help="Filter period: month, quarter, year")] = "month",
    team: Annotated[str | None, typer.Option("--team", help="Sales team name")] = None,
) -> None:
    """Sales dashboard — orders by state with totals."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, "sale.order"):
        out.error(module_hint("sale.order"))
        raise typer.Exit(1)

    domain: list = period_domain("date_order", period)
    if team:
        domain.append(("team_id.name", "ilike", team))

    orders = c.search_read(
        "sale.order",
        domain=domain,
        fields=["id", "state", "amount_total"],
    )

    buckets: dict[str, dict] = {}
    for o in orders:
        st = o.get("state", "unknown")
        b = buckets.setdefault(st, {"count": 0, "amount": 0.0})
        b["count"] += 1
        b["amount"] += o.get("amount_total", 0.0)

    total_revenue = sum(b["amount"] for b in buckets.values())
    total_count = sum(b["count"] for b in buckets.values())

    state_labels = {
        "draft": "Quotation",
        "sent": "Sent",
        "sale": "Confirmed",
        "done": "Done",
        "cancel": "Cancelled",
    }

    rows = []
    json_data: list[dict] = []
    for st in ("draft", "sent", "sale", "done", "cancel"):
        b = buckets.get(st)
        if not b:
            continue
        rows.append([state_labels.get(st, st), str(b["count"]), fmt_amount(b["amount"])])
        json_data.append({"state": st, "label": state_labels.get(st, st), "count": b["count"], "amount": b["amount"]})

    rows.append(["[bold]Total[/bold]", f"[bold]{total_count}[/bold]", f"[bold]{fmt_amount(total_revenue)}[/bold]"])
    json_data.append({"state": "total", "label": "Total", "count": total_count, "amount": total_revenue})

    title = f"Sales Summary ({period})"
    if team:
        title += f" — team: {team}"
    out.table(
        title,
        [("State", ""), ("Count", "cyan"), ("Amount", "green")],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# OVERDUE ORDERS
# ===================================================================


@app.command("overdue")
def overdue_orders(
    ctx: typer.Context,
    order_type: Annotated[str, typer.Option("--type", help="sale or purchase")] = "sale",
    days: Annotated[int, typer.Option("--days", help="Minimum days overdue")] = 7,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List overdue/expired quotations or purchase orders."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    now = datetime.now(tz=UTC)
    cutoff = (now - timedelta(days=days)).strftime("%Y-%m-%d")

    if order_type == "sale":
        if not model_available(c, "sale.order"):
            out.error(module_hint("sale.order"))
            raise typer.Exit(1)

        orders = c.search_read(
            "sale.order",
            domain=[
                ("state", "in", ["draft", "sent"]),
                ("validity_date", "!=", False),
                ("validity_date", "<", cutoff),
            ],
            fields=["name", "partner_id", "validity_date", "amount_total"],
            limit=limit,
            order="validity_date asc",
        )
        date_field = "validity_date"
        label = "Sale"
    else:
        if not model_available(c, "purchase.order"):
            out.error(module_hint("purchase.order"))
            raise typer.Exit(1)

        orders = c.search_read(
            "purchase.order",
            domain=[
                ("state", "in", ["draft", "sent", "to approve"]),
                ("date_planned", "!=", False),
                ("date_planned", "<", cutoff),
            ],
            fields=["name", "partner_id", "date_planned", "amount_total"],
            limit=limit,
            order="date_planned asc",
        )
        date_field = "date_planned"
        label = "Purchase"

    if not orders:
        out.info(f"No overdue {label.lower()} orders found (>{days} days).")
        return

    rows = []
    json_data: list[dict] = []
    for o in orders:
        partner = o.get("partner_id")
        partner_name = partner[1] if isinstance(partner, list) else str(partner or "-")
        date_val = str(o.get(date_field, ""))[:10]
        rows.append(
            [
                o.get("name", ""),
                partner_name,
                date_val,
                fmt_amount(o.get("amount_total", 0)),
            ]
        )
        json_data.append(
            {
                "reference": o.get("name"),
                "partner": partner_name,
                "date": date_val,
                "amount": o.get("amount_total"),
            }
        )

    out.table(
        f"Overdue {label} Orders (>{days} days) — {len(orders)} found",
        [("Reference", "cyan"), ("Partner", ""), ("Date", "dim"), ("Amount", "green")],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# CRM PIPELINE
# ===================================================================


@app.command("crm-pipeline")
def crm_pipeline(
    ctx: typer.Context,
    team: Annotated[str | None, typer.Option("--team", help="Sales team name")] = None,
) -> None:
    """CRM pipeline — opportunities by stage with expected revenue."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, "crm.lead"):
        out.error(module_hint("crm.lead"))
        raise typer.Exit(1)

    domain: list = [("type", "=", "opportunity")]
    if team:
        domain.append(("team_id.name", "ilike", team))

    leads = c.search_read(
        "crm.lead",
        domain=domain,
        fields=["stage_id", "expected_revenue"],
    )

    stages: dict[str, dict] = {}
    for lead in leads:
        stage = lead.get("stage_id")
        stage_name = stage[1] if isinstance(stage, list) else str(stage or "Unknown")
        s = stages.setdefault(stage_name, {"count": 0, "revenue": 0.0})
        s["count"] += 1
        s["revenue"] += lead.get("expected_revenue", 0.0)

    total_count = sum(s["count"] for s in stages.values())
    total_revenue = sum(s["revenue"] for s in stages.values())

    rows = []
    json_data: list[dict] = []
    for name, s in stages.items():
        rows.append([name, str(s["count"]), fmt_amount(s["revenue"])])
        json_data.append({"stage": name, "count": s["count"], "expected_revenue": s["revenue"]})

    rows.append(
        ["[bold]Total Pipeline[/bold]", f"[bold]{total_count}[/bold]", f"[bold]{fmt_amount(total_revenue)}[/bold]"]
    )
    json_data.append({"stage": "total", "count": total_count, "expected_revenue": total_revenue})

    title = "CRM Pipeline"
    if team:
        title += f" — team: {team}"
    out.table(
        title,
        [("Stage", ""), ("Opportunities", "cyan"), ("Expected Revenue", "green")],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# CANCEL ORDER
# ===================================================================


@app.command("cancel-order")
def cancel_order(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Sale order name (e.g. S00001) or numeric ID")],
    force: Annotated[bool, typer.Option("--force", "-y", help="Skip confirmation prompt")] = False,
) -> None:
    """Cancel a sale order (set to cancelled state).

    Examples:
        kctl-odoo sales cancel-order S00001
        kctl-odoo sales cancel-order S00001 --force
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    try:
        order_id, order_display = _resolve(c, "sale.order", "name", name, "Sale Order")
    except typer.BadParameter as e:
        out.error(str(e))
        raise typer.Exit(1) from e

    if not force and not typer.confirm(f"Cancel sale order {order_display}?"):
        raise typer.Exit(0)

    try:
        c.execute_kw("sale.order", "action_cancel", [[order_id]])
    except RPCError as e:
        out.error(f"Failed to cancel {order_display}: {e}")
        raise typer.Exit(1) from e

    out.success(f"Cancelled sale order {order_display}")

    if actx.json_mode:
        out.raw_json({"id": order_id, "name": order_display, "action": "cancelled"})


# ===================================================================
# BY PRODUCT
# ===================================================================


@app.command("by-product")
def by_product(
    ctx: typer.Context,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 20,
    date_from: Annotated[str | None, typer.Option("--date-from", help="From date (YYYY-MM-DD)")] = None,
    date_to: Annotated[str | None, typer.Option("--date-to", help="To date (YYYY-MM-DD)")] = None,
) -> None:
    """Sales revenue breakdown by product.

    Examples:
        kctl-odoo sales by-product --limit 10
        kctl-odoo sales by-product --date-from 2025-01-01 --date-to 2025-03-31
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    order_domain: list = [("state", "in", ["sale", "done"])]
    if date_from:
        order_domain.append(("date_order", ">=", date_from))
    if date_to:
        order_domain.append(("date_order", "<=", date_to))

    try:
        order_ids = c.search("sale.order", order_domain)
    except RPCError as e:
        out.error(f"Failed to search sale orders: {e}")
        raise typer.Exit(1) from e

    if not order_ids:
        out.info("No confirmed sale orders found for the given period.")
        if actx.json_mode:
            out.raw_json([])
        return

    try:
        lines = c.search_read(
            "sale.order.line",
            domain=[("order_id", "in", order_ids)],
            fields=["product_id", "product_uom_qty", "price_subtotal"],
            limit=0,
        )
    except RPCError as e:
        out.error(f"Failed to read order lines: {e}")
        raise typer.Exit(1) from e

    # Aggregate by product
    product_data: dict[str, dict] = {}
    for ln in lines:
        product = _m2o_name(ln.get("product_id"))
        if not product:
            continue
        p = product_data.setdefault(product, {"qty": 0.0, "revenue": 0.0})
        p["qty"] += ln.get("product_uom_qty", 0.0)
        p["revenue"] += ln.get("price_subtotal", 0.0)

    total_revenue = sum(p["revenue"] for p in product_data.values())

    # Sort by revenue descending, apply limit
    sorted_products = sorted(product_data.items(), key=lambda x: x[1]["revenue"], reverse=True)[:limit]

    rows = []
    json_data: list[dict] = []
    for product, p in sorted_products:
        pct = (p["revenue"] / total_revenue * 100) if total_revenue else 0.0
        rows.append([product, _fmt_amount(p["qty"]), _fmt_amount(p["revenue"]), f"{pct:.1f}%"])
        json_data.append({"product": product, "qty_sold": p["qty"], "revenue": p["revenue"], "pct_of_total": pct})

    out.table(
        f"Sales by Product (top {limit})",
        [("Product", "cyan"), ("Qty Sold", ""), ("Revenue", "green"), ("% of Total", "dim")],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# BY CUSTOMER
# ===================================================================


@app.command("by-customer")
def by_customer(
    ctx: typer.Context,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 20,
    date_from: Annotated[str | None, typer.Option("--date-from", help="From date (YYYY-MM-DD)")] = None,
    date_to: Annotated[str | None, typer.Option("--date-to", help="To date (YYYY-MM-DD)")] = None,
) -> None:
    """Sales revenue breakdown by customer.

    Examples:
        kctl-odoo sales by-customer --limit 10
        kctl-odoo sales by-customer --date-from 2025-01-01 --date-to 2025-03-31
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    domain: list = [("state", "in", ["sale", "done"])]
    if date_from:
        domain.append(("date_order", ">=", date_from))
    if date_to:
        domain.append(("date_order", "<=", date_to))

    try:
        records = c.search_read(
            "sale.order",
            domain=domain,
            fields=["partner_id", "amount_total"],
            limit=0,
        )
    except RPCError as e:
        out.error(f"Failed to read sale orders: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.info("No confirmed sale orders found.")
        if actx.json_mode:
            out.raw_json([])
        return

    # Aggregate by customer
    customer_data: dict[str, dict] = {}
    for r in records:
        customer = _m2o_name(r.get("partner_id"))
        if not customer:
            continue
        cd = customer_data.setdefault(customer, {"orders": 0, "revenue": 0.0})
        cd["orders"] += 1
        cd["revenue"] += r.get("amount_total", 0.0)

    # Sort by revenue descending, apply limit
    sorted_customers = sorted(customer_data.items(), key=lambda x: x[1]["revenue"], reverse=True)[:limit]

    rows = []
    json_data: list[dict] = []
    for customer, cd in sorted_customers:
        avg_order = cd["revenue"] / cd["orders"] if cd["orders"] else 0.0
        rows.append([customer, str(cd["orders"]), _fmt_amount(cd["revenue"]), _fmt_amount(avg_order)])
        json_data.append(
            {"customer": customer, "orders": cd["orders"], "revenue": cd["revenue"], "avg_order": avg_order}
        )

    out.table(
        f"Sales by Customer (top {limit})",
        [("Customer", "cyan"), ("Orders", ""), ("Revenue", "green"), ("Avg Order", "dim")],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# BY SALESPERSON
# ===================================================================


@app.command("by-salesperson")
def by_salesperson(
    ctx: typer.Context,
    date_from: Annotated[str | None, typer.Option("--date-from", help="From date (YYYY-MM-DD)")] = None,
    date_to: Annotated[str | None, typer.Option("--date-to", help="To date (YYYY-MM-DD)")] = None,
) -> None:
    """Sales revenue breakdown by salesperson.

    Examples:
        kctl-odoo sales by-salesperson
        kctl-odoo sales by-salesperson --date-from 2025-01-01 --date-to 2025-03-31
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    domain: list = [("state", "in", ["sale", "done"])]
    if date_from:
        domain.append(("date_order", ">=", date_from))
    if date_to:
        domain.append(("date_order", "<=", date_to))

    try:
        records = c.search_read(
            "sale.order",
            domain=domain,
            fields=["user_id", "amount_total"],
            limit=0,
        )
    except RPCError as e:
        out.error(f"Failed to read sale orders: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.info("No confirmed sale orders found.")
        if actx.json_mode:
            out.raw_json([])
        return

    # Aggregate by salesperson
    sp_data: dict[str, dict] = {}
    for r in records:
        sp = _m2o_name(r.get("user_id")) or "Unassigned"
        s = sp_data.setdefault(sp, {"orders": 0, "revenue": 0.0})
        s["orders"] += 1
        s["revenue"] += r.get("amount_total", 0.0)

    # Sort by revenue descending
    sorted_sp = sorted(sp_data.items(), key=lambda x: x[1]["revenue"], reverse=True)

    rows = []
    json_data: list[dict] = []
    for sp, s in sorted_sp:
        rows.append([sp, str(s["orders"]), _fmt_amount(s["revenue"])])
        json_data.append({"salesperson": sp, "orders": s["orders"], "revenue": s["revenue"]})

    out.table(
        "Sales by Salesperson",
        [("Salesperson", "cyan"), ("Orders", ""), ("Revenue", "green")],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# TREND
# ===================================================================


@app.command("trend")
def trend(
    ctx: typer.Context,
    period: Annotated[str, typer.Option("--period", help="Period: week, month, quarter, year")] = "month",
) -> None:
    """Sales trend — compare this period vs previous.

    Examples:
        kctl-odoo sales trend
        kctl-odoo sales trend --period week
        kctl-odoo sales trend --period quarter
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    now = datetime.now(tz=UTC)

    if period == "week":
        delta = timedelta(weeks=1)
        current_start = now - timedelta(days=now.weekday())
        previous_start = current_start - delta
        previous_end = current_start
    elif period == "quarter":
        quarter_month = ((now.month - 1) // 3) * 3 + 1
        current_start = now.replace(month=quarter_month, day=1, hour=0, minute=0, second=0, microsecond=0)
        prev_quarter_month = quarter_month - 3 if quarter_month > 3 else 10
        prev_year = now.year if quarter_month > 3 else now.year - 1
        previous_start = now.replace(
            year=prev_year, month=prev_quarter_month, day=1, hour=0, minute=0, second=0, microsecond=0
        )
        previous_end = current_start
    elif period == "year":
        current_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        previous_start = current_start.replace(year=now.year - 1)
        previous_end = current_start
    else:  # month (default)
        current_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if now.month == 1:
            previous_start = now.replace(year=now.year - 1, month=12, day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            previous_start = now.replace(month=now.month - 1, day=1, hour=0, minute=0, second=0, microsecond=0)
        previous_end = current_start

    current_start_str = current_start.strftime("%Y-%m-%d")
    previous_start_str = previous_start.strftime("%Y-%m-%d")
    previous_end_str = previous_end.strftime("%Y-%m-%d")

    try:
        current_orders = c.search_read(
            "sale.order",
            domain=[("state", "in", ["sale", "done"]), ("date_order", ">=", current_start_str)],
            fields=["amount_total"],
            limit=0,
        )
        previous_orders = c.search_read(
            "sale.order",
            domain=[
                ("state", "in", ["sale", "done"]),
                ("date_order", ">=", previous_start_str),
                ("date_order", "<", previous_end_str),
            ],
            fields=["amount_total"],
            limit=0,
        )
    except RPCError as e:
        out.error(f"Failed to read sale orders: {e}")
        raise typer.Exit(1) from e

    current_count = len(current_orders)
    current_revenue = sum(r.get("amount_total", 0) for r in current_orders)
    previous_count = len(previous_orders)
    previous_revenue = sum(r.get("amount_total", 0) for r in previous_orders)

    def _change_pct(current: float, previous: float) -> str:
        if previous == 0:
            return "N/A" if current == 0 else "+100%"
        pct = (current - previous) / previous * 100
        sign = "+" if pct >= 0 else ""
        return f"{sign}{pct:.1f}%"

    rows = [
        ["Orders", str(current_count), str(previous_count), _change_pct(current_count, previous_count)],
        [
            "Revenue",
            _fmt_amount(current_revenue),
            _fmt_amount(previous_revenue),
            _change_pct(current_revenue, previous_revenue),
        ],
    ]
    json_data = [
        {
            "metric": "orders",
            "current": current_count,
            "previous": previous_count,
            "change_pct": _change_pct(current_count, previous_count),
        },
        {
            "metric": "revenue",
            "current": current_revenue,
            "previous": previous_revenue,
            "change_pct": _change_pct(current_revenue, previous_revenue),
        },
    ]

    out.table(
        f"Sales Trend ({period}: {current_start_str} vs {previous_start_str}–{previous_end_str})",
        [("Metric", ""), ("This Period", "cyan"), ("Previous", "dim"), ("Change", "green")],
        rows,
        data_for_json=json_data,
    )
