"""Client and site management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_rmm.core.callbacks import AppContext

app = typer.Typer(help="Manage clients and sites.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all clients."""
    c: AppContext = ctx.obj
    data = c.client.get("/clients/")

    clients = data if isinstance(data, list) else data.get("results", []) if isinstance(data, dict) else []

    rows: list[list[str]] = []
    for cl in clients:
        sites = cl.get("sites", [])
        site_names = ", ".join(s.get("name", "") for s in sites) if sites else "-"
        rows.append(
            [
                str(cl.get("id", "")),
                cl.get("name", ""),
                str(len(sites)),
                site_names[:80],
            ]
        )

    c.output.table(
        f"Clients ({len(clients)})",
        [("ID", "cyan"), ("Name", ""), ("Sites", ""), ("Site Names", "dim")],
        rows,
        data_for_json=clients,
    )


@app.command()
def get(
    ctx: typer.Context,
    client_id: Annotated[int, typer.Argument(help="Client ID")],
) -> None:
    """Get client details with sites."""
    c: AppContext = ctx.obj
    client = c.client.get(f"/clients/{client_id}/")

    if not isinstance(client, dict):
        c.output.error("Unexpected response format")
        raise typer.Exit(1)

    sections: list[tuple[str, list[tuple[str, str]]]] = [
        (
            "Client Info",
            [
                ("ID", str(client.get("id", ""))),
                ("Name", client.get("name", "")),
            ],
        ),
    ]

    sites = client.get("sites", [])
    if sites:
        site_kvs = [(str(s.get("id", "")), s.get("name", "")) for s in sites]
        sections.append(("Sites", site_kvs))

    c.output.detail(f"Client: {client.get('name', client_id)}", sections, data_for_json=client)


@app.command()
def sites(
    ctx: typer.Context,
    client_filter: Annotated[str | None, typer.Option("--client", help="Filter by client name")] = None,
) -> None:
    """List all sites."""
    c: AppContext = ctx.obj
    data = c.client.get("/clients/")

    clients = data if isinstance(data, list) else data.get("results", []) if isinstance(data, dict) else []

    if client_filter:
        clients = [cl for cl in clients if client_filter.lower() in cl.get("name", "").lower()]

    rows: list[list[str]] = []
    all_sites: list[dict] = []
    for cl in clients:
        for site in cl.get("sites", []):
            rows.append(
                [
                    str(site.get("id", "")),
                    site.get("name", ""),
                    cl.get("name", ""),
                ]
            )
            all_sites.append({**site, "client_name": cl.get("name", "")})

    c.output.table(
        f"Sites ({len(rows)})",
        [("ID", "cyan"), ("Site", ""), ("Client", "")],
        rows,
        data_for_json=all_sites,
    )
