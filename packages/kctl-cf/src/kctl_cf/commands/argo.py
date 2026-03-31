"""Argo Smart Routing and Tiered Caching management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_cloudflare.core.callbacks import AppContext
from kctl_cloudflare.core.utils import resolve_zone

app = typer.Typer(help="Manage Argo Smart Routing and Tiered Caching.")


@app.command()
def status(
    ctx: typer.Context,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """Show Argo Smart Routing and Tiered Caching status."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    smart_routing = c.client.get(f"/zones/{zone_id}/argo/smart_routing")
    tiered_caching = c.client.get(f"/zones/{zone_id}/argo/tiered_caching")
    sr_value = smart_routing.get("value", "off") if isinstance(smart_routing, dict) else str(smart_routing)
    tc_value = tiered_caching.get("value", "off") if isinstance(tiered_caching, dict) else str(tiered_caching)
    sections = [
        (
            "Argo Features",
            [
                ("Smart Routing", sr_value),
                ("Tiered Caching", tc_value),
            ],
        ),
    ]
    c.output.detail(
        f"Argo Status — {zone}",
        sections,
        data_for_json={"smart_routing": sr_value, "tiered_caching": tc_value},
    )


@app.command("smart-routing")
def smart_routing(
    ctx: typer.Context,
    enable: Annotated[bool | None, typer.Option("--enable/--disable", help="Enable or disable Smart Routing")] = None,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """Get or set Argo Smart Routing."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    if enable is not None:
        value = "on" if enable else "off"
        c.client.patch(f"/zones/{zone_id}/argo/smart_routing", json={"value": value})
        c.output.success(f"Argo Smart Routing set to: {value}")
    else:
        result = c.client.get(f"/zones/{zone_id}/argo/smart_routing")
        sr_value = result.get("value", "off") if isinstance(result, dict) else str(result)
        sections = [
            (
                "Smart Routing",
                [
                    ("Status", sr_value),
                ],
            ),
        ]
        c.output.detail(f"Argo Smart Routing — {zone}", sections, data_for_json=result)


@app.command("tiered-caching")
def tiered_caching(
    ctx: typer.Context,
    enable: Annotated[bool | None, typer.Option("--enable/--disable", help="Enable or disable Tiered Caching")] = None,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """Get or set Argo Tiered Caching."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    if enable is not None:
        value = "on" if enable else "off"
        c.client.patch(f"/zones/{zone_id}/argo/tiered_caching", json={"value": value})
        c.output.success(f"Argo Tiered Caching set to: {value}")
    else:
        result = c.client.get(f"/zones/{zone_id}/argo/tiered_caching")
        tc_value = result.get("value", "off") if isinstance(result, dict) else str(result)
        sections = [
            (
                "Tiered Caching",
                [
                    ("Status", tc_value),
                ],
            ),
        ]
        c.output.detail(f"Argo Tiered Caching — {zone}", sections, data_for_json=result)
