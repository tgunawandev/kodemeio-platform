"""Load balancer management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_hetzner.core.callbacks import AppContext
from kctl_hetzner.core.utils import parse_labels

app = typer.Typer(help="Manage Hetzner Cloud load balancers.")


def _resolve_lb(c: AppContext, name: str) -> dict:
    """Resolve load balancer by name, returning the first match or exiting."""
    data = c.client.get("/load_balancers", params={"name": name})
    items = data.get("load_balancers", [])
    if not items:
        c.output.error(f"Load balancer '{name}' not found")
        raise typer.Exit(1)
    return items[0]


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all load balancers."""
    c: AppContext = ctx.obj
    lbs = c.client.get_all("/load_balancers", "load_balancers")
    rows = []
    for lb in lbs:
        targets = lb.get("targets", [])
        services = lb.get("services", [])
        lb_type = lb.get("load_balancer_type", {}).get("name", "-")
        location = lb.get("location", {}).get("name", "-")
        ipv4 = lb.get("public_net", {}).get("ipv4", {}).get("ip", "-")
        rows.append(
            [
                str(lb.get("id", "")),
                lb.get("name", ""),
                lb_type,
                location,
                ipv4,
                str(len(targets)),
                str(len(services)),
            ]
        )
    c.output.table(
        "Load Balancers",
        [
            ("ID", "dim"),
            ("Name", "cyan"),
            ("Type", ""),
            ("Location", ""),
            ("IPv4", ""),
            ("Targets", ""),
            ("Services", ""),
        ],
        rows,
        data_for_json=lbs,
    )


@app.command()
def get(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Load balancer name")],
) -> None:
    """Get load balancer details."""
    c: AppContext = ctx.obj
    lb = _resolve_lb(c, name)
    targets = lb.get("targets", [])
    services = lb.get("services", [])
    algorithm = lb.get("algorithm", {}).get("type", "-")
    lb_type = lb.get("load_balancer_type", {}).get("name", "-")
    location = lb.get("location", {}).get("name", "-")
    ipv4 = lb.get("public_net", {}).get("ipv4", {}).get("ip", "-")
    ipv6 = lb.get("public_net", {}).get("ipv6", {}).get("ip", "-")

    sections = [
        (
            "Load Balancer",
            [
                ("Name", lb.get("name", "")),
                ("ID", str(lb.get("id", ""))),
                ("Type", lb_type),
                ("Algorithm", algorithm),
                ("Location", location),
                ("IPv4", ipv4),
                ("IPv6", ipv6),
                ("Created", lb.get("created", "")),
            ],
        )
    ]

    if targets:
        target_kvs = []
        for t in targets:
            server_id = t.get("server", {}).get("id", "")
            use_private = "yes" if t.get("use_private_ip") else "no"
            health = "unknown"
            health_status = t.get("health_status", [])
            if health_status:
                health = health_status[0].get("status", "unknown")
            target_kvs.append((f"Server {server_id}", f"health={health}, private_ip={use_private}"))
        sections.append((f"Targets ({len(targets)})", target_kvs))

    if services:
        svc_kvs = []
        for svc in services:
            proto = svc.get("protocol", "")
            listen = svc.get("listen_port", "")
            dest = svc.get("destination_port", "")
            svc_kvs.append((f"{proto}:{listen}", f"-> {dest}"))
        sections.append((f"Services ({len(services)})", svc_kvs))

    c.output.detail(f"Load Balancer: {name}", sections, data_for_json=lb)


@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Load balancer name")],
    lb_type: Annotated[str, typer.Option("--type", help="LB type (lb11, lb21, lb31)")] = "lb11",
    location: Annotated[str, typer.Option("--location", help="Location (e.g. fsn1, nbg1, hel1)")] = "fsn1",
    algorithm: Annotated[
        str, typer.Option("--algorithm", help="Algorithm (round_robin, least_connections)")
    ] = "round_robin",
    network: Annotated[int | None, typer.Option("--network", help="Network ID to attach")] = None,
) -> None:
    """Create a new load balancer."""
    c: AppContext = ctx.obj
    payload: dict = {
        "name": name,
        "load_balancer_type": lb_type,
        "location": location,
        "algorithm": {"type": algorithm},
    }
    if network is not None:
        payload["network"] = network

    result = c.client.post("/load_balancers", json=payload)
    lb = result.get("load_balancer", {})
    ipv4 = lb.get("public_net", {}).get("ipv4", {}).get("ip", "pending")
    c.output.success(f"Load balancer '{lb.get('name', name)}' created (ID: {lb.get('id')}, IPv4: {ipv4})")
    if c.output.json_mode:
        c.output.raw_json(result)


