"""Purchase operations commands — orders, receipts, billing."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

import typer

from kctl_odoo.core.biz_helpers import fmt_amount, model_available, module_hint, parse_ids, period_domain
from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.exceptions import RPCError

app = typer.Typer(help="Purchase operations: orders, receipts, billing.")


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
    state: Annotated[str | None, typer.Option("--state", "-s", help="Filter by state: draft, purchase, done")] = None,
    partner: Annotated[str | None, typer.Option("--partner", help="Filter by vendor name")] = None,
    date_from: Annotated[str | None, typer.Option("--date-from", help="From date (YYYY-MM-DD)")] = None,
    date_to: Annotated[str | None, typer.Option("--date-to", help="To date (YYYY-MM-DD)")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List purchase orders with key fields.

    Examples:
        kctl-odoo purchasing orders
        kctl-odoo purchasing orders --state purchase --limit 20
        kctl-odoo purchasing orders --partner "PT Supplier"
        kctl-odoo purchasing orders --date-from 2025-01-01 --date-to 2025-01-31
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
            "purchase.order",
            domain=domain,
            fields=["name", "partner_id", "date_order", "amount_total", "state", "invoice_status"],
            limit=limit,
            order="date_order desc",
        )
    except RPCError as e:
        out.error(f"Failed to list purchase orders: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.info("No purchase orders found.")
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
        f"Purchase Orders ({len(records)})",
        [
            ("Name", "cyan"),
            ("Vendor", ""),
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
    name: Annotated[str, typer.Argument(help="Purchase order name (e.g. P00001) or numeric ID")],
) -> None:
    """Get purchase order detail by name or ID.

    Shows header information and order lines.

    Examples:
        kctl-odoo purchasing get-order P00001
        kctl-odoo purchasing get-order 42
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    domain = [("id", "=", int(name))] if name.isdigit() else [("name", "=", name)]

    try:
        records = c.search_read(
            "purchase.order",
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
        out.error(f"Failed to fetch purchase order: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.error(f"Purchase order not found: {name}")
        raise typer.Exit(1)

    rec = records[0]

    header_sections = [
        (
            "Purchase Order",
            [
                ("Name", rec["name"]),
                ("Vendor", _m2o_name(rec.get("partner_id"))),
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

    out.detail("Purchase Order Detail", header_sections, data_for_json=json_result)

    # Order lines
    line_ids = rec.get("order_line", [])
    if line_ids:
        try:
            lines = c.read(
                "purchase.order.line",
                line_ids,
                ["product_id", "product_qty", "price_unit", "price_subtotal"],
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
                    str(ln.get("product_qty", 0)),
                    _fmt_amount(ln.get("price_unit", 0)),
                    _fmt_amount(ln.get("price_subtotal", 0)),
                ]
            )
            lines_json.append(
                {
                    "product": _m2o_name(ln.get("product_id")),
                    "qty": ln.get("product_qty", 0),
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
    partner_name: Annotated[str, typer.Option("--partner", help="Vendor name or ID")],
    product_name: Annotated[str, typer.Option("--product", help="Product name or ID")],
    qty: Annotated[float, typer.Option("--qty", help="Quantity")] = 1.0,
    price: Annotated[
        float | None, typer.Option("--price", help="Unit price (uses product standard price if omitted)")
    ] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview without creating")] = False,
    force: Annotated[bool, typer.Option("--force", "-y", help="Skip confirmation prompt")] = False,
) -> None:
    """Create a purchase order with one line.

    Resolves vendor and product by name.  Uses product standard price
    if ``--price`` is not specified.

    Examples:
        kctl-odoo purchasing create-order --partner "PT Supplier" --product "Raw Material" --qty 100
        kctl-odoo purchasing create-order --partner 5 --product 12 --qty 50 --price 200
        kctl-odoo purchasing create-order --partner "PT Supplier" --product "Raw Material" --dry-run
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    try:
        partner_id, partner_display = _resolve(c, "res.partner", "name", partner_name, "Vendor")
        product_id, product_display = _resolve(c, "product.product", "name", product_name, "Product")
    except typer.BadParameter as e:
        out.error(str(e))
        raise typer.Exit(1) from e

    # If no price given, fetch standard_price from product
    if price is None:
        try:
            prod_data = c.read("product.product", [product_id], ["standard_price"])
            price = prod_data[0].get("standard_price", 0.0) if prod_data else 0.0
        except RPCError:
            price = 0.0

    line_vals = {
        "product_id": product_id,
        "product_qty": qty,
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
            "Purchase Order Preview",
            [
                (
                    "Order",
                    [
                        ("Vendor", partner_display),
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
        out.info(f"Create PO: vendor={partner_display}, product={product_display}, qty={qty}, price={price}")
        if not typer.confirm("Create this purchase order?"):
            raise typer.Exit(0)

    try:
        order_id = c.create("purchase.order", order_vals)
    except RPCError as e:
        out.error(f"Failed to create purchase order: {e}")
        raise typer.Exit(1) from e

    # Re-read to get the generated name
    try:
        created = c.read("purchase.order", [order_id], ["name"])
        order_name = created[0]["name"] if created else str(order_id)
    except RPCError:
        order_name = str(order_id)

    out.success(f"Created purchase order {order_name} (id={order_id})")

    if actx.json_mode:
        out.raw_json({"id": order_id, "name": order_name, **summary})


# ===================================================================
# CONFIRM ORDER
# ===================================================================


@app.command("confirm-order")
def order_confirm(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Purchase order name (e.g. P00001) or numeric ID")],
    force: Annotated[bool, typer.Option("--force", "-y", help="Skip confirmation prompt")] = False,
) -> None:
    """Confirm a draft purchase order.

    Examples:
        kctl-odoo purchasing confirm-order P00001
        kctl-odoo purchasing confirm-order P00001 --force
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    try:
        order_id, order_display = _resolve(c, "purchase.order", "name", name, "Purchase Order")
    except typer.BadParameter as e:
        out.error(str(e))
        raise typer.Exit(1) from e

    if not force and not typer.confirm(f"Confirm purchase order {order_display}?"):
        raise typer.Exit(0)

    try:
        c.execute_kw("purchase.order", "button_confirm", [[order_id]])
    except RPCError as e:
        out.error(f"Failed to confirm {order_display}: {e}")
        raise typer.Exit(1) from e

    out.success(f"Confirmed purchase order {order_display}")

    if actx.json_mode:
        out.raw_json({"id": order_id, "name": order_display, "action": "confirmed"})


# ===================================================================
# LIST RECEIPTS
# ===================================================================


@app.command("receipts")
def receipts(
    ctx: typer.Context,
    state: Annotated[str | None, typer.Option("--state", "-s", help="Filter by state: assigned, done")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List incoming receipts (purchase-related stock pickings).

    Examples:
        kctl-odoo purchasing receipts
        kctl-odoo purchasing receipts --state assigned
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    domain: list = [("picking_type_code", "=", "incoming")]
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
        out.error(f"Failed to list receipts: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.info("No incoming receipts found.")
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
        f"Incoming Receipts ({len(records)})",
        [
            ("Name", "cyan"),
            ("Vendor", ""),
            ("Scheduled", "dim"),
            ("State", ""),
            ("Origin", ""),
        ],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# VALIDATE RECEIPT
# ===================================================================


@app.command("validate-receipt")
def receipt_validate(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Receipt name (e.g. WH/IN/00001) or numeric ID")],
    force: Annotated[bool, typer.Option("--force", "-y", help="Skip confirmation prompt")] = False,
) -> None:
    """Validate an incoming receipt picking.

    Examples:
        kctl-odoo purchasing validate-receipt WH/IN/00001
        kctl-odoo purchasing validate-receipt WH/IN/00001 --force
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    try:
        pick_id, pick_display = _resolve(c, "stock.picking", "name", name, "Receipt")
    except typer.BadParameter as e:
        out.error(str(e))
        raise typer.Exit(1) from e

    if not force and not typer.confirm(f"Validate receipt {pick_display}?"):
        raise typer.Exit(0)

    try:
        c.execute_kw("stock.picking", "button_validate", [[pick_id]])
    except RPCError as e:
        out.error(f"Failed to validate {pick_display}: {e}")
        raise typer.Exit(1) from e

    out.success(f"Validated receipt {pick_display}")

    if actx.json_mode:
        out.raw_json({"id": pick_id, "name": pick_display, "action": "validated"})


# ===================================================================
# CREATE VENDOR BILL
# ===================================================================


@app.command("create-bill")
def bill_create(
    ctx: typer.Context,
    po_name: Annotated[str, typer.Argument(help="Purchase order name (e.g. P00001) or numeric ID")],
    force: Annotated[bool, typer.Option("--force", "-y", help="Skip confirmation prompt")] = False,
) -> None:
    """Create a vendor bill from a confirmed purchase order.

    Calls ``action_create_invoice`` on the purchase order to generate the bill.

    Examples:
        kctl-odoo purchasing create-bill P00001
        kctl-odoo purchasing create-bill P00001 --force
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    try:
        order_id, order_display = _resolve(c, "purchase.order", "name", po_name, "Purchase Order")
    except typer.BadParameter as e:
        out.error(str(e))
        raise typer.Exit(1) from e

    if not force and not typer.confirm(f"Create vendor bill from {order_display}?"):
        raise typer.Exit(0)

    try:
        result = c.execute_kw("purchase.order", "action_create_invoice", [[order_id]])
    except RPCError as e:
        out.error(f"Failed to create bill from {order_display}: {e}")
        raise typer.Exit(1) from e

    # action_create_invoice returns an action dict; extract invoice id if possible
    bill_id = None
    if isinstance(result, dict) and result.get("res_id"):
        bill_id = result["res_id"]

    out.success(f"Created vendor bill from {order_display}")

    if actx.json_mode:
        json_result: dict = {"purchase_order": order_display, "purchase_order_id": order_id, "action": "bill_created"}
        if bill_id:
            json_result["bill_id"] = bill_id
        out.raw_json(json_result)


# ===================================================================
# SUMMARY / DASHBOARD
# ===================================================================


@app.command("summary")
def purchase_summary(
    ctx: typer.Context,
    period: Annotated[str, typer.Option("--period", help="Filter period: month, quarter, year")] = "month",
) -> None:
    """Purchase dashboard — POs by state with totals."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, "purchase.order"):
        out.error(module_hint("purchase.order"))
        raise typer.Exit(1)

    domain: list = period_domain("date_order", period)
    orders = c.search_read(
        "purchase.order",
        domain=domain,
        fields=["id", "state", "amount_total"],
    )

    buckets: dict[str, dict] = {}
    for o in orders:
        st = o.get("state", "unknown")
        b = buckets.setdefault(st, {"count": 0, "amount": 0.0})
        b["count"] += 1
        b["amount"] += o.get("amount_total", 0.0)

    total_spend = sum(b["amount"] for b in buckets.values())
    total_count = sum(b["count"] for b in buckets.values())

    state_labels = {
        "draft": "Draft RFQ",
        "sent": "RFQ Sent",
        "to approve": "To Approve",
        "purchase": "Confirmed PO",
        "done": "Done",
        "cancel": "Cancelled",
    }

    rows = []
    json_data: list[dict] = []
    for st in ("draft", "sent", "to approve", "purchase", "done", "cancel"):
        b = buckets.get(st)
        if not b:
            continue
        rows.append([state_labels.get(st, st), str(b["count"]), fmt_amount(b["amount"])])
        json_data.append({"state": st, "label": state_labels.get(st, st), "count": b["count"], "amount": b["amount"]})

    rows.append(["[bold]Total[/bold]", f"[bold]{total_count}[/bold]", f"[bold]{fmt_amount(total_spend)}[/bold]"])
    json_data.append({"state": "total", "label": "Total", "count": total_count, "amount": total_spend})

    out.table(
        f"Purchase Summary ({period})",
        [("State", ""), ("Count", "cyan"), ("Amount", "green")],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# APPROVE PURCHASES
# ===================================================================


@app.command("approve")
def approve_purchases(
    ctx: typer.Context,
    ids: Annotated[str | None, typer.Option("--ids", help="Comma-separated PO IDs")] = None,
    all_: Annotated[bool, typer.Option("--all", help="Approve all pending")] = False,
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation prompt")] = False,
) -> None:
    """Approve purchase orders awaiting approval."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, "purchase.order"):
        out.error(module_hint("purchase.order"))
        raise typer.Exit(1)

    parsed_ids = parse_ids(ids)
    if parsed_ids:
        search_domain: list = [("id", "in", parsed_ids), ("state", "=", "to approve")]
    elif all_:
        search_domain = [("state", "=", "to approve")]
    else:
        out.error("Specify --ids or --all")
        raise typer.Exit(1)

    orders = c.search_read("purchase.order", domain=search_domain, fields=["id", "name"], limit=0)

    if not orders:
        out.info("No purchase orders awaiting approval.")
        return

    out.info(f"Found {len(orders)} purchase order(s) to approve.")
    if not force and not typer.confirm(f"Approve {len(orders)} purchase order(s)?"):
        raise typer.Exit(0)

    approved = 0
    errors = 0
    for o in orders:
        try:
            c.execute_kw("purchase.order", "button_approve", [[o["id"]]])
            approved += 1
        except RPCError as e:
            out.warn(f"Failed to approve {o.get('name', o['id'])}: {e}")
            errors += 1

    out.success(f"Approved {approved} purchase order(s), {errors} error(s).")

    if actx.json_mode:
        out.raw_json({"approved": approved, "errors": errors, "total": len(orders)})


# ===================================================================
# CANCEL ORDER
# ===================================================================


@app.command("cancel-order")
def cancel_order(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Purchase order name (e.g. P00001) or numeric ID")],
    force: Annotated[bool, typer.Option("--force", "-y", help="Skip confirmation prompt")] = False,
) -> None:
    """Cancel a purchase order.

    Examples:
        kctl-odoo purchasing cancel-order P00001
        kctl-odoo purchasing cancel-order P00001 --force
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    try:
        order_id, order_display = _resolve(c, "purchase.order", "name", name, "Purchase Order")
    except typer.BadParameter as e:
        out.error(str(e))
        raise typer.Exit(1) from e

    if not force and not typer.confirm(f"Cancel purchase order {order_display}?"):
        raise typer.Exit(0)

    try:
        c.execute_kw("purchase.order", "button_cancel", [[order_id]])
    except RPCError as e:
        out.error(f"Failed to cancel {order_display}: {e}")
        raise typer.Exit(1) from e

    out.success(f"Cancelled purchase order {order_display}")

    if actx.json_mode:
        out.raw_json({"id": order_id, "name": order_display, "action": "cancelled"})


# ===================================================================
# BY VENDOR
# ===================================================================


@app.command("by-vendor")
def by_vendor(
    ctx: typer.Context,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 20,
    date_from: Annotated[str | None, typer.Option("--date-from", help="From date (YYYY-MM-DD)")] = None,
) -> None:
    """Purchase volume breakdown by vendor.

    Examples:
        kctl-odoo purchasing by-vendor --limit 10
        kctl-odoo purchasing by-vendor --date-from 2025-01-01
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    domain: list = [("state", "in", ["purchase", "done"])]
    if date_from:
        domain.append(("date_order", ">=", date_from))

    try:
        records = c.search_read(
            "purchase.order",
            domain=domain,
            fields=["partner_id", "amount_total"],
            limit=0,
        )
    except RPCError as e:
        out.error(f"Failed to read purchase orders: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.info("No confirmed purchase orders found.")
        if actx.json_mode:
            out.raw_json([])
        return

    # Aggregate by vendor
    vendor_data: dict[str, dict] = {}
    for r in records:
        vendor = _m2o_name(r.get("partner_id"))
        if not vendor:
            continue
        vd = vendor_data.setdefault(vendor, {"pos": 0, "amount": 0.0})
        vd["pos"] += 1
        vd["amount"] += r.get("amount_total", 0.0)

    # Sort by amount descending, apply limit
    sorted_vendors = sorted(vendor_data.items(), key=lambda x: x[1]["amount"], reverse=True)[:limit]

    rows = []
    json_data: list[dict] = []
    for vendor, vd in sorted_vendors:
        avg_po = vd["amount"] / vd["pos"] if vd["pos"] else 0.0
        rows.append([vendor, str(vd["pos"]), _fmt_amount(vd["amount"]), _fmt_amount(avg_po)])
        json_data.append({"vendor": vendor, "pos": vd["pos"], "total_amount": vd["amount"], "avg_po": avg_po})

    out.table(
        f"Purchase by Vendor (top {limit})",
        [("Vendor", "cyan"), ("POs", ""), ("Total Amount", "green"), ("Avg PO", "dim")],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# BY PRODUCT
# ===================================================================


@app.command("by-product")
def by_product(
    ctx: typer.Context,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 20,
    date_from: Annotated[str | None, typer.Option("--date-from", help="From date (YYYY-MM-DD)")] = None,
) -> None:
    """Purchase volume breakdown by product.

    Examples:
        kctl-odoo purchasing by-product
        kctl-odoo purchasing by-product --limit 10 --date-from 2025-01-01
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    order_domain: list = [("state", "in", ["purchase", "done"])]
    if date_from:
        order_domain.append(("date_order", ">=", date_from))

    try:
        order_ids = c.search("purchase.order", order_domain)
    except RPCError as e:
        out.error(f"Failed to search purchase orders: {e}")
        raise typer.Exit(1) from e

    if not order_ids:
        out.info("No confirmed purchase orders found for the given period.")
        if actx.json_mode:
            out.raw_json([])
        return

    try:
        lines = c.search_read(
            "purchase.order.line",
            domain=[("order_id", "in", order_ids)],
            fields=["product_id", "product_qty", "price_subtotal"],
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
        p = product_data.setdefault(product, {"qty": 0.0, "amount": 0.0})
        p["qty"] += ln.get("product_qty", 0.0)
        p["amount"] += ln.get("price_subtotal", 0.0)

    # Sort by amount descending, apply limit
    sorted_products = sorted(product_data.items(), key=lambda x: x[1]["amount"], reverse=True)[:limit]

    rows = []
    json_data: list[dict] = []
    for product, p in sorted_products:
        rows.append([product, _fmt_amount(p["qty"]), _fmt_amount(p["amount"])])
        json_data.append({"product": product, "qty": p["qty"], "total_amount": p["amount"]})

    out.table(
        f"Purchase by Product (top {limit})",
        [("Product", "cyan"), ("Qty", ""), ("Total Amount", "green")],
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
    """Purchase trend — compare this period vs previous.

    Examples:
        kctl-odoo purchasing trend
        kctl-odoo purchasing trend --period week
        kctl-odoo purchasing trend --period quarter
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    now = datetime.now(tz=UTC)

    if period == "week":
        current_start = now - timedelta(days=now.weekday())
        previous_start = current_start - timedelta(weeks=1)
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
            "purchase.order",
            domain=[("state", "in", ["purchase", "done"]), ("date_order", ">=", current_start_str)],
            fields=["amount_total"],
            limit=0,
        )
        previous_orders = c.search_read(
            "purchase.order",
            domain=[
                ("state", "in", ["purchase", "done"]),
                ("date_order", ">=", previous_start_str),
                ("date_order", "<", previous_end_str),
            ],
            fields=["amount_total"],
            limit=0,
        )
    except RPCError as e:
        out.error(f"Failed to read purchase orders: {e}")
        raise typer.Exit(1) from e

    current_count = len(current_orders)
    current_amount = sum(r.get("amount_total", 0) for r in current_orders)
    previous_count = len(previous_orders)
    previous_amount = sum(r.get("amount_total", 0) for r in previous_orders)

    def _change_pct(current: float, previous: float) -> str:
        if previous == 0:
            return "N/A" if current == 0 else "+100%"
        pct = (current - previous) / previous * 100
        sign = "+" if pct >= 0 else ""
        return f"{sign}{pct:.1f}%"

    rows = [
        ["Orders", str(current_count), str(previous_count), _change_pct(current_count, previous_count)],
        [
            "Spend",
            _fmt_amount(current_amount),
            _fmt_amount(previous_amount),
            _change_pct(current_amount, previous_amount),
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
            "metric": "spend",
            "current": current_amount,
            "previous": previous_amount,
            "change_pct": _change_pct(current_amount, previous_amount),
        },
    ]

    out.table(
        f"Purchase Trend ({period}: {current_start_str} vs {previous_start_str}–{previous_end_str})",
        [("Metric", ""), ("This Period", "cyan"), ("Previous", "dim"), ("Change", "green")],
        rows,
        data_for_json=json_data,
    )
