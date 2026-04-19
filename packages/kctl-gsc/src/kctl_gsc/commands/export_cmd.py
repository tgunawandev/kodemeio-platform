"""export — csv / json dump of Search Analytics rows."""

from __future__ import annotations

import csv as csv_mod
import json as json_mod
from pathlib import Path
from typing import Annotated

import typer

from kctl_gsc.commands.queries import _query

app = typer.Typer(help="Export raw Search Analytics rows.")


def _fetch(actx, dimensions: list[str], days: int, row_limit: int) -> list[dict]:  # type: ignore[no-untyped-def, type-arg]
    rows = _query(actx.client, actx.property, dimensions, days, row_limit)
    out: list[dict] = []  # type: ignore[type-arg]
    for r in rows:
        keys = r.get("keys", [])
        row: dict = {d: keys[i] if i < len(keys) else "" for i, d in enumerate(dimensions)}  # type: ignore[type-arg]
        row["clicks"] = r.get("clicks", 0)
        row["impressions"] = r.get("impressions", 0)
        row["ctr"] = round(r.get("ctr", 0) * 100, 4)
        row["position"] = round(r.get("position", 0), 2)
        out.append(row)
    return out


@app.command()
def csv(
    ctx: typer.Context,
    dimensions: Annotated[
        str,
        typer.Option("--dimensions", help="Comma-separated: query,page,country,device,date"),
    ] = "query",
    days: Annotated[int, typer.Option("--days")] = 28,
    row_limit: Annotated[int, typer.Option("--row-limit")] = 5000,
    out: Annotated[Path, typer.Option("--out")] = Path("gsc-export.csv"),
) -> None:
    """Dump Search Analytics rows as CSV."""
    actx = ctx.obj
    dim_list = [d.strip() for d in dimensions.split(",") if d.strip()]
    rows = _fetch(actx, dim_list, days, row_limit)
    if not rows:
        actx.output.warn("No rows to export")
        return
    with open(out, "w", newline="") as f:
        w = csv_mod.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    actx.output.success(f"Wrote {len(rows)} rows -> {out}")


@app.command()
def json(
    ctx: typer.Context,
    dimensions: Annotated[str, typer.Option("--dimensions")] = "query",
    days: Annotated[int, typer.Option("--days")] = 28,
    row_limit: Annotated[int, typer.Option("--row-limit")] = 5000,
    out: Annotated[Path, typer.Option("--out")] = Path("gsc-export.json"),
) -> None:
    """Dump Search Analytics rows as JSON."""
    actx = ctx.obj
    dim_list = [d.strip() for d in dimensions.split(",") if d.strip()]
    rows = _fetch(actx, dim_list, days, row_limit)
    out.write_text(json_mod.dumps(rows, indent=2))
    actx.output.success(f"Wrote {len(rows)} rows -> {out}")
