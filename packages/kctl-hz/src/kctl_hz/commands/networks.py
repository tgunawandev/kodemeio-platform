"""Network management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_hz.core.callbacks import AppContext
from kctl_hz.core.utils import parse_labels

app = typer.Typer(help="Manage Hetzner Cloud networks.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all networks."""
    c: AppContext = ctx.obj
    networks = c.client.get_all("/networks", "networks")
    rows = []
    for n in networks:
        subnets = n.get("subnets", [])
        subnet_strs = ", ".join(s.get("ip_range", "") for s in subnets) if subnets else "-"
        servers = n.get("servers", [])
        rows.append(
            [
                str(n.get("id", "")),
                n.get("name", ""),
                n.get("ip_range", ""),
                subnet_strs,
                str(len(servers)),
            ]
        )
    c.output.table(
        "Networks",
        [("ID", "dim"), ("Name", "cyan"), ("IP Range", ""), ("Subnets", ""), ("Servers", "")],
        rows,
        data_for_json=networks,
    )


@app.command()
def get(
    ctx: typer.Context,
    network_id: Annotated[int, typer.Argument(help="Network ID")],
) -> None:
    """Get network details."""
    c: AppContext = ctx.obj
    data = c.client.get(f"/networks/{network_id}")
    net = data.get("network", {})
    if not net:
        c.output.error(f"Network {network_id} not found")
        raise typer.Exit(1)

    subnets = net.get("subnets", [])
    routes = net.get("routes", [])
    servers = net.get("servers", [])
    labels = net.get("labels", {})
    labels_str = ", ".join(f"{k}={v}" for k, v in labels.items()) if labels else "-"
    protection = net.get("protection", {})

    sections = [
        (
            "Network",
            [
                ("ID", str(net.get("id", ""))),
                ("Name", net.get("name", "")),
                ("IP Range", net.get("ip_range", "")),
                ("Delete Protection", str(protection.get("delete", False))),
                ("Labels", labels_str),
                ("Created", net.get("created", "")),
                ("Servers", str(len(servers))),
            ],
        )
    ]

    if subnets:
        subnet_kvs = []
        for i, s in enumerate(subnets, 1):
            subnet_kvs.append(
                (
                    f"Subnet {i}",
                    f"{s.get('ip_range', '')} ({s.get('type', '')}, {s.get('network_zone', '')},"
                    f" gw: {s.get('gateway', '-')})",
                )
            )
        sections.append(("Subnets", subnet_kvs))

    if routes:
        route_kvs = []
        for i, r in enumerate(routes, 1):
            route_kvs.append((f"Route {i}", f"{r.get('destination', '')} via {r.get('gateway', '')}"))
        sections.append(("Routes", route_kvs))

    c.output.detail(f"Network: {net.get('name', network_id)}", sections, data_for_json=net)


@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Network name")],
    ip_range: Annotated[str, typer.Option("--ip-range", help="IP range in CIDR notation (e.g. 10.0.0.0/16)")],
) -> None:
    """Create a new network."""
    c: AppContext = ctx.obj
    result = c.client.post("/networks", json={"name": name, "ip_range": ip_range})
    net = result.get("network", {})
    c.output.success(f"Network '{net.get('name')}' created (ID: {net.get('id')}, Range: {ip_range})")
    if c.output.json_mode:
        c.output.raw_json(result)


