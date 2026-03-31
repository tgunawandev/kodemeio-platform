"""Placement group management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_hz.core.callbacks import AppContext
from kctl_hz.core.utils import parse_labels

app = typer.Typer(help="Manage Hetzner Cloud placement groups.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all placement groups."""
    c: AppContext = ctx.obj
    groups = c.client.get_all("/placement_groups", "placement_groups")
    rows = []
    for pg in groups:
        servers = pg.get("servers", [])
        rows.append(
            [
                str(pg.get("id", "")),
                pg.get("name", ""),
                pg.get("type", ""),
                str(len(servers)),
                pg.get("created", ""),
            ]
        )
    c.output.table(
        "Placement Groups",
        [("ID", "dim"), ("Name", "cyan"), ("Type", ""), ("Servers", ""), ("Created", "dim")],
        rows,
        data_for_json=groups,
    )


@app.command()
def get(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Placement group name")],
) -> None:
    """Get placement group details."""
    c: AppContext = ctx.obj
    data = c.client.get("/placement_groups", params={"name": name})
    items = data.get("placement_groups", [])
    if not items:
        c.output.error(f"Placement group '{name}' not found")
        raise typer.Exit(1)
    pg = items[0]
    servers = pg.get("servers", [])

    sections = [
        (
            "Placement Group",
            [
                ("Name", pg.get("name", "")),
                ("ID", str(pg.get("id", ""))),
                ("Type", pg.get("type", "")),
                ("Created", pg.get("created", "")),
                ("Servers", str(len(servers))),
            ],
        )
    ]

    # Show server IDs if any
    if servers:
        server_kvs = [("Server ID", str(sid)) for sid in servers]
        sections.append(("Assigned Servers", server_kvs))

    # Show labels
    labels = pg.get("labels", {})
    if labels:
        label_kvs = [(k, v) for k, v in labels.items()]
        sections.append(("Labels", label_kvs))

    c.output.detail(f"Placement Group: {name}", sections, data_for_json=pg)


@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Placement group name")],
    pg_type: Annotated[str, typer.Option("--type", help="Placement type (spread)")] = "spread",
) -> None:
    """Create a new placement group."""
    c: AppContext = ctx.obj
    payload = {"name": name, "type": pg_type}
    result = c.client.post("/placement_groups", json=payload)
    pg = result.get("placement_group", {})
    c.output.success(f"Placement group '{pg.get('name', name)}' created (ID: {pg.get('id')})")
    if c.output.json_mode:
        c.output.raw_json(result)


@app.command()
def update(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Placement group name")],
    new_name: Annotated[str | None, typer.Option("--name", help="New name")] = None,
    labels: Annotated[str | None, typer.Option("--labels", help="Labels as key=val,key=val")] = None,
) -> None:
    """Update a placement group (name, labels)."""
    c: AppContext = ctx.obj
    data = c.client.get("/placement_groups", params={"name": name})
    items = data.get("placement_groups", [])
    if not items:
        c.output.error(f"Placement group '{name}' not found")
        raise typer.Exit(1)
    pg_id = items[0]["id"]

    payload: dict = {}
    if new_name is not None:
        payload["name"] = new_name
    if labels is not None:
        payload["labels"] = parse_labels(labels)
    if not payload:
        c.output.error("Provide at least one option to update (--name, --labels)")
        raise typer.Exit(1)
    result = c.client.put(f"/placement_groups/{pg_id}", json=payload)
    c.output.success(f"Placement group '{name}' updated")
    if c.output.json_mode:
        c.output.raw_json(result)


@app.command()
def delete(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Placement group name")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete a placement group."""
    c: AppContext = ctx.obj
    data = c.client.get("/placement_groups", params={"name": name})
    items = data.get("placement_groups", [])
    if not items:
        c.output.error(f"Placement group '{name}' not found")
        raise typer.Exit(1)
    pg = items[0]
    pg_id = pg["id"]
    servers = pg.get("servers", [])
    if servers and not force:
        c.output.warn(f"Placement group '{name}' has {len(servers)} server(s) assigned")
    if not force:
        typer.confirm(f"Delete placement group '{name}' (ID: {pg_id})?", abort=True)
    c.client.delete(f"/placement_groups/{pg_id}")
    c.output.success(f"Placement group '{name}' deleted")
