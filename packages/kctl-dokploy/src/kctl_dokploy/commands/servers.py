"""Server management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_dokploy.core.callbacks import AppContext

app = typer.Typer(help="Manage Dokploy servers.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all servers."""
    c: AppContext = ctx.obj
    servers = c.client.get("/server.all")
    if not isinstance(servers, list):
        servers = []
    rows = []
    for s in servers:
        sid = s.get("serverId", "")[:12]
        name = s.get("name", "")
        ip = s.get("ipAddress", "")
        status = s.get("serverStatus", "unknown")
        docker = s.get("dockerVersion", "-")
        rows.append([sid, name, ip, status, str(docker)])
    c.output.table(
        "Servers",
        [("ID", "dim"), ("Name", "cyan"), ("IP", ""), ("Status", ""), ("Docker", "dim")],
        rows,
        data_for_json=servers,
    )


@app.command()
def get(
    ctx: typer.Context,
    server_id: Annotated[str, typer.Argument(help="Server ID")],
) -> None:
    """Get server details."""
    c: AppContext = ctx.obj
    data = c.client.get("/server.one", params={"serverId": server_id})
    if not isinstance(data, dict):
        c.output.error(f"Server '{server_id}' not found")
        raise typer.Exit(1)
    name = data.get("name", "unknown")
    ip = data.get("ipAddress", "-")
    status = data.get("serverStatus", "unknown")
    docker = data.get("dockerVersion", "-")
    os_info = data.get("os", "-")
    ssh_key = data.get("sshKeyId", "-")
    sections = [
        (
            "Server",
            [
                ("ID", data.get("serverId", "")),
                ("Name", name),
                ("IP Address", ip),
                ("Status", status),
                ("Docker", str(docker)),
                ("OS", str(os_info)),
                ("SSH Key ID", str(ssh_key)),
            ],
        ),
    ]
    c.output.detail(f"Server: {name}", sections, data_for_json=data)


@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", "-n", help="Server name")],
    ip_address: Annotated[str, typer.Option("--ip", help="IP address")],
    ssh_key_id: Annotated[str | None, typer.Option("--ssh-key", help="SSH key ID")] = None,
    port: Annotated[int, typer.Option("--port", "-p", help="SSH port")] = 22,
    username: Annotated[str, typer.Option("--username", "-u", help="SSH username")] = "root",
) -> None:
    """Register a new server."""
    c: AppContext = ctx.obj
    payload: dict = {
        "name": name,
        "ipAddress": ip_address,
        "port": port,
        "username": username,
    }
    if ssh_key_id:
        payload["sshKeyId"] = ssh_key_id
    result = c.client.post("/server.create", json=payload)
    sid = result.get("serverId", "") if isinstance(result, dict) else ""
    c.output.success(f"Server '{name}' registered: {sid}")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def remove(
    ctx: typer.Context,
    server_id: Annotated[str, typer.Argument(help="Server ID to remove")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Remove a server from Dokploy (destructive)."""
    c: AppContext = ctx.obj
    if not force:
        typer.confirm(f"Remove server '{server_id}'? This cannot be undone.", abort=True)
    result = c.client.delete("/server.remove", json={"serverId": server_id})
    c.output.success(f"Server '{server_id}' removed")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def update(
    ctx: typer.Context,
    server_id: Annotated[str, typer.Argument(help="Server ID")],
    name: Annotated[str | None, typer.Option("--name", "-n", help="New server name")] = None,
    ip_address: Annotated[str | None, typer.Option("--ip", help="New IP address")] = None,
    port: Annotated[int | None, typer.Option("--port", "-p", help="New SSH port")] = None,
    username: Annotated[str | None, typer.Option("--username", "-u", help="New SSH username")] = None,
) -> None:
    """Update a server configuration."""
    c: AppContext = ctx.obj
    payload: dict = {"serverId": server_id}
    if name is not None:
        payload["name"] = name
    if ip_address is not None:
        payload["ipAddress"] = ip_address
    if port is not None:
        payload["port"] = port
    if username is not None:
        payload["username"] = username
    if len(payload) == 1:
        c.output.error("No update options provided. Use --name, --ip, --port, or --username.")
        raise typer.Exit(1)
    result = c.client.post("/server.update", json=payload)
    c.output.success(f"Server '{server_id}' updated")
    if c.json_mode:
        c.output.raw_json(result)
