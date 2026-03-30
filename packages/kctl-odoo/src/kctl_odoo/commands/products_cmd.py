"""Product management commands — catalog, pricing, categories."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_odoo.core.biz_helpers import fmt_amount, model_available
from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.exceptions import RPCError
from kctl_odoo.core.field_helpers import safe_fields

app = typer.Typer(help="Product management: catalog, pricing, categories.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _m2o_name(val: object) -> str:
    """Extract display name from an M2O field value ([id, name] or False)."""
    if isinstance(val, list):
        return str(val[1])
    return str(val or "-")


def _resolve_product(c: object, identifier: str) -> dict:
    """Resolve product.template by name or ID. Raises BadParameter if not found."""
    if identifier.isdigit():
        recs = c.read("product.template", [int(identifier)], ["id", "display_name"])  # type: ignore[attr-defined]
    else:
        recs = c.search_read(  # type: ignore[attr-defined]
            "product.template", [("name", "ilike", identifier)], ["id", "display_name"], limit=1
        )
    if not recs:
        raise typer.BadParameter(f"Product not found: {identifier}")
    return recs[0]


# ===================================================================
# LIST
# ===================================================================


@app.command("list")
def list_products(
    ctx: typer.Context,
    category: Annotated[str | None, typer.Option("--category", "-c", help="Filter by category name")] = None,
    product_type: Annotated[
        str | None, typer.Option("--type", "-t", help="Filter by type: consu, service, product")
    ] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List product templates with key fields.

    Examples:
        kctl-odoo products list
        kctl-odoo products list --category "All / Consumable"
        kctl-odoo products list --type service --limit 20
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    domain: list = []
    if category:
        domain.append(("categ_id.name", "ilike", category))
    if product_type:
        domain.append(("type", "=", product_type))

    preferred = [
        "display_name",
        "default_code",
        "list_price",
        "standard_price",
        "type",
        "categ_id",
        "active",
        "qty_available",
    ]
    fields = safe_fields(c, "product.template", preferred)

    try:
        records = c.search_read("product.template", domain, fields, limit=limit)  # type: ignore[attr-defined]
    except RPCError as e:
        out.error(f"Failed to list products: {e}")
        raise typer.Exit(1)

    if not records:
        out.info("No products found.")
        return

    if actx.json_mode:
        out.raw_json(records)
        return

    rows = []
    for r in records:
        rows.append(
            [
                r.get("display_name", "-"),
                r.get("default_code") or "-",
                r.get("type", "-"),
                _m2o_name(r.get("categ_id", False)),
                fmt_amount(float(r.get("list_price", 0))),
                fmt_amount(float(r.get("standard_price", 0))),
                "Yes" if r.get("active", True) else "No",
            ]
        )

    out.table(
        f"Products ({len(rows)} of {limit} max)",
        [
            ("Name", ""),
            ("Code", "dim"),
            ("Type", ""),
            ("Category", "dim"),
            ("Sale Price", ""),
            ("Cost", "dim"),
            ("Active", ""),
        ],
        rows,
    )


# ===================================================================
# GET
# ===================================================================


@app.command("get")
def get_product(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="Product name or ID")],
) -> None:
    """Show full product details by name or ID.

    Examples:
        kctl-odoo products get 42
        kctl-odoo products get "Rice 5kg"
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    rec = _resolve_product(c, identifier)
    pid = rec["id"]

    detail_fields = [
        "name",
        "default_code",
        "type",
        "list_price",
        "standard_price",
        "categ_id",
        "uom_id",
        "barcode",
        "weight",
        "volume",
        "description_sale",
        "seller_ids",
        "active",
    ]
    fields = safe_fields(c, "product.template", detail_fields)

    try:
        records = c.read("product.template", [pid], fields)  # type: ignore[attr-defined]
    except RPCError as e:
        out.error(f"Failed to read product: {e}")
        raise typer.Exit(1)

    if not records:
        out.error(f"Product {pid} not found.")
        raise typer.Exit(1)

    r = records[0]

    # Count variants
    variant_count = 0
    try:
        variant_count = c.search_count("product.product", [("product_tmpl_id", "=", pid)])  # type: ignore[attr-defined]
    except RPCError:
        pass

    # Count BOMs if mrp installed
    bom_count = 0
    if model_available(c, "mrp.bom"):
        try:
            bom_count = c.search_count("mrp.bom", [("product_tmpl_id", "=", pid)])  # type: ignore[attr-defined]
        except RPCError:
            pass

    supplier_count = len(r.get("seller_ids", []))

    if actx.json_mode:
        out.raw_json({**r, "variant_count": variant_count, "bom_count": bom_count, "supplier_count": supplier_count})
        return

    out.info(f"Product: {r.get('name', '-')}")
    rows = [
        ["Name", r.get("name", "-")],
        ["Internal Code", r.get("default_code") or "-"],
        ["Type", r.get("type", "-")],
        ["Sale Price", fmt_amount(float(r.get("list_price", 0)))],
        ["Cost", fmt_amount(float(r.get("standard_price", 0)))],
        ["Category", _m2o_name(r.get("categ_id", False))],
        ["UoM", _m2o_name(r.get("uom_id", False))],
        ["Barcode", r.get("barcode") or "-"],
        ["Weight", f"{r.get('weight', 0)} kg"],
        ["Volume", f"{r.get('volume', 0)} m³"],
        ["Description", (r.get("description_sale") or "-")[:80]],
        ["Variants", str(variant_count)],
        ["Suppliers", str(supplier_count)],
        ["BOMs", str(bom_count)],
        ["Active", "Yes" if r.get("active", True) else "No"],
    ]

    out.table(
        f"Product #{pid}",
        [("Field", ""), ("Value", "")],
        rows,
    )


