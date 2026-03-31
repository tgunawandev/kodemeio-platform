"""Load Balancer management commands."""

from __future__ import annotations

import json as json_mod
import pathlib
from typing import Annotated

import typer

from kctl_cf.core.callbacks import AppContext
from kctl_cf.core.utils import require_account, resolve_zone

app = typer.Typer(help="Manage Load Balancers, pools, and monitors.")


@app.command("list")
def list_(
    ctx: typer.Context,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """List load balancers."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    result = c.client.get(f"/zones/{zone_id}/load_balancers")
    if not isinstance(result, list):
        result = []
    rows = []
    for lb in result:
        default_pools = lb.get("default_pools", []) or []
        rows.append(
            [
                lb.get("id", "")[:12],
                lb.get("name", ""),
                str(len(default_pools)),
                (lb.get("fallback_pool", "") or "")[:12],
                "Yes" if lb.get("proxied") else "No",
                "Yes" if lb.get("enabled", True) else "No",
            ]
        )
    c.output.table(
        f"Load Balancers — {zone}",
        [
            ("ID", "dim"),
            ("Name", "cyan"),
            ("Default Pools", ""),
            ("Fallback Pool", "dim"),
            ("Proxied", "green"),
            ("Enabled", ""),
        ],
        rows,
        data_for_json=result,
    )


@app.command()
def get(
    ctx: typer.Context,
    lb_id: Annotated[str, typer.Argument(help="Load balancer ID")],
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """Get load balancer details."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    result = c.client.get(f"/zones/{zone_id}/load_balancers/{lb_id}")
    if not isinstance(result, dict):
        result = {}
    default_pools = result.get("default_pools", []) or []
    sections = [
        (
            "Load Balancer",
            [
                ("ID", result.get("id", "")),
                ("Name", result.get("name", "")),
                ("Description", result.get("description", "")),
                ("TTL", str(result.get("ttl", ""))),
                ("Proxied", str(result.get("proxied", False))),
                ("Enabled", str(result.get("enabled", True))),
            ],
        ),
        (
            "Pools",
            [
                ("Default Pools", ", ".join(default_pools)),
                ("Fallback Pool", result.get("fallback_pool", "")),
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
    c.output.detail(f"Load Balancer — {result.get('name', lb_id)}", sections, data_for_json=result)


@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", help="Load balancer name (DNS hostname)")],
    default_pools: Annotated[str, typer.Option("--default-pools", help="Comma-separated pool IDs")],
    fallback_pool: Annotated[str | None, typer.Option("--fallback-pool", help="Fallback pool ID")] = None,
    proxied: Annotated[bool, typer.Option("--proxied/--no-proxied", help="Enable Cloudflare proxy")] = False,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """Create a load balancer."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    pools = [p.strip() for p in default_pools.split(",") if p.strip()]
    payload: dict = {
        "name": name,
        "default_pools": pools,
        "proxied": proxied,
    }
    if fallback_pool:
        payload["fallback_pool"] = fallback_pool
    elif pools:
        payload["fallback_pool"] = pools[0]
    result = c.client.post(f"/zones/{zone_id}/load_balancers", json=payload)
    lb_id = result.get("id", "") if isinstance(result, dict) else ""
    c.output.success(f"Load balancer created: {lb_id}")


@app.command()
def update(
    ctx: typer.Context,
    lb_id: Annotated[str, typer.Argument(help="Load balancer ID to update")],
    name: Annotated[str | None, typer.Option("--name", help="Load balancer name")] = None,
    enabled: Annotated[bool | None, typer.Option("--enabled/--disabled", help="Enable or disable")] = None,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """Update a load balancer."""
    c: AppContext = ctx.obj
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    payload: dict = {}
    if name is not None:
        payload["name"] = name
    if enabled is not None:
        payload["enabled"] = enabled
    c.client.patch(f"/zones/{zone_id}/load_balancers/{lb_id}", json=payload)
    c.output.success(f"Load balancer updated: {lb_id}")


@app.command("delete")
def delete_(
    ctx: typer.Context,
    lb_id: Annotated[str, typer.Argument(help="Load balancer ID to delete")],
    force: Annotated[bool, typer.Option("--force", help="Required to confirm deletion")] = False,
    zone: Annotated[str | None, typer.Option("--zone", help="Zone name")] = None,
) -> None:
    """Delete a load balancer. Requires --force to confirm."""
    c: AppContext = ctx.obj
    if not force:
        c.output.error("Delete blocked: pass --force to confirm deletion")
        raise typer.Exit(1)
    zone = resolve_zone(c, zone)
    zone_id = c.client.get_zone_id(zone)
    c.client.delete(f"/zones/{zone_id}/load_balancers/{lb_id}")
    c.output.success(f"Load balancer deleted: {lb_id}")


@app.command()
def pools(ctx: typer.Context) -> None:
    """List load balancer pools."""
    c: AppContext = ctx.obj
    acct = require_account(c)
    result = c.client.get(f"/accounts/{acct}/load_balancers/pools")
    if not isinstance(result, list):
        result = []
    rows = []
    for p in result:
        origins = p.get("origins", []) or []
        rows.append(
            [
                p.get("id", "")[:12],
                p.get("name", ""),
                "Yes" if p.get("enabled", True) else "No",
                str(len(origins)),
                "Yes" if p.get("healthy") else "No",
            ]
        )
    c.output.table(
        "Load Balancer Pools",
        [("ID", "dim"), ("Name", "cyan"), ("Enabled", "green"), ("Origins", ""), ("Healthy", "green")],
        rows,
        data_for_json=result,
    )


@app.command("create-pool")
def create_pool(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", help="Pool name")],
    origins: Annotated[str, typer.Option("--origins", help="JSON file with array of origin objects")],
) -> None:
    """Create a load balancer pool from a JSON origins file."""
    c: AppContext = ctx.obj
    acct = require_account(c)
    origins_path = pathlib.Path(origins)
    if not origins_path.exists():
        c.output.error(f"File not found: {origins}")
        raise typer.Exit(1)
    origins_data = json_mod.loads(origins_path.read_text())
    if not isinstance(origins_data, list):
        c.output.error("JSON file must contain an array of origin objects")
        raise typer.Exit(1)
    payload: dict = {
        "name": name,
        "origins": origins_data,
    }
    result = c.client.post(f"/accounts/{acct}/load_balancers/pools", json=payload)
    pool_id = result.get("id", "") if isinstance(result, dict) else ""
    c.output.success(f"Pool created: {pool_id}")


@app.command("delete-pool")
def delete_pool(
    ctx: typer.Context,
    pool_id: Annotated[str, typer.Argument(help="Pool ID to delete")],
    force: Annotated[bool, typer.Option("--force", help="Required to confirm deletion")] = False,
) -> None:
    """Delete a load balancer pool. Requires --force to confirm."""
    c: AppContext = ctx.obj
    if not force:
        c.output.error("Delete blocked: pass --force to confirm deletion")
        raise typer.Exit(1)
    acct = require_account(c)
    c.client.delete(f"/accounts/{acct}/load_balancers/pools/{pool_id}")
    c.output.success(f"Pool deleted: {pool_id}")


@app.command()
def monitors(ctx: typer.Context) -> None:
    """List load balancer monitors."""
    c: AppContext = ctx.obj
    acct = require_account(c)
    result = c.client.get(f"/accounts/{acct}/load_balancers/monitors")
    if not isinstance(result, list):
        result = []
    rows = []
    for m in result:
        rows.append(
            [
                m.get("id", "")[:12],
                m.get("type", ""),
                m.get("description", ""),
                str(m.get("interval", "")),
            ]
        )
    c.output.table(
        "Load Balancer Monitors",
        [("ID", "dim"), ("Type", "cyan"), ("Description", ""), ("Interval", "dim")],
        rows,
        data_for_json=result,
    )


@app.command("create-monitor")
def create_monitor(
    ctx: typer.Context,
    monitor_type: Annotated[str, typer.Option("--type", help="Monitor type (http, https, tcp)")],
    description: Annotated[str | None, typer.Option("--description", help="Monitor description")] = None,
    expected_codes: Annotated[str, typer.Option("--expected-codes", help="Expected HTTP response codes")] = "2xx",
) -> None:
    """Create a load balancer monitor."""
    c: AppContext = ctx.obj
    acct = require_account(c)
    payload: dict = {
        "type": monitor_type,
        "expected_codes": expected_codes,
    }
    if description:
        payload["description"] = description
    result = c.client.post(f"/accounts/{acct}/load_balancers/monitors", json=payload)
    monitor_id = result.get("id", "") if isinstance(result, dict) else ""
    c.output.success(f"Monitor created: {monitor_id}")


@app.command("delete-monitor")
def delete_monitor(
    ctx: typer.Context,
    monitor_id: Annotated[str, typer.Argument(help="Monitor ID to delete")],
    force: Annotated[bool, typer.Option("--force", help="Required to confirm deletion")] = False,
) -> None:
    """Delete a load balancer monitor. Requires --force to confirm."""
    c: AppContext = ctx.obj
    if not force:
        c.output.error("Delete blocked: pass --force to confirm deletion")
        raise typer.Exit(1)
    acct = require_account(c)
    c.client.delete(f"/accounts/{acct}/load_balancers/monitors/{monitor_id}")
    c.output.success(f"Monitor deleted: {monitor_id}")
