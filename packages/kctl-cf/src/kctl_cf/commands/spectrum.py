"""Spectrum application management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_cloudflare.core.callbacks import AppContext
from kctl_cloudflare.core.utils import resolve_zone

app = typer.Typer(help="Manage Spectrum applications.")


@app.command("list")
def list_(
    ctx: typer.Context,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """List Spectrum applications."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    result = c.client.get(f"/zones/{zone_id}/spectrum/apps")
    if not isinstance(result, list):
        result = []
    rows = []
    for a in result:
        dns = a.get("dns", {}) or {}
        origin_direct = a.get("origin_direct", []) or []
        rows.append(
            [
                a.get("id", "")[:12],
                a.get("protocol", ""),
                dns.get("name", ""),
                ", ".join(origin_direct)[:40],
                "Yes" if a.get("ip_firewall") else "No",
                a.get("proxy_protocol", "off"),
                (a.get("created_on") or "")[:19],
            ]
        )
    c.output.table(
        f"Spectrum Apps — {zone}",
        [
            ("ID", "dim"),
            ("Protocol", "cyan"),
            ("DNS Name", "green"),
            ("Origin Direct", ""),
            ("IP Firewall", ""),
            ("Proxy Protocol", "dim"),
            ("Created", "dim"),
        ],
        rows,
        data_for_json=result,
    )


@app.command()
def get(
    ctx: typer.Context,
    app_id: Annotated[str, typer.Argument(help="Spectrum application ID")],
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """Get Spectrum application details."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    result = c.client.get(f"/zones/{zone_id}/spectrum/apps/{app_id}")
    if not isinstance(result, dict):
        result = {}
    dns = result.get("dns", {}) or {}
    origin_direct = result.get("origin_direct", []) or []
    sections = [
        (
            "Spectrum Application",
            [
                ("ID", result.get("id", "")),
                ("Protocol", result.get("protocol", "")),
                ("IP Firewall", str(result.get("ip_firewall", False))),
                ("Proxy Protocol", result.get("proxy_protocol", "off")),
                ("TLS", result.get("tls", "")),
            ],
        ),
        (
            "DNS",
            [
                ("DNS Name", dns.get("name", "")),
                ("DNS Type", dns.get("type", "")),
            ],
        ),
        (
            "Origin",
            [
                ("Origin Direct", ", ".join(origin_direct)),
            ],
        ),
        (
            "Timestamps",
            [
                ("Created", (result.get("created_on") or "")[:19]),
                ("Modified", (result.get("modified_on") or "")[:19]),
            ],
        ),
    ]
    c.output.detail(f"Spectrum App — {dns.get('name', app_id)}", sections, data_for_json=result)


@app.command()
def create(
    ctx: typer.Context,
    protocol: Annotated[str, typer.Option("--protocol", help="Protocol and port (e.g. tcp/22, udp/53)")],
    dns_name: Annotated[str, typer.Option("--dns-name", help="DNS name for the application")],
    origin_direct: Annotated[str, typer.Option("--origin-direct", help="Origin address (ip:port)")],
    dns_type: Annotated[str, typer.Option("--dns-type", help="DNS record type (CNAME or ADDRESS)")] = "CNAME",
    proxy_protocol: Annotated[
        str, typer.Option("--proxy-protocol", help="Proxy protocol (off, v1, v2, simple)")
    ] = "off",
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """Create a Spectrum application."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    payload: dict = {
        "protocol": protocol,
        "dns": {
            "type": dns_type,
            "name": dns_name,
        },
        "origin_direct": [origin_direct],
        "proxy_protocol": proxy_protocol,
    }
    result = c.client.post(f"/zones/{zone_id}/spectrum/apps", json=payload)
    sa_id = result.get("id", "") if isinstance(result, dict) else ""
    c.output.success(f"Spectrum app created: {sa_id}")


@app.command()
def update(
    ctx: typer.Context,
    app_id: Annotated[str, typer.Argument(help="Spectrum application ID to update")],
    protocol: Annotated[str | None, typer.Option("--protocol", help="Protocol and port (e.g. tcp/22)")] = None,
    origin_direct: Annotated[str | None, typer.Option("--origin-direct", help="Origin address (ip:port)")] = None,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """Update a Spectrum application (merges with existing settings)."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    existing = c.client.get(f"/zones/{zone_id}/spectrum/apps/{app_id}")
    if not isinstance(existing, dict):
        existing = {}
    payload: dict = {
        "protocol": protocol or existing.get("protocol", ""),
        "dns": existing.get("dns", {}),
        "origin_direct": [origin_direct] if origin_direct else existing.get("origin_direct", []),
        "proxy_protocol": existing.get("proxy_protocol", "off"),
    }
    c.client.put(f"/zones/{zone_id}/spectrum/apps/{app_id}", json=payload)
    c.output.success(f"Spectrum app updated: {app_id}")


@app.command("delete")
def delete_(
    ctx: typer.Context,
    app_id: Annotated[str, typer.Argument(help="Spectrum application ID to delete")],
    force: Annotated[bool, typer.Option("--force", help="Required to confirm deletion")] = False,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """Delete a Spectrum application. Requires --force to confirm."""
    c: AppContext = ctx.obj
    if not force:
        c.output.error("Delete blocked: pass --force to confirm deletion")
        raise typer.Exit(1)
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    c.client.delete(f"/zones/{zone_id}/spectrum/apps/{app_id}")
    c.output.success(f"Spectrum app deleted: {app_id}")
