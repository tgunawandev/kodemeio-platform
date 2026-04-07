"""DNS record management commands."""

from __future__ import annotations

import json as json_mod
import pathlib
from typing import Annotated

import typer

from kctl_cf.core.callbacks import AppContext
from kctl_cf.core.utils import resolve_zone

app = typer.Typer(help="Manage DNS records.")


@app.command("list")
def list_(
    ctx: typer.Context,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
    record_type: Annotated[str | None, typer.Option("--type", help="Record type (A, CNAME, etc.)")] = None,
) -> None:
    """List DNS records."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    params = {}
    if record_type:
        params["type"] = record_type.upper()
    records = c.client.get(f"/zones/{zone_id}/dns_records", params=params)
    if not isinstance(records, list):
        records = []
    rows = []
    for r in records:
        rows.append(
            [
                r.get("type", ""),
                r.get("name", ""),
                r.get("content", "")[:50],
                str(r.get("ttl", "")),
                "✓" if r.get("proxied") else "✗",
            ]
        )
    c.output.table(
        f"DNS Records — {zone}",
        [("Type", "cyan"), ("Name", "green"), ("Content", ""), ("TTL", "dim"), ("Proxied", "")],
        rows,
        data_for_json=records,
    )


@app.command()
def create(
    ctx: typer.Context,
    record_type: Annotated[str, typer.Option("--type", help="Record type (A, AAAA, CNAME, MX, TXT, etc.)")],
    name: Annotated[str, typer.Option("--name", help="Record name")],
    content: Annotated[str, typer.Option("--content", help="Record content")],
    ttl: Annotated[int, typer.Option("--ttl", help="TTL in seconds (1=auto)")] = 1,
    proxied: Annotated[bool, typer.Option("--proxied/--no-proxied", help="Cloudflare proxy")] = False,
    priority: Annotated[
        int | None, typer.Option("--priority", help="Record priority (required for MX records)")
    ] = None,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """Create a DNS record."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    payload: dict = {
        "type": record_type.upper(),
        "name": name,
        "content": content,
        "ttl": ttl,
        "proxied": proxied,
    }
    if priority is not None:
        payload["priority"] = priority
    result = c.client.post(f"/zones/{zone_id}/dns_records", json=payload)
    rec_id = result.get("id", "") if isinstance(result, dict) else ""
    c.output.success(f"DNS record created: {rec_id}")


