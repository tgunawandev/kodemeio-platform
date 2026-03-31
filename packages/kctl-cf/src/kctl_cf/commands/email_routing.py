"""Email Routing management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_cf.core.callbacks import AppContext
from kctl_cf.core.utils import require_account, resolve_zone

app = typer.Typer(help="Manage Cloudflare Email Routing.")


@app.command()
def status(
    ctx: typer.Context,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """Show email routing status for a zone."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    result = c.client.get(f"/zones/{zone_id}/email/routing")
    enabled = result.get("enabled", False) if isinstance(result, dict) else False
    name = result.get("name", "") if isinstance(result, dict) else ""
    data = {"zone": zone, "enabled": enabled, "name": name}
    sections = [
        (
            "Email Routing",
            [
                ("Zone", zone),
                ("Enabled", str(enabled)),
                ("Name", name),
            ],
        )
    ]
    c.output.detail(f"Email Routing — {zone}", sections, data_for_json=data)


@app.command()
def enable(
    ctx: typer.Context,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """Enable email routing for a zone."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    c.client.put(f"/zones/{zone_id}/email/routing/enable")
    c.output.success(f"Email routing enabled for {zone}")


@app.command()
def disable(
    ctx: typer.Context,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """Disable email routing for a zone."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    c.client.put(f"/zones/{zone_id}/email/routing/disable")
    c.output.success(f"Email routing disabled for {zone}")


@app.command()
def rules(
    ctx: typer.Context,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """List email routing rules."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    result = c.client.get(f"/zones/{zone_id}/email/routing/rules")
    if not isinstance(result, list):
        result = []
    rows = []
    for r in result:
        matchers = r.get("matchers", [])
        actions = r.get("actions", [])
        match_val = matchers[0].get("value", "") if matchers else ""
        action_type = actions[0].get("type", "") if actions else ""
        action_dest = ""
        if actions:
            action_dest = ", ".join(
                actions[0].get("value", [])
                if isinstance(actions[0].get("value"), list)
                else [str(actions[0].get("value", ""))]
            )
        rows.append(
            [
                r.get("tag", "")[:12],
                r.get("name", ""),
                match_val,
                action_type,
                action_dest[:40],
                "on" if r.get("enabled") else "off",
            ]
        )
    c.output.table(
        f"Email Routing Rules — {zone}",
        [("ID", "dim"), ("Name", "cyan"), ("Match", "green"), ("Action", ""), ("Destination", ""), ("Active", "")],
        rows,
        data_for_json=result,
    )


@app.command("create-rule")
def create_rule(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", help="Rule name")],
    match: Annotated[str, typer.Option("--match", help="Email address to match")],
    action: Annotated[str, typer.Option("--action", help="Action type (forward, drop, worker)")] = "forward",
    destination: Annotated[str | None, typer.Option("--destination", help="Destination email")] = None,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """Create an email routing rule."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    payload: dict = {
        "name": name,
        "enabled": True,
        "matchers": [{"type": "literal", "field": "to", "value": match}],
        "actions": [{"type": action}],
    }
    if destination and action == "forward":
        payload["actions"] = [{"type": "forward", "value": [destination]}]
    result = c.client.post(f"/zones/{zone_id}/email/routing/rules", json=payload)
    tag = result.get("tag", "") if isinstance(result, dict) else ""
    c.output.success(f"Email routing rule created: {tag}")


@app.command("delete-rule")
def delete_rule(
    ctx: typer.Context,
    rule_id: Annotated[str, typer.Argument(help="Rule ID to delete")],
    force: Annotated[bool, typer.Option("--force", help="Required to confirm deletion")] = False,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """Delete an email routing rule. Requires --force to confirm."""
    c: AppContext = ctx.obj
    if not force:
        c.output.error("Delete blocked: pass --force to confirm deletion")
        raise typer.Exit(1)
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    c.client.delete(f"/zones/{zone_id}/email/routing/rules/{rule_id}")
    c.output.success(f"Email routing rule deleted: {rule_id}")


@app.command("catch-all")
def catch_all(
    ctx: typer.Context,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """Show catch-all rule for email routing."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    result = c.client.get(f"/zones/{zone_id}/email/routing/rules/catch_all")
    if not isinstance(result, dict):
        result = {}
    actions = result.get("actions", [])
    action_type = actions[0].get("type", "") if actions else ""
    action_dest = ""
    if actions and isinstance(actions[0].get("value"), list):
        action_dest = ", ".join(actions[0]["value"])
    elif actions:
        action_dest = str(actions[0].get("value", ""))
    data = {"zone": zone, "enabled": result.get("enabled", False), "action": action_type, "destination": action_dest}
    sections = [
        (
            "Catch-All Rule",
            [
                ("Zone", zone),
                ("Enabled", str(result.get("enabled", False))),
                ("Action", action_type),
                ("Destination", action_dest),
            ],
        )
    ]
    c.output.detail(f"Catch-All — {zone}", sections, data_for_json=data)


@app.command("set-catch-all")
def set_catch_all(
    ctx: typer.Context,
    action: Annotated[str, typer.Option("--action", help="Action type (forward, drop, worker)")] = "forward",
    destination: Annotated[str | None, typer.Option("--destination", help="Destination email")] = None,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """Set catch-all rule for email routing."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    payload: dict = {
        "enabled": True,
        "matchers": [{"type": "all"}],
        "actions": [{"type": action}],
    }
    if destination and action == "forward":
        payload["actions"] = [{"type": "forward", "value": [destination]}]
    c.client.put(f"/zones/{zone_id}/email/routing/rules/catch_all", json=payload)
    c.output.success(f"Catch-all rule updated for {zone}")


@app.command()
def addresses(ctx: typer.Context) -> None:
    """List verified destination email addresses."""
    c: AppContext = ctx.obj
    acct = require_account(c)
    result = c.client.get(f"/accounts/{acct}/email/routing/addresses")
    if not isinstance(result, list):
        result = []
    rows = []
    for a in result:
        rows.append(
            [
                a.get("email", ""),
                a.get("verified", ""),
                a.get("created", "")[:19],
                a.get("tag", "")[:12],
            ]
        )
    c.output.table(
        "Email Routing Addresses",
        [("Email", "cyan"), ("Verified", "green"), ("Created", "dim"), ("ID", "dim")],
        rows,
        data_for_json=result,
    )
