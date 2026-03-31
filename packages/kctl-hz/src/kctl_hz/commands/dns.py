"""DNS management commands (uses Hetzner DNS API, not Cloud API)."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_hetzner.core.callbacks import AppContext
from kctl_hetzner.core.resolve import resolve_dns_zone_id

app = typer.Typer(help="Manage Hetzner DNS zones and records.")


@app.command()
def zones(ctx: typer.Context) -> None:
    """List all DNS zones."""
    c: AppContext = ctx.obj
    data = c.dns_client.get("/zones")
    zone_list = data.get("zones", [])
    rows = []
    for z in zone_list:
        rows.append(
            [
                z.get("id", ""),
                z.get("name", ""),
                str(z.get("records_count", 0)),
            ]
        )
    c.output.table(
        "DNS Zones",
        [("ID", "dim"), ("Name", "cyan"), ("Records", "")],
        rows,
        data_for_json=zone_list,
    )


@app.command()
def records(
    ctx: typer.Context,
    zone_name: Annotated[str, typer.Argument(help="DNS zone name (e.g. example.com)")],
) -> None:
    """List DNS records for a zone."""
    c: AppContext = ctx.obj
    zone_id = resolve_dns_zone_id(c.dns_client, zone_name, c.output)
    data = c.dns_client.get("/records", params={"zone_id": zone_id})
    record_list = data.get("records", [])
    rows = []
    for r in record_list:
        rows.append(
            [
                r.get("id", ""),
                r.get("type", ""),
                r.get("name", ""),
                r.get("value", ""),
                str(r.get("ttl", "-")),
            ]
        )
    c.output.table(
        f"DNS Records: {zone_name}",
        [("ID", "dim"), ("Type", "cyan"), ("Name", ""), ("Value", "green"), ("TTL", "")],
        rows,
        data_for_json=record_list,
    )


@app.command("create-record")
def create_record(
    ctx: typer.Context,
    zone_name: Annotated[str, typer.Argument(help="DNS zone name (e.g. example.com)")],
    record_type: Annotated[str, typer.Option("--type", help="Record type (A, AAAA, CNAME, MX, TXT, etc.)")],
    name: Annotated[str, typer.Option("--name", help="Record name (e.g. www, @, mail)")],
    value: Annotated[str, typer.Option("--value", help="Record value (e.g. 1.2.3.4)")],
    ttl: Annotated[int | None, typer.Option("--ttl", help="TTL in seconds")] = 300,
) -> None:
    """Create a DNS record in a zone."""
    c: AppContext = ctx.obj
    zone_id = resolve_dns_zone_id(c.dns_client, zone_name, c.output)
    payload = {
        "zone_id": zone_id,
        "type": record_type,
        "name": name,
        "value": value,
        "ttl": ttl,
    }
    result = c.dns_client.post("/records", json=payload)
    record = result.get("record", {})
    c.output.success(
        f"DNS record created: {record.get('type', '')} {record.get('name', '')} -> {record.get('value', '')} "
        f"(ID: {record.get('id', '')})"
    )
    if c.output.json_mode:
        c.output.raw_json(result)


@app.command("update-record")
def update_record(
    ctx: typer.Context,
    record_id: Annotated[str, typer.Argument(help="DNS record ID")],
    zone_name: Annotated[str, typer.Option("--zone", help="DNS zone name (required for API)")],
    record_type: Annotated[str | None, typer.Option("--type", help="Record type (A, AAAA, CNAME, etc.)")] = None,
    name: Annotated[str | None, typer.Option("--name", help="Record name")] = None,
    value: Annotated[str | None, typer.Option("--value", help="Record value")] = None,
    ttl: Annotated[int | None, typer.Option("--ttl", help="TTL in seconds")] = None,
) -> None:
    """Update a DNS record."""
    c: AppContext = ctx.obj
    zone_id = resolve_dns_zone_id(c.dns_client, zone_name, c.output)

    # Fetch current record to merge unchanged fields
    data = c.dns_client.get(f"/records/{record_id}")
    current = data.get("record", {})
    if not current:
        c.output.error(f"DNS record {record_id} not found")
        raise typer.Exit(1)

    payload: dict = {
        "zone_id": zone_id,
        "type": record_type if record_type is not None else current.get("type", ""),
        "name": name if name is not None else current.get("name", ""),
        "value": value if value is not None else current.get("value", ""),
        "ttl": ttl if ttl is not None else current.get("ttl", 300),
    }
    result = c.dns_client.put(f"/records/{record_id}", json=payload)
    record = result.get("record", {})
    c.output.success(
        f"DNS record updated: {record.get('type', '')} {record.get('name', '')} -> {record.get('value', '')} "
        f"(ID: {record.get('id', '')})"
    )
    if c.output.json_mode:
        c.output.raw_json(result)


@app.command("delete-record")
def delete_record(
    ctx: typer.Context,
    record_id: Annotated[str, typer.Argument(help="DNS record ID")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete a DNS record."""
    c: AppContext = ctx.obj
    if not force:
        typer.confirm(f"Delete DNS record {record_id}?", abort=True)
    c.dns_client.delete(f"/records/{record_id}")
    c.output.success(f"DNS record {record_id} deleted")