@app.command("delete")
def delete_(
    ctx: typer.Context,
    record_id: Annotated[str, typer.Argument(help="DNS record ID to delete")],
    force: Annotated[bool, typer.Option("--force", help="Required to confirm deletion")] = False,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """Delete a DNS record. Requires --force to confirm."""
    c: AppContext = ctx.obj
    if not force:
        c.output.error("Delete blocked: pass --force to confirm deletion")
        raise typer.Exit(1)
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    c.client.delete(f"/zones/{zone_id}/dns_records/{record_id}")
    c.output.success(f"DNS record deleted: {record_id}")


@app.command()
def update(
    ctx: typer.Context,
    record_id: Annotated[str, typer.Argument(help="DNS record ID to update")],
    record_type: Annotated[str | None, typer.Option("--type", help="Record type (A, CNAME, etc.)")] = None,
    name: Annotated[str | None, typer.Option("--name", help="Record name")] = None,
    content: Annotated[str | None, typer.Option("--content", help="Record content")] = None,
    ttl: Annotated[int | None, typer.Option("--ttl", help="TTL in seconds (1=auto)")] = None,
    proxied: Annotated[bool | None, typer.Option("--proxied/--no-proxied", help="Cloudflare proxy")] = None,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """Update an existing DNS record."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    existing = c.client.get(f"/zones/{zone_id}/dns_records/{record_id}")
    if not isinstance(existing, dict):
        existing = {}
    payload: dict = {
        "type": record_type or existing.get("type", "A"),
        "name": name or existing.get("name", ""),
        "content": content or existing.get("content", ""),
        "ttl": ttl if ttl is not None else existing.get("ttl", 1),
    }
    if proxied is not None:
        payload["proxied"] = proxied
    elif "proxied" in existing:
        payload["proxied"] = existing["proxied"]
    c.client.put(f"/zones/{zone_id}/dns_records/{record_id}", json=payload)
    c.output.success(f"DNS record updated: {record_id}")


@app.command("bulk-create")
def bulk_create(
    ctx: typer.Context,
    file: Annotated[str, typer.Option("--file", "-f", help="JSON file with array of record objects")],
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """Bulk create DNS records from a JSON file."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    file_path = pathlib.Path(file)
    if not file_path.exists():
        c.output.error(f"File not found: {file}")
        raise typer.Exit(1)
    records_data = json_mod.loads(file_path.read_text())
    if not isinstance(records_data, list):
        c.output.error("JSON file must contain an array of record objects")
        raise typer.Exit(1)
    created = 0
    errors = 0
    for record in records_data:
        try:
            c.client.post(f"/zones/{zone_id}/dns_records", json=record)
            created += 1
        except Exception as e:
            c.output.error(f"Failed to create record {record.get('name', '?')}: {e}")
            errors += 1
    c.output.success(f"Bulk create complete: {created} created, {errors} errors")


@app.command("import")
def import_(
    ctx: typer.Context,
    file: Annotated[str, typer.Option("--file", "-f", help="BIND zone file to import")],
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """Import DNS records from a BIND zone file."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    file_path = pathlib.Path(file)
    if not file_path.exists():
        c.output.error(f"File not found: {file}")
        raise typer.Exit(1)
    file_content = file_path.read_bytes()
    resp = c.client.request(
        "POST",
        f"/zones/{zone_id}/dns_records/import",
        files={"file": (file_path.name, file_content, "application/octet-stream")},
    )
    result = resp.json() if resp.content else {}
    total = result.get("result", {}).get("total_records_parsed", 0) if isinstance(result, dict) else 0
    c.output.success(f"Import complete: {total} records parsed")


@app.command()
def get(
    ctx: typer.Context,
    record_id: Annotated[str, typer.Argument(help="DNS record ID")],
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """Get a single DNS record by ID."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    data = c.client.get(f"/zones/{zone_id}/dns_records/{record_id}")
    if not isinstance(data, dict):
        data = {}
    sections = [
        (
            "DNS Record",
            [
                ("Type", data.get("type", "")),
                ("Name", data.get("name", "")),
                ("Content", data.get("content", "")),
                ("TTL", str(data.get("ttl", ""))),
                ("Proxied", "Yes" if data.get("proxied") else "No"),
                ("Zone Name", data.get("zone_name", "")),
                ("Created", (data.get("created_on") or "")[:19]),
                ("Modified", (data.get("modified_on") or "")[:19]),
            ],
        )
    ]
    c.output.detail(f"DNS Record: {record_id}", sections, data_for_json=data)


@app.command("export")
def export_(
    ctx: typer.Context,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
    file: Annotated[str | None, typer.Option("--file", "-f", help="Output file path for BIND export")] = None,
) -> None:
    """Export DNS records in BIND format."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    resp = c.client.request("GET", f"/zones/{zone_id}/dns_records/export")
    bind_text = resp.text
    if file:
        file_path = pathlib.Path(file)
        file_path.write_text(bind_text)
        c.output.success(f"DNS records exported to {file}")
    else:
        typer.echo(bind_text)


@app.command()
def scan(
    ctx: typer.Context,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """Scan for DNS records in a zone."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    result = c.client.post(f"/zones/{zone_id}/dns_records/scan")
    if not isinstance(result, dict):
        result = {}
    recs_added = result.get("recs_added", 0)
    total_parsed = result.get("total_records_parsed", 0)
    if c.output.json_mode:
        c.output.raw_json(result)
    else:
        c.output.success(f"Scan complete: {recs_added} records added, {total_parsed} total parsed")
