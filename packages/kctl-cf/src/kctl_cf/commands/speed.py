"""Speed optimization settings commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_cf.core.callbacks import AppContext
from kctl_cf.core.utils import resolve_zone

app = typer.Typer(help="Manage speed optimization settings (minify, polish, mirage, etc.).")


_SPEED_SETTINGS = [
    "minify",
    "polish",
    "mirage",
    "rocket_loader",
    "h2_prioritization",
    "early_hints",
    "brotli",
]


@app.command()
def settings(
    ctx: typer.Context,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """Show speed-related settings for a zone."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)

    data: dict = {"zone": zone}
    kvs: list[tuple[str, str]] = [("Zone", zone)]

    for setting in _SPEED_SETTINGS:
        try:
            result = c.client.get(f"/zones/{zone_id}/settings/{setting}")
            val = result.get("value", "") if isinstance(result, dict) else str(result)
            data[setting] = val
            label = setting.replace("_", " ").title()
            if isinstance(val, dict):
                # minify returns {css, html, js}
                parts = ", ".join(f"{k}={v}" for k, v in val.items())
                kvs.append((label, parts))
            else:
                kvs.append((label, str(val)))
        except Exception:
            data[setting] = "unavailable"
            kvs.append((setting.replace("_", " ").title(), "[dim]unavailable[/dim]"))

    c.output.detail(f"Speed Settings -- {zone}", [("Speed Optimization", kvs)], data_for_json=data)


@app.command()
def minify(
    ctx: typer.Context,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
    html: Annotated[bool | None, typer.Option("--html/--no-html", help="Minify HTML")] = None,
    css: Annotated[bool | None, typer.Option("--css/--no-css", help="Minify CSS")] = None,
    js: Annotated[bool | None, typer.Option("--js/--no-js", help="Minify JS")] = None,
) -> None:
    """Show or set auto-minification settings."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)

    if html is None and css is None and js is None:
        # Show current settings
        result = c.client.get(f"/zones/{zone_id}/settings/minify")
        val = result.get("value", {}) if isinstance(result, dict) else {}
        data = {"zone": zone, "minify": val}
        kvs = [
            ("Zone", zone),
            ("HTML", str(val.get("html", ""))),
            ("CSS", str(val.get("css", ""))),
            ("JS", str(val.get("js", ""))),
        ]
        c.output.detail(f"Minify -- {zone}", [("Auto Minify", kvs)], data_for_json=data)
    else:
        # Get current, merge changes
        result = c.client.get(f"/zones/{zone_id}/settings/minify")
        current = result.get("value", {}) if isinstance(result, dict) else {}
        value = dict(current)
        if html is not None:
            value["html"] = "on" if html else "off"
        if css is not None:
            value["css"] = "on" if css else "off"
        if js is not None:
            value["js"] = "on" if js else "off"
        c.client.patch(f"/zones/{zone_id}/settings/minify", json={"value": value})
        c.output.success(f"Minify settings updated for {zone}: {value}")


@app.command()
def polish(
    ctx: typer.Context,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
    mode: Annotated[str | None, typer.Option("--mode", help="Mode: off, lossless, lossy")] = None,
) -> None:
    """Show or set Polish (image optimization) mode."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)

    if mode:
        if mode not in ("off", "lossless", "lossy"):
            c.output.error("Mode must be: off, lossless, or lossy")
            raise typer.Exit(1)
        c.client.patch(f"/zones/{zone_id}/settings/polish", json={"value": mode})
        c.output.success(f"Polish set to '{mode}' for {zone}")
    else:
        result = c.client.get(f"/zones/{zone_id}/settings/polish")
        val = result.get("value", "") if isinstance(result, dict) else str(result)
        data = {"zone": zone, "polish": val}
        c.output.detail(
            f"Polish -- {zone}",
            [("Polish", [("Zone", zone), ("Mode", str(val))])],
            data_for_json=data,
        )


def _toggle_setting(
    c: AppContext,
    zone: str,
    setting: str,
    enable: bool | None,
    label: str,
) -> None:
    """Show or toggle a simple on/off zone setting."""
    zone_id = c.client.get_zone_id(zone)

    if enable is not None:
        value = "on" if enable else "off"
        c.client.patch(f"/zones/{zone_id}/settings/{setting}", json={"value": value})
        c.output.success(f"{label} {'enabled' if enable else 'disabled'} for {zone}")
    else:
        result = c.client.get(f"/zones/{zone_id}/settings/{setting}")
        val = result.get("value", "") if isinstance(result, dict) else str(result)
        data = {"zone": zone, setting: val}
        c.output.detail(
            f"{label} -- {zone}",
            [(label, [("Zone", zone), ("Status", str(val))])],
            data_for_json=data,
        )


@app.command()
def mirage(
    ctx: typer.Context,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
    enable: Annotated[bool | None, typer.Option("--enable/--disable", help="Enable or disable Mirage")] = None,
) -> None:
    """Show or toggle Mirage (image lazy loading for mobile)."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    _toggle_setting(c, zone, "mirage", enable, "Mirage")


@app.command("rocket-loader")
def rocket_loader(
    ctx: typer.Context,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
    enable: Annotated[bool | None, typer.Option("--enable/--disable", help="Enable or disable Rocket Loader")] = None,
) -> None:
    """Show or toggle Rocket Loader (async JS loading)."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    _toggle_setting(c, zone, "rocket_loader", enable, "Rocket Loader")


@app.command("early-hints")
def early_hints(
    ctx: typer.Context,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
    enable: Annotated[bool | None, typer.Option("--enable/--disable", help="Enable or disable Early Hints")] = None,
) -> None:
    """Show or toggle Early Hints (103 responses)."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    _toggle_setting(c, zone, "early_hints", enable, "Early Hints")


@app.command()
def brotli(
    ctx: typer.Context,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
    enable: Annotated[
        bool | None, typer.Option("--enable/--disable", help="Enable or disable Brotli compression")
    ] = None,
) -> None:
    """Show or toggle Brotli compression."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    _toggle_setting(c, zone, "brotli", enable, "Brotli")