# ===================================================================
# SEARCH
# ===================================================================


@app.command("search")
def search(
    ctx: typer.Context,
    query: Annotated[str, typer.Argument(help="Search by name, code, or barcode")],
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 20,
) -> None:
    """Search products by name, internal code, or barcode.

    Examples:
        kctl-odoo products search "rice"
        kctl-odoo products search "PRD-001"
        kctl-odoo products search "8991234567890"
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    domain: list = ["|", "|", ("name", "ilike", query), ("default_code", "ilike", query), ("barcode", "=", query)]
    fields = safe_fields(
        c, "product.template", ["display_name", "default_code", "barcode", "type", "list_price", "categ_id"]
    )

    try:
        records = c.search_read("product.template", domain, fields, limit=limit)  # type: ignore[attr-defined]
    except RPCError as e:
        out.error(f"Search failed: {e}")
        raise typer.Exit(1)

    if not records:
        out.info(f"No products found matching '{query}'.")
        return

    if actx.json_mode:
        out.raw_json(records)
        return

    rows = [
        [
            r.get("display_name", "-"),
            r.get("default_code") or "-",
            r.get("barcode") or "-",
            r.get("type", "-"),
            fmt_amount(float(r.get("list_price", 0))),
            _m2o_name(r.get("categ_id", False)),
        ]
        for r in records
    ]

    out.table(
        f"Search results for '{query}' ({len(rows)} found)",
        [("Name", ""), ("Code", "dim"), ("Barcode", "dim"), ("Type", ""), ("Sale Price", ""), ("Category", "dim")],
        rows,
    )


# ===================================================================
# CATEGORIES
# ===================================================================


@app.command("categories")
def categories(
    ctx: typer.Context,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List product categories.

    Examples:
        kctl-odoo products categories
        kctl-odoo products categories --limit 100
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    fields = safe_fields(c, "product.category", ["display_name", "parent_id", "complete_name"])

    try:
        records = c.search_read("product.category", [], fields, limit=limit)  # type: ignore[attr-defined]
    except RPCError as e:
        out.error(f"Failed to list categories: {e}")
        raise typer.Exit(1)

    if not records:
        out.info("No categories found.")
        return

    if actx.json_mode:
        out.raw_json(records)
        return

    rows = [
        [
            r.get("complete_name") or r.get("display_name", "-"),
            _m2o_name(r.get("parent_id", False)),
        ]
        for r in records
    ]

    out.table(
        f"Product Categories ({len(rows)})",
        [("Name", ""), ("Parent", "dim")],
        rows,
    )


# ===================================================================
# UPDATE-PRICE
# ===================================================================


@app.command("update-price")
def update_price(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="Product name or ID")],
    sale_price: Annotated[float | None, typer.Option("--sale-price", help="New sale price")] = None,
    cost_price: Annotated[float | None, typer.Option("--cost-price", help="New cost price")] = None,
    force: Annotated[bool, typer.Option("--force", "-y", help="Skip confirmation")] = False,
) -> None:
    """Update sale price and/or cost price on a product.

    Examples:
        kctl-odoo products update-price "Rice 5kg" --sale-price 25000
        kctl-odoo products update-price 42 --sale-price 25000 --cost-price 20000 --force
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if sale_price is None and cost_price is None:
        out.error("At least one of --sale-price or --cost-price must be provided.")
        raise typer.Exit(1)

    rec = _resolve_product(c, identifier)
    pid = rec["id"]
    name = rec.get("display_name", str(pid))

    vals: dict = {}
    if sale_price is not None:
        vals["list_price"] = sale_price
    if cost_price is not None:
        vals["standard_price"] = cost_price

    if not force:
        parts = []
        if sale_price is not None:
            parts.append(f"sale price → {fmt_amount(sale_price)}")
        if cost_price is not None:
            parts.append(f"cost → {fmt_amount(cost_price)}")
        typer.confirm(f"Update '{name}': {', '.join(parts)}?", abort=True)

    try:
        c.execute_kw("product.template", "write", [[pid], vals])  # type: ignore[attr-defined]
    except RPCError as e:
        out.error(f"Failed to update price: {e}")
        raise typer.Exit(1)

    out.success(f"Updated prices for '{name}' (ID {pid}).")


