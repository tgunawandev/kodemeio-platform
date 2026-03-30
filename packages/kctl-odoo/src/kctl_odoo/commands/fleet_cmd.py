"""Fleet management commands — vehicles, contracts, services, odometer, costs."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

import typer

from kctl_odoo.core.biz_helpers import model_available
from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.exceptions import RPCError

app = typer.Typer(help="Fleet management: vehicles, contracts, services.")

_FLEET_MODEL = "fleet.vehicle"
_FLEET_HINT = "Fleet module (fleet) is not installed."


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _m2o_name(val: object) -> str:
    """Extract display name from M2O field value ([id, name] or False)."""
    if isinstance(val, list):
        return str(val[1])
    return str(val or "-")


def _resolve_vehicle(c: object, value: str) -> tuple[int, str]:
    """Resolve vehicle by numeric ID or name search. Returns (id, display_name)."""
    if value.isdigit():
        recs = c.read(_FLEET_MODEL, [int(value)], ["id", "display_name"])  # type: ignore[attr-defined]
    else:
        recs = c.search_read(  # type: ignore[attr-defined]
            _FLEET_MODEL, [("name", "ilike", value)], ["id", "display_name"], limit=1
        )
    if not recs:
        raise typer.BadParameter(f"Vehicle not found: {value}")
    return recs[0]["id"], recs[0].get("display_name", str(recs[0]["id"]))


# ===================================================================
# SUMMARY
# ===================================================================


@app.command("summary")
def summary(ctx: typer.Context) -> None:
    """Fleet dashboard: vehicle count, expiring contracts, services due.

    Examples:
        kctl-odoo fleet summary
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _FLEET_MODEL):
        out.warn(_FLEET_HINT)
        return

    try:
        vehicle_count = c.search_count(_FLEET_MODEL, [])  # type: ignore[attr-defined]
    except RPCError as e:
        out.error(f"Failed to count vehicles: {e}")
        raise typer.Exit(1) from e

    now = datetime.now(tz=UTC)
    cutoff = (now + timedelta(days=30)).strftime("%Y-%m-%d")

    expiring_count = 0
    if model_available(c, "fleet.vehicle.log.contract"):
        try:
            expiring_count = c.search_count(  # type: ignore[attr-defined]
                "fleet.vehicle.log.contract",
                [
                    ("expiration_date", "<=", cutoff),
                    ("expiration_date", ">=", now.strftime("%Y-%m-%d")),
                    ("state_id.name", "!=", "Closed"),
                ],
            )
        except RPCError:
            expiring_count = 0

    services_due = 0
    if model_available(c, "fleet.vehicle.log.services"):
        try:
            services_due = c.search_count(  # type: ignore[attr-defined]
                "fleet.vehicle.log.services",
                [("date", "<=", now.strftime("%Y-%m-%d"))],
            )
        except RPCError:
            services_due = 0

    rows = [
        ["Total Vehicles", str(vehicle_count)],
        ["Contracts Expiring (30d)", str(expiring_count)],
        ["Services Due", str(services_due)],
    ]
    json_data = {
        "vehicle_count": vehicle_count,
        "contracts_expiring_30d": expiring_count,
        "services_due": services_due,
    }

    out.table(
        "Fleet Summary",
        [("Metric", ""), ("Value", "cyan")],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# VEHICLES
# ===================================================================


@app.command("vehicles")
def vehicles(
    ctx: typer.Context,
    state: Annotated[str | None, typer.Option("--state", help="Filter by state name")] = None,
    driver: Annotated[str | None, typer.Option("--driver", help="Filter by driver name")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List fleet vehicles.

    Examples:
        kctl-odoo fleet vehicles
        kctl-odoo fleet vehicles --state Active --limit 20
        kctl-odoo fleet vehicles --driver "John"
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _FLEET_MODEL):
        out.warn(_FLEET_HINT)
        return

    domain: list = []
    if state:
        domain.append(("state_id.name", "ilike", state))
    if driver:
        domain.append(("driver_id.name", "ilike", driver))

    try:
        records = c.search_read(  # type: ignore[attr-defined]
            _FLEET_MODEL,
            domain=domain,
            fields=["name", "driver_id", "state_id", "license_plate", "model_id", "odometer"],
            limit=limit,
            order="name asc",
        )
    except RPCError as e:
        out.error(f"Failed to list vehicles: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.info("No vehicles found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for r in records:
        rows.append(
            [
                r.get("name", ""),
                _m2o_name(r.get("driver_id")),
                _m2o_name(r.get("state_id")),
                str(r.get("license_plate", "")),
                _m2o_name(r.get("model_id")),
                str(r.get("odometer", 0)),
            ]
        )
        json_data.append(
            {
                "id": r["id"],
                "name": r.get("name"),
                "driver": _m2o_name(r.get("driver_id")),
                "state": _m2o_name(r.get("state_id")),
                "license_plate": r.get("license_plate"),
                "model": _m2o_name(r.get("model_id")),
                "odometer": r.get("odometer"),
            }
        )

    out.table(
        f"Fleet Vehicles ({len(records)})",
        [("Name", "cyan"), ("Driver", ""), ("State", ""), ("Plate", ""), ("Model", ""), ("Odometer", "dim")],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# GET VEHICLE
# ===================================================================


@app.command("get-vehicle")
def get_vehicle(
    ctx: typer.Context,
    vehicle_id: Annotated[int, typer.Argument(help="Vehicle ID")],
) -> None:
    """Get vehicle detail by ID.

    Examples:
        kctl-odoo fleet get-vehicle 5
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _FLEET_MODEL):
        out.warn(_FLEET_HINT)
        return

    try:
        records = c.read(  # type: ignore[attr-defined]
            _FLEET_MODEL,
            [vehicle_id],
            [
                "name",
                "driver_id",
                "state_id",
                "license_plate",
                "model_id",
                "odometer",
                "acquisition_date",
                "color",
                "vin_sn",
                "fuel_type",
                "transmission",
            ],
        )
    except RPCError as e:
        out.error(f"Failed to fetch vehicle {vehicle_id}: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.error(f"Vehicle not found: {vehicle_id}")
        raise typer.Exit(1)

    rec = records[0]
    sections = [
        (
            "Vehicle",
            [
                ("ID", str(rec["id"])),
                ("Name", rec.get("name", "")),
                ("Driver", _m2o_name(rec.get("driver_id"))),
                ("State", _m2o_name(rec.get("state_id"))),
                ("License Plate", str(rec.get("license_plate", ""))),
                ("Model", _m2o_name(rec.get("model_id"))),
                ("Odometer", str(rec.get("odometer", 0))),
                ("Acquisition Date", str(rec.get("acquisition_date", ""))),
                ("Color", str(rec.get("color", ""))),
                ("VIN", str(rec.get("vin_sn", ""))),
                ("Fuel Type", str(rec.get("fuel_type", ""))),
                ("Transmission", str(rec.get("transmission", ""))),
            ],
        )
    ]

    json_result = {
        "id": rec["id"],
        "name": rec.get("name"),
        "driver": _m2o_name(rec.get("driver_id")),
        "state": _m2o_name(rec.get("state_id")),
        "license_plate": rec.get("license_plate"),
        "model": _m2o_name(rec.get("model_id")),
        "odometer": rec.get("odometer"),
        "acquisition_date": rec.get("acquisition_date"),
    }

    out.detail("Vehicle Detail", sections, data_for_json=json_result)


# ===================================================================
# CONTRACTS
# ===================================================================


@app.command("contracts")
def contracts(
    ctx: typer.Context,
    expiring_days: Annotated[int, typer.Option("--expiring-days", help="Show contracts expiring within N days")] = 30,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List fleet contracts, optionally filtered by expiry window.

    Examples:
        kctl-odoo fleet contracts
        kctl-odoo fleet contracts --expiring-days 60
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, "fleet.vehicle.log.contract"):
        out.warn("Fleet contract module is not installed.")
        return

    now = datetime.now(tz=UTC)
    cutoff = (now + timedelta(days=expiring_days)).strftime("%Y-%m-%d")

    domain: list = [
        ("expiration_date", "!=", False),
        ("expiration_date", "<=", cutoff),
    ]

    try:
        records = c.search_read(  # type: ignore[attr-defined]
            "fleet.vehicle.log.contract",
            domain=domain,
            fields=["name", "vehicle_id", "expiration_date", "cost_generated_frequency", "state_id", "amount"],
            limit=limit,
            order="expiration_date asc",
        )
    except RPCError as e:
        out.error(f"Failed to list contracts: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.info(f"No contracts expiring within {expiring_days} days.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for r in records:
        rows.append(
            [
                r.get("name", ""),
                _m2o_name(r.get("vehicle_id")),
                str(r.get("expiration_date", "")),
                _m2o_name(r.get("state_id")),
                str(r.get("amount", 0)),
            ]
        )
        json_data.append(
            {
                "id": r["id"],
                "name": r.get("name"),
                "vehicle": _m2o_name(r.get("vehicle_id")),
                "expiration_date": r.get("expiration_date"),
                "state": _m2o_name(r.get("state_id")),
                "amount": r.get("amount"),
            }
        )

    out.table(
        f"Contracts Expiring within {expiring_days} Days ({len(records)})",
        [("Name", "cyan"), ("Vehicle", ""), ("Expires", ""), ("State", ""), ("Amount", "dim")],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# SERVICES
# ===================================================================


@app.command("services")
def services(
    ctx: typer.Context,
    vehicle: Annotated[str | None, typer.Option("--vehicle", help="Filter by vehicle name or ID")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 50,
) -> None:
    """List fleet service logs.

    Examples:
        kctl-odoo fleet services
        kctl-odoo fleet services --vehicle "Fleet/001"
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, "fleet.vehicle.log.services"):
        out.warn("Fleet service module is not installed.")
        return

    domain: list = []
    if vehicle:
        if vehicle.isdigit():
            domain.append(("vehicle_id", "=", int(vehicle)))
        else:
            domain.append(("vehicle_id.name", "ilike", vehicle))

    try:
        records = c.search_read(  # type: ignore[attr-defined]
            "fleet.vehicle.log.services",
            domain=domain,
            fields=["name", "vehicle_id", "date", "cost", "state_id"],
            limit=limit,
            order="date desc",
        )
    except RPCError as e:
        out.error(f"Failed to list services: {e}")
        raise typer.Exit(1) from e

    if not records:
        out.info("No service records found.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for r in records:
        rows.append(
            [
                r.get("name", ""),
                _m2o_name(r.get("vehicle_id")),
                str(r.get("date", "")),
                str(r.get("cost", 0)),
                _m2o_name(r.get("state_id")),
            ]
        )
        json_data.append(
            {
                "id": r["id"],
                "name": r.get("name"),
                "vehicle": _m2o_name(r.get("vehicle_id")),
                "date": r.get("date"),
                "cost": r.get("cost"),
                "state": _m2o_name(r.get("state_id")),
            }
        )

    out.table(
        f"Fleet Services ({len(records)})",
        [("Name", "cyan"), ("Vehicle", ""), ("Date", ""), ("Cost", ""), ("State", "dim")],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# LOG ODOMETER
# ===================================================================


@app.command("log-odometer")
def log_odometer(
    ctx: typer.Context,
    vehicle: Annotated[str, typer.Argument(help="Vehicle name or numeric ID")],
    value: Annotated[float, typer.Argument(help="Odometer reading value")],
) -> None:
    """Log an odometer reading for a vehicle.

    Examples:
        kctl-odoo fleet log-odometer "Fleet/001" 45000
        kctl-odoo fleet log-odometer 5 45000
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _FLEET_MODEL):
        out.warn(_FLEET_HINT)
        return

    try:
        vehicle_id, vehicle_name = _resolve_vehicle(c, vehicle)
    except typer.BadParameter as e:
        out.error(str(e))
        raise typer.Exit(1) from e

    today = datetime.now(tz=UTC).strftime("%Y-%m-%d")

    try:
        new_id = c.create(  # type: ignore[attr-defined]
            "fleet.vehicle.odometer",
            {"vehicle_id": vehicle_id, "value": value, "date": today},
        )
    except RPCError as e:
        out.error(f"Failed to log odometer: {e}")
        raise typer.Exit(1) from e

    out.success(f"Logged odometer {value} for vehicle '{vehicle_name}' (record ID: {new_id})")

    if actx.json_mode:
        out.raw_json({"id": new_id, "vehicle_id": vehicle_id, "vehicle": vehicle_name, "value": value, "date": today})


# ===================================================================
# COSTS
# ===================================================================


@app.command("costs")
def costs(
    ctx: typer.Context,
    vehicle: Annotated[str | None, typer.Option("--vehicle", help="Filter by vehicle name or ID")] = None,
    period: Annotated[str, typer.Option("--period", help="Period: month, year, all")] = "month",
) -> None:
    """Summarize fleet costs grouped by vehicle.

    Examples:
        kctl-odoo fleet costs
        kctl-odoo fleet costs --period year
        kctl-odoo fleet costs --vehicle "Fleet/001"
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, "fleet.vehicle.cost"):
        out.warn("Fleet cost tracking is not installed.")
        return

    domain: list = []
    now = datetime.now(tz=UTC)
    if period == "month":
        start = now.replace(day=1).strftime("%Y-%m-%d")
        domain.append(("date", ">=", start))
    elif period == "year":
        start = now.replace(month=1, day=1).strftime("%Y-%m-%d")
        domain.append(("date", ">=", start))

    if vehicle:
        if vehicle.isdigit():
            domain.append(("vehicle_id", "=", int(vehicle)))
        else:
            domain.append(("vehicle_id.name", "ilike", vehicle))

    try:
        groups = c.read_group(  # type: ignore[attr-defined]
            "fleet.vehicle.cost",
            domain=domain,
            fields=["vehicle_id", "amount"],
            groupby=["vehicle_id"],
        )
    except RPCError as e:
        out.error(f"Failed to fetch costs: {e}")
        raise typer.Exit(1) from e

    if not groups:
        out.info(f"No costs found for period: {period}")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for g in groups:
        vehicle_name = _m2o_name(g.get("vehicle_id"))
        amount = g.get("amount", 0) or 0
        rows.append([vehicle_name, f"{amount:,.2f}"])
        json_data.append({"vehicle": vehicle_name, "total_cost": amount})

    out.table(
        f"Fleet Costs ({period})",
        [("Vehicle", "cyan"), ("Total Cost", "")],
        rows,
        data_for_json=json_data,
    )


# ===================================================================
# EXPIRING
# ===================================================================


@app.command("expiring")
def expiring(
    ctx: typer.Context,
    days: Annotated[int, typer.Option("--days", help="Show items expiring within N days")] = 30,
) -> None:
    """Show contracts and insurances expiring within N days.

    Examples:
        kctl-odoo fleet expiring
        kctl-odoo fleet expiring --days 60
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not model_available(c, _FLEET_MODEL):
        out.warn(_FLEET_HINT)
        return

    now = datetime.now(tz=UTC)
    cutoff = (now + timedelta(days=days)).strftime("%Y-%m-%d")
    today = now.strftime("%Y-%m-%d")

    results: list[dict] = []

    # Contracts
    if model_available(c, "fleet.vehicle.log.contract"):
        try:
            ctrs = c.search_read(  # type: ignore[attr-defined]
                "fleet.vehicle.log.contract",
                domain=[("expiration_date", ">=", today), ("expiration_date", "<=", cutoff)],
                fields=["name", "vehicle_id", "expiration_date"],
                limit=100,
                order="expiration_date asc",
            )
            for r in ctrs:
                results.append(
                    {
                        "type": "contract",
                        "name": r.get("name", ""),
                        "vehicle": _m2o_name(r.get("vehicle_id")),
                        "expiration_date": str(r.get("expiration_date", "")),
                    }
                )
        except RPCError:
            pass

    if not results:
        out.info(f"No items expiring in the next {days} days.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = [[r["type"], r["name"], r["vehicle"], r["expiration_date"]] for r in results]

    out.table(
        f"Expiring Items (next {days} days, {len(results)} found)",
        [("Type", ""), ("Name", "cyan"), ("Vehicle", ""), ("Expires", "")],
        rows,
        data_for_json=results,
    )