@app.command()
def delete(
    ctx: typer.Context,
    network_id: Annotated[int, typer.Argument(help="Network ID")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete a network."""
    c: AppContext = ctx.obj
    if not force:
        typer.confirm(f"Delete network {network_id}?", abort=True)
    c.client.delete(f"/networks/{network_id}")
    c.output.success(f"Network {network_id} deleted")


@app.command()
def update(
    ctx: typer.Context,
    network_id: Annotated[int, typer.Argument(help="Network ID")],
    name: Annotated[str | None, typer.Option("--name", help="New network name")] = None,
    labels: Annotated[str | None, typer.Option("--labels", help="Labels as key=val,key=val")] = None,
) -> None:
    """Update a network (name, labels)."""
    c: AppContext = ctx.obj
    payload: dict = {}
    if name is not None:
        payload["name"] = name
    if labels is not None:
        payload["labels"] = parse_labels(labels)
    if not payload:
        c.output.error("Provide at least one option to update (--name, --labels)")
        raise typer.Exit(1)
    result = c.client.put(f"/networks/{network_id}", json=payload)
    c.output.success(f"Network {network_id} updated")
    if c.output.json_mode:
        c.output.raw_json(result)


@app.command("add-subnet")
def add_subnet(
    ctx: typer.Context,
    network_id: Annotated[int, typer.Argument(help="Network ID")],
    subnet_type: Annotated[str, typer.Option("--type", help="Subnet type: cloud, vswitch, or server")],
    ip_range: Annotated[str, typer.Option("--ip-range", help="Subnet CIDR (e.g. 10.0.1.0/24)")],
    network_zone: Annotated[str, typer.Option("--network-zone", help="Network zone (e.g. eu-central)")],
) -> None:
    """Add a subnet to a network."""
    c: AppContext = ctx.obj

    if subnet_type not in ("cloud", "vswitch", "server"):
        c.output.error("--type must be 'cloud', 'vswitch', or 'server'")
        raise typer.Exit(1)

    payload = {
        "type": subnet_type,
        "ip_range": ip_range,
        "network_zone": network_zone,
    }
    result = c.client.post(f"/networks/{network_id}/actions/add_subnet", json=payload)
    c.output.success(f"Subnet {ip_range} added to network {network_id}")
    if c.output.json_mode:
        c.output.raw_json(result)


@app.command("remove-subnet")
def remove_subnet(
    ctx: typer.Context,
    network_id: Annotated[int, typer.Argument(help="Network ID")],
    ip_range: Annotated[str, typer.Option("--ip-range", help="Subnet CIDR to remove")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Remove a subnet from a network."""
    c: AppContext = ctx.obj
    if not force:
        typer.confirm(f"Remove subnet {ip_range} from network {network_id}?", abort=True)
    result = c.client.post(f"/networks/{network_id}/actions/delete_subnet", json={"ip_range": ip_range})
    c.output.success(f"Subnet {ip_range} removed from network {network_id}")
    if c.output.json_mode:
        c.output.raw_json(result)


@app.command("attach-server")
def attach_server(
    ctx: typer.Context,
    network_id: Annotated[int, typer.Argument(help="Network ID")],
    server: Annotated[int, typer.Option("--server", help="Server ID to attach")],
    ip: Annotated[str | None, typer.Option("--ip", help="Specific IP to assign within the network")] = None,
) -> None:
    """Attach a server to a network."""
    c: AppContext = ctx.obj
    payload: dict = {"network": network_id}
    if ip:
        payload["ip"] = ip
    result = c.client.post(f"/servers/{server}/actions/attach_to_network", json=payload)
    c.output.success(f"Server {server} attached to network {network_id}")
    if c.output.json_mode:
        c.output.raw_json(result)


@app.command("detach-server")
def detach_server(
    ctx: typer.Context,
    network_id: Annotated[int, typer.Argument(help="Network ID")],
    server: Annotated[int, typer.Option("--server", help="Server ID to detach")],
) -> None:
    """Detach a server from a network."""
    c: AppContext = ctx.obj
    result = c.client.post(f"/servers/{server}/actions/detach_from_network", json={"network": network_id})
    c.output.success(f"Server {server} detached from network {network_id}")
    if c.output.json_mode:
        c.output.raw_json(result)


@app.command("change-ip-range")
def change_ip_range(
    ctx: typer.Context,
    network_id: Annotated[int, typer.Argument(help="Network ID")],
    ip_range: Annotated[str, typer.Option("--ip-range", help="New IP range in CIDR notation")],
) -> None:
    """Change the IP range of a network."""
    c: AppContext = ctx.obj
    result = c.client.post(f"/networks/{network_id}/actions/change_ip_range", json={"ip_range": ip_range})
    c.output.success(f"Network {network_id} IP range changed to {ip_range}")
    if c.output.json_mode:
        c.output.raw_json(result)


@app.command("add-route")
def add_route(
    ctx: typer.Context,
    network_id: Annotated[int, typer.Argument(help="Network ID")],
    destination: Annotated[str, typer.Option("--destination", help="Destination CIDR (e.g. 10.10.0.0/16)")],
    gateway: Annotated[str, typer.Option("--gateway", help="Gateway IP address")],
) -> None:
    """Add a static route to a network."""
    c: AppContext = ctx.obj
    payload = {"destination": destination, "gateway": gateway}
    result = c.client.post(f"/networks/{network_id}/actions/add_route", json=payload)
    c.output.success(f"Route {destination} via {gateway} added to network {network_id}")
    if c.output.json_mode:
        c.output.raw_json(result)


@app.command("remove-route")
def remove_route(
    ctx: typer.Context,
    network_id: Annotated[int, typer.Argument(help="Network ID")],
    destination: Annotated[str, typer.Option("--destination", help="Destination CIDR to remove")],
    gateway: Annotated[str, typer.Option("--gateway", help="Gateway IP address")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Remove a static route from a network."""
    c: AppContext = ctx.obj
    if not force:
        typer.confirm(f"Remove route {destination} via {gateway} from network {network_id}?", abort=True)
    payload = {"destination": destination, "gateway": gateway}
    result = c.client.post(f"/networks/{network_id}/actions/delete_route", json=payload)
    c.output.success(f"Route {destination} via {gateway} removed from network {network_id}")
    if c.output.json_mode:
        c.output.raw_json(result)
