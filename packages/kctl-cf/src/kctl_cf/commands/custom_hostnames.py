"""Custom Hostnames (Cloudflare for SaaS) management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_cf.core.callbacks import AppContext
from kctl_cf.core.utils import resolve_zone

app = typer.Typer(help="Manage Custom Hostnames (Cloudflare for SaaS).")


@app.command("list")
def list_(
    ctx: typer.Context,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
    hostname: Annotated[str | None, typer.Option("--hostname", help="Filter by hostname")] = None,
) -> None:
    """List custom hostnames."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    params: dict = {}
    if hostname:
        params["hostname"] = hostname
    result = c.client.get(f"/zones/{zone_id}/custom_hostnames", params=params)
    if not isinstance(result, list):
        result = []
    rows = []
    for h in result:
        ssl = h.get("ssl", {}) or {}
        rows.append(
            [
                h.get("id", ""),
                h.get("hostname", ""),
                h.get("status", ""),
                ssl.get("status", ""),
                (h.get("created_at") or "")[:19],
            ]
        )
    c.output.table(
        f"Custom Hostnames — {zone}",
        [("ID", "dim"), ("Hostname", "cyan"), ("Status", "green"), ("SSL Status", ""), ("Created", "dim")],
        rows,
        data_for_json=result,
    )


@app.command()
def get(
    ctx: typer.Context,
    hostname_id: Annotated[str, typer.Argument(help="Custom hostname ID")],
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """Get details for a custom hostname."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    result = c.client.get(f"/zones/{zone_id}/custom_hostnames/{hostname_id}")
    if not isinstance(result, dict):
        result = {}
    ssl = result.get("ssl", {}) or {}
    sections = [
        (
            "Custom Hostname",
            [
                ("ID", result.get("id", "")),
                ("Hostname", result.get("hostname", "")),
                ("Status", result.get("status", "")),
                ("Custom Origin Server", result.get("custom_origin_server", "")),
                ("Custom Origin SNI", result.get("custom_origin_sni", "")),
                ("Created", result.get("created_at", "")[:19]),
                ("Updated", (result.get("updated_at") or "")[:19]),
            ],
        ),
        (
            "SSL",
            [
                ("SSL Status", ssl.get("status", "")),
                ("SSL Method", ssl.get("method", "")),
                ("SSL Type", ssl.get("type", "")),
                ("Certificate Authority", ssl.get("certificate_authority", "")),
            ],
        ),
    ]
    c.output.detail(f"Custom Hostname — {result.get('hostname', hostname_id)}", sections, data_for_json=result)


@app.command()
def create(
    ctx: typer.Context,
    hostname: Annotated[str, typer.Option("--hostname", help="Custom hostname")],
    ssl_method: Annotated[str, typer.Option("--ssl-method", help="SSL validation method (http, txt, email)")] = "http",
    ssl_type: Annotated[str, typer.Option("--ssl-type", help="SSL certificate type")] = "dv",
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """Create a custom hostname."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    payload: dict = {
        "hostname": hostname,
        "ssl": {
            "method": ssl_method,
            "type": ssl_type,
        },
    }
    result = c.client.post(f"/zones/{zone_id}/custom_hostnames", json=payload)
    ch_id = result.get("id", "") if isinstance(result, dict) else ""
    c.output.success(f"Custom hostname created: {ch_id}")


@app.command()
def update(
    ctx: typer.Context,
    hostname_id: Annotated[str, typer.Argument(help="Custom hostname ID to update")],
    ssl_method: Annotated[str | None, typer.Option("--ssl-method", help="SSL validation method")] = None,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """Update a custom hostname."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    payload: dict = {}
    if ssl_method:
        payload["ssl"] = {"method": ssl_method}
    c.client.patch(f"/zones/{zone_id}/custom_hostnames/{hostname_id}", json=payload)
    c.output.success(f"Custom hostname updated: {hostname_id}")


@app.command("delete")
def delete_(
    ctx: typer.Context,
    hostname_id: Annotated[str, typer.Argument(help="Custom hostname ID to delete")],
    force: Annotated[bool, typer.Option("--force", help="Required to confirm deletion")] = False,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """Delete a custom hostname. Requires --force to confirm."""
    c: AppContext = ctx.obj
    if not force:
        c.output.error("Delete blocked: pass --force to confirm deletion")
        raise typer.Exit(1)
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    c.client.delete(f"/zones/{zone_id}/custom_hostnames/{hostname_id}")
    c.output.success(f"Custom hostname deleted: {hostname_id}")
