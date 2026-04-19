"""reports — overview, product (keyword-cluster), opportunities, drift."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Annotated

import typer

from kctl_gsc.commands.queries import _query
from kctl_gsc.core.clusters import apply_clusters, load_clusters

app = typer.Typer(help="Opinionated reports.")

DEFAULT_CLUSTERS_PATH = Path("deploys/marketing/gsc-keyword-clusters.yaml")


@app.command()
def overview(
    ctx: typer.Context,
    days: Annotated[int, typer.Option("--days")] = 28,
) -> None:
    """Totals across the active property."""
    actx = ctx.obj
    rows = _query(actx.client, actx.property, ["date"], days, days)
    total_clicks = sum(r.get("clicks", 0) for r in rows)
    total_impr = sum(r.get("impressions", 0) for r in rows)
    ctr = (total_clicks / total_impr * 100) if total_impr else 0.0
    data = {
        "property": actx.property,
        "window_days": days,
        "clicks": total_clicks,
        "impressions": total_impr,
        "ctr_pct": round(ctr, 2),
    }
    sections = [
        (
            "Overview",
            [
                ("property", str(data["property"])),
                ("window_days", str(data["window_days"])),
                ("clicks", str(data["clicks"])),
                ("impressions", str(data["impressions"])),
                ("ctr_pct", str(data["ctr_pct"])),
            ],
        )
    ]
    actx.output.detail(f"Overview ({days}d)", sections, data_for_json=data)


@app.command()
def product(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="bas | hrm | tpm | tms")],
    days: Annotated[int, typer.Option("--days")] = 28,
    clusters: Annotated[Path, typer.Option("--clusters")] = DEFAULT_CLUSTERS_PATH,
    row_limit: Annotated[int, typer.Option("--row-limit")] = 5000,
) -> None:
    """Per-product keyword-cluster report."""
    actx = ctx.obj
    out = actx.output
    if not clusters.is_file():
        out.error(f"Clusters file not found: {clusters}")
        raise typer.Exit(code=1)
    cfg = load_clusters(clusters)
    product_cfg = cfg.products.get(name)
    if product_cfg is None:
        out.error(f"Product '{name}' not defined in {clusters}")
        raise typer.Exit(code=1)

    filters: list[dict] = []  # type: ignore[type-arg]
    if product_cfg.path_filter:
        filters = [{"dimension": "page", "operator": "contains", "expression": product_cfg.path_filter}]

    raw = _query(actx.client, product_cfg.property, ["query"], days, row_limit, filters=filters)
    rows = [
        {"query": r["keys"][0], **{k: r.get(k, 0) for k in ("clicks", "impressions", "ctr", "position")}} for r in raw
    ]

    buckets = apply_clusters(product_cfg, rows)
    bucket_json = [
        {
            "cluster": b.name,
            "impressions": b.impressions,
            "clicks": b.clicks,
            "ctr_pct": round(b.ctr, 2),
            "avg_position": round(b.avg_position, 2),
            "top_query": b.top_query,
        }
        for b in buckets
    ]
    table_rows = [
        [
            str(d["cluster"]),
            str(d["impressions"]),
            str(d["clicks"]),
            str(d["ctr_pct"]),
            str(d["avg_position"]),
            str(d["top_query"]),
        ]
        for d in bucket_json
    ]
    out.table(
        f"Product clusters: {name} ({days}d)",
        [
            ("cluster", "cyan"),
            ("impressions", ""),
            ("clicks", ""),
            ("ctr_pct", ""),
            ("avg_position", ""),
            ("top_query", ""),
        ],
        table_rows,
        data_for_json=bucket_json,
    )

    # Opportunity queries: position in [4,10] AND ctr<2%
    opp = [r for r in rows if 4 <= r["position"] <= 10 and r["ctr"] * 100 < 2 and r["impressions"] >= 50]
    if opp:
        out.info(f"\n{len(opp)} opportunity queries (rank 4-10, CTR<2%):")
        opp_json = [
            {"query": r["query"], "impressions": r["impressions"], "position": round(r["position"], 2)}
            for r in opp[:10]
        ]
        opp_rows = [[str(d["query"]), str(d["impressions"]), str(d["position"])] for d in opp_json]
        out.table(
            "Opportunities",
            [("query", "cyan"), ("impressions", ""), ("position", "")],
            opp_rows,
            data_for_json=opp_json,
        )


@app.command()
def opportunities(
    ctx: typer.Context,
    days: Annotated[int, typer.Option("--days")] = 28,
    min_impressions: Annotated[int, typer.Option("--min-impressions")] = 100,
    limit: Annotated[int, typer.Option("--limit")] = 5000,
) -> None:
    """Queries ranked 4-10 with CTR below 2% — SEO quick wins."""
    actx = ctx.obj
    rows = _query(actx.client, actx.property, ["query"], days, limit)
    opp = [
        {
            "query": r["keys"][0],
            "impressions": r.get("impressions", 0),
            "position": round(r.get("position", 0), 2),
            "ctr_pct": round(r.get("ctr", 0) * 100, 2),
        }
        for r in rows
        if 4 <= r.get("position", 0) <= 10 and r.get("ctr", 0) * 100 < 2 and r.get("impressions", 0) >= min_impressions
    ]
    opp.sort(key=lambda x: x["impressions"], reverse=True)
    table_rows = [[str(d["query"]), str(d["impressions"]), str(d["position"]), str(d["ctr_pct"])] for d in opp]
    actx.output.table(
        f"Opportunities ({days}d)",
        [("query", "cyan"), ("impressions", ""), ("position", ""), ("ctr_pct", "")],
        table_rows,
        data_for_json=opp,
    )


@app.command()
def drift(
    ctx: typer.Context,
    days: Annotated[int, typer.Option("--days")] = 7,
    threshold: Annotated[float, typer.Option("--threshold", help="Minimum positions lost")] = 3.0,
    row_limit: Annotated[int, typer.Option("--row-limit")] = 5000,
) -> None:
    """Queries that lost >= N rank positions vs the prior period."""
    actx = ctx.obj

    end = date.today()
    cur_start = end - timedelta(days=days)
    prior_end = cur_start
    prior_start = prior_end - timedelta(days=days)

    def fetch(start_d: date, end_d: date) -> dict[str, dict]:  # type: ignore[type-arg]
        body = {
            "startDate": start_d.isoformat(),
            "endDate": end_d.isoformat(),
            "dimensions": ["query"],
            "rowLimit": row_limit,
        }
        data = actx.client.searchanalytics().query(siteUrl=actx.property, body=body).execute() or {}
        return {r["keys"][0]: r for r in data.get("rows", [])}

    cur = fetch(cur_start, end)
    prior = fetch(prior_start, prior_end)

    drifted: list[dict] = []  # type: ignore[type-arg]
    for q, c in cur.items():
        p = prior.get(q)
        if not p:
            continue
        delta = c.get("position", 0) - p.get("position", 0)  # positive = lost rank
        if delta >= threshold:
            drifted.append(
                {
                    "query": q,
                    "prior_pos": round(p.get("position", 0), 2),
                    "current_pos": round(c.get("position", 0), 2),
                    "delta": round(delta, 2),
                    "impressions": c.get("impressions", 0),
                    "weight": round(delta * c.get("impressions", 0), 0),
                }
            )
    drifted.sort(key=lambda x: x["weight"], reverse=True)
    table_rows = [
        [
            str(d["query"]),
            str(d["prior_pos"]),
            str(d["current_pos"]),
            str(d["delta"]),
            str(d["impressions"]),
            str(d["weight"]),
        ]
        for d in drifted
    ]
    actx.output.table(
        f"Drift ({days}d, threshold>={threshold})",
        [
            ("query", "cyan"),
            ("prior_pos", ""),
            ("current_pos", ""),
            ("delta", ""),
            ("impressions", ""),
            ("weight", ""),
        ],
        table_rows,
        data_for_json=drifted,
    )