@app.command()
def delete(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Load balancer name")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete a load balancer."""
    c: AppContext = ctx.obj
    lb = _resolve_lb(c, name)
    lb_id = lb["id"]
    if not force:
        typer.confirm(f"Delete load balancer '{name}' (ID: {lb_id})?", abort=True)
    c.client.delete(f"/load_balancers/{lb_id}")
    c.output.success(f"Load balancer '{name}' deleted")


@app.command()
def update(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Load balancer name")],
    new_name: Annotated[str | None, typer.Option("--name", help="New name")] = None,
    labels: Annotated[str | None, typer.Option("--labels", help="Labels as key=val,key=val")] = None,
) -> None:
    """Update a load balancer (name, labels)."""
    c: AppContext = ctx.obj
    lb = _resolve_lb(c, name)
    lb_id = lb["id"]
    payload: dict = {}
    if new_name is not None:
        payload["name"] = new_name
    if labels is not None:
        payload["labels"] = parse_labels(labels)
    if not payload:
        c.output.error("Provide at least one option to update (--name, --labels)")
        raise typer.Exit(1)
    result = c.client.put(f"/load_balancers/{lb_id}", json=payload)
    updated = result.get("load_balancer", {})
    if new_name:
        c.output.success(f"Load balancer '{name}' renamed to '{updated.get('name', new_name)}'")
    else:
        c.output.success(f"Load balancer '{name}' updated")
    if c.output.json_mode:
        c.output.raw_json(result)


@app.command("add-target")
def add_target(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Load balancer name")],
    server: Annotated[int, typer.Option("--server", help="Server ID to add as target")],
    use_private_ip: Annotated[bool, typer.Option("--use-private-ip", help="Use private IP for target")] = False,
) -> None:
    """Add a server target to a load balancer."""
    c: AppContext = ctx.obj
    lb = _resolve_lb(c, name)
    lb_id = lb["id"]
    payload = {
        "type": "server",
        "server": {"id": server},
        "use_private_ip": use_private_ip,
    }
    result = c.client.post(f"/load_balancers/{lb_id}/actions/add_target", json=payload)
    c.output.success(f"Server {server} added as target to load balancer '{name}'")
    if c.output.json_mode:
        c.output.raw_json(result)


@app.command("remove-target")
def remove_target(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Load balancer name")],
    server: Annotated[int, typer.Option("--server", help="Server ID to remove from targets")],
) -> None:
    """Remove a server target from a load balancer."""
    c: AppContext = ctx.obj
    lb = _resolve_lb(c, name)
    lb_id = lb["id"]
    payload = {
        "type": "server",
        "server": {"id": server},
    }
    result = c.client.post(f"/load_balancers/{lb_id}/actions/remove_target", json=payload)
    c.output.success(f"Server {server} removed from load balancer '{name}'")
    if c.output.json_mode:
        c.output.raw_json(result)


@app.command("add-service")
def add_service(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Load balancer name")],
    protocol: Annotated[str, typer.Option("--protocol", help="Protocol (http, https, tcp)")],
    listen_port: Annotated[int, typer.Option("--listen-port", help="Listen port (1-65535)")],
    dest_port: Annotated[int, typer.Option("--dest-port", help="Destination port (1-65535)")],
    health_check_path: Annotated[str | None, typer.Option("--health-check-path", help="HTTP health check path")] = None,
) -> None:
    """Add a service (listener) to a load balancer."""
    c: AppContext = ctx.obj
    lb = _resolve_lb(c, name)
    lb_id = lb["id"]

    payload: dict = {
        "protocol": protocol,
        "listen_port": listen_port,
        "destination_port": dest_port,
        "proxyprotocol": False,
    }

    # Build health check
    if protocol in ("http", "https"):
        hc_proto = "http" if protocol == "http" else "https"
        hc_path = health_check_path or "/"
        payload["health_check"] = {
            "protocol": hc_proto,
            "port": dest_port,
            "interval": 15,
            "timeout": 10,
            "retries": 3,
            "http": {
                "path": hc_path,
                "status_codes": ["2??", "3??"],
            },
        }
    else:
        # TCP health check
        payload["health_check"] = {
            "protocol": "tcp",
            "port": dest_port,
            "interval": 15,
            "timeout": 10,
            "retries": 3,
        }

    result = c.client.post(f"/load_balancers/{lb_id}/actions/add_service", json=payload)
    c.output.success(f"Service {protocol}:{listen_port} -> {dest_port} added to load balancer '{name}'")
    if c.output.json_mode:
        c.output.raw_json(result)


@app.command("remove-service")
def remove_service(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Load balancer name")],
    listen_port: Annotated[int, typer.Option("--listen-port", help="Listen port of service to remove")],
) -> None:
    """Remove a service (listener) from a load balancer."""
    c: AppContext = ctx.obj
    lb = _resolve_lb(c, name)
    lb_id = lb["id"]
    payload = {"listen_port": listen_port}
    result = c.client.post(f"/load_balancers/{lb_id}/actions/delete_service", json=payload)
    c.output.success(f"Service on port {listen_port} removed from load balancer '{name}'")
    if c.output.json_mode:
        c.output.raw_json(result)
