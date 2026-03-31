"""Cloudflare Tunnel management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_cf.core.callbacks import AppContext
from kctl_cf.core.utils import require_account

app = typer.Typer(help="Manage Cloudflare Tunnels.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all tunnels."""
    c: AppContext = ctx.obj
    acct = require_account(c)
    tunnels = c.client.get(f"/accounts/{acct}/cfd_tunnel", params={"is_deleted": "false"})
    if not isinstance(tunnels, list):
        tunnels = []
    rows = []
    for t in tunnels:
        rows.append(
            [
                t.get("name", ""),
                t.get("id", "")[:12],
                t.get("status", ""),
                str(len(t.get("connections", []))),
            ]
        )
    c.output.table(
        "Tunnels",
        [("Name", "cyan"), ("ID", "dim"), ("Status", "green"), ("Connections", "")],
        rows,
        data_for_json=tunnels,
    )


@app.command()
def get(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Tunnel name")],
) -> None:
    """Get tunnel details."""
    c: AppContext = ctx.obj
    acct = require_account(c)
    tunnels = c.client.get(f"/accounts/{acct}/cfd_tunnel", params={"name": name, "is_deleted": "false"})
    if not isinstance(tunnels, list) or not tunnels:
        c.output.error(f"Tunnel '{name}' not found")
        raise typer.Exit(1)
    t = tunnels[0]
    sections = [
        (
            "Tunnel",
            [
                ("Name", t.get("name", "")),
                ("ID", t.get("id", "")),
                ("Status", t.get("status", "")),
                ("Created", t.get("created_at", "")),
                ("Connections", str(len(t.get("connections", [])))),
            ],
        )
    ]
    c.output.detail(f"Tunnel: {name}", sections, data_for_json=t)


@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Tunnel name")],
    secret: Annotated[str | None, typer.Option("--secret", help="Tunnel secret (auto-generated if omitted)")] = None,
) -> None:
    """Create a Cloudflare Tunnel."""
    import base64
    import secrets as secrets_mod

    c: AppContext = ctx.obj
    acct = require_account(c)
    tunnel_secret = secret or base64.b64encode(secrets_mod.token_bytes(32)).decode()
    payload = {"name": name, "tunnel_secret": tunnel_secret}
    result = c.client.post(f"/accounts/{acct}/cfd_tunnel", json=payload)
    tunnel_id = result.get("id", "") if isinstance(result, dict) else ""
    token = result.get("token", "") if isinstance(result, dict) else ""
    if c.output.json_mode:
        c.output.raw_json(result if isinstance(result, dict) else {"id": tunnel_id})
    else:
        c.output.success(f"Tunnel created: {tunnel_id}")
        if token:
            c.output.kv("Token", token)


@app.command("delete")
def delete_(
    ctx: typer.Context,
    tunnel_id: Annotated[str, typer.Argument(help="Tunnel ID to delete")],
    force: Annotated[bool, typer.Option("--force", help="Required to confirm deletion")] = False,
) -> None:
    """Delete a Cloudflare Tunnel. Requires --force to confirm."""
    c: AppContext = ctx.obj
    if not force:
        c.output.error("Delete blocked: pass --force to confirm deletion")
        raise typer.Exit(1)
    acct = require_account(c)
    c.client.delete(f"/accounts/{acct}/cfd_tunnel/{tunnel_id}")
    c.output.success(f"Tunnel deleted: {tunnel_id}")


@app.command("get-config")
def get_config(
    ctx: typer.Context,
    tunnel_id: Annotated[str, typer.Argument(help="Tunnel ID")],
) -> None:
    """Get tunnel configuration (ingress rules)."""
    import json as json_mod

    c: AppContext = ctx.obj
    acct = require_account(c)
    data = c.client.get(f"/accounts/{acct}/cfd_tunnel/{tunnel_id}/configurations")
    if not isinstance(data, dict):
        data = {}
    config = data.get("config", {}) or {}
    ingress = config.get("ingress", [])
    rows = []
    for rule in ingress:
        origin_req = rule.get("originRequest", {}) or {}
        rows.append(
            [
                rule.get("hostname", "*"),
                rule.get("service", ""),
                rule.get("path", ""),
                json_mod.dumps(origin_req, default=str) if origin_req else "",
            ]
        )
    c.output.table(
        f"Tunnel Config — {tunnel_id[:12]}",
        [("Hostname", "cyan"), ("Service", "green"), ("Path", ""), ("OriginRequest", "dim")],
        rows,
        data_for_json=data,
    )


@app.command("update-config")
def update_config(
    ctx: typer.Context,
    tunnel_id: Annotated[str, typer.Argument(help="Tunnel ID")],
    file: Annotated[str, typer.Option("--file", "-f", help="JSON file with tunnel config")],
) -> None:
    """Update tunnel configuration from a JSON file."""
    import json as json_mod
    import pathlib

    c: AppContext = ctx.obj
    acct = require_account(c)
    file_path = pathlib.Path(file)
    if not file_path.exists():
        c.output.error(f"File not found: {file}")
        raise typer.Exit(1)
    config_data = json_mod.loads(file_path.read_text())
    result = c.client.put(f"/accounts/{acct}/cfd_tunnel/{tunnel_id}/configurations", json=config_data)
    if c.output.json_mode:
        c.output.raw_json(result if isinstance(result, dict) else {})
    else:
        c.output.success(f"Tunnel config updated: {tunnel_id[:12]}")


@app.command()
def connections(
    ctx: typer.Context,
    tunnel_id: Annotated[str, typer.Argument(help="Tunnel ID")],
) -> None:
    """List active tunnel connections."""
    c: AppContext = ctx.obj
    acct = require_account(c)
    items = c.client.get(f"/accounts/{acct}/cfd_tunnel/{tunnel_id}/connections")
    if not isinstance(items, list):
        items = []
    rows = []
    for conn in items:
        rows.append(
            [
                (conn.get("id") or "")[:12],
                (conn.get("client_id") or "")[:12],
                (conn.get("opened_at") or "")[:19],
                conn.get("origin_ip", ""),
                "Yes" if conn.get("is_pending_reconnect") else "No",
            ]
        )
    c.output.table(
        f"Connections — {tunnel_id[:12]}",
        [("ID", "dim"), ("Client ID", "dim"), ("Opened At", ""), ("Origin IP", "cyan"), ("Pending Reconnect", "")],
        rows,
        data_for_json=items,
    )


@app.command("clean-connections")
def clean_connections(
    ctx: typer.Context,
    tunnel_id: Annotated[str, typer.Argument(help="Tunnel ID")],
    force: Annotated[bool, typer.Option("--force", help="Required to confirm deletion")] = False,
) -> None:
    """Remove inactive tunnel connections. Requires --force to confirm."""
    c: AppContext = ctx.obj
    if not force:
        c.output.error("Delete blocked: pass --force to confirm deletion")
        raise typer.Exit(1)
    acct = require_account(c)
    c.client.delete(f"/accounts/{acct}/cfd_tunnel/{tunnel_id}/connections")
    c.output.success(f"Inactive connections cleaned for tunnel: {tunnel_id[:12]}")
