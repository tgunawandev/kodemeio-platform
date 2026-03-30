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
    result = c.client.post("/server.remove", json={"serverId": server_id})
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


@app.command()
def setup(
    ctx: typer.Context,
    server_id: Annotated[str, typer.Argument(help="Server ID")],
) -> None:
    """Run initial setup on a server (install Docker, configure SSH)."""
    c: AppContext = ctx.obj
    c.output.info(f"Running setup on server '{server_id}'...")
    result = c.client.post("/server.setup", json={"serverId": server_id})
    c.output.success(f"Server '{server_id}' setup initiated")
    if c.json_mode:
        c.output.raw_json(result)


@app.command("setup-monitoring")
def setup_monitoring(
    ctx: typer.Context,
    server_id: Annotated[str, typer.Argument(help="Server ID")],
) -> None:
    """Set up monitoring agent on a server."""
    c: AppContext = ctx.obj
    c.output.info(f"Setting up monitoring on server '{server_id}'...")
    result = c.client.post("/server.setupMonitoring", json={"serverId": server_id})
    c.output.success(f"Monitoring setup initiated on server '{server_id}'")
    if c.json_mode:
        c.output.raw_json(result)


@app.command()
def metrics(
    ctx: typer.Context,
    server_id: Annotated[str, typer.Argument(help="Server ID")],
) -> None:
    """Get server resource metrics (CPU, memory, disk)."""
    c: AppContext = ctx.obj
    data = c.client.get("/server.getServerMetrics", params={"serverId": server_id})
    if c.json_mode:
        c.output.raw_json(data if isinstance(data, dict) else {"metrics": data})
        return
    if not isinstance(data, dict):
        c.output.info("No metrics available")
        return
    sections = [
        (
            "Server Metrics",
            [(str(k), str(v)) for k, v in data.items() if not isinstance(v, (dict, list))],
        ),
    ]
    c.output.detail(f"Metrics: {server_id}", sections, data_for_json=data)


@app.command("time")
def server_time(
    ctx: typer.Context,
    server_id: Annotated[str, typer.Argument(help="Server ID")],
) -> None:
    """Get current server time."""
    c: AppContext = ctx.obj
    data = c.client.get("/server.getServerTime", params={"serverId": server_id})
    if c.json_mode:
        c.output.raw_json(data if isinstance(data, dict) else {"time": data})
    else:
        c.output.info(f"Server time: {data}")


@app.command("public-ip")
def public_ip(
    ctx: typer.Context,
    server_id: Annotated[str, typer.Argument(help="Server ID")],
) -> None:
    """Get public IP address of a server."""
    c: AppContext = ctx.obj
    data = c.client.get("/server.publicIp", params={"serverId": server_id})
    if c.json_mode:
        c.output.raw_json(data if isinstance(data, dict) else {"ip": data})
    else:
        c.output.info(f"Public IP: {data}")


@app.command("security")
def security(
    ctx: typer.Context,
    server_id: Annotated[str, typer.Argument(help="Server ID")],
) -> None:
    """Get server security information."""
    c: AppContext = ctx.obj
    data = c.client.get("/server.security", params={"serverId": server_id})
    if c.json_mode:
        c.output.raw_json(data if isinstance(data, dict) else {"security": data})
        return
    if isinstance(data, dict):
        sections = [("Security", [(str(k), str(v)) for k, v in data.items()])]
        c.output.detail(f"Security: {server_id}", sections, data_for_json=data)
    else:
        c.output.info(f"Security: {data}")


@app.command("validate")
def validate(
    ctx: typer.Context,
    server_id: Annotated[str, typer.Argument(help="Server ID")],
) -> None:
    """Validate server connectivity and configuration."""
    c: AppContext = ctx.obj
    data = c.client.get("/server.validate", params={"serverId": server_id})
    if c.json_mode:
        c.output.raw_json(data if isinstance(data, dict) else {"valid": data})
    else:
        c.output.success(f"Server '{server_id}' validation: {data}")


@app.command("ssh-keys")
def with_ssh_key(ctx: typer.Context) -> None:
    """List servers with their SSH key assignments."""
    c: AppContext = ctx.obj
    data = c.client.get("/server.withSSHKey")
    if not isinstance(data, list):
        data = []
    rows = []
    for s in data:
        sid = s.get("serverId", "")[:12]
        name = s.get("name", "")
        ip = s.get("ipAddress", "")
        key_name = ""
        ssh_key = s.get("sshKey", {})
        if isinstance(ssh_key, dict):
            key_name = ssh_key.get("name", s.get("sshKeyId", "-"))
        rows.append([sid, name, ip, str(key_name)])
    c.output.table(
        "Servers with SSH Keys",
        [("ID", "dim"), ("Name", "cyan"), ("IP", ""), ("SSH Key", "green")],
        rows,
        data_for_json=data,
    )


@app.command("build-servers")
def build_servers(ctx: typer.Context) -> None:
    """List servers available for builds."""
    c: AppContext = ctx.obj
    data = c.client.get("/server.buildServers")
    if not isinstance(data, list):
        data = []
    rows = []
    for s in data:
        sid = s.get("serverId", "")[:12]
        name = s.get("name", "")
        ip = s.get("ipAddress", "")
        status = s.get("serverStatus", "unknown")
        rows.append([sid, name, ip, status])
    c.output.table(
        "Build Servers",
        [("ID", "dim"), ("Name", "cyan"), ("IP", ""), ("Status", "")],
        rows,
        data_for_json=data,
    )


@app.command("count")
def count(ctx: typer.Context) -> None:
    """Get total server count."""
    c: AppContext = ctx.obj
    data = c.client.get("/server.count")
    if c.json_mode:
        c.output.raw_json(data if isinstance(data, dict) else {"count": data})
    else:
        c.output.info(f"Total servers: {data}")


@app.command("deployments")
def server_deployments(
    ctx: typer.Context,
    server_id: Annotated[str, typer.Argument(help="Server ID")],
) -> None:
    """List all deployments on a server."""
    c: AppContext = ctx.obj
    deployments = c.client.get("/deployment.allByServer", params={"serverId": server_id})
    if not isinstance(deployments, list):
        deployments = []
    rows = []
    for d in deployments:
        did = d.get("deploymentId", "")[:12]
        status = d.get("status", "unknown")
        deploy_type = d.get("deploymentType", "-")
        created = d.get("createdAt", "")
        title = d.get("title", d.get("description", "-"))
        rows.append([did, status, deploy_type, created, str(title)])
    c.output.table(
        f"Deployments on Server: {server_id}",
        [("ID", "dim"), ("Status", "cyan"), ("Type", ""), ("Created", ""), ("Title", "")],
        rows,
        data_for_json=deployments,
    )


@app.command("reload")
def reload_server(ctx: typer.Context) -> None:
    """Reload the Dokploy server configuration."""
    c: AppContext = ctx.obj
    c.output.info("Reloading server...")
    result = c.client.post("/settings.reloadServer")
    c.output.success("Server reloaded")
    if c.json_mode:
        c.output.raw_json(result)
