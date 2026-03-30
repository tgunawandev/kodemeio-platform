"""Website & eCommerce commands — pages, products, publishing."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

import typer

from kctl_odoo.core.biz_helpers import model_available
from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.exceptions import RPCError

app = typer.Typer(help="Website & eCommerce: pages, products, publishing.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _m2o_name(val: object) -> str:
    """Extract display name from an M2O field value ([id, name] or False)."""
    if isinstance(val, list):
        return str(val[1])
    return str(val or "-")


def _website_check(c: object, out: object) -> bool:
    """Return True if the website module is installed, else warn and return False."""
    if not model_available(c, "website"):
        out.warn("Website module (website) is not installed.")  # type: ignore[attr-defined]
        return False
    return True


# ===================================================================
# SUMMARY / DASHBOARD
# ===================================================================


@app.command("summary")
def summary(
    ctx: typer.Context,
) -> None:
    """Dashboard — page count, published product count, eCommerce order count.

    Examples:
        kctl-odoo website summary
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _website_check(c, out):
        return

    try:
        page_count = c.search_count("website.page", [])
        published_page_count = c.search_count("website.page", [("website_published", "=", True)])
    except RPCError:
        page_count = 0
        published_page_count = 0

    try:
        product_count = c.search_count("product.template", [("website_published", "=", True)])
    except RPCError:
        product_count = 0

    try:
        order_count = c.search_count("sale.order", [("website_id", "!=", False)])
    except RPCError:
        order_count = 0

    rows = [
        ["Pages (total)", str(page_count)],
        ["Pages (published)", str(published_page_count)],
        ["Products (published)", str(product_count)],
        ["eCommerce Orders", str(order_count)],
    ]
    json_data = {
        "pages_total": page_count,
        "pages_published": published_page_count,
        "products_published": product_count,
        "ecommerce_orders": order_count,
    }

    out.table(
        "Website Summary",
        [("Metric", ""), ("Count", "cyan")],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# LIST PAGES
# ===================================================================


@app.command("pages")
def pages(
    ctx: typer.Context,
    published: Annotated[bool | None, typer.Option("--published/--all", help="Filter by published status")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List website pages.

    Examples:
        kctl-odoo website pages
        kctl-odoo website pages --published
        kctl-odoo website pages --limit 20
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _website_check(c, out):
        return

    domain: list = []
    if published is not None:
        domain.append(("website_published", "=", published))

    try:
        records = c.search_read(
            "website.page",
            domain=domain,
            fields=["name", "url", "website_published", "website_id", "date_publish"],
            limit=limit,
            order="name asc",
        )
    except RPCError as e:
        out.error(f"Failed to list website pages: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.info("No website pages found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for r in records:
        rows.append(
            [
                str(r.get("name", "")),
                str(r.get("url", "")),
                "Yes" if r.get("website_published") else "No",
                _m2o_name(r.get("website_id")),
                str(r.get("date_publish", "") or ""),
            ]
        )
        json_data.append(
            {
                "name": r.get("name"),
                "url": r.get("url"),
                "published": r.get("website_published"),
                "website": _m2o_name(r.get("website_id")),
                "date_publish": r.get("date_publish"),
            }
        )

    out.table(
        f"Website Pages ({len(records)})",
        [
            ("Name", "cyan"),
            ("URL", ""),
            ("Published", ""),
            ("Website", "dim"),
            ("Publish Date", "dim"),
        ],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# LIST PRODUCTS
# ===================================================================


@app.command("products")
def products(
    ctx: typer.Context,
    published: Annotated[bool | None, typer.Option("--published/--all", help="Filter by published status")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List eCommerce products.

    Examples:
        kctl-odoo website products
        kctl-odoo website products --published
        kctl-odoo website products --limit 20
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _website_check(c, out):
        return

    domain: list = []
    if published is not None:
        domain.append(("website_published", "=", published))

    try:
        records = c.search_read(
            "product.template",
            domain=domain,
            fields=["name", "list_price", "website_published", "website_url"],
            limit=limit,
            order="name asc",
        )
    except RPCError as e:
        out.error(f"Failed to list eCommerce products: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.info("No eCommerce products found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for r in records:
        rows.append(
            [
                str(r.get("name", "")),
                f"{r.get('list_price', 0):,.2f}",
                "Yes" if r.get("website_published") else "No",
                str(r.get("website_url", "") or ""),
            ]
        )
        json_data.append(
            {
                "name": r.get("name"),
                "list_price": r.get("list_price"),
                "published": r.get("website_published"),
                "website_url": r.get("website_url"),
            }
        )

    out.table(
        f"eCommerce Products ({len(records)})",
        [
            ("Name", "cyan"),
            ("Price", ""),
            ("Published", ""),
            ("URL", "dim"),
        ],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# PUBLISH
# ===================================================================


@app.command("publish")
def publish(
    ctx: typer.Context,
    model: Annotated[str, typer.Argument(help="Model name (e.g. website.page, product.template)")],
    ids: Annotated[str, typer.Argument(help="Comma-separated record IDs")],
) -> None:
    """Publish records by setting website_published=True.

    Examples:
        kctl-odoo website publish website.page 1,2,3
        kctl-odoo website publish product.template 42
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _website_check(c, out):
        return

    if not model_available(c, model):
        out.error(f"Model not found: {model}")
        raise typer.Exit(1)

    try:
        record_ids = [int(i.strip()) for i in ids.split(",") if i.strip()]
    except ValueError:
        out.error(f"Invalid IDs: {ids}. Must be comma-separated integers.")
        raise typer.Exit(1) from None

    if not record_ids:
        out.error("No valid IDs provided.")
        raise typer.Exit(1)

    try:
        c.execute_kw(model, "write", [record_ids, {"website_published": True}])
    except RPCError as e:
        out.error(f"Failed to publish records: {e}")
        raise typer.Exit(1) from e

    out.success(f"Published {len(record_ids)} record(s) on {model}")
    if actx.json_mode:
        out.raw_json({"model": model, "ids": record_ids, "action": "published"})


# ===================================================================
# UNPUBLISH
# ===================================================================


@app.command("unpublish")
def unpublish(
    ctx: typer.Context,
    model: Annotated[str, typer.Argument(help="Model name (e.g. website.page, product.template)")],
    ids: Annotated[str, typer.Argument(help="Comma-separated record IDs")],
) -> None:
    """Unpublish records by setting website_published=False.

    Examples:
        kctl-odoo website unpublish website.page 1,2,3
        kctl-odoo website unpublish product.template 42
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _website_check(c, out):
        return

    if not model_available(c, model):
        out.error(f"Model not found: {model}")
        raise typer.Exit(1)

    try:
        record_ids = [int(i.strip()) for i in ids.split(",") if i.strip()]
    except ValueError:
        out.error(f"Invalid IDs: {ids}. Must be comma-separated integers.")
        raise typer.Exit(1) from None

    if not record_ids:
        out.error("No valid IDs provided.")
        raise typer.Exit(1)

    try:
        c.execute_kw(model, "write", [record_ids, {"website_published": False}])
    except RPCError as e:
        out.error(f"Failed to unpublish records: {e}")
        raise typer.Exit(1) from e

    out.success(f"Unpublished {len(record_ids)} record(s) on {model}")
    if actx.json_mode:
        out.raw_json({"model": model, "ids": record_ids, "action": "unpublished"})


# ===================================================================
# ECOMMERCE ORDERS
# ===================================================================


@app.command("orders")
def orders(
    ctx: typer.Context,
    state: Annotated[
        str | None, typer.Option("--state", "-s", help="Filter by state: draft, sale, done, cancel")
    ] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List eCommerce orders (sale orders placed via website).

    Examples:
        kctl-odoo website orders
        kctl-odoo website orders --state sale --limit 20
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _website_check(c, out):
        return

    domain: list = [("website_id", "!=", False)]
    if state:
        domain.append(("state", "=", state))

    try:
        records = c.search_read(
            "sale.order",
            domain=domain,
            fields=["name", "partner_id", "date_order", "amount_total", "state"],
            limit=limit,
            order="date_order desc",
        )
    except RPCError as e:
        out.error(f"Failed to list eCommerce orders: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.info("No eCommerce orders found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for r in records:
        rows.append(
            [
                str(r.get("name", "")),
                _m2o_name(r.get("partner_id")),
                str(r.get("date_order", "")),
                f"{r.get('amount_total', 0):,.2f}",
                str(r.get("state", "")),
            ]
        )
        json_data.append(
            {
                "name": r.get("name"),
                "partner": _m2o_name(r.get("partner_id")),
                "date_order": r.get("date_order"),
                "amount_total": r.get("amount_total"),
                "state": r.get("state"),
            }
        )

    out.table(
        f"eCommerce Orders ({len(records)})",
        [
            ("Name", "cyan"),
            ("Partner", ""),
            ("Date", "dim"),
            ("Total", ""),
            ("State", ""),
        ],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# VISITOR STATS
# ===================================================================


@app.command("visitors")
def visitors(
    ctx: typer.Context,
    days: Annotated[int, typer.Option("--days", "-d", help="Number of past days to count")] = 7,
) -> None:
    """Visitor stats for the last N days.

    Examples:
        kctl-odoo website visitors
        kctl-odoo website visitors --days 30
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _website_check(c, out):
        return

    if not model_available(c, "website.visitor"):
        out.warn("website.visitor model not available (requires website_livechat or website_sale).")
        return

    cutoff = (datetime.now(tz=UTC) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

    try:
        total = c.search_count("website.visitor", [("last_connection_datetime", ">=", cutoff)])
        unique = c.search_count(
            "website.visitor",
            [("last_connection_datetime", ">=", cutoff), ("partner_id", "!=", False)],
        )
    except RPCError as e:
        out.error(f"Failed to fetch visitor stats: {e}")
        raise typer.Exit(1) from e

    anonymous = total - unique
    rows = [
        ["Total Visitors", str(total)],
        ["Identified (with partner)", str(unique)],
        ["Anonymous", str(anonymous)],
    ]
    json_data = {
        "days": days,
        "total": total,
        "identified": unique,
        "anonymous": anonymous,
    }

    out.table(
        f"Visitor Stats (last {days} days)",
        [("Metric", ""), ("Count", "cyan")],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# MENUS
# ===================================================================


@app.command("menus")
def menus(
    ctx: typer.Context,
) -> None:
    """List website menu items in tree structure.

    Examples:
        kctl-odoo website menus
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _website_check(c, out):
        return

    try:
        records = c.search_read(
            "website.menu",
            domain=[],
            fields=["name", "url", "parent_id", "sequence"],
            order="sequence asc",
        )
    except RPCError as e:
        out.error(f"Failed to list website menus: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.info("No website menu items found.")
        if actx.json_mode:
            out.raw_json([])
        return

    # Build a parent → children map for tree display
    {r["id"]: r for r in records}
    children_map: dict[int | None, list[dict]] = {}
    for r in records:
        parent_val = r.get("parent_id")
        parent_id: int | None = parent_val[0] if isinstance(parent_val, list) else None
        children_map.setdefault(parent_id, []).append(r)

    rows = []
    json_data = []

    def _walk(parent_id: int | None, depth: int) -> None:
        for r in children_map.get(parent_id, []):
            indent = "  " * depth
            rows.append(
                [
                    f"{indent}{r.get('name', '')}",
                    str(r.get("url", "") or ""),
                    _m2o_name(r.get("parent_id")),
                    str(r.get("sequence", "")),
                ]
            )
            json_data.append(
                {
                    "id": r["id"],
                    "name": r.get("name"),
                    "url": r.get("url"),
                    "parent": _m2o_name(r.get("parent_id")),
                    "sequence": r.get("sequence"),
                    "depth": depth,
                }
            )
            _walk(r["id"], depth + 1)

    _walk(None, 0)

    out.table(
        f"Website Menus ({len(records)})",
        [
            ("Name", "cyan"),
            ("URL", ""),
            ("Parent", "dim"),
            ("Seq", "dim"),
        ],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# REDIRECTS
# ===================================================================


@app.command("redirects")
def redirects(
    ctx: typer.Context,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List URL redirects configured on the website.

    Examples:
        kctl-odoo website redirects
        kctl-odoo website redirects --limit 100
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not _website_check(c, out):
        return

    # Try website.rewrite first (Odoo 17+), fall back to website.redirect
    model = "website.rewrite"
    if not model_available(c, model):
        model = "website.redirect"
        if not model_available(c, model):
            out.warn("No redirect model found (website.rewrite / website.redirect).")
            return

    try:
        if model == "website.rewrite":
            records = c.search_read(
                model,
                domain=[],
                fields=["name", "url_from", "url_to", "redirect_type"],
                limit=limit,
                order="url_from asc",
            )
        else:
            records = c.search_read(
                model,
                domain=[],
                fields=["name", "url_from", "url_to", "redirect_type"],
                limit=limit,
                order="url_from asc",
            )
    except RPCError as e:
        out.error(f"Failed to list redirects: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.info("No URL redirects found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for r in records:
        rows.append(
            [
                str(r.get("name", "") or ""),
                str(r.get("url_from", "")),
                str(r.get("url_to", "") or ""),
                str(r.get("redirect_type", "") or ""),
            ]
        )
        json_data.append(
            {
                "name": r.get("name"),
                "url_from": r.get("url_from"),
                "url_to": r.get("url_to"),
                "redirect_type": r.get("redirect_type"),
            }
        )

    out.table(
        f"URL Redirects ({len(records)}) — model: {model}",
        [
            ("Name", "dim"),
            ("From", "cyan"),
            ("To", ""),
            ("Type", ""),
        ],
        rows,
        data_for_json=json_data,
    )
