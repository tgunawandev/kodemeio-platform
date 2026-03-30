"""Reverse DNS management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_hetzner.core.callbacks import AppContext

app = typer.Typer(help="Manage reverse DNS entries on Hetzner Cloud resources.")

# Mapping of resource types to their API endpoints and response keys
_RESOURCE_MAP: dict[str, tuple[str, str]] = {
    "server": ("servers", "server"),
    "floating_ip": ("floating_ips", "floating_ip"),
    "primary_ip": ("primary_ips", "primary_ip"),
    "load_balancer": ("load_balancers", "load_balancer"),
}


def _resolve_resource(resource_type: str) -> tuple[str, str]:
    """Return (endpoint_collection, response_key) for a resource type."""
    if resource_type not in _RESOURCE_MAP:
        valid = ", ".join(sorted(_RESOURCE_MAP.keys()))
        raise typer.BadParameter(f"Unknown resource type '{resource_type}'. Valid types: {valid}")
    return _RESOURCE_MAP[resource_type]


def _get_dns_entries(resource: dict, resource_type: str) -> list[dict]:
    """Extract DNS pointer entries from a resource."""
    if resource_type == "server":
        # Servers have rDNS in public_net.ipv4.dns_ptr and public_net.ipv6.dns_ptr
        public_net = resource.get("public_net", {})
        entries = []
        ipv4 = public_net.get("ipv4", {})
        if ipv4 and ipv4.get("dns_ptr"):
            entries.append({"ip": ipv4.get("ip", ""), "dns_ptr": ipv4.get("dns_ptr", "")})
        ipv6 = public_net.get("ipv6", {})
        for ptr in ipv6.get("dns_ptr", []):
            entries.append({"ip": ptr.get("ip", ""), "dns_ptr": ptr.get("dns_ptr", "")})
        return entries
    else:
        # Floating IPs, Primary IPs, Load Balancers have dns_ptr as a list
        return resource.get("dns_ptr", [])


@app.command()
def get(
    ctx: typer.Context,
    resource_type: Annotated[
        str, typer.Argument(help="Resource type (server, floating_ip, primary_ip, load_balancer)")
    ],
    resource_id: Annotated[int, typer.Argument(help="Resource ID")],
) -> None:
    """Show reverse DNS entries for a resource."""
    c: AppContext = ctx.obj
    endpoint, key = _resolve_resource(resource_type)
    data = c.client.get(f"/{endpoint}/{resource_id}")
    resource = data.get(key, {})
    if not resource:
        c.output.error(f"{resource_type} {resource_id} not found")
        raise typer.Exit(1)

    entries = _get_dns_entries(resource, resource_type)

    if c.output.json_mode:
        c.output.raw_json(entries)
        return

    rows = []
    for e in entries:
        rows.append([e.get("ip", ""), e.get("dns_ptr", "") or "-"])

    if not rows:
        c.output.info(f"No rDNS entries on {resource_type} {resource_id}")
        return

    c.output.table(
        f"Reverse DNS for {resource_type} {resource_id}",
        [("IP", "cyan"), ("DNS Pointer", "green")],
        rows,
        data_for_json=entries,
    )


@app.command("set")
def set_rdns(
    ctx: typer.Context,
    resource_type: Annotated[
        str, typer.Argument(help="Resource type (server, floating_ip, primary_ip, load_balancer)")
    ],
    resource_id: Annotated[int, typer.Argument(help="Resource ID")],
    ip: Annotated[str, typer.Option("--ip", help="IP address to set rDNS for")],
    dns_ptr: Annotated[str, typer.Option("--dns-ptr", help="DNS pointer hostname")],
) -> None:
    """Set a reverse DNS entry for a resource."""
    c: AppContext = ctx.obj
    endpoint, _key = _resolve_resource(resource_type)
    payload = {"ip": ip, "dns_ptr": dns_ptr}
    result = c.client.post(f"/{endpoint}/{resource_id}/actions/change_dns_ptr", json=payload)
    c.output.success(f"rDNS set: {ip} -> {dns_ptr} on {resource_type} {resource_id}")
    if c.output.json_mode:
        c.output.raw_json(result)


@app.command("delete")
def delete_rdns(
    ctx: typer.Context,
    resource_type: Annotated[
        str, typer.Argument(help="Resource type (server, floating_ip, primary_ip, load_balancer)")
    ],
    resource_id: Annotated[int, typer.Argument(help="Resource ID")],
    ip: Annotated[str, typer.Option("--ip", help="IP address to remove rDNS for")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete a reverse DNS entry (set to null)."""
    c: AppContext = ctx.obj
    if not force:
        typer.confirm(f"Delete rDNS for {ip} on {resource_type} {resource_id}?", abort=True)
    endpoint, _key = _resolve_resource(resource_type)
    # Setting dns_ptr to null removes the rDNS entry
    payload = {"ip": ip, "dns_ptr": None}
    result = c.client.post(f"/{endpoint}/{resource_id}/actions/change_dns_ptr", json=payload)
    c.output.success(f"rDNS deleted for {ip} on {resource_type} {resource_id}")
    if c.output.json_mode:
        c.output.raw_json(result)
