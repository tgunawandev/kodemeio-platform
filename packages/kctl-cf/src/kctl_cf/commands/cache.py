"""Cache management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_cf.core.callbacks import AppContext
from kctl_cf.core.utils import resolve_zone

app = typer.Typer(help="Manage cache settings and purge.")


@app.command()
def status(
    ctx: typer.Context,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """Show cache settings for a zone."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    cache_level = c.client.get(f"/zones/{zone_id}/settings/cache_level")
    browser_ttl = c.client.get(f"/zones/{zone_id}/settings/browser_cache_ttl")

    cache_val = cache_level.get("value", "") if isinstance(cache_level, dict) else str(cache_level)
    ttl_val = browser_ttl.get("value", "") if isinstance(browser_ttl, dict) else str(browser_ttl)

    data = {"zone": zone, "cache_level": cache_val, "browser_cache_ttl": ttl_val}
    sections = [
        (
            "Cache Settings",
            [
                ("Zone", zone),
                ("Cache Level", str(cache_val)),
                ("Browser Cache TTL", str(ttl_val)),
            ],
        )
    ]
    c.output.detail(f"Cache — {zone}", sections, data_for_json=data)


@app.command("purge-all")
def purge_all(
    ctx: typer.Context,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
    confirm: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation")] = False,
) -> None:
    """Purge all cached content for a zone."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    if not confirm:
        typer.confirm(f"Purge ALL cache for zone '{zone}'?", abort=True)
    zone_id = c.client.get_zone_id(zone)
    result = c.client.post(f"/zones/{zone_id}/purge_cache", json={"purge_everything": True})
    data = result if isinstance(result, dict) else {"success": True}
    c.output.success(f"Cache purged for {zone}")
    if c.output.json_mode:
        c.output.raw_json(data)


@app.command()
def purge(
    ctx: typer.Context,
    urls: Annotated[list[str], typer.Argument(help="URLs to purge")],
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """Purge specific URLs from the cache."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    result = c.client.post(f"/zones/{zone_id}/purge_cache", json={"files": urls})
    data = result if isinstance(result, dict) else {"success": True, "files": urls}
    c.output.success(f"Purged {len(urls)} URL(s) from {zone}")
    if c.output.json_mode:
        c.output.raw_json(data)
