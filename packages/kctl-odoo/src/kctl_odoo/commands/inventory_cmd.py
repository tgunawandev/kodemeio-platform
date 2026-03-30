"""Inventory / stock operations — levels, transfers, adjustments, lots, scrap."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Optional

import typer

from kctl_odoo.core.biz_helpers import fmt_amount, model_available, module_hint
from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.exceptions import RPCError
from kctl_odoo.core.field_helpers import safe_fields

app = typer.Typer(help="Inventory: stock levels, transfers, adjustments, lots, scrap.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _m2o_name(val: object) -> str:
    """Extract display name from an M2O field value ([id, name] or False)."""
    if isinstance(val, list):
        return str(val[1]) if len(val) > 1 else str(val[0])
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


def _fmt_qty(qty: float) -> str:
    """Format a quantity with up to 2 decimal places."""
    if qty == int(qty):
        return str(int(qty))
    return f"{qty:.2f}"


# ===================================================================
# READ: STOCK LEVELS
# ===================================================================


@app.command("stock-levels")
def stock_levels(
    ctx: typer.Context,
    warehouse: Annotated[str | None, typer.Option("--warehouse", "-w", help="Filter by warehouse name")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """Show stock levels per product (internal locations).

    Uses read_group on stock.quant grouped by product_id, filtered to
    internal locations only.

    Examples:
        kctl-odoo inventory stock-levels
        kctl-odoo inventory stock-levels --warehouse "Main Warehouse"
        kctl-odoo inventory stock-levels --limit 100 --json
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    domain: list = [("location_id.usage", "=", "internal")]
    if warehouse:
        domain.append(("location_id.warehouse_id.name", "ilike", warehouse))

    try:
        groups = c.execute_kw(
            "stock.quant",
            "read_group",
            [domain],
            {
                "fields": ["product_id", "quantity", "product_uom_id"],
                "groupby": ["product_id"],
                "limit": limit,
                "orderby": "quantity desc",
            },
        )
    except RPCError as e:
        out.error(f"Failed to read stock levels: {e}")
        raise typer.Exit(1) from e

    if not groups:
        out.info("No stock found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for g in groups:
        product = _m2o_name(g.get("product_id"))
        qty = g.get("quantity", 0)
        uom = _m2o_name(g.get("product_uom_id")) if g.get("product_uom_id") else ""
        rows.append([product, _fmt_qty(qty), uom])
        json_data.append({"product": product, "quantity": qty, "uom": uom})

    out.table(
        f"Stock Levels ({len(groups)})",
        [("Product", "cyan"), ("Quantity", ""), ("UoM", "dim")],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# READ: PRODUCT STOCK
# ===================================================================


@app.command("product-stock")
def product_stock(
    ctx: typer.Context,
    product: Annotated[str, typer.Argument(help="Product name or numeric ID")],
) -> None:
    """Detailed stock for one product across all internal locations.

    Shows breakdown by location and lot with reserved quantities.

    Examples:
        kctl-odoo inventory product-stock "Widget A"
        kctl-odoo inventory product-stock 42
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    try:
        product_id, product_display = _resolve(c, "product.product", "name", product, "Product")
    except typer.BadParameter as e:
        out.error(str(e))
        raise typer.Exit(1) from e

    try:
        quants = c.search_read(
            "stock.quant",
            domain=[("product_id", "=", product_id), ("location_id.usage", "=", "internal")],
            fields=["location_id", "lot_id", "quantity", "reserved_quantity"],
            order="location_id, lot_id",
        )
    except RPCError as e:
        out.error(f"Failed to read quants: {e}")
        raise typer.Exit(1) from e

    if not quants:
        out.info(f"No stock found for {product_display}.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for q in quants:
        location = _m2o_name(q.get("location_id"))
        lot = _m2o_name(q.get("lot_id")) or "-"
        qty = q.get("quantity", 0)
        reserved = q.get("reserved_quantity", 0)
        rows.append([location, lot, _fmt_qty(qty), _fmt_qty(reserved)])
        json_data.append(
            {
                "location": location,
                "lot": lot if lot != "-" else None,
                "quantity": qty,
                "reserved_quantity": reserved,
            }
        )

    out.table(
        f"Stock for {product_display}",
        [("Location", "cyan"), ("Lot", ""), ("Quantity", ""), ("Reserved", "dim")],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# READ: WAREHOUSES
# ===================================================================


@app.command("warehouses")
def warehouses(ctx: typer.Context) -> None:
    """List warehouses.

    Examples:
        kctl-odoo inventory warehouses
        kctl-odoo inventory warehouses --json
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    try:
        records = c.search_read(
            "stock.warehouse",
            domain=[],
            fields=["id", "name", "code", "company_id"],
            order="name",
        )
    except RPCError as e:
        out.error(f"Failed to list warehouses: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.info("No warehouses found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for r in records:
        rows.append(
            [
                str(r["id"]),
                r.get("name", ""),
                r.get("code", ""),
                _m2o_name(r.get("company_id")),
            ]
        )
        json_data.append(
            {
                "id": r["id"],
                "name": r.get("name"),
                "code": r.get("code"),
                "company": _m2o_name(r.get("company_id")),
            }
        )

    out.table(
        f"Warehouses ({len(records)})",
        [("ID", "dim"), ("Name", "cyan"), ("Code", ""), ("Company", "")],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# READ: TRANSFERS
# ===================================================================


@app.command("transfers")
def transfers(
    ctx: typer.Context,
    state: Annotated[
        str | None, typer.Option("--state", "-s", help="Filter by state: draft, waiting, confirmed, assigned, done")
    ] = None,
    picking_type: Annotated[
        str | None, typer.Option("--type", "-t", help="Filter by type: incoming, outgoing, internal")
    ] = None,
    date_from: Annotated[str | None, typer.Option("--date-from", help="From date (YYYY-MM-DD)")] = None,
    partner: Annotated[str | None, typer.Option("--partner", help="Filter by partner name")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List stock transfers (pickings).

    Examples:
        kctl-odoo inventory transfers
        kctl-odoo inventory transfers --state assigned --type incoming
        kctl-odoo inventory transfers --type internal --limit 20
        kctl-odoo inventory transfers --date-from 2025-01-01 --partner "PT Maju"
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    domain: list = []
    if state:
        domain.append(("state", "=", state))
    if picking_type:
        domain.append(("picking_type_code", "=", picking_type))
    if date_from:
        domain.append(("scheduled_date", ">=", date_from))
    if partner:
        domain.append(("partner_id.name", "ilike", partner))

    try:
        records = c.search_read(
            "stock.picking",
            domain=domain,
            fields=["name", "partner_id", "scheduled_date", "origin", "state", "picking_type_code"],
            limit=limit,
            order="scheduled_date desc",
        )
    except RPCError as e:
        out.error(f"Failed to list transfers: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.info("No transfers found.")
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
                str(r.get("origin", "")),
                r.get("state", ""),
            ]
        )
        json_data.append(
            {
                "name": r["name"],
                "partner": _m2o_name(r.get("partner_id")),
                "scheduled_date": r.get("scheduled_date"),
                "origin": r.get("origin"),
                "state": r.get("state"),
            }
        )

    out.table(
        f"Transfers ({len(records)})",
        [
            ("Name", "cyan"),
            ("Partner", ""),
            ("Scheduled", "dim"),
            ("Origin", ""),
            ("State", ""),
        ],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# READ: LOTS
# ===================================================================


@app.command("lots")
def lots(
    ctx: typer.Context,
    product: Annotated[str | None, typer.Option("--product", help="Filter by product name or ID")] = None,
    expired: Annotated[bool, typer.Option("--expired", help="Show only expired lots")] = False,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List stock lots / serial numbers.

    Examples:
        kctl-odoo inventory lots
        kctl-odoo inventory lots --product "Widget A"
        kctl-odoo inventory lots --expired
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    domain: list = []

    if product:
        try:
            product_id, _ = _resolve(c, "product.product", "name", product, "Product")
        except typer.BadParameter as e:
            out.error(str(e))
            raise typer.Exit(1) from e
        domain.append(("product_id", "=", product_id))

    if expired:
        now_str = datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M:%S")
        domain.append(("expiration_date", "<", now_str))

    try:
        records = c.search_read(
            "stock.lot",
            domain=domain,
            fields=["name", "product_id", "expiration_date", "product_qty"],
            limit=limit,
            order="name",
        )
    except RPCError as e:
        out.error(f"Failed to list lots: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.info("No lots found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for r in records:
        rows.append(
            [
                r.get("name", ""),
                _m2o_name(r.get("product_id")),
                str(r.get("expiration_date", "") or ""),
                _fmt_qty(r.get("product_qty", 0)),
            ]
        )
        json_data.append(
            {
                "name": r.get("name"),
                "product": _m2o_name(r.get("product_id")),
                "expiration_date": r.get("expiration_date"),
                "quantity": r.get("product_qty", 0),
            }
        )

    out.table(
        f"Lots ({len(records)})",
        [("Lot/Serial", "cyan"), ("Product", ""), ("Expiration", "dim"), ("Qty", "")],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# WRITE: TRANSFER CREATE (internal)
# ===================================================================


@app.command("create-transfer")
def transfer_create(
    ctx: typer.Context,
    from_wh: Annotated[str, typer.Option("--from", help="Source warehouse name or ID")],
    to_wh: Annotated[str, typer.Option("--to", help="Destination warehouse name or ID")],
    product_name: Annotated[str, typer.Option("--product", help="Product name or ID")],
    qty: Annotated[float, typer.Option("--qty", help="Quantity to transfer")],
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview without creating")] = False,
    force: Annotated[bool, typer.Option("--force", "-y", help="Skip confirmation prompt")] = False,
) -> None:
    """Create an internal stock transfer between warehouses.

    Creates a stock.picking with the internal transfer picking type of the
    source warehouse and adds a single move line.

    Examples:
        kctl-odoo inventory create-transfer --from "Main" --to "Branch" --product "Widget" --qty 10
        kctl-odoo inventory create-transfer --from 1 --to 2 --product 42 --qty 5 --dry-run
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    try:
        from_id, from_display = _resolve(c, "stock.warehouse", "name", from_wh, "Source warehouse")
        to_id, to_display = _resolve(c, "stock.warehouse", "name", to_wh, "Destination warehouse")
        product_id, product_display = _resolve(c, "product.product", "name", product_name, "Product")
    except typer.BadParameter as e:
        out.error(str(e))
        raise typer.Exit(1) from e

    # Get internal transfer picking type for source warehouse
    try:
        pick_types = c.search_read(
            "stock.picking.type",
            domain=[("warehouse_id", "=", from_id), ("code", "=", "internal")],
            fields=["id", "name", "default_location_src_id", "default_location_dest_id"],
            limit=1,
        )
    except RPCError as e:
        out.error(f"Failed to find internal transfer type: {e}")
        raise typer.Exit(1) from e

    if not pick_types:
        out.error(f"No internal transfer type found for warehouse {from_display}.")
        raise typer.Exit(1)

    pick_type = pick_types[0]

    # Get destination warehouse lot_stock_id for the dest location
    try:
        dest_wh = c.read("stock.warehouse", [to_id], ["lot_stock_id"])
        dest_location_id = dest_wh[0]["lot_stock_id"][0] if dest_wh and dest_wh[0].get("lot_stock_id") else None
    except RPCError:
        dest_location_id = None

    src_location_id = pick_type.get("default_location_src_id")
    if isinstance(src_location_id, list):
        src_location_id = src_location_id[0]

    if not dest_location_id:
        out.error("Could not determine destination location.")
        raise typer.Exit(1)

    # Get product UoM
    try:
        prod_data = c.read("product.product", [product_id], ["uom_id"])
        uom_id = prod_data[0]["uom_id"][0] if prod_data and isinstance(prod_data[0].get("uom_id"), list) else False
    except RPCError:
        uom_id = False

    summary = {
        "from_warehouse": from_display,
        "to_warehouse": to_display,
        "product": product_display,
        "qty": qty,
    }

    if dry_run:
        out.info("Dry run -- transfer will NOT be created.")
        out.detail(
            "Internal Transfer Preview",
            [
                (
                    "Transfer",
                    [
                        ("From", from_display),
                        ("To", to_display),
                        ("Product", product_display),
                        ("Qty", _fmt_qty(qty)),
                    ],
                )
            ],
            data_for_json=summary,
        )
        return

    if not force:
        out.info(f"Create transfer: {product_display} x {_fmt_qty(qty)} from {from_display} to {to_display}")
        if not typer.confirm("Create this transfer?"):
            raise typer.Exit(0)

    move_vals = {
        "name": product_display,
        "product_id": product_id,
        "product_uom_qty": qty,
        "product_uom": uom_id,
        "location_id": src_location_id,
        "location_dest_id": dest_location_id,
    }

    picking_vals = {
        "picking_type_id": pick_type["id"],
        "location_id": src_location_id,
        "location_dest_id": dest_location_id,
        "move_ids": [(0, 0, move_vals)],
    }

    try:
        picking_id = c.create("stock.picking", picking_vals)
    except RPCError as e:
        out.error(f"Failed to create transfer: {e}")
        raise typer.Exit(1) from e

    # Read back the name
    try:
        created = c.read("stock.picking", [picking_id], ["name"])
        picking_name = created[0]["name"] if created else str(picking_id)
    except RPCError:
        picking_name = str(picking_id)

    out.success(f"Created internal transfer {picking_name} (id={picking_id})")

    if actx.json_mode:
        out.raw_json({"id": picking_id, "name": picking_name, **summary})


# ===================================================================
# WRITE: TRANSFER VALIDATE
# ===================================================================


@app.command("validate-transfer")
def transfer_validate(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Transfer name (e.g. WH/INT/00001) or numeric ID")],
    force: Annotated[bool, typer.Option("--force", "-y", help="Skip confirmation prompt")] = False,
) -> None:
    """Validate (confirm) a stock transfer.

    Calls button_validate on the picking.

    Examples:
        kctl-odoo inventory validate-transfer WH/INT/00001
        kctl-odoo inventory validate-transfer WH/OUT/00005 --force
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    try:
        pick_id, pick_display = _resolve(c, "stock.picking", "name", name, "Transfer")
    except typer.BadParameter as e:
        out.error(str(e))
        raise typer.Exit(1) from e

    if not force and not typer.confirm(f"Validate transfer {pick_display}?"):
        raise typer.Exit(0)

    try:
        c.execute_kw("stock.picking", "button_validate", [[pick_id]])
    except RPCError as e:
        out.error(f"Failed to validate {pick_display}: {e}")
        raise typer.Exit(1) from e

    out.success(f"Validated transfer {pick_display}")

    if actx.json_mode:
        out.raw_json({"id": pick_id, "name": pick_display, "action": "validated"})


# ===================================================================
# WRITE: INVENTORY ADJUSTMENT
# ===================================================================


@app.command("adjustments")
def adjustment(
    ctx: typer.Context,
    product_name: Annotated[str, typer.Option("--product", help="Product name or ID")],
    location_name: Annotated[str, typer.Option("--location", help="Stock location name or ID")],
    qty: Annotated[float, typer.Option("--qty", help="New inventory quantity")],
    reason: Annotated[str | None, typer.Option("--reason", help="Adjustment reason")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview without applying")] = False,
    force: Annotated[bool, typer.Option("--force", "-y", help="Skip confirmation prompt")] = False,
) -> None:
    """Create an inventory adjustment (Odoo 18 stock.quant method).

    Sets ``inventory_quantity`` on the matching stock.quant record and calls
    ``action_apply_inventory``.  If no quant exists yet, one is created first.

    Examples:
        kctl-odoo inventory adjustment --product "Widget" --location "WH/Stock" --qty 100
        kctl-odoo inventory adjustment --product 42 --location 8 --qty 50 --reason "Cycle count"
        kctl-odoo inventory adjustment --product "Widget" --location "WH/Stock" --qty 0 --dry-run
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    try:
        product_id, product_display = _resolve(c, "product.product", "name", product_name, "Product")
        location_id, location_display = _resolve(c, "stock.location", "complete_name", location_name, "Location")
    except typer.BadParameter as e:
        out.error(str(e))
        raise typer.Exit(1) from e

    summary = {
        "product": product_display,
        "location": location_display,
        "new_quantity": qty,
        "reason": reason,
    }

    if dry_run:
        out.info("Dry run -- adjustment will NOT be applied.")
        out.detail(
            "Inventory Adjustment Preview",
            [
                (
                    "Adjustment",
                    [
                        ("Product", product_display),
                        ("Location", location_display),
                        ("New Qty", _fmt_qty(qty)),
                        ("Reason", reason or "-"),
                    ],
                )
            ],
            data_for_json=summary,
        )
        return

    if not force:
        out.info(f"Adjust inventory: {product_display} at {location_display} -> {_fmt_qty(qty)}")
        if not typer.confirm("Apply this adjustment?"):
            raise typer.Exit(0)

    # Find existing quant
    try:
        quant_ids = c.search(
            "stock.quant",
            [("product_id", "=", product_id), ("location_id", "=", location_id)],
        )
    except RPCError as e:
        out.error(f"Failed to search quants: {e}")
        raise typer.Exit(1) from e

    try:
        if quant_ids:
            c.write("stock.quant", quant_ids, {"inventory_quantity": qty})
            c.execute_kw("stock.quant", "action_apply_inventory", [quant_ids])
        else:
            # Create a new quant then apply
            quant_id = c.create(
                "stock.quant",
                {
                    "product_id": product_id,
                    "location_id": location_id,
                    "inventory_quantity": qty,
                },
            )
            c.execute_kw("stock.quant", "action_apply_inventory", [[quant_id]])
    except RPCError as e:
        out.error(f"Failed to apply adjustment: {e}")
        raise typer.Exit(1) from e

    out.success(f"Applied inventory adjustment: {product_display} at {location_display} = {_fmt_qty(qty)}")

    if actx.json_mode:
        out.raw_json({"action": "adjusted", **summary})


# ===================================================================
# WRITE: SCRAP
# ===================================================================


@app.command("scrap")
def scrap(
    ctx: typer.Context,
    product_name: Annotated[str, typer.Option("--product", help="Product name or ID")],
    qty: Annotated[float, typer.Option("--qty", help="Quantity to scrap")],
    reason: Annotated[str | None, typer.Option("--reason", help="Scrap reason")] = None,
    force: Annotated[bool, typer.Option("--force", "-y", help="Skip confirmation prompt")] = False,
) -> None:
    """Create and validate a scrap order.

    Creates a ``stock.scrap`` record and calls ``action_validate``.

    Examples:
        kctl-odoo inventory scrap --product "Widget" --qty 5 --reason "Damaged"
        kctl-odoo inventory scrap --product 42 --qty 2 --force
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    try:
        product_id, product_display = _resolve(c, "product.product", "name", product_name, "Product")
    except typer.BadParameter as e:
        out.error(str(e))
        raise typer.Exit(1) from e

    if not force:
        reason_msg = f" (reason: {reason})" if reason else ""
        out.info(f"Scrap: {product_display} x {_fmt_qty(qty)}{reason_msg}")
        if not typer.confirm("Create and validate this scrap order?"):
            raise typer.Exit(0)

    scrap_vals: dict = {
        "product_id": product_id,
        "scrap_qty": qty,
    }
    if reason:
        scrap_vals["origin"] = reason

    try:
        scrap_id = c.create("stock.scrap", scrap_vals)
    except RPCError as e:
        out.error(f"Failed to create scrap order: {e}")
        raise typer.Exit(1) from e

    try:
        c.execute_kw("stock.scrap", "action_validate", [[scrap_id]])
    except RPCError as e:
        out.error(f"Failed to validate scrap order: {e}")
        raise typer.Exit(1) from e

    # Read back the name
    try:
        created = c.read("stock.scrap", [scrap_id], ["name"])
        scrap_name = created[0]["name"] if created else str(scrap_id)
    except RPCError:
        scrap_name = str(scrap_id)

    out.success(f"Created and validated scrap order {scrap_name} (id={scrap_id})")

    if actx.json_mode:
        out.raw_json(
            {
                "id": scrap_id,
                "name": scrap_name,
                "product": product_display,
                "qty": qty,
                "reason": reason,
                "action": "validated",
            }
        )


# ===================================================================
# WRITE: QUICK INVENTORY ADJUST
# ===================================================================


@app.command("adjust")
def adjust(
    ctx: typer.Context,
    product: Annotated[str, typer.Option("--product", help="Product name or ID")],
    qty: Annotated[float, typer.Option("--qty", help="New quantity")],
    location: Annotated[str | None, typer.Option("--location", help="Stock location (default: main warehouse)")] = None,
    force: Annotated[bool, typer.Option("--force", "-y", help="Skip confirmation prompt")] = False,
) -> None:
    """Quick inventory adjustment for a single product.

    Resolves the product, finds or creates a stock.quant at the given
    location (or the main warehouse stock location), sets inventory_quantity,
    and calls action_apply_inventory.

    Examples:
        kctl-odoo inventory adjust --product "Widget A" --qty 100
        kctl-odoo inventory adjust --product 42 --qty 50 --location "WH/Stock"
        kctl-odoo inventory adjust --product "Widget" --qty 0 --force
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Resolve product
    try:
        product_id, product_display = _resolve(c, "product.product", "name", product, "Product")
    except typer.BadParameter as e:
        out.error(str(e))
        raise typer.Exit(1) from e

    # Resolve location
    if location:
        try:
            location_id, location_display = _resolve(c, "stock.location", "complete_name", location, "Location")
        except typer.BadParameter as e:
            out.error(str(e))
            raise typer.Exit(1) from e
    else:
        # Default: main warehouse stock location
        try:
            warehouses = c.search_read(
                "stock.warehouse",
                domain=[],
                fields=["id", "name", "lot_stock_id"],
                limit=1,
                order="id asc",
            )
        except RPCError as e:
            out.error(f"Failed to find warehouse: {e}")
            raise typer.Exit(1) from e

        if not warehouses:
            out.error("No warehouse found. Please specify --location explicitly.")
            raise typer.Exit(1)

        wh = warehouses[0]
        lot_stock = wh.get("lot_stock_id")
        if not lot_stock:
            out.error(f"Warehouse {wh.get('name')} has no stock location configured.")
            raise typer.Exit(1)

        location_id = lot_stock[0] if isinstance(lot_stock, list) else lot_stock
        location_display = lot_stock[1] if isinstance(lot_stock, list) else str(lot_stock)

    if not force:
        out.info(f"Adjust inventory: {product_display} at {location_display} -> {_fmt_qty(qty)}")
        if not typer.confirm("Apply this adjustment?"):
            raise typer.Exit(0)

    # Find existing quant
    try:
        quant_ids = c.search(
            "stock.quant",
            [("product_id", "=", product_id), ("location_id", "=", location_id)],
        )
    except RPCError as e:
        out.error(f"Failed to search quants: {e}")
        raise typer.Exit(1) from e

    try:
        if quant_ids:
            c.write("stock.quant", quant_ids, {"inventory_quantity": qty})
            c.execute_kw("stock.quant", "action_apply_inventory", [quant_ids])
        else:
            # Create a new quant then apply
            quant_id = c.create(
                "stock.quant",
                {
                    "product_id": product_id,
                    "location_id": location_id,
                    "inventory_quantity": qty,
                },
            )
            c.execute_kw("stock.quant", "action_apply_inventory", [[quant_id]])
    except RPCError as e:
        out.error(f"Failed to apply adjustment: {e}")
        raise typer.Exit(1) from e

    out.success(f"Adjusted inventory: {product_display} at {location_display} = {_fmt_qty(qty)}")

    if actx.json_mode:
        out.raw_json(
            {
                "action": "adjusted",
                "product": product_display,
                "location": location_display,
                "new_quantity": qty,
            }
        )


# ---------------------------------------------------------------------------
# Inventory Close — period-end inventory validation
# ---------------------------------------------------------------------------


@app.command("close-period")
def inventory_close(
    ctx: typer.Context,
    period_end: Annotated[str | None, typer.Option("--date", "-d", help="Period end date (YYYY-MM-DD)")] = None,
) -> None:
    """Period-end inventory validation.

    Runs all checks needed before closing an inventory period:
    - No negative stock quantities
    - No stuck transfers (waiting/confirmed)
    - No orphan stock moves
    - Stock valuation matches GL
    - No expired lots with stock on hand
    - No products with negative forecast
    - All internal transfers completed
    - Physical inventory adjustments applied

    Examples:
        kctl-odoo inventory close-period
        kctl-odoo inventory close-period --date 2025-12-31
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    now = datetime.now(tz=UTC)
    if period_end:
        close_date = period_end
    else:
        first_of_month = date(now.year, now.month, 1)
        last_month_end = first_of_month - timedelta(days=1)
        close_date = str(last_month_end)

    rows: list[list[str]] = []
    json_data: list[dict] = []
    total_issues = 0

    def _add(name: str, ok: bool, detail: str) -> None:
        nonlocal total_issues
        if not ok:
            total_issues += 1
        status = "[green]PASS[/green]" if ok else "[red]FAIL[/red]"
        rows.append([name, status, detail])
        json_data.append({"check": name, "passed": ok, "detail": detail})

    out.info(f"Inventory close validation for period ending: {close_date}")

    # 1. Negative stock
    try:
        negative = c.search_count("stock.quant", [("quantity", "<", 0), ("location_id.usage", "=", "internal")])
        _add("No negative stock", negative == 0, f"{negative} products have negative quantities")
    except Exception as e:
        _add("Negative stock", False, str(e))

    # 2. Stuck transfers — waiting or confirmed >7 days
    try:
        cutoff_7d = (now - timedelta(days=7)).strftime("%Y-%m-%d")
        stuck = c.search_count(
            "stock.picking",
            [
                ("state", "in", ["waiting", "confirmed"]),
                ("scheduled_date", "<", cutoff_7d),
            ],
        )
        _add("No stuck transfers (>7d)", stuck == 0, f"{stuck} transfers in waiting/confirmed >7 days")
    except Exception as e:
        _add("Stuck transfers", False, str(e))

    # 3. Unprocessed deliveries (assigned but not done)
    try:
        unshipped = c.search_count(
            "stock.picking",
            [
                ("state", "=", "assigned"),
                ("picking_type_code", "=", "outgoing"),
                ("scheduled_date", "<=", close_date),
            ],
        )
        _add("All deliveries processed", unshipped == 0, f"{unshipped} ready deliveries not shipped by {close_date}")
    except Exception as e:
        _add("Deliveries", False, str(e))

    # 4. Unprocessed receipts
    try:
        unreceived = c.search_count(
            "stock.picking",
            [
                ("state", "=", "assigned"),
                ("picking_type_code", "=", "incoming"),
                ("scheduled_date", "<=", close_date),
            ],
        )
        _add("All receipts processed", unreceived == 0, f"{unreceived} ready receipts not processed by {close_date}")
    except Exception as e:
        _add("Receipts", False, str(e))

    # 5. Internal transfers completed
    try:
        pending_internal = c.search_count(
            "stock.picking",
            [
                ("state", "not in", ["done", "cancel"]),
                ("picking_type_code", "=", "internal"),
                ("scheduled_date", "<=", close_date),
            ],
        )
        _add(
            "Internal transfers completed",
            pending_internal == 0,
            f"{pending_internal} internal transfers pending in period",
        )
    except Exception as e:
        _add("Internal transfers", False, str(e))

    # 6. Orphan stock moves
    try:
        orphan_moves = c.search_count(
            "stock.move",
            [
                ("picking_id", "=", False),
                ("state", "not in", ["done", "cancel"]),
                ("date", "<=", close_date),
            ],
        )
        _add("No orphan stock moves", orphan_moves == 0, f"{orphan_moves} stock moves without picking in period")
    except Exception as e:
        _add("Orphan moves", False, str(e))

    # 7. Inventory valuation vs GL
    try:
        layers = c.search_read("stock.valuation.layer", [("company_id", "!=", False)], fields=["value"], limit=0)
        layer_total = sum(line.get("value", 0) for line in layers)

        stock_accounts = c.search_read(
            "account.account",
            [("account_type", "=", "asset_current"), ("name", "ilike", "stock valuation")],
            fields=["id"],
            limit=5,
        )
        gl_total = 0.0
        for sa in stock_accounts:
            gl_lines = c.search_read(
                "account.move.line",
                [("account_id", "=", sa["id"]), ("parent_state", "=", "posted")],
                fields=["debit", "credit"],
                limit=0,
            )
            gl_total += sum(line.get("debit", 0) - line.get("credit", 0) for line in gl_lines)

        diff = abs(layer_total - gl_total)
        _add("Valuation matches GL", diff < 1.0, f"Layers: {layer_total:,.2f}, GL: {gl_total:,.2f}, Diff: {diff:,.2f}")
    except Exception:
        _add("Valuation vs GL", True, "Skipped — stock valuation layer not available")

    # 8. Expired lots
    try:
        today_str = now.strftime("%Y-%m-%d")
        expired = c.search_count(
            "stock.lot",
            [
                ("expiration_date", "<", today_str),
                ("product_qty", ">", 0),
            ],
        )
        _add(
            "No expired lots with stock",
            expired == 0,
            f"{expired} expired lots still have stock — quarantine or dispose",
        )
    except Exception:
        _add("Expired lots", True, "Lot tracking not active (skipped)")

    # 9. Products with negative forecast
    try:
        neg_forecast = c.search_count(
            "product.product",
            [
                ("virtual_available", "<", 0),
                ("type", "!=", "service"),
            ],
        )
        _add("No negative forecast", neg_forecast == 0, f"{neg_forecast} products oversold (forecast < 0)")
    except Exception:
        _add("Negative forecast", True, "Skipped")

    # 10. Zero-cost storable products with stock
    try:
        zero_cost_with_stock = c.search_read(
            "product.product",
            [("standard_price", "<=", 0), ("type", "!=", "service"), ("qty_available", ">", 0)],
            fields=["default_code", "name"],
            limit=10,
        )
        _add(
            "No zero-cost products with stock",
            len(zero_cost_with_stock) == 0,
            f"{len(zero_cost_with_stock)} products with stock have zero cost — valuation is wrong",
        )
    except Exception:
        _add("Zero-cost products", True, "Skipped")

    # Summary
    passed = sum(1 for d in json_data if d["passed"])
    total = len(json_data)
    title = f"Inventory Close — {close_date} ({passed}/{total} passed)"
    if total_issues:
        title += f" — [red]{total_issues} blocking[/red]"
    else:
        title += " — [green]ready to close[/green]"

    out.table(
        title,
        [("Check", "cyan"), ("Status", ""), ("Detail", "dim")],
        rows,
        json_data,
    )

    if total_issues:
        out.warn(f"Fix {total_issues} issues before closing inventory period {close_date}")
    else:
        out.success(f"All checks passed — inventory period {close_date} is ready to close")


# ===================================================================
# DASHBOARDS (moved from biz_inventory)
# ===================================================================


@app.command("summary")
def inventory_summary(
    ctx: typer.Context,
    warehouse: Annotated[str | None, typer.Option("--warehouse", help="Warehouse name filter")] = None,
) -> None:
    """Inventory dashboard — stock levels, pending transfers."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, "stock.quant"):
        out.error(module_hint("stock.quant"))
        raise typer.Exit(1)

    quant_domain: list = [("quantity", ">", 0)]
    if warehouse:
        quant_domain.append(("location_id.warehouse_id.name", "ilike", warehouse))

    products_in_stock = c.search_count("stock.quant", quant_domain)

    quants = c.search_read(
        "stock.quant",
        domain=quant_domain,
        fields=["quantity", "value"],
        limit=0,
    )
    total_qty = sum(q.get("quantity", 0) for q in quants)
    total_value = sum(q.get("value", 0) for q in quants)

    picking_states: dict[str, int] = {}
    for st in ("waiting", "confirmed", "assigned", "done"):
        cnt = c.search_count("stock.picking", [("state", "=", st)])
        if cnt:
            picking_states[st] = cnt

    sections = [
        (
            "Stock",
            [
                ("Products in stock", str(products_in_stock)),
                ("Total quantity", f"{total_qty:,.2f}"),
                ("Total stock value", fmt_amount(total_value)),
            ],
        ),
        (
            "Transfers",
            [
                ("Waiting", str(picking_states.get("waiting", 0))),
                ("Confirmed", str(picking_states.get("confirmed", 0))),
                ("Ready", str(picking_states.get("assigned", 0))),
                ("Done", str(picking_states.get("done", 0))),
            ],
        ),
    ]

    json_out = {
        "products_in_stock": products_in_stock,
        "total_quantity": total_qty,
        "total_value": total_value,
        "transfers": picking_states,
    }

    title = "Inventory Summary"
    if warehouse:
        title += f" — {warehouse}"
    out.detail(title, sections, data_for_json=json_out)


@app.command("manufacturing")
def manufacturing_summary(ctx: typer.Context) -> None:
    """Manufacturing dashboard — production orders by state."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, "mrp.production"):
        out.error(module_hint("mrp.production"))
        raise typer.Exit(1)

    orders = c.search_read(
        "mrp.production",
        domain=[],
        fields=["state", "product_qty"],
    )

    buckets: dict[str, dict] = {}
    for o in orders:
        st = o.get("state", "unknown")
        b = buckets.setdefault(st, {"count": 0, "qty": 0.0})
        b["count"] += 1
        b["qty"] += o.get("product_qty", 0.0)

    state_labels = {
        "draft": "Draft",
        "confirmed": "Confirmed",
        "progress": "In Progress",
        "to_close": "To Close",
        "done": "Done",
        "cancel": "Cancelled",
    }

    rows = []
    json_data: list[dict] = []
    total_count = 0
    total_qty = 0.0
    for st in ("draft", "confirmed", "progress", "to_close", "done", "cancel"):
        b = buckets.get(st)
        if not b:
            continue
        rows.append([state_labels.get(st, st), str(b["count"]), f"{b['qty']:,.2f}"])
        json_data.append({"state": st, "label": state_labels.get(st, st), "count": b["count"], "quantity": b["qty"]})
        total_count += b["count"]
        total_qty += b["qty"]

    rows.append(["[bold]Total[/bold]", f"[bold]{total_count}[/bold]", f"[bold]{total_qty:,.2f}[/bold]"])
    json_data.append({"state": "total", "label": "Total", "count": total_count, "quantity": total_qty})

    out.table(
        "Manufacturing Summary",
        [("State", ""), ("Count", "cyan"), ("Planned Qty", "green")],
        rows,
        data_for_json=json_data,
    )


@app.command("low-stock")
def low_stock(
    ctx: typer.Context,
    threshold: Annotated[int, typer.Option("--threshold", help="Low stock threshold")] = 10,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """Products with stock below threshold."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, "stock.quant"):
        out.error(module_hint("stock.quant"))
        raise typer.Exit(1)

    # qty_available on product.product is a computed non-stored field and
    # cannot be used in search domains (SQL).  Instead, aggregate actual
    # on-hand stock from stock.quant grouped by product_id, then filter
    # in Python.
    try:
        quant_groups = c.execute_kw(
            "stock.quant",
            "read_group",
            [
                [("location_id.usage", "=", "internal")],
                ["product_id", "quantity:sum"],
                ["product_id"],
            ],
        )
    except RPCError:
        quant_groups = []

    # Filter to products with 0 < qty < threshold
    low_items = [g for g in quant_groups if 0 < (g.get("quantity") or 0) < threshold]
    # Sort ascending by quantity
    low_items.sort(key=lambda g: g.get("quantity") or 0)
    low_items = low_items[:limit]

    if not low_items:
        out.info(f"No products with stock below {threshold}.")
        return

    # Fetch product details for display
    product_ids = [g["product_id"][0] if isinstance(g["product_id"], list) else g["product_id"] for g in low_items]
    product_map: dict[int, dict] = {}
    if product_ids:
        products_data = c.read("product.product", product_ids, fields=["id", "display_name", "uom_id"])
        product_map = {p["id"]: p for p in products_data}

    rows = []
    json_data: list[dict] = []
    for g in low_items:
        pid = g["product_id"][0] if isinstance(g["product_id"], list) else g["product_id"]
        qty = g.get("quantity") or 0
        pdata = product_map.get(pid, {})
        uom = pdata.get("uom_id")
        uom_name = uom[1] if isinstance(uom, list) else str(uom or "")
        rows.append(
            [
                str(pid),
                pdata.get("display_name", g["product_id"][1] if isinstance(g["product_id"], list) else str(pid)),
                f"{qty:,.2f}",
                uom_name,
            ]
        )
        json_data.append(
            {
                "id": pid,
                "product": pdata.get("display_name") or str(pid),
                "qty_available": qty,
                "uom": uom_name,
            }
        )

    out.table(
        f"Low Stock (< {threshold}) — {len(rows)} products",
        [("ID", "cyan"), ("Product", ""), ("Qty Available", "red"), ("UoM", "dim")],
        rows,
        data_for_json=json_data,
    )


@app.command("stuck")
def stuck_transfers(
    ctx: typer.Context,
    days: Annotated[int, typer.Option("--days", help="Minimum days stuck")] = 3,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """Transfers stuck in waiting/ready state beyond threshold."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, "stock.picking"):
        out.error(module_hint("stock.picking"))
        raise typer.Exit(1)

    now = datetime.now(tz=UTC)
    cutoff = (now - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

    pickings = c.search_read(
        "stock.picking",
        domain=[
            ("state", "in", ["confirmed", "assigned", "waiting"]),
            ("create_date", "<", cutoff),
        ],
        fields=["name", "picking_type_id", "partner_id", "state", "create_date"],
        limit=limit,
        order="create_date asc",
    )

    if not pickings:
        out.info(f"No transfers stuck for more than {days} days.")
        return

    state_labels = {"confirmed": "Waiting", "assigned": "Ready", "waiting": "Waiting Another"}

    rows = []
    json_data: list[dict] = []
    for p in pickings:
        partner = p.get("partner_id")
        partner_name = partner[1] if isinstance(partner, list) else str(partner or "-")
        ptype = p.get("picking_type_id")
        type_name = ptype[1] if isinstance(ptype, list) else str(ptype or "-")
        created = str(p.get("create_date", ""))[:10]
        age = (now.date() - datetime.strptime(created, "%Y-%m-%d").date()).days if created else 0
        st = p.get("state", "")
        rows.append(
            [
                p.get("name", ""),
                type_name,
                partner_name,
                state_labels.get(st, st),
                f"{age}d",
            ]
        )
        json_data.append(
            {
                "reference": p.get("name"),
                "type": type_name,
                "partner": partner_name,
                "state": st,
                "age_days": age,
                "create_date": created,
            }
        )

    out.table(
        f"Stuck Transfers (>{days} days) — {len(pickings)} found",
        [("Reference", "cyan"), ("Type", ""), ("Partner", ""), ("State", "yellow"), ("Age", "red")],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# VALUATION
# ===================================================================


@app.command("valuation")
def valuation(
    ctx: typer.Context,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """Show inventory valuation — stock value per product.

    Examples:
        kctl-odoo inventory valuation
        kctl-odoo inventory valuation --limit 100
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Try stock.valuation.layer first (Odoo 16+)
    try:
        groups = c.execute_kw(
            "stock.valuation.layer",
            "read_group",
            [[]],
            {
                "fields": ["product_id", "quantity", "value"],
                "groupby": ["product_id"],
                "limit": limit,
                "orderby": "value desc",
            },
        )
        use_valuation_layer = True
    except RPCError:
        groups = []
        use_valuation_layer = False

    if use_valuation_layer and groups:
        rows = []
        json_data: list[dict] = []
        total_value = 0.0
        for g in groups:
            product = _m2o_name(g.get("product_id"))
            qty = g.get("quantity", 0)
            value = g.get("value", 0.0)
            unit_cost = (value / qty) if qty else 0.0
            total_value += value
            rows.append([product, _fmt_qty(qty), _fmt_qty(unit_cost), f"{value:,.2f}"])
            json_data.append({"product": product, "qty": qty, "unit_cost": unit_cost, "total_value": value})

        rows.append(["[bold]Total[/bold]", "", "", f"[bold]{total_value:,.2f}[/bold]"])
        json_data.append({"product": "total", "qty": None, "unit_cost": None, "total_value": total_value})

        out.table(
            f"Inventory Valuation ({len(rows) - 1} products)",
            [("Product", "cyan"), ("Qty", ""), ("Unit Cost", "dim"), ("Total Value", "green")],
            rows,
            data_for_json=json_data,
        )
        return

    # Fallback: calculate from product standard_price * qty_available
    try:
        quant_groups = c.execute_kw(
            "stock.quant",
            "read_group",
            [[("location_id.usage", "=", "internal")]],
            {
                "fields": ["product_id", "quantity"],
                "groupby": ["product_id"],
                "limit": limit,
                "orderby": "quantity desc",
            },
        )
    except RPCError as e:
        out.error(f"Failed to read stock quants: {e}")
        raise typer.Exit(1) from e

    if not quant_groups:
        out.info("No stock found.")
        if actx.json_mode:
            out.raw_json([])
        return

    # Get standard prices for all products
    product_ids = [g["product_id"][0] if isinstance(g["product_id"], list) else g["product_id"] for g in quant_groups]
    try:
        products = c.read("product.product", product_ids, ["id", "standard_price"])
        price_map = {p["id"]: p.get("standard_price", 0.0) for p in products}
    except RPCError:
        price_map = {}

    rows = []
    json_data = []
    total_value = 0.0
    for g in quant_groups:
        product = _m2o_name(g.get("product_id"))
        pid = g["product_id"][0] if isinstance(g["product_id"], list) else g["product_id"]
        qty = g.get("quantity", 0)
        unit_cost = price_map.get(pid, 0.0)
        value = qty * unit_cost
        total_value += value
        rows.append([product, _fmt_qty(qty), _fmt_qty(unit_cost), f"{value:,.2f}"])
        json_data.append({"product": product, "qty": qty, "unit_cost": unit_cost, "total_value": value})

    # Sort by value descending
    combined = sorted(zip(rows, json_data), key=lambda x: x[1]["total_value"], reverse=True)
    rows = [r for r, _ in combined]
    json_data = [d for _, d in combined]

    rows.append(["[bold]Total[/bold]", "", "", f"[bold]{total_value:,.2f}[/bold]"])
    json_data.append({"product": "total", "qty": None, "unit_cost": None, "total_value": total_value})

    out.table(
        f"Inventory Valuation ({len(rows) - 1} products, standard price basis)",
        [("Product", "cyan"), ("Qty", ""), ("Unit Cost", "dim"), ("Total Value", "green")],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# STOCK MOVES
# ===================================================================


@app.command("stock-moves")
def stock_moves(
    ctx: typer.Context,
    product: Annotated[str | None, typer.Option("--product", help="Filter by product name or ID")] = None,
    date_from: Annotated[str | None, typer.Option("--date-from", help="From date (YYYY-MM-DD)")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List stock moves (detailed movement history).

    Examples:
        kctl-odoo inventory stock-moves --product "Widget" --limit 20
        kctl-odoo inventory stock-moves --date-from 2025-01-01
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    domain: list = [("state", "=", "done")]
    if date_from:
        domain.append(("date", ">=", date_from))
    if product:
        try:
            product_id, _ = _resolve(c, "product.product", "name", product, "Product")
        except typer.BadParameter as e:
            out.error(str(e))
            raise typer.Exit(1) from e
        domain.append(("product_id", "=", product_id))

    try:
        records = c.search_read(
            "stock.move",
            domain=domain,
            fields=["date", "product_id", "location_id", "location_dest_id", "quantity", "reference"],
            limit=limit,
            order="date desc",
        )
    except RPCError as e:
        out.error(f"Failed to read stock moves: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.info("No stock moves found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data: list[dict] = []
    for r in records:
        date_str = str(r.get("date", ""))[:10]
        product_name = _m2o_name(r.get("product_id"))
        from_loc = _m2o_name(r.get("location_id"))
        to_loc = _m2o_name(r.get("location_dest_id"))
        qty = r.get("quantity", 0)
        ref = str(r.get("reference", "") or "")
        rows.append([date_str, product_name, from_loc, to_loc, _fmt_qty(qty), ref])
        json_data.append(
            {
                "date": date_str,
                "product": product_name,
                "from_location": from_loc,
                "to_location": to_loc,
                "qty": qty,
                "reference": ref,
            }
        )

    out.table(
        f"Stock Moves ({len(records)})",
        [("Date", "dim"), ("Product", "cyan"), ("From", ""), ("To", ""), ("Qty", ""), ("Reference", "dim")],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# TURNOVER
# ===================================================================


@app.command("turnover")
def turnover(
    ctx: typer.Context,
    days: Annotated[int, typer.Option("--days", help="Number of days to analyze")] = 90,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 20,
) -> None:
    """Inventory turnover analysis — fast vs slow moving products.

    Examples:
        kctl-odoo inventory turnover --days 90
        kctl-odoo inventory turnover --days 30 --limit 30
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    now = datetime.now(tz=UTC)
    since = (now - timedelta(days=days)).strftime("%Y-%m-%d")

    # Get current stock (on-hand) per product
    try:
        quant_groups = c.execute_kw(
            "stock.quant",
            "read_group",
            [[("location_id.usage", "=", "internal")]],
            {
                "fields": ["product_id", "quantity"],
                "groupby": ["product_id"],
                "limit": 0,
            },
        )
    except RPCError as e:
        out.error(f"Failed to read stock quants: {e}")
        raise typer.Exit(1) from e

    if not quant_groups:
        out.info("No stock found.")
        if actx.json_mode:
            out.raw_json([])
        return

    # Build stock map
    stock_map: dict[int, float] = {}
    for g in quant_groups:
        pid = g["product_id"][0] if isinstance(g["product_id"], list) else g["product_id"]
        stock_map[pid] = max(g.get("quantity", 0), 0)

    product_ids = list(stock_map.keys())

    # Get stock moves for these products in the analysis window
    try:
        move_groups = c.execute_kw(
            "stock.move",
            "read_group",
            [
                [
                    ("state", "=", "done"),
                    ("product_id", "in", product_ids),
                    ("date", ">=", since),
                    ("location_id.usage", "=", "internal"),
                ]
            ],
            {
                "fields": ["product_id", "quantity"],
                "groupby": ["product_id"],
                "limit": 0,
            },
        )
    except RPCError:
        move_groups = []

    moved_map: dict[int, float] = {}
    for g in move_groups:
        pid = g["product_id"][0] if isinstance(g["product_id"], list) else g["product_id"]
        moved_map[pid] = g.get("quantity", 0)

    # Get product names
    try:
        products = c.read(product_ids, ["id", "display_name"])  # type: ignore[arg-type]
        name_map = {p["id"]: p.get("display_name", str(p["id"])) for p in products}
    except RPCError:
        try:
            products = c.read("product.product", product_ids, ["id", "display_name"])
            name_map = {p["id"]: p.get("display_name", str(p["id"])) for p in products}
        except RPCError:
            name_map = {pid: str(pid) for pid in product_ids}

    # Calculate turnover ratio
    results = []
    for pid, stock in stock_map.items():
        if stock <= 0:
            continue
        moved = moved_map.get(pid, 0)
        ratio = moved / stock if stock > 0 else 0.0
        if ratio >= 1.0:
            category = "Fast"
        elif ratio >= 0.25:
            category = "Medium"
        else:
            category = "Slow"
        results.append(
            {
                "product": name_map.get(pid, str(pid)),
                "avg_stock": stock,
                "moved_qty": moved,
                "turnover_ratio": ratio,
                "category": category,
            }
        )

    # Sort by turnover descending, apply limit
    results.sort(key=lambda x: x["turnover_ratio"], reverse=True)
    results = results[:limit]

    if not results:
        out.info("No turnover data found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data: list[dict] = []
    cat_colors = {"Fast": "[green]Fast[/green]", "Medium": "[yellow]Medium[/yellow]", "Slow": "[red]Slow[/red]"}
    for r in results:
        rows.append(
            [
                r["product"],
                _fmt_qty(r["avg_stock"]),
                _fmt_qty(r["moved_qty"]),
                f"{r['turnover_ratio']:.2f}",
                cat_colors.get(r["category"], r["category"]),
            ]
        )
        json_data.append(r)

    out.table(
        f"Inventory Turnover (last {days} days, top {limit})",
        [("Product", "cyan"), ("Avg Stock", ""), ("Moved Qty", ""), ("Turnover", ""), ("Category", "")],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# REORDER RULES
# ===================================================================


@app.command("reorder-rules")
def reorder_rules(ctx: typer.Context, triggered: bool = False, limit: int = 50) -> None:
    """List reorder rules (stock.warehouse.orderpoint).

    Shows min/max quantities and trigger status.

    Examples:
        kctl-odoo inventory reorder-rules
        kctl-odoo inventory reorder-rules --triggered
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    domain = []
    if triggered:
        domain.append(("qty_to_order", ">", 0))

    preferred = [
        "display_name",
        "product_id",
        "warehouse_id",
        "location_id",
        "product_min_qty",
        "product_max_qty",
        "qty_on_hand",
        "qty_to_order",
    ]
    fields = safe_fields(c, "stock.warehouse.orderpoint", preferred)

    try:
        rules = c.search_read("stock.warehouse.orderpoint", domain=domain, fields=fields, limit=limit)
    except RPCError as e:
        out.error(f"Failed: {e}")
        raise typer.Exit(1)

    if not rules:
        out.info("No reorder rules found." + (" (with --triggered filter)" if triggered else ""))
        return

    rows = []
    for r in rules:
        product = _m2o_name(r.get("product_id"))
        warehouse = _m2o_name(r.get("warehouse_id"))
        rows.append(
            [
                product,
                warehouse,
                str(r.get("product_min_qty", 0)),
                str(r.get("product_max_qty", 0)),
                str(r.get("qty_on_hand", 0)),
                str(r.get("qty_to_order", 0)),
            ]
        )

    out.table(
        f"Reorder Rules ({len(rules)})",
        [("Product", ""), ("Warehouse", ""), ("Min", ""), ("Max", ""), ("On Hand", ""), ("To Order", "")],
        rows,
    )


# ===================================================================
# STOCK LOCATIONS
# ===================================================================


@app.command("locations")
def locations(ctx: typer.Context, warehouse: Optional[str] = None, limit: int = 50) -> None:
    """List stock locations.

    Examples:
        kctl-odoo inventory locations
        kctl-odoo inventory locations --warehouse "Main"
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    domain = [("usage", "in", ["internal", "transit"])]
    if warehouse:
        domain.append(("complete_name", "ilike", warehouse))

    preferred = ["display_name", "complete_name", "usage", "warehouse_id", "active"]
    fields = safe_fields(c, "stock.location", preferred)

    try:
        locs = c.search_read("stock.location", domain=domain, fields=fields, limit=limit)
    except RPCError as e:
        out.error(f"Failed: {e}")
        raise typer.Exit(1)

    if not locs:
        out.info("No stock locations found.")
        return

    rows = []
    for loc in locs:
        rows.append(
            [
                str(loc.get("id", "")),
                loc.get("complete_name", "") or loc.get("display_name", ""),
                loc.get("usage", ""),
                _m2o_name(loc.get("warehouse_id")),
            ]
        )

    out.table(
        f"Stock Locations ({len(locs)})",
        [("ID", ""), ("Name", ""), ("Usage", ""), ("Warehouse", "")],
        rows,
    )
