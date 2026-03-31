"""Page Rules management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_cloudflare.core.callbacks import AppContext
from kctl_cloudflare.core.utils import resolve_zone

app = typer.Typer(help="Manage Cloudflare Page Rules.")


@app.command("list")
def list_(
    ctx: typer.Context,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """List page rules for a zone."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    rules = c.client.get(f"/zones/{zone_id}/pagerules")
    if not isinstance(rules, list):
        rules = []
    rows = []
    for r in rules:
        targets = r.get("targets", [])
        target_url = ""
        if targets:
            constraint = targets[0].get("constraint", {})
            target_url = constraint.get("value", "")
        actions = r.get("actions", [])
        action_str = ", ".join(a.get("id", "") for a in actions)
        rows.append(
            [
                r.get("id", "")[:12],
                target_url[:50],
                action_str[:40],
                str(r.get("priority", "")),
                r.get("status", ""),
            ]
        )
    c.output.table(
        f"Page Rules — {zone}",
        [("ID", "dim"), ("Target", "cyan"), ("Actions", "green"), ("Priority", "dim"), ("Status", "")],
        rows,
        data_for_json=rules,
    )


@app.command()
def get(
    ctx: typer.Context,
    rule_id: Annotated[str, typer.Argument(help="Page rule ID")],
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """Get details for a specific page rule."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    result = c.client.get(f"/zones/{zone_id}/pagerules/{rule_id}")
    if not isinstance(result, dict):
        result = {}
    targets = result.get("targets", [])
    target_url = ""
    if targets:
        constraint = targets[0].get("constraint", {})
        target_url = constraint.get("value", "")
    actions = result.get("actions", [])
    action_kvs = []
    for a in actions:
        val = a.get("value", "")
        if isinstance(val, dict):
            val = str(val)
        action_kvs.append((a.get("id", ""), str(val)))
    sections = [
        (
            "Page Rule",
            [
                ("ID", result.get("id", "")),
                ("Target", target_url),
                ("Status", result.get("status", "")),
                ("Priority", str(result.get("priority", ""))),
            ],
        ),
        ("Actions", action_kvs),
    ]
    c.output.detail(f"Page Rule — {rule_id[:12]}", sections, data_for_json=result)


@app.command()
def create(
    ctx: typer.Context,
    target: Annotated[str, typer.Option("--target", help="URL pattern to match (e.g., *example.com/path/*)")],
    action: Annotated[str, typer.Option("--action", help="Action ID (e.g., forwarding_url, always_use_https)")],
    value: Annotated[str | None, typer.Option("--value", help="Action value (e.g., redirect URL)")] = None,
    priority: Annotated[int, typer.Option("--priority", help="Rule priority")] = 1,
    status_flag: Annotated[str, typer.Option("--status", help="Rule status (active/disabled)")] = "active",
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """Create a page rule."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    action_obj: dict = {"id": action}
    if value:
        action_obj["value"] = value
    payload = {
        "targets": [{"target": "url", "constraint": {"operator": "matches", "value": target}}],
        "actions": [action_obj],
        "priority": priority,
        "status": status_flag,
    }
    result = c.client.post(f"/zones/{zone_id}/pagerules", json=payload)
    rule_id = result.get("id", "") if isinstance(result, dict) else ""
    c.output.success(f"Page rule created: {rule_id}")


@app.command()
def update(
    ctx: typer.Context,
    rule_id: Annotated[str, typer.Argument(help="Page rule ID to update")],
    target: Annotated[str | None, typer.Option("--target", help="URL pattern to match")] = None,
    action: Annotated[str | None, typer.Option("--action", help="Action ID")] = None,
    value: Annotated[str | None, typer.Option("--value", help="Action value")] = None,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """Update a page rule."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    # Fetch existing rule to merge
    existing = c.client.get(f"/zones/{zone_id}/pagerules/{rule_id}")
    if not isinstance(existing, dict):
        existing = {}
    payload: dict = {}
    if target:
        payload["targets"] = [{"target": "url", "constraint": {"operator": "matches", "value": target}}]
    else:
        payload["targets"] = existing.get("targets", [])
    if action:
        action_obj: dict = {"id": action}
        if value:
            action_obj["value"] = value
        payload["actions"] = [action_obj]
    else:
        payload["actions"] = existing.get("actions", [])
    c.client.put(f"/zones/{zone_id}/pagerules/{rule_id}", json=payload)
    c.output.success(f"Page rule updated: {rule_id}")


@app.command("delete")
def delete_(
    ctx: typer.Context,
    rule_id: Annotated[str, typer.Argument(help="Page rule ID to delete")],
    force: Annotated[bool, typer.Option("--force", help="Required to confirm deletion")] = False,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """Delete a page rule. Requires --force to confirm."""
    c: AppContext = ctx.obj
    if not force:
        c.output.error("Delete blocked: pass --force to confirm deletion")
        raise typer.Exit(1)
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    c.client.delete(f"/zones/{zone_id}/pagerules/{rule_id}")
    c.output.success(f"Page rule deleted: {rule_id}")