# ===================================================================
# BY-CATEGORY
# ===================================================================


@app.command("by-category")
def by_category(
    ctx: typer.Context,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max categories to show")] = 20,
) -> None:
    """Count products per category.

    Examples:
        kctl-odoo products by-category
        kctl-odoo products by-category --limit 10
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    try:
        records = c.search_read(  # type: ignore[attr-defined]
            "product.template", [], ["categ_id"], limit=0
        )
    except RPCError as e:
        out.error(f"Failed to fetch products: {e}")
        raise typer.Exit(1)

    # Aggregate manually
    counts: dict[str, int] = {}
    for r in records:
        cat = _m2o_name(r.get("categ_id", False)) or "Uncategorized"
        counts[cat] = counts.get(cat, 0) + 1

    sorted_counts = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:limit]

    if not sorted_counts:
        out.info("No products found.")
        return

    if actx.json_mode:
        out.raw_json([{"category": k, "count": v} for k, v in sorted_counts])
        return

    rows = [[cat, str(cnt)] for cat, cnt in sorted_counts]
    out.table(
        f"Products by Category (top {limit})",
        [("Category", ""), ("Count", "")],
        rows,
    )


# ===================================================================
# LOW-MARGIN
# ===================================================================


@app.command("low-margin")
def low_margin(
    ctx: typer.Context,
    threshold: Annotated[float, typer.Option("--threshold", help="Margin % threshold")] = 10.0,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 20,
) -> None:
    """Find products with low margin (below threshold %).

    Margin = (sale_price - cost) / sale_price * 100

    Examples:
        kctl-odoo products low-margin
        kctl-odoo products low-margin --threshold 20 --limit 50
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    try:
        records = c.search_read(  # type: ignore[attr-defined]
            "product.template",
            [("list_price", ">", 0)],
            ["display_name", "list_price", "standard_price"],
            limit=500,
        )
    except RPCError as e:
        out.error(f"Failed to fetch products: {e}")
        raise typer.Exit(1)

    low = []
    for r in records:
        sale = float(r.get("list_price", 0))
        cost = float(r.get("standard_price", 0))
        if sale <= 0:
            continue
        margin = (sale - cost) / sale * 100
        if margin < threshold:
            low.append((r.get("display_name", "-"), sale, cost, margin))

    low.sort(key=lambda x: x[3])
    low = low[:limit]

    if not low:
        out.info(f"No products with margin below {threshold}%.")
        return

    if actx.json_mode:
        out.raw_json([{"name": n, "sale_price": s, "cost": co, "margin_pct": round(m, 2)} for n, s, co, m in low])
        return

    rows = [[name, fmt_amount(sale), fmt_amount(cost), f"{margin:.1f}%"] for name, sale, cost, margin in low]

    out.table(
        f"Low Margin Products (< {threshold}%)",
        [("Product", ""), ("Sale Price", ""), ("Cost", "dim"), ("Margin %", "")],
        rows,
    )


# ===================================================================
# BARCODE-LOOKUP
# ===================================================================


@app.command("barcode-lookup")
def barcode_lookup(
    ctx: typer.Context,
    barcode: Annotated[str, typer.Argument(help="Barcode to look up")],
) -> None:
    """Find product variant by exact barcode.

    Examples:
        kctl-odoo products barcode-lookup 8991234567890
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    fields = safe_fields(
        c,
        "product.product",
        ["display_name", "default_code", "barcode", "product_tmpl_id", "lst_price", "standard_price"],
    )

    try:
        records = c.search_read("product.product", [("barcode", "=", barcode)], fields)  # type: ignore[attr-defined]
    except RPCError as e:
        out.error(f"Barcode lookup failed: {e}")
        raise typer.Exit(1)

    if not records:
        out.info(f"No product found with barcode: {barcode}")
        return

    if actx.json_mode:
        out.raw_json(records)
        return

    r = records[0]
    rows = [
        ["Name", r.get("display_name", "-")],
        ["Internal Code", r.get("default_code") or "-"],
        ["Barcode", r.get("barcode", "-")],
        ["Template", _m2o_name(r.get("product_tmpl_id", False))],
        ["Sale Price", fmt_amount(float(r.get("lst_price", 0)))],
        ["Cost", fmt_amount(float(r.get("standard_price", 0)))],
    ]

    out.table(
        f"Barcode: {barcode}",
        [("Field", ""), ("Value", "")],
        rows,
    )
