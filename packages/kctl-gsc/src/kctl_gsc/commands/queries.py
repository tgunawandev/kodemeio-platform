"""queries — Search Analytics API (dimensions=query)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated

import typer

app = typer.Typer(help="Top queries, search, and trends.")


def _daterange(days: int) -> tuple[str, str]:
    end = date.today()
    start = end - timedelta(days=days)
    return start.isoformat(), end.isoformat()


def _query(
    client,  # type: ignore[no-untyped-def]
    property_uri: str,
    dimensions: list[str],
    days: int,
    row_limit: int,
    filters: list[dict] | None = None,  # type: ignore[type-arg]
) -> list[dict]:  # type: ignore[type-arg]
    start, end = _daterange(days)
    body: dict = {  # type: ignore[type-arg]
        "startDate": start,
        "endDate": end,
        "dimensions": dimensions,
        "rowLimit": row_limit,
    }
    if filters:
        body["dimensionFilterGroups"] = [{"filters": filters}]
    data = client.searchanalytics().query(siteUrl=property_uri, body=body).execute() or {}
    return data.get("rows", [])  # type: ignore[no-any-return]


@app.command()
def top(
    ctx: typer.Context,
    days: Annotated[int, typer.Option("--days")] = 28,
    limit: Annotated[int, typer.Option("--limit")] = 25,
) -> None:
    """Top queries by clicks over N days."""
    actx = ctx.obj
    rows = _query(actx.client, actx.property, ["query"], days, limit)
    data_for_json = [
        {
            "query": r["keys"][0],
            "clicks": r.get("clicks", 0),
            "impressions": r.get("impressions", 0),
            "ctr": round(r.get("ctr", 0) * 100, 2),
            "position": round(r.get("position", 0), 2),
        }
        for r in rows
    ]
    table_rows = [
        [
            str(d["query"]),
            str(d["clicks"]),
            str(d["impressions"]),
            str(d["ctr"]),
            str(d["position"]),
        ]
        for d in data_for_json
    ]
    actx.output.table(
        f"Top queries ({days}d)",
        [("query", "cyan"), ("clicks", ""), ("impressions", ""), ("ctr", ""), ("position", "")],
        table_rows,
        data_for_json=data_for_json,
    )


@app.command()
def search(
    ctx: typer.Context,
    pattern: str,
    days: Annotated[int, typer.Option("--days")] = 28,
    limit: Annotated[int, typer.Option("--limit")] = 100,
) -> None:
    """Substring-match queries (case-insensitive)."""
    actx = ctx.obj
    rows = _query(actx.client, actx.property, ["query"], days, limit)
    needle = pattern.lower()
    matches = [r for r in rows if needle in r["keys"][0].lower()]
    data_for_json = [
        {
            "query": r["keys"][0],
            "clicks": r.get("clicks", 0),
            "impressions": r.get("impressions", 0),
            "position": round(r.get("position", 0), 2),
        }
        for r in matches
    ]
    table_rows = [[str(d["query"]), str(d["clicks"]), str(d["impressions"]), str(d["position"])] for d in data_for_json]
    actx.output.table(
        f"Queries matching '{pattern}'",
        [("query", "cyan"), ("clicks", ""), ("impressions", ""), ("position", "")],
        table_rows,
        data_for_json=data_for_json,
    )


@app.command()
def trends(
    ctx: typer.Context,
    query: str,
    days: Annotated[int, typer.Option("--days")] = 90,
) -> None:
    """Daily impressions + position for a single query."""
    actx = ctx.obj
    rows = _query(
        actx.client,
        actx.property,
        ["date"],
        days,
        days,
        filters=[{"dimension": "query", "operator": "equals", "expression": query}],
    )
    data_for_json = [
        {
            "date": r["keys"][0],
            "impressions": r.get("impressions", 0),
            "clicks": r.get("clicks", 0),
            "position": round(r.get("position", 0), 2),
        }
        for r in rows
    ]
    table_rows = [[str(d["date"]), str(d["impressions"]), str(d["clicks"]), str(d["position"])] for d in data_for_json]
    actx.output.table(
        f"Trend: {query} ({days}d)",
        [("date", "cyan"), ("impressions", ""), ("clicks", ""), ("position", "")],
        table_rows,
        data_for_json=data_for_json,
    )
