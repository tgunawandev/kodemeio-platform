"""Shared resource resolution utilities.

Centralizes the pattern of looking up Hetzner Cloud resources by name or ID,
eliminating duplication across command modules.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer

if TYPE_CHECKING:
    from kctl_hetzner.core.client import HetznerCloudClient, HetznerDnsClient
    from kctl_hetzner.core.output import Output


def resolve_resource(
    client: HetznerCloudClient,
    endpoint: str,
    key: str,
    identifier: str,
    *,
    search_param: str = "name",
    label: str | None = None,
    output: Output | None = None,
) -> dict:
    """Resolve a Hetzner Cloud resource by name or numeric ID.

    If *identifier* is purely digits, fetches by ``/{endpoint}/{id}``.
    Otherwise searches via ``?{search_param}={identifier}``.

    Returns the resource dict or calls ``typer.Exit(1)`` if not found.
    """
    display = label or key.rstrip("s").title()

    if identifier.isdigit():
        from kctl_hetzner.core.exceptions import APIError

        try:
            data = client.get(f"/{endpoint}/{identifier}")
        except APIError as exc:
            if output:
                output.error(f"{display} not found: {identifier}")
            else:
                typer.echo(f"{display} not found: {identifier}", err=True)
            raise typer.Exit(1) from exc
        # Hetzner returns single resources under the singular key (e.g. "server" for /servers/123)
        resource = data.get(key.rstrip("s"))
        if resource is None:
            if output:
                output.error(f"{display} not found: {identifier}")
            else:
                typer.echo(f"{display} not found: {identifier}", err=True)
            raise typer.Exit(1)
        return resource

    # Search by name
    data = client.get(f"/{endpoint}", params={search_param: identifier})
    items = data.get(key, [])
    if not items:
        if output:
            output.error(f"{display} '{identifier}' not found")
        else:
            typer.echo(f"{display} '{identifier}' not found", err=True)
        raise typer.Exit(1)
    return items[0]


def resolve_server(
    client: HetznerCloudClient,
    name: str,
    output: Output | None = None,
) -> dict:
    """Resolve a server by name or ID."""
    return resolve_resource(client, "servers", "servers", name, label="Server", output=output)


def resolve_volume(
    client: HetznerCloudClient,
    identifier: str,
    output: Output | None = None,
) -> dict:
    """Resolve a volume by name or ID."""
    return resolve_resource(client, "volumes", "volumes", identifier, label="Volume", output=output)


def resolve_firewall(
    client: HetznerCloudClient,
    identifier: str,
    output: Output | None = None,
) -> dict:
    """Resolve a firewall by name or ID."""
    return resolve_resource(client, "firewalls", "firewalls", identifier, label="Firewall", output=output)


def resolve_network(
    client: HetznerCloudClient,
    identifier: str,
    output: Output | None = None,
) -> dict:
    """Resolve a network by name or ID."""
    return resolve_resource(client, "networks", "networks", identifier, label="Network", output=output)


def resolve_load_balancer(
    client: HetznerCloudClient,
    identifier: str,
    output: Output | None = None,
) -> dict:
    """Resolve a load balancer by name or ID."""
    return resolve_resource(
        client, "load_balancers", "load_balancers", identifier, label="Load Balancer", output=output
    )


def resolve_ssh_key(
    client: HetznerCloudClient,
    identifier: str,
    output: Output | None = None,
) -> dict:
    """Resolve an SSH key by name or ID."""
    return resolve_resource(client, "ssh_keys", "ssh_keys", identifier, label="SSH Key", output=output)


def resolve_image(
    client: HetznerCloudClient,
    identifier: str,
    output: Output | None = None,
) -> dict:
    """Resolve an image by name or ID."""
    if identifier.isdigit():
        return resolve_resource(client, "images", "images", identifier, label="Image", output=output)
    # Images use description for search, not name
    data = client.get("/images", params={"name": identifier})
    items = data.get("images", [])
    if not items:
        if output:
            output.error(f"Image '{identifier}' not found")
        else:
            typer.echo(f"Image '{identifier}' not found", err=True)
        raise typer.Exit(1)
    return items[0]


def resolve_dns_zone_id(
    dns_client: HetznerDnsClient,
    zone_name: str,
    output: Output | None = None,
) -> str:
    """Resolve a DNS zone name to its zone ID.

    Returns the zone ID string or calls ``typer.Exit(1)`` if not found.
    """
    data = dns_client.get("/zones", params={"name": zone_name})
    zones = data.get("zones", [])
    if not zones:
        if output:
            output.error(f"DNS zone '{zone_name}' not found")
        else:
            typer.echo(f"DNS zone '{zone_name}' not found", err=True)
        raise typer.Exit(1)
    return zones[0]["id"]
