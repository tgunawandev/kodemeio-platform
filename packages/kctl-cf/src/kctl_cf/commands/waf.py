"""WAF and firewall rule management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_cf.core.callbacks import AppContext
from kctl_cf.core.utils import resolve_zone

app = typer.Typer(help="Manage WAF and firewall rules.")


@app.command("list")
def list_(
    ctx: typer.Context,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """List firewall rules."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    rules = c.client.get(f"/zones/{zone_id}/firewall/rules")
    if not isinstance(rules, list):
        rules = []
    rows = []
    for r in rules:
        filt = r.get("filter", {})
        rows.append(
            [
                r.get("id", "")[:12],
                r.get("action", ""),
                filt.get("expression", "")[:60],
                str(r.get("priority", "")),
                "on" if not r.get("paused") else "off",
            ]
        )
    c.output.table(
        f"Firewall Rules — {zone}",
        [("ID", "dim"), ("Action", "cyan"), ("Expression", ""), ("Priority", "dim"), ("Active", "green")],
        rows,
        data_for_json=rules,
    )


@app.command()
def create(
    ctx: typer.Context,
    expression: Annotated[str, typer.Option("--expression", help="Firewall rule expression")],
    action: Annotated[str, typer.Option("--action", help="Action (block, challenge, js_challenge, allow)")] = "block",
    description: Annotated[str | None, typer.Option("--description", help="Rule description")] = None,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """Create a firewall rule."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    # Create filter first
    filter_payload = {"expression": expression}
    if description:
        filter_payload["description"] = description
    filters = c.client.post(f"/zones/{zone_id}/filters", json=[filter_payload])
    filter_id = filters[0].get("id", "") if isinstance(filters, list) and filters else ""
    if not filter_id:
        c.output.error("Failed to create filter")
        raise typer.Exit(1)
    rule_payload = [{"filter": {"id": filter_id}, "action": action}]
    if description:
        rule_payload[0]["description"] = description
    result = c.client.post(f"/zones/{zone_id}/firewall/rules", json=rule_payload)
    rule_id = result[0].get("id", "") if isinstance(result, list) and result else ""
    c.output.success(f"Firewall rule created: {rule_id}")


@app.command()
def update(
    ctx: typer.Context,
    rule_id: Annotated[str, typer.Argument(help="Firewall rule ID")],
    expression: Annotated[str | None, typer.Option("--expression", help="New expression")] = None,
    action: Annotated[str | None, typer.Option("--action", help="New action")] = None,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """Update a firewall rule."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    existing = c.client.get(f"/zones/{zone_id}/firewall/rules/{rule_id}")
    if not isinstance(existing, dict):
        existing = {}
    payload: dict = {
        "id": rule_id,
        "action": action or existing.get("action", "block"),
        "filter": dict(existing.get("filter", {})),
    }
    if expression:
        payload["filter"]["expression"] = expression
    c.client.put(f"/zones/{zone_id}/firewall/rules/{rule_id}", json=payload)
    c.output.success(f"Firewall rule updated: {rule_id}")


@app.command("delete")
def delete_(
    ctx: typer.Context,
    rule_id: Annotated[str, typer.Argument(help="Firewall rule ID to delete")],
    force: Annotated[bool, typer.Option("--force", help="Required to confirm deletion")] = False,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """Delete a firewall rule. Requires --force to confirm."""
    c: AppContext = ctx.obj
    if not force:
        c.output.error("Delete blocked: pass --force to confirm deletion")
        raise typer.Exit(1)
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    c.client.delete(f"/zones/{zone_id}/firewall/rules/{rule_id}")
    c.output.success(f"Firewall rule deleted: {rule_id}")


@app.command("ip-rules")
def ip_rules(
    ctx: typer.Context,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """List IP access rules."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    rules = c.client.get(f"/zones/{zone_id}/firewall/access_rules/rules")
    if not isinstance(rules, list):
        rules = []
    rows = []
    for r in rules:
        cfg = r.get("configuration", {})
        rows.append(
            [
                r.get("mode", ""),
                cfg.get("target", ""),
                cfg.get("value", ""),
                r.get("notes", "")[:40],
                r.get("created_on", "")[:10],
            ]
        )
    c.output.table(
        f"IP Access Rules — {zone}",
        [("Mode", "cyan"), ("Target", ""), ("Value", "green"), ("Notes", "dim"), ("Created", "dim")],
        rows,
        data_for_json=rules,
    )


@app.command("create-ip-rule")
def create_ip_rule(
    ctx: typer.Context,
    mode: Annotated[str, typer.Option("--mode", help="Rule mode (block, challenge, whitelist, js_challenge)")],
    value: Annotated[str, typer.Option("--value", help="Target value (IP, CIDR, ASN, country code)")],
    target: Annotated[str, typer.Option("--target", help="Target type (ip, ip_range, asn, country)")] = "ip",
    notes: Annotated[str, typer.Option("--notes", help="Rule notes")] = "",
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """Create an IP access rule."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    payload: dict = {
        "mode": mode,
        "configuration": {"target": target, "value": value},
    }
    if notes:
        payload["notes"] = notes
    result = c.client.post(f"/zones/{zone_id}/firewall/access_rules/rules", json=payload)
    rule_id = result.get("id", "") if isinstance(result, dict) else ""
    c.output.success(f"IP access rule created: {rule_id}")


@app.command("update-ip-rule")
def update_ip_rule(
    ctx: typer.Context,
    rule_id: Annotated[str, typer.Argument(help="IP access rule ID")],
    mode: Annotated[str | None, typer.Option("--mode", help="New mode")] = None,
    notes: Annotated[str | None, typer.Option("--notes", help="New notes")] = None,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """Update an IP access rule."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    payload: dict = {}
    if mode:
        payload["mode"] = mode
    if notes is not None:
        payload["notes"] = notes
    c.client.patch(f"/zones/{zone_id}/firewall/access_rules/rules/{rule_id}", json=payload)
    c.output.success(f"IP access rule updated: {rule_id}")


@app.command("delete-ip-rule")
def delete_ip_rule(
    ctx: typer.Context,
    rule_id: Annotated[str, typer.Argument(help="IP access rule ID to delete")],
    force: Annotated[bool, typer.Option("--force", help="Required to confirm deletion")] = False,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """Delete an IP access rule. Requires --force to confirm."""
    c: AppContext = ctx.obj
    if not force:
        c.output.error("Delete blocked: pass --force to confirm deletion")
        raise typer.Exit(1)
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    c.client.delete(f"/zones/{zone_id}/firewall/access_rules/rules/{rule_id}")
    c.output.success(f"IP access rule deleted: {rule_id}")


@app.command("rate-limits")
def rate_limits(
    ctx: typer.Context,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """List rate limiting rules."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    rules = c.client.get(f"/zones/{zone_id}/rate_limits")
    if not isinstance(rules, list):
        rules = []
    rows = []
    for r in rules:
        match = r.get("match", {})
        req = match.get("request", {})
        action = r.get("action", {})
        rows.append(
            [
                r.get("id", "")[:12],
                req.get("url", "*"),
                str(r.get("threshold", "")),
                str(r.get("period", "")),
                action.get("mode", ""),
                "on" if not r.get("disabled") else "off",
            ]
        )
    c.output.table(
        f"Rate Limits — {zone}",
        [
            ("ID", "dim"),
            ("URL", "cyan"),
            ("Threshold", ""),
            ("Period", "dim"),
            ("Action", "green"),
            ("Active", ""),
        ],
        rows,
        data_for_json=rules,
    )


@app.command("create-rate-limit")
def create_rate_limit(
    ctx: typer.Context,
    url: Annotated[str, typer.Option("--url", help="URL pattern to match")] = "*",
    threshold: Annotated[int, typer.Option("--threshold", help="Request threshold")] = 100,
    period: Annotated[int, typer.Option("--period", help="Period in seconds")] = 60,
    action_mode: Annotated[
        str, typer.Option("--action", help="Action (simulate, ban, challenge, js_challenge)")
    ] = "ban",
    timeout: Annotated[int, typer.Option("--timeout", help="Action timeout in seconds")] = 3600,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """Create a rate limiting rule."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    payload = {
        "match": {"request": {"url": url}},
        "threshold": threshold,
        "period": period,
        "action": {"mode": action_mode},
    }
    if action_mode == "ban":
        payload["action"]["timeout"] = timeout
    result = c.client.post(f"/zones/{zone_id}/rate_limits", json=payload)
    rl_id = result.get("id", "") if isinstance(result, dict) else ""
    c.output.success(f"Rate limit created: {rl_id}")


@app.command("update-rate-limit")
def update_rate_limit(
    ctx: typer.Context,
    rule_id: Annotated[str, typer.Argument(help="Rate limit rule ID")],
    threshold: Annotated[int | None, typer.Option("--threshold", help="New threshold")] = None,
    period: Annotated[int | None, typer.Option("--period", help="New period")] = None,
    disabled: Annotated[bool | None, typer.Option("--disabled/--enabled", help="Disable or enable")] = None,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """Update a rate limiting rule."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    existing = c.client.get(f"/zones/{zone_id}/rate_limits/{rule_id}")
    if not isinstance(existing, dict):
        existing = {}
    _writable = {"match", "threshold", "period", "action", "disabled", "description", "bypass", "correlate"}
    payload = {k: v for k, v in existing.items() if k in _writable}
    if threshold is not None:
        payload["threshold"] = threshold
    if period is not None:
        payload["period"] = period
    if disabled is not None:
        payload["disabled"] = disabled
    c.client.put(f"/zones/{zone_id}/rate_limits/{rule_id}", json=payload)
    c.output.success(f"Rate limit updated: {rule_id}")


@app.command("delete-rate-limit")
def delete_rate_limit(
    ctx: typer.Context,
    rule_id: Annotated[str, typer.Argument(help="Rate limit rule ID to delete")],
    force: Annotated[bool, typer.Option("--force", help="Required to confirm deletion")] = False,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """Delete a rate limiting rule. Requires --force to confirm."""
    c: AppContext = ctx.obj
    if not force:
        c.output.error("Delete blocked: pass --force to confirm deletion")
        raise typer.Exit(1)
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    c.client.delete(f"/zones/{zone_id}/rate_limits/{rule_id}")
    c.output.success(f"Rate limit deleted: {rule_id}")
