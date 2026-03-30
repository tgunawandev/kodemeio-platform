"""Date range/fiscal period management commands."""

from __future__ import annotations

from datetime import date
from typing import Annotated

import typer

from kctl_odoo.core.biz_helpers import model_available
from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.exceptions import RPCError

app = typer.Typer(help="Fiscal periods and date range management.")

_DATE_RANGE_MODEL = "date.range"
_DATE_RANGE_TYPE_MODEL = "date.range.type"
_PERIODS_HINT = "OCA date_range module is not installed."


def _m2o_name(val: object) -> str:
    if isinstance(val, list):
        return str(val[1])
    return str(val or "-")


# ===================================================================
# LIST
# ===================================================================


@app.command("list")
def list_periods(
    ctx: typer.Context,
    range_type: Annotated[str | None, typer.Option("--type", help="Filter by date range type name (ilike)")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List date ranges (fiscal periods).

    Examples:
        kctl-odoo periods list
        kctl-odoo periods list --type "Fiscal Year" --limit 20
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _DATE_RANGE_MODEL):
        out.warn(_PERIODS_HINT)
        return

    domain: list = []
    if range_type:
        domain.append(("type_id.name", "ilike", range_type))

    try:
        records = c.search_read(  # type: ignore[attr-defined]
            _DATE_RANGE_MODEL,
            domain=domain,
            fields=["name", "type_id", "date_start", "date_end", "active", "company_id"],
            limit=limit,
            order="date_start desc",
        )
    except RPCError as e:
        out.error(f"Failed to list date ranges: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.info("No date ranges found.")
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
                _m2o_name(r.get("type_id")),
                str(r.get("date_start", "")),
                str(r.get("date_end", "")),
                "Yes" if r.get("active") else "No",
            ]
        )
        json_data.append(
            {
                "id": r["id"],
                "name": r.get("name"),
                "type": _m2o_name(r.get("type_id")),
                "date_start": r.get("date_start"),
                "date_end": r.get("date_end"),
                "active": r.get("active"),
            }
        )

    out.table(
        f"Date Ranges ({len(records)})",
        [("ID", "dim"), ("Name", "cyan"), ("Type", ""), ("Start", ""), ("End", ""), ("Active", "")],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# TYPES
# ===================================================================


@app.command("types")
def types(ctx: typer.Context) -> None:
    """List date range types.

    Examples:
        kctl-odoo periods types
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _DATE_RANGE_TYPE_MODEL):
        out.warn(_PERIODS_HINT)
        return

    try:
        records = c.search_read(  # type: ignore[attr-defined]
            _DATE_RANGE_TYPE_MODEL,
            domain=[],
            fields=["name", "allow_overlap", "company_id"],
            order="name asc",
        )
    except RPCError as e:
        out.error(f"Failed to list date range types: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.info("No date range types found.")
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
                "Yes" if r.get("allow_overlap") else "No",
                _m2o_name(r.get("company_id")),
            ]
        )
        json_data.append(
            {
                "id": r["id"],
                "name": r.get("name"),
                "allow_overlap": r.get("allow_overlap"),
                "company": _m2o_name(r.get("company_id")),
            }
        )

    out.table(
        f"Date Range Types ({len(records)})",
        [("ID", "dim"), ("Name", "cyan"), ("Allow Overlap", ""), ("Company", "")],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# CREATE YEAR
# ===================================================================


@app.command("create-year")
def create_year(
    ctx: typer.Context,
    year: Annotated[int, typer.Argument(help="Fiscal year (e.g. 2025)")],
    range_type: Annotated[str, typer.Option("--type", help="Date range type name")] = "fiscal_year",
) -> None:
    """Create 12 monthly date ranges for a fiscal year.

    Creates January through December periods for the given year using the
    specified date range type. Will skip months that already exist.

    Examples:
        kctl-odoo periods create-year 2025
        kctl-odoo periods create-year 2026 --type "Month"
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _DATE_RANGE_MODEL):
        out.warn(_PERIODS_HINT)
        return

    # Resolve type
    try:
        types_data = c.search_read(  # type: ignore[attr-defined]
            _DATE_RANGE_TYPE_MODEL,
            [("name", "ilike", range_type)],
            ["id", "name"],
            limit=1,
        )
    except RPCError as e:
        out.error(f"Failed to resolve date range type '{range_type}': {e}")
        raise typer.Exit(1) from e

    if not types_data:
        out.error(f"Date range type not found: {range_type}")
        out.info("Available types: kctl-odoo periods types")
        raise typer.Exit(1)

    type_id = types_data[0]["id"]
    type_name = types_data[0]["name"]
    out.info(f"Creating monthly periods for {year} using type: {type_name}")

    import calendar

    created = []
    skipped = []

    for month in range(1, 13):
        last_day = calendar.monthrange(year, month)[1]
        date_start = date(year, month, 1).strftime("%Y-%m-%d")
        date_end = date(year, month, last_day).strftime("%Y-%m-%d")
        period_name = f"{year}-{month:02d}"

        # Check if exists
        try:
            existing = c.search_count(  # type: ignore[attr-defined]
                _DATE_RANGE_MODEL,
                [("name", "=", period_name), ("type_id", "=", type_id)],
            )
        except RPCError:
            existing = 0

        if existing:
            skipped.append(period_name)
            continue

        try:
            period_id = c.create(  # type: ignore[attr-defined]
                _DATE_RANGE_MODEL,
                {"name": period_name, "type_id": type_id, "date_start": date_start, "date_end": date_end},
            )
            created.append({"name": period_name, "id": period_id, "date_start": date_start, "date_end": date_end})
        except RPCError as e:
            out.warn(f"Failed to create period {period_name}: {e}")

    if created:
        out.success(f"Created {len(created)} periods for {year}.")
        rows = [[p["name"], p["date_start"], p["date_end"], str(p["id"])] for p in created]
        out.table(
            "Created Periods",
            [("Period", "cyan"), ("Start", ""), ("End", ""), ("ID", "dim")],
            rows,
            data_for_json=created,
        )

    if skipped:
        out.info(f"Skipped {len(skipped)} existing periods: {', '.join(skipped)}")

    if actx.json_mode:
        out.raw_json({"created": created, "skipped": skipped, "year": year})
