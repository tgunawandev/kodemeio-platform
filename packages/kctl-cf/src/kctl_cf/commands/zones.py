"""DNS zone management commands."""

from __future__ import annotations

import json as json_mod
from typing import Annotated

import typer

from kctl_cloudflare.core.callbacks import AppContext
from kctl_cloudflare.core.utils import resolve_zone

app = typer.Typer(help="Manage DNS zones.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all zones."""
    c: AppContext = ctx.obj
    zones = c.client.get("/zones")
    if not isinstance(zones, list):
        zones = []
    rows = []
    for z in zones:
        rows.append(
            [
                z.get("name", ""),
                z.get("status", ""),
                z.get("plan", {}).get("name", ""),
                str(len(z.get("name_servers", []))),
            ]
        )
    c.output.table(
        "Zones",
        [("Name", "cyan"), ("Status", "green"), ("Plan", ""), ("Nameservers", "dim")],
        rows,
        data_for_json=zones,
    )


@app.command()
def get(
    ctx: typer.Context,
    zone: Annotated[str, typer.Argument(help="Zone name (e.g. kodeme.io)")],
) -> None:
    """Get zone details."""
    c: AppContext = ctx.obj
    zone_id = c.client.get_zone_id(zone)
    data = c.client.get(f"/zones/{zone_id}")
    if not isinstance(data, dict):
        data = {}
    sections = [
        (
            "Zone",
            [
                ("Name", data.get("name", "")),
                ("ID", data.get("id", "")),
                ("Status", data.get("status", "")),
                ("Plan", data.get("plan", {}).get("name", "")),
                ("Nameservers", ", ".join(data.get("name_servers", []))),
            ],
        )
    ]
    c.output.detail(f"Zone: {zone}", sections, data_for_json=data)


@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Zone domain name (e.g. example.com)")],
    jump_start: Annotated[bool, typer.Option("--jump-start/--no-jump-start", help="Auto-scan DNS records")] = True,
) -> None:
    """Create a new DNS zone."""
    c: AppContext = ctx.obj
    acct = c.client.account_id
    payload: dict = {"name": name, "jump_start": jump_start}
    if acct:
        payload["account"] = {"id": acct}
    result = c.client.post("/zones", json=payload)
    zone_id = result.get("id", "") if isinstance(result, dict) else ""
    ns = result.get("name_servers", []) if isinstance(result, dict) else []
    if c.output.json_mode:
        c.output.raw_json(result if isinstance(result, dict) else {"id": zone_id})
    else:
        c.output.success(f"Zone created: {zone_id}")
        if ns:
            c.output.kv("Nameservers", ", ".join(ns))


@app.command("delete")
def delete_(
    ctx: typer.Context,
    zone: Annotated[str, typer.Argument(help="Zone name to delete")],
    force: Annotated[bool, typer.Option("--force", help="Required to confirm deletion")] = False,
) -> None:
    """Delete a DNS zone. Requires --force to confirm."""
    c: AppContext = ctx.obj
    if not force:
        c.output.error("Delete blocked: pass --force to confirm deletion")
        raise typer.Exit(1)
    zone_id = c.client.get_zone_id(zone)
    c.client.delete(f"/zones/{zone_id}")
    c.output.success(f"Zone deleted: {zone}")


@app.command()
def settings(
    ctx: typer.Context,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """List all zone settings."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    items = c.client.get(f"/zones/{zone_id}/settings")
    if not isinstance(items, list):
        items = []
    rows = []
    for s in items:
        rows.append(
            [
                s.get("id", ""),
                str(s.get("value", "")),
                "Yes" if s.get("editable") else "No",
                (s.get("modified_on") or "")[:19],
            ]
        )
    c.output.table(
        f"Zone Settings — {zone}",
        [("Setting ID", "cyan"), ("Value", ""), ("Editable", "dim"), ("Modified", "dim")],
        rows,
        data_for_json=items,
    )


@app.command("edit-setting")
def edit_setting(
    ctx: typer.Context,
    setting: Annotated[str, typer.Option("--setting", help="Setting ID to modify")],
    value: Annotated[str, typer.Option("--value", help="New value (JSON or string)")],
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """Edit a zone setting."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    try:
        parsed_value = json_mod.loads(value)
    except (json_mod.JSONDecodeError, ValueError):
        parsed_value = value
    result = c.client.patch(f"/zones/{zone_id}/settings/{setting}", json={"value": parsed_value})
    if c.output.json_mode:
        c.output.raw_json(result if isinstance(result, dict) else {})
    else:
        c.output.success(f"Setting '{setting}' updated")


@app.command("activation-check")
def activation_check(
    ctx: typer.Context,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """Trigger an activation check for a zone."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    result = c.client.put(f"/zones/{zone_id}/activation_check")
    if c.output.json_mode:
        c.output.raw_json(result if isinstance(result, dict) else {})
    else:
        c.output.success(f"Activation check initiated for {zone}")


@app.command()
def hold(
    ctx: typer.Context,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
    include_subdomains: Annotated[
        bool, typer.Option("--include-subdomains/--no-include-subdomains", help="Include subdomains in hold")
    ] = False,
) -> None:
    """Place a hold on a zone."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    result = c.client.post(f"/zones/{zone_id}/hold", json={"include_subdomains": include_subdomains})
    if c.output.json_mode:
        c.output.raw_json(result if isinstance(result, dict) else {})
    else:
        c.output.success(f"Hold placed on zone: {zone}")


@app.command("release-hold")
def release_hold(
    ctx: typer.Context,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """Release a hold on a zone."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    c.client.delete(f"/zones/{zone_id}/hold")
    c.output.success(f"Hold released for zone: {zone}")
