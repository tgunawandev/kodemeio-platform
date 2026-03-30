"""Cluster and Docker Swarm management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_dokploy.core.callbacks import AppContext

app = typer.Typer(help="Manage Docker Swarm cluster and nodes.")


# ---------------------------------------------------------------------------
# Cluster commands
# ---------------------------------------------------------------------------


@app.command("nodes")
def get_nodes(
    ctx: typer.Context,
    server_id: Annotated[str, typer.Argument(help="Server ID")],
) -> None:
    """List cluster nodes for a server."""
    c: AppContext = ctx.obj
    data = c.client.get("/cluster.getNodes", params={"serverId": server_id})
    if not isinstance(data, list):
        data = [data] if data else []
    rows = []
    for n in data:
        if isinstance(n, dict):
            nid = str(n.get("ID", n.get("nodeId", "")))[:12]
            hostname = (
                n.get("Description", {}).get("Hostname", n.get("hostname", "-"))
                if isinstance(n.get("Description"), dict)
                else str(n.get("hostname", "-"))
            )
            role = (
                n.get("Spec", {}).get("Role", n.get("role", "-"))
                if isinstance(n.get("Spec"), dict)
                else str(n.get("role", "-"))
            )
            status = (
                n.get("Status", {}).get("State", n.get("status", "-"))
                if isinstance(n.get("Status"), dict)
                else str(n.get("status", "-"))
            )
            rows.append([nid, hostname, role, status])
        else:
            rows.append([str(n), "-", "-", "-"])
    c.output.table(
        "Cluster Nodes",
        [("ID", "dim"), ("Hostname", "cyan"), ("Role", ""), ("Status", "")],
        rows,
        data_for_json=data,
    )


@app.command("add-manager")
def add_manager(
    ctx: typer.Context,
    server_id: Annotated[str, typer.Argument(help="Server ID to add as manager")],
) -> None:
    """Get the command to add a server as a Swarm manager."""
    c: AppContext = ctx.obj
    data = c.client.get("/cluster.addManager", params={"serverId": server_id})
    if c.json_mode:
        c.output.raw_json(data if isinstance(data, dict) else {"command": data})
    else:
        c.output.info(f"Join command: {data}")


@app.command("add-worker")
def add_worker(
    ctx: typer.Context,
    server_id: Annotated[str, typer.Argument(help="Server ID to add as worker")],
) -> None:
    """Get the command to add a server as a Swarm worker."""
    c: AppContext = ctx.obj
    data = c.client.get("/cluster.addWorker", params={"serverId": server_id})
    if c.json_mode:
        c.output.raw_json(data if isinstance(data, dict) else {"command": data})
    else:
        c.output.info(f"Join command: {data}")


@app.command("remove-worker")
def remove_worker(
    ctx: typer.Context,
    node_id: Annotated[str, typer.Argument(help="Node ID to remove")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Remove a worker node from the cluster (destructive)."""
    c: AppContext = ctx.obj
    if not force:
        typer.confirm(f"Remove worker node '{node_id}' from cluster?", abort=True)
    result = c.client.post("/cluster.removeWorker", json={"nodeId": node_id})
    c.output.success(f"Worker node '{node_id}' removed")
    if c.json_mode:
        c.output.raw_json(result)


# ---------------------------------------------------------------------------
# Swarm commands
# ---------------------------------------------------------------------------


@app.command("swarm-nodes")
def swarm_nodes(
    ctx: typer.Context,
    server_id: Annotated[str, typer.Argument(help="Server ID")],
) -> None:
    """List Swarm nodes for a server."""
    c: AppContext = ctx.obj
    data = c.client.get("/swarm.getNodes", params={"serverId": server_id})
    if not isinstance(data, list):
        data = [data] if data else []
    rows = []
    for n in data:
        if isinstance(n, dict):
            nid = str(n.get("ID", n.get("nodeId", "")))[:12]
            hostname = n.get("Description", {}).get("Hostname", "-") if isinstance(n.get("Description"), dict) else "-"
            role = n.get("Spec", {}).get("Role", "-") if isinstance(n.get("Spec"), dict) else "-"
            status = n.get("Status", {}).get("State", "-") if isinstance(n.get("Status"), dict) else "-"
            rows.append([nid, hostname, role, status])
        else:
            rows.append([str(n), "-", "-", "-"])
    c.output.table(
        "Swarm Nodes",
        [("ID", "dim"), ("Hostname", "cyan"), ("Role", ""), ("Status", "")],
        rows,
        data_for_json=data,
    )


@app.command("swarm-info")
def swarm_node_info(
    ctx: typer.Context,
    node_id: Annotated[str, typer.Argument(help="Swarm node ID")],
    server_id: Annotated[str, typer.Option("--server", "-s", help="Server ID")],
) -> None:
    """Get detailed info for a Swarm node."""
    c: AppContext = ctx.obj
    data = c.client.get("/swarm.getNodeInfo", params={"nodeId": node_id, "serverId": server_id})
    if c.json_mode:
        c.output.raw_json(data)
        return
    if isinstance(data, dict):
        sections = [("Swarm Node", [(str(k), str(v)) for k, v in data.items() if not isinstance(v, (dict, list))])]
        c.output.detail(f"Node: {node_id}", sections, data_for_json=data)
    else:
        c.output.info(f"Node info: {data}")


@app.command("swarm-apps")
def swarm_node_apps(
    ctx: typer.Context,
    server_id: Annotated[str, typer.Argument(help="Server ID")],
) -> None:
    """List applications running on Swarm nodes."""
    c: AppContext = ctx.obj
    data = c.client.get("/swarm.getNodeApps", params={"serverId": server_id})
    if not isinstance(data, list):
        data = [data] if data else []
    rows = []
    for a in data:
        if isinstance(a, dict):
            name = a.get("name", a.get("Name", "-"))
            status = a.get("status", a.get("Status", "-"))
            rows.append([str(name), str(status)])
        else:
            rows.append([str(a), "-"])
    c.output.table(
        "Swarm Applications",
        [("Name", "cyan"), ("Status", "")],
        rows,
        data_for_json=data,
    )
