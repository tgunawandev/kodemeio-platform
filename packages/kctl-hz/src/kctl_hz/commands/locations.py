"""Location listing commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_hz.core.callbacks import AppContext

app = typer.Typer(help="Browse Hetzner Cloud locations and datacenters.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all available locations."""
    c: AppContext = ctx.obj
    locations = c.client.get_all("/locations", "locations")
    rows = []
    for loc in locations:
        rows.append(
            [
                str(loc.get("id", "")),
                loc.get("name", ""),
                loc.get("description", ""),
                loc.get("city", ""),
                loc.get("country", ""),
                loc.get("network_zone", ""),
            ]
        )
    c.output.table(
        "Locations",
        [
            ("ID", "dim"),
            ("Name", "cyan"),
            ("Description", ""),
            ("City", ""),
            ("Country", ""),
            ("Network Zone", ""),
        ],
        rows,
        data_for_json=locations,
    )


@app.command()
def get(
    ctx: typer.Context,
    location_id: Annotated[int, typer.Argument(help="Location ID")],
) -> None:
    """Get details of a location."""
    c: AppContext = ctx.obj
    data = c.client.get(f"/locations/{location_id}")
    loc = data.get("location", {})
    if not loc:
        c.output.error(f"Location {location_id} not found")
        raise typer.Exit(1)

    sections = [
        (
            "Location",
            [
                ("ID", str(loc.get("id", ""))),
                ("Name", loc.get("name", "")),
                ("Description", loc.get("description", "")),
                ("City", loc.get("city", "")),
                ("Country", loc.get("country", "")),
                ("Latitude", str(loc.get("latitude", ""))),
                ("Longitude", str(loc.get("longitude", ""))),
                ("Network Zone", loc.get("network_zone", "")),
            ],
        )
    ]
    c.output.detail(f"Location: {loc.get('name', location_id)}", sections, data_for_json=loc)


@app.command("datacenters")
def list_datacenters(ctx: typer.Context) -> None:
    """List all available datacenters."""
    c: AppContext = ctx.obj
    datacenters = c.client.get_all("/datacenters", "datacenters")
    rows = []
    for dc in datacenters:
        location = dc.get("location", {})
        rows.append(
            [
                str(dc.get("id", "")),
                dc.get("name", ""),
                dc.get("description", ""),
                location.get("name", "-"),
                location.get("city", "-"),
            ]
        )
    c.output.table(
        "Datacenters",
        [
            ("ID", "dim"),
            ("Name", "cyan"),
            ("Description", ""),
            ("Location", ""),
            ("City", ""),
        ],
        rows,
        data_for_json=datacenters,
    )
