"""Export Cloudflare configuration as JSON."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_cloudflare.core.callbacks import AppContext
from kctl_cloudflare.core.utils import resolve_zone

app = typer.Typer(help="Export Cloudflare configuration.")


@app.command("all")
def all_(
    ctx: typer.Context,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """Export all zone configuration (zones, records, settings) as JSON."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)

    # Fetch zone details
    zone_data = c.client.get(f"/zones/{zone_id}")
    if not isinstance(zone_data, dict):
        zone_data = {}

    # Fetch DNS records
    records = c.client.get(f"/zones/{zone_id}/dns_records")
    if not isinstance(records, list):
        records = []

    # Fetch key settings
    settings: dict = {}
    for setting_name in ("ssl", "cache_level", "browser_cache_ttl", "security_level", "min_tls_version"):
        try:
            result = c.client.get(f"/zones/{zone_id}/settings/{setting_name}")
            if isinstance(result, dict):
                settings[setting_name] = result.get("value", "")
            else:
                settings[setting_name] = result
        except Exception:
            settings[setting_name] = None

    export_data = {
        "zone": zone_data,
        "dns_records": records,
        "settings": settings,
    }

    c.output.raw_json(export_data)
