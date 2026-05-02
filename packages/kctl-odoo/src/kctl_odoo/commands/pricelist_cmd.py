"""Pricelist analysis & bulk-edit commands.

Bridges the gap between ``master-data pricelists`` (header list only) and
``shell call product.pricelist.item`` (raw RPC). Targeted at multi-OU
distribution setups where one product carries different strata across
many regional pricelists.
"""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path
from typing import Annotated

import typer

from kctl_odoo.core.biz_helpers import fmt_amount
from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.exceptions import RPCError

app = typer.Typer(help="Pricelist inspection, strata analysis, and bulk-edit templates.")


# ---------------------------------------------------------------------------
# Resolvers
# ---------------------------------------------------------------------------


def _m2o_name(val: object) -> str:
    if isinstance(val, list) and len(val) == 2:
        return str(val[1])
    return str(val or "-")


def _resolve_pricelist(c, identifier: str) -> dict:
    if identifier.isdigit():
        recs = c.read("product.pricelist", [int(identifier)], ["id", "name", "currency_id"])
    else:
        recs = c.search_read(
            "product.pricelist",
            [("name", "=", identifier)],
            ["id", "name", "currency_id"],
            limit=1,
        )
        if not recs:
            recs = c.search_read(
                "product.pricelist",
                [("name", "ilike", identifier)],
                ["id", "name", "currency_id"],
                limit=1,
            )
    if not recs:
        raise typer.BadParameter(f"Pricelist not found: {identifier}")
    return recs[0]


def _resolve_product_template(c, identifier: str) -> dict:
    if identifier.isdigit():
        recs = c.read("product.template", [int(identifier)], ["id", "default_code", "name", "list_price"])
    else:
        domain = ["|", ("default_code", "=", identifier), ("name", "=ilike", identifier)]
        recs = c.search_read("product.template", domain, ["id", "default_code", "name", "list_price"], limit=1)
        if not recs:
            recs = c.search_read(
                "product.template",
                [("name", "ilike", identifier)],
                ["id", "default_code", "name", "list_price"],
                limit=1,
            )
    if not recs:
        raise typer.BadParameter(f"Product template not found: {identifier}")
    return recs[0]


def _pricelist_domain(prefix: str | None) -> list:
    if not prefix:
        return []
    # Allow both literal substring and SQL LIKE wildcards
    op = "=like" if any(ch in prefix for ch in "%_") else "=like"
    return [("pricelist_id.name", op, prefix if "%" in prefix else f"{prefix}%")]


# ===========================================================================
# items
# ===========================================================================


