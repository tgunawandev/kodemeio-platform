"""pages — Search Analytics by page dimension."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_gsc.commands.queries import _query

app = typer.Typer(help="Top pages, impressions, orphan audit.")


@app.command()
def top(
    ctx: typer.Context,
    days: Annotated[int, typer.Option("--days")] = 28,
    limit: Annotated[int, typer.Option("--limit")] = 25,
) -> None:
    """Top pages by clicks."""
    actx = ctx.obj
    rows = _query(actx.client, actx.property, ["page"], days, limit)
    data_for_json = [
        {
            "page": r["keys"][0],
            "clicks": r.get("clicks", 0),
            "impressions": r.get("impressions", 0),
            "ctr": round(r.get("ctr", 0) * 100, 2),
            "position": round(r.get("position", 0), 2),
        }
        for r in rows
    ]
    table_rows = [
        [
            str(d["page"]),
            str(d["clicks"]),
            str(d["impressions"]),
            str(d["ctr"]),
            str(d["position"]),
        ]
        for d in data_for_json
    ]
    actx.output.table(
        f"Top pages ({days}d)",
        [("page", "cyan"), ("clicks", ""), ("impressions", ""), ("ctr", ""), ("position", "")],
        table_rows,
        data_for_json=data_for_json,
    )


@app.command()
def impressions(
    ctx: typer.Context,
    days: Annotated[int, typer.Option("--days")] = 28,
    limit: Annotated[int, typer.Option("--limit")] = 50,
) -> None:
    """Pages ranked by impressions (visibility, not click-through)."""
    actx = ctx.obj
    rows = _query(actx.client, actx.property, ["page"], days, limit)
    rows.sort(key=lambda r: r.get("impressions", 0), reverse=True)
    data_for_json = [
        {
            "page": r["keys"][0],
            "impressions": r.get("impressions", 0),
            "position": round(r.get("position", 0), 2),
        }
        for r in rows
    ]
    table_rows = [[str(d["page"]), str(d["impressions"]), str(d["position"])] for d in data_for_json]
    actx.output.table(
        f"Pages by impressions ({days}d)",
        [("page", "cyan"), ("impressions", ""), ("position", "")],
        table_rows,
        data_for_json=data_for_json,
    )


@app.command()
def orphans(
    ctx: typer.Context,
    days: Annotated[int, typer.Option("--days")] = 28,
    min_impressions: Annotated[int, typer.Option("--min-impressions")] = 50,
    limit: Annotated[int, typer.Option("--limit")] = 200,
) -> None:
    """Pages with impressions but zero clicks (indexed but unreachable from SERP)."""
    actx = ctx.obj
    rows = _query(actx.client, actx.property, ["page"], days, limit)
    orphan_rows = [r for r in rows if r.get("clicks", 0) == 0 and r.get("impressions", 0) >= min_impressions]
    data_for_json = [
        {
            "page": r["keys"][0],
            "impressions": r.get("impressions", 0),
            "position": round(r.get("position", 0), 2),
        }
        for r in orphan_rows
    ]
    table_rows = [[str(d["page"]), str(d["impressions"]), str(d["position"])] for d in data_for_json]
    actx.output.table(
        f"Orphan pages ({days}d, min_impressions={min_impressions})",
        [("page", "cyan"), ("impressions", ""), ("position", "")],
        table_rows,
        data_for_json=data_for_json,
    )
