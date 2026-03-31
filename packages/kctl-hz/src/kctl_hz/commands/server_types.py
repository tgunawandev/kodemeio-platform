"""Server type listing commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_hz.core.callbacks import AppContext

app = typer.Typer(help="Browse Hetzner Cloud server types.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all available server types."""
    c: AppContext = ctx.obj
    server_types = c.client.get_all("/server_types", "server_types")
    rows = []
    for st in server_types:
        # Extract cheapest hourly price if available
        prices = st.get("prices", [])
        price_str = "-"
        if prices:
            hourly = prices[0].get("price_hourly", {}).get("gross", "")
            if hourly:
                price_str = f"{hourly}/h"

        rows.append(
            [
                str(st.get("id", "")),
                st.get("name", ""),
                st.get("description", ""),
                str(st.get("cores", "")),
                f"{st.get('memory', '')} GB",
                f"{st.get('disk', '')} GB",
                st.get("storage_type", ""),
                st.get("architecture", ""),
                price_str,
            ]
        )
    c.output.table(
        "Server Types",
        [
            ("ID", "dim"),
            ("Name", "cyan"),
            ("Description", ""),
            ("Cores", ""),
            ("Memory", ""),
            ("Disk", ""),
            ("Storage", ""),
            ("Arch", ""),
            ("Price", "green"),
        ],
        rows,
        data_for_json=server_types,
    )


@app.command()
def get(
    ctx: typer.Context,
    type_id: Annotated[int, typer.Argument(help="Server type ID")],
) -> None:
    """Get details of a server type."""
    c: AppContext = ctx.obj
    data = c.client.get(f"/server_types/{type_id}")
    st = data.get("server_type", {})
    if not st:
        c.output.error(f"Server type {type_id} not found")
        raise typer.Exit(1)

    prices = st.get("prices", [])
    price_kvs = []
    for p in prices:
        location = p.get("location", "?")
        hourly = p.get("price_hourly", {}).get("gross", "-")
        monthly = p.get("price_monthly", {}).get("gross", "-")
        price_kvs.append((location, f"{hourly}/h, {monthly}/mo"))

    sections = [
        (
            "Server Type",
            [
                ("ID", str(st.get("id", ""))),
                ("Name", st.get("name", "")),
                ("Description", st.get("description", "")),
                ("Cores", str(st.get("cores", ""))),
                ("Memory", f"{st.get('memory', '')} GB"),
                ("Disk", f"{st.get('disk', '')} GB"),
                ("Storage Type", st.get("storage_type", "")),
                ("CPU Type", st.get("cpu_type", "")),
                ("Architecture", st.get("architecture", "")),
                ("Deprecation", str(st.get("deprecation")) if st.get("deprecation") else "-"),
            ],
        )
    ]
    if price_kvs:
        sections.append(("Prices (gross)", price_kvs))

    c.output.detail(f"Server Type: {st.get('name', type_id)}", sections, data_for_json=st)