@app.command("items")
def items(
    ctx: typer.Context,
    pricelist: Annotated[str, typer.Argument(help="Pricelist name, partial name, or ID")],
    product: Annotated[str | None, typer.Option("--product", "-p", help="Filter to one product (name or ID)")] = None,
    active_only: Annotated[bool, typer.Option("--active-only", help="Hide rows with date_end in the past")] = False,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max rows")] = 200,
) -> None:
    """List tier lines of a pricelist.

    Examples:
        kctl-odoo pricelist items TLN-JKT_JAKARTA
        kctl-odoo pricelist items 39752 --product 550
        kctl-odoo pricelist items TLN-JKT_JAKARTA -p "ECO TEA" --active-only
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    pl = _resolve_pricelist(c, pricelist)
    domain: list = [("pricelist_id", "=", pl["id"])]
    if product:
        prod = _resolve_product_template(c, product)
        domain.append(("product_tmpl_id", "=", prod["id"]))
    if active_only:
        from datetime import datetime

        today = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        domain += ["|", ("date_end", "=", False), ("date_end", ">=", today)]

    try:
        rows = c.search_read(
            "product.pricelist.item",
            domain,
            [
                "id",
                "product_tmpl_id",
                "applied_on",
                "min_quantity",
                "compute_price",
                "fixed_price",
                "percent_price",
                "date_start",
                "date_end",
            ],
            limit=limit,
            order="product_tmpl_id, min_quantity, date_start",
        )
    except RPCError as e:
        out.error(f"Failed to read pricelist items: {e}")
        raise typer.Exit(1)

    if not rows:
        out.info(f"No items found for pricelist '{pl['name']}' (id {pl['id']}).")
        if actx.json_mode:
            out.raw_json([])
        return

    if actx.json_mode:
        out.raw_json(rows)
        return

    table_rows = []
    for r in rows:
        if r["compute_price"] == "percentage":
            disc = f"{r['percent_price']:.3f}%"
        elif r["compute_price"] == "fixed":
            disc = fmt_amount(r["fixed_price"])
        else:
            disc = r["compute_price"]
        table_rows.append(
            [
                str(r["id"]),
                _m2o_name(r["product_tmpl_id"]),
                f"{int(r['min_quantity']):,}"
                if r["min_quantity"] == int(r["min_quantity"])
                else f"{r['min_quantity']:,.2f}",
                r["compute_price"],
                disc,
                (r["date_start"] or "")[:10],
                (r["date_end"] or "")[:10],
            ]
        )

    out.table(
        f"Items of '{pl['name']}' (id {pl['id']}) — {len(rows)} rows",
        [
            ("ID", "dim"),
            ("Product", ""),
            ("Min Qty", ""),
            ("Compute", "dim"),
            ("Discount / Price", ""),
            ("Start", "dim"),
            ("End", "dim"),
        ],
        table_rows,
    )


# ===========================================================================
# strata
# ===========================================================================


@app.command("strata")
def strata(
    ctx: typer.Context,
    product: Annotated[str, typer.Argument(help="Product template name, default_code, or ID")],
    prefix: Annotated[str | None, typer.Option("--prefix", help="Pricelist name prefix (e.g. 'TLN-')")] = None,
    latest_only: Annotated[
        bool,
        typer.Option(
            "--latest-only",
            help="Per pricelist, keep only the cohort with the most recent date_start",
        ),
    ] = False,
) -> None:
    """Per-pricelist tier breakdown for one product.

    Shows: pricelist, min_qty, compute, discount %, net price, start date.

    Examples:
        kctl-odoo pricelist strata "ECO TEA CUP 24" --prefix TLN-
        kctl-odoo pricelist strata 550 --prefix TLN- --latest-only
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    prod = _resolve_product_template(c, product)
    list_price = float(prod.get("list_price") or 0.0)

    domain: list = [("product_tmpl_id", "=", prod["id"])]
    domain += _pricelist_domain(prefix)

    try:
        rows = c.search_read(
            "product.pricelist.item",
            domain,
            [
                "id",
                "pricelist_id",
                "min_quantity",
                "compute_price",
                "percent_price",
                "fixed_price",
                "date_start",
                "date_end",
            ],
            limit=20000,
            order="pricelist_id, min_quantity, date_start",
        )
    except RPCError as e:
        out.error(f"Failed to read strata: {e}")
        raise typer.Exit(1)

    if latest_only:
        # Per pricelist, keep only the rows whose date_start matches the per-pricelist max
        per_pl_max: dict[int, str] = {}
        for r in rows:
            pid = r["pricelist_id"][0]
            ds = r["date_start"] or ""
            if ds > per_pl_max.get(pid, ""):
                per_pl_max[pid] = ds
        rows = [r for r in rows if (r["date_start"] or "") == per_pl_max.get(r["pricelist_id"][0], "")]

    if not rows:
        out.info(f"No pricelist items found for '{prod.get('name', prod['id'])}'.")
        if actx.json_mode:
            out.raw_json([])
        return

    if actx.json_mode:
        out.raw_json(rows)
        return

    table_rows = []
    for r in rows:
        if r["compute_price"] == "percentage":
            pct = r["percent_price"]
            net = list_price * (1 - pct / 100.0) if list_price else 0.0
            disc_str = f"{pct:.3f}%"
            net_str = fmt_amount(net) if list_price else "-"
        elif r["compute_price"] == "fixed":
            disc_str = "fixed"
            net_str = fmt_amount(r["fixed_price"])
        else:
            disc_str = r["compute_price"]
            net_str = "-"
        table_rows.append(
            [
                _m2o_name(r["pricelist_id"]),
                f"{int(r['min_quantity']):,}"
                if r["min_quantity"] == int(r["min_quantity"])
                else f"{r['min_quantity']:,.2f}",
                disc_str,
                net_str,
                (r["date_start"] or "")[:10],
            ]
        )

    title_suffix = " (latest cohort per pricelist)" if latest_only else ""
    out.table(
        f"Strata for '{prod.get('name', prod['id'])}' (list price {fmt_amount(list_price)}){title_suffix} — {len(rows)} rows",
        [
            ("Pricelist", ""),
            ("Min Qty", ""),
            ("Discount / Price", ""),
            ("Net Price", ""),
            ("Start", "dim"),
        ],
        table_rows,
    )


