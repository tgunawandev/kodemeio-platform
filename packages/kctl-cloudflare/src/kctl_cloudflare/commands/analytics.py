"""Zone analytics commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_cloudflare.core.callbacks import AppContext
from kctl_cloudflare.core.utils import human_size, resolve_zone

app = typer.Typer(help="Zone analytics and traffic reports.")


@app.command()
def dashboard(
    ctx: typer.Context,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
    since: Annotated[int, typer.Option("--since", help="Minutes ago (negative). Default: -1440 (24h)")] = -1440,
) -> None:
    """Show zone analytics dashboard (requests, bandwidth, threats, etc.)."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)

    result = c.client.get(f"/zones/{zone_id}/analytics/dashboard", params={"since": since})

    if not isinstance(result, dict):
        c.output.error("Unexpected response format")
        raise typer.Exit(1)

    totals = result.get("totals", {})
    timeseries = result.get("timeseries", [])

    # Requests
    requests = totals.get("requests", {})
    req_all = requests.get("all", 0)
    req_cached = requests.get("cached", 0)
    req_uncached = requests.get("uncached", 0)

    # Bandwidth
    bandwidth = totals.get("bandwidth", {})
    bw_all = bandwidth.get("all", 0)
    bw_cached = bandwidth.get("cached", 0)

    # Threats
    threats = totals.get("threats", {})
    threat_all = threats.get("all", 0)

    # Page views
    pageviews = totals.get("pageviews", {})
    pv_all = pageviews.get("all", 0)

    # Uniques
    uniques = totals.get("uniques", {})
    uniq_all = uniques.get("all", 0)

    sections = [
        (
            "Requests",
            [
                ("Total", f"{req_all:,}"),
                ("Cached", f"{req_cached:,}"),
                ("Uncached", f"{req_uncached:,}"),
                ("Cache Rate", f"{(req_cached / req_all * 100):.1f}%" if req_all else "N/A"),
            ],
        ),
        (
            "Bandwidth",
            [
                ("Total", human_size(bw_all)),
                ("Cached", human_size(bw_cached)),
            ],
        ),
        (
            "Security",
            [
                ("Threats Stopped", f"{threat_all:,}"),
            ],
        ),
        (
            "Visitors",
            [
                ("Page Views", f"{pv_all:,}"),
                ("Unique Visitors", f"{uniq_all:,}"),
            ],
        ),
    ]

    # Top content types from requests
    content_types = requests.get("content_type", {})
    if content_types:
        ct_kvs = [
            (ct, f"{count:,}") for ct, count in sorted(content_types.items(), key=lambda x: x[1], reverse=True)[:10]
        ]
        sections.append(("Top Content Types", ct_kvs))

    # Top countries
    countries = requests.get("country", {})
    if countries:
        country_kvs = [
            (cc, f"{count:,}") for cc, count in sorted(countries.items(), key=lambda x: x[1], reverse=True)[:10]
        ]
        sections.append(("Top Countries", country_kvs))

    data = {
        "zone": zone,
        "since_minutes": since,
        "totals": totals,
        "timeseries_points": len(timeseries),
    }

    c.output.detail(f"Analytics Dashboard -- {zone}", sections, data_for_json=data)


@app.command()
def dns(
    ctx: typer.Context,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
    since: Annotated[int, typer.Option("--since", help="Minutes ago (negative). Default: -1440 (24h)")] = -1440,
) -> None:
    """Show DNS analytics report."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)

    params = {
        "since": since,
        "metrics": "queryCount,uncachedCount,staleCount",
        "dimensions": "queryType",
    }

    try:
        result = c.client.get(f"/zones/{zone_id}/dns_analytics/report", params=params)
    except Exception as e:
        c.output.error(f"DNS analytics not available: {e}")
        raise typer.Exit(1) from e

    if not isinstance(result, dict):
        c.output.error("Unexpected response format")
        raise typer.Exit(1)

    totals = result.get("totals", {})
    data_rows = result.get("data", [])

    # Summary
    total_queries = 0
    if isinstance(totals, dict):
        total_queries = totals.get("queryCount", 0)
    elif isinstance(totals, list) and totals:
        total_queries = totals[0] if isinstance(totals[0], int) else 0

    # Build table from data
    rows: list[list[str]] = []
    json_data: list[dict] = []

    if isinstance(data_rows, list):
        for entry in data_rows:
            if isinstance(entry, dict):
                dimensions = entry.get("dimensions", [])
                metrics = entry.get("metrics", [])
                query_type = dimensions[0] if dimensions else "-"
                query_count = metrics[0] if metrics else 0
                uncached = metrics[1] if len(metrics) > 1 else 0
                stale = metrics[2] if len(metrics) > 2 else 0
                rows.append(
                    [
                        str(query_type),
                        f"{query_count:,}" if isinstance(query_count, int) else str(query_count),
                        f"{uncached:,}" if isinstance(uncached, int) else str(uncached),
                        f"{stale:,}" if isinstance(stale, int) else str(stale),
                    ]
                )
                json_data.append(
                    {
                        "query_type": query_type,
                        "query_count": query_count,
                        "uncached": uncached,
                        "stale": stale,
                    }
                )

    if not rows:
        c.output.info(f"No DNS analytics data for {zone}")
        return

    c.output.info(f"Zone: {zone} | Total queries: {total_queries:,}")

    c.output.table(
        f"DNS Analytics -- {zone}",
        [("Query Type", "cyan"), ("Queries", ""), ("Uncached", "yellow"), ("Stale", "dim")],
        rows,
        data_for_json=json_data,
    )
