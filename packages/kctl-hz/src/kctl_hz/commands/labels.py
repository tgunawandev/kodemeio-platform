"""Label management helper commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_hetzner.core.callbacks import AppContext

app = typer.Typer(help="Manage labels on Hetzner Cloud resources.")

# Mapping of user-facing resource types to API endpoints and response keys
_RESOURCE_MAP: dict[str, tuple[str, str]] = {
    "server": ("servers", "server"),
    "volume": ("volumes", "volume"),
    "network": ("networks", "network"),
    "firewall": ("firewalls", "firewall"),
    "floating_ip": ("floating_ips", "floating_ip"),
    "primary_ip": ("primary_ips", "primary_ip"),
    "image": ("images", "image"),
    "ssh_key": ("ssh_keys", "ssh_key"),
    "load_balancer": ("load_balancers", "load_balancer"),
    "placement_group": ("placement_groups", "placement_group"),
}


def _resolve_resource(resource_type: str) -> tuple[str, str]:
    """Return (endpoint_collection, response_key) for a resource type."""
    if resource_type not in _RESOURCE_MAP:
        valid = ", ".join(sorted(_RESOURCE_MAP.keys()))
        raise typer.BadParameter(f"Unknown resource type '{resource_type}'. Valid types: {valid}")
    return _RESOURCE_MAP[resource_type]


@app.command("list")
def list_labels(
    ctx: typer.Context,
    resource_type: Annotated[str, typer.Argument(help="Resource type (e.g. server, volume, network)")],
    resource_id: Annotated[int, typer.Argument(help="Resource ID")],
) -> None:
    """Show labels on a resource."""
    c: AppContext = ctx.obj
    endpoint, key = _resolve_resource(resource_type)
    data = c.client.get(f"/{endpoint}/{resource_id}")
    resource = data.get(key, {})
    if not resource:
        c.output.error(f"{resource_type} {resource_id} not found")
        raise typer.Exit(1)

    labels = resource.get("labels", {})

    if c.output.json_mode:
        c.output.raw_json(labels)
        return

    rows = []
    for k, v in labels.items():
        rows.append([k, v])

    if not rows:
        c.output.info(f"No labels on {resource_type} {resource_id}")
        return

    c.output.table(
        f"Labels on {resource_type} {resource_id}",
        [("Key", "cyan"), ("Value", "")],
        rows,
        data_for_json=labels,
    )


@app.command("set")
def set_labels(
    ctx: typer.Context,
    resource_type: Annotated[str, typer.Argument(help="Resource type (e.g. server, volume, network)")],
    resource_id: Annotated[int, typer.Argument(help="Resource ID")],
    labels: Annotated[str, typer.Option("--labels", help="Comma-separated key=value pairs (e.g. env=prod,team=ops)")],
) -> None:
    """Set labels on a resource (merges with existing labels)."""
    c: AppContext = ctx.obj
    endpoint, key = _resolve_resource(resource_type)

    # Fetch current labels
    data = c.client.get(f"/{endpoint}/{resource_id}")
    resource = data.get(key, {})
    if not resource:
        c.output.error(f"{resource_type} {resource_id} not found")
        raise typer.Exit(1)

    current_labels = dict(resource.get("labels", {}))

    # Parse and merge new labels
    for pair in labels.split(","):
        pair = pair.strip()
        if "=" not in pair:
            c.output.error(f"Invalid label format: '{pair}'. Expected key=value")
            raise typer.Exit(1)
        k, v = pair.split("=", 1)
        current_labels[k.strip()] = v.strip()

    result = c.client.put(f"/{endpoint}/{resource_id}", json={"labels": current_labels})
    c.output.success(f"Labels updated on {resource_type} {resource_id}")
    if c.output.json_mode:
        c.output.raw_json(result)


@app.command("remove")
def remove_label(
    ctx: typer.Context,
    resource_type: Annotated[str, typer.Argument(help="Resource type (e.g. server, volume, network)")],
    resource_id: Annotated[int, typer.Argument(help="Resource ID")],
    key: Annotated[str, typer.Option("--key", help="Label key to remove")],
) -> None:
    """Remove a label from a resource."""
    c: AppContext = ctx.obj
    endpoint, resp_key = _resolve_resource(resource_type)

    # Fetch current labels
    data = c.client.get(f"/{endpoint}/{resource_id}")
    resource = data.get(resp_key, {})
    if not resource:
        c.output.error(f"{resource_type} {resource_id} not found")
        raise typer.Exit(1)

    current_labels = dict(resource.get("labels", {}))

    if key not in current_labels:
        c.output.warn(f"Label '{key}' not found on {resource_type} {resource_id}")
        raise typer.Exit(0)

    del current_labels[key]

    result = c.client.put(f"/{endpoint}/{resource_id}", json={"labels": current_labels})
    c.output.success(f"Label '{key}' removed from {resource_type} {resource_id}")
    if c.output.json_mode:
        c.output.raw_json(result)