# ===========================================================================
# analyze (fingerprint distinct strata patterns)
# ===========================================================================


@app.command("analyze")
def analyze(
    ctx: typer.Context,
    product: Annotated[str, typer.Argument(help="Product template name, default_code, or ID")],
    prefix: Annotated[str | None, typer.Option("--prefix", help="Pricelist name prefix (e.g. 'TLN-')")] = None,
    latest_only: Annotated[
        bool,
        typer.Option(
            "--latest-only",
            help="Per pricelist, keep only the cohort with the most recent date_start",
        ),
    ] = True,
) -> None:
    """Fingerprint distinct strata patterns for one product across pricelists.

    Groups pricelists with identical (min_qty, discount%, start_date) tuples.
    Surfaces consistency / fragmentation across regional or channel pricelists.

    Examples:
        kctl-odoo pricelist analyze "ECO TEA BIG CUP 24" --prefix TLN-
        kctl-odoo pricelist analyze 550 --prefix TLN- --no-latest-only
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    prod = _resolve_product_template(c, product)

    domain: list = [("product_tmpl_id", "=", prod["id"])]
    domain += _pricelist_domain(prefix)

    try:
        rows = c.search_read(
            "product.pricelist.item",
            domain,
            ["pricelist_id", "min_quantity", "compute_price", "percent_price", "fixed_price", "date_start"],
            limit=50000,
            order="pricelist_id, min_quantity",
        )
    except RPCError as e:
        out.error(f"Failed to read pricelist items: {e}")
        raise typer.Exit(1)

    if not rows:
        out.info(f"No pricelist items found for '{prod.get('name', prod['id'])}'.")
        if actx.json_mode:
            out.raw_json([])
        return

    # Group rows per pricelist
    by_pl: dict[int, list[dict]] = defaultdict(list)
    pl_names: dict[int, str] = {}
    for r in rows:
        pid = r["pricelist_id"][0]
        by_pl[pid].append(r)
        pl_names[pid] = r["pricelist_id"][1]

    # If latest_only, trim per-pricelist to the latest cohort
    if latest_only:
        for pid, items_ in list(by_pl.items()):
            mx = max((it["date_start"] or "") for it in items_)
            by_pl[pid] = [it for it in items_ if (it["date_start"] or "") == mx]

    # Build a fingerprint per pricelist: tuple of (min_qty, compute, value)
    def _fp(items_: list[dict]) -> tuple:
        sig = []
        for it in sorted(items_, key=lambda x: (x["min_quantity"], x.get("date_start") or "")):
            if it["compute_price"] == "percentage":
                v = round(it["percent_price"], 3)
            elif it["compute_price"] == "fixed":
                v = round(it["fixed_price"], 2)
            else:
                v = 0
            sig.append(
                (
                    int(it["min_quantity"]) if it["min_quantity"] == int(it["min_quantity"]) else it["min_quantity"],
                    it["compute_price"],
                    v,
                )
            )
        return tuple(sig)

    buckets: dict[tuple, list[int]] = defaultdict(list)
    for pid, items_ in by_pl.items():
        buckets[_fp(items_)].append(pid)

    if actx.json_mode:
        out.raw_json(
            [
                {
                    "pricelists": sorted(pl_names[pid] for pid in pids),
                    "tiers": [{"min_quantity": qty, "compute_price": comp, "value": val} for qty, comp, val in fp],
                }
                for fp, pids in sorted(buckets.items(), key=lambda x: -len(x[1]))
            ]
        )
        return

    out.info(
        f"'{prod.get('name', prod['id'])}' — {len(by_pl)} pricelists → "
        f"{len(buckets)} distinct strata pattern(s)" + (" (latest cohort)" if latest_only else "")
    )
    sorted_buckets = sorted(buckets.items(), key=lambda x: -len(x[1]))
    for i, (fp, pids) in enumerate(sorted_buckets, 1):
        names = sorted(pl_names[pid] for pid in pids)
        if not fp:
            tier_str = "(no tiers)"
        else:
            tier_str = " / ".join(
                f"{qty:,}={val:.3f}%" if comp == "percentage" else f"{qty:,}=Rp {val:,.2f}" for qty, comp, val in fp
            )
        head = f"  Pattern #{i} — {len(pids)} pricelist(s), {len(fp)} tier(s)"
        out.info(head)
        out.info(f"    Tiers: {tier_str}")
        sample = ", ".join(names[:6]) + (f"  +{len(names) - 6} more" if len(names) > 6 else "")
        out.info(f"    OUs:   {sample}")


# ===========================================================================
# export-template (generate the safe ID-based CSV)
# ===========================================================================


@app.command("export-template")
def export_template(
    ctx: typer.Context,
    mode: Annotated[
        str,
        typer.Argument(help="add-lines (only mode currently supported)"),
    ] = "add-lines",
    prefix: Annotated[str | None, typer.Option("--prefix", help="Pricelist name prefix (e.g. 'TLN-')")] = None,
    products: Annotated[
        str | None,
        typer.Option(
            "--products",
            help="Comma-separated list of product template IDs or default_codes",
        ),
    ] = None,
    output: Annotated[Path | None, typer.Option("--output", "-o", help="Output CSV path (default: stdout)")] = None,
) -> None:
    """Generate a safe ID-based CSV template for bulk-adding pricelist tier lines.

    Uses ``pricelist_id/.id`` and ``product_tmpl_id/.id`` so Odoo's import
    wizard can never create a new pricelist or product — it can only attach
    new ``product.pricelist.item`` rows to existing records.

    Examples:
        kctl-odoo pricelist export-template add-lines --prefix TLN- --products 550,554,551 -o tln.csv
        kctl-odoo pricelist export-template --prefix TLN- --products "01010101160,01020101180,01010101280"
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if mode != "add-lines":
        out.error(f"Mode '{mode}' not supported. Use 'add-lines'.")
        raise typer.Exit(2)
    if not products:
        out.error("--products is required (comma-separated IDs or default_codes).")
        raise typer.Exit(2)

    # Resolve products
    prod_list: list[dict] = []
    for tok in [t.strip() for t in products.split(",") if t.strip()]:
        prod_list.append(_resolve_product_template(c, tok))

    # Resolve target pricelists
    pl_domain: list = []
    if prefix:
        pl_domain = [("name", "=like", f"{prefix}%")]
    try:
        pl_rows = c.search_read("product.pricelist", pl_domain, ["id", "name"], order="name", limit=10000)
    except RPCError as e:
        out.error(f"Failed to list pricelists: {e}")
        raise typer.Exit(1)
    if not pl_rows:
        out.error("No matching pricelists found.")
        raise typer.Exit(1)

    # Emit CSV
    sink = output.open("w", newline="") if output else sys.stdout
    try:
        w = csv.writer(sink)
        w.writerow(
            [
                "pricelist_id/.id",
                "_pricelist_name",
                "applied_on",
                "product_tmpl_id/.id",
                "_product_name",
                "min_quantity",
                "compute_price",
                "percent_price",
                "date_start",
                "date_end",
            ]
        )
        for pl in pl_rows:
            for prod in prod_list:
                code = prod.get("default_code") or ""
                pname = prod.get("name") or str(prod["id"])
                display = f"[{code}] {pname}" if code else pname
                w.writerow(
                    [
                        pl["id"],
                        pl["name"],
                        "1_product",
                        prod["id"],
                        display,
                        "",
                        "percentage",
                        "",
                        "",
                        "",
                    ]
                )
    finally:
        if output:
            sink.close()

    if output:
        rows_written = len(pl_rows) * len(prod_list)
        out.success(f"Wrote {rows_written} starter rows to {output}")
        out.info(
            f"  ({len(pl_rows)} pricelists × {len(prod_list)} products). "
            "Fill in min_quantity, percent_price, and date_start columns before importing."
        )
