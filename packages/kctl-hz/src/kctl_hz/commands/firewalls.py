"""Firewall management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_hz.core.callbacks import AppContext
from kctl_hz.core.utils import parse_labels

app = typer.Typer(help="Manage Hetzner Cloud firewalls.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all firewalls."""
    c: AppContext = ctx.obj
    firewalls = c.client.get_all("/firewalls", "firewalls")
    rows = []
    for fw in firewalls:
        rules = fw.get("rules", [])
        applied = fw.get("applied_to", [])
        rows.append(
            [
                str(fw.get("id", "")),
                fw.get("name", ""),
                str(len(rules)),
                str(len(applied)),
            ]
        )
    c.output.table(
        "Firewalls",
        [("ID", "dim"), ("Name", "cyan"), ("Rules", ""), ("Applied To", "")],
        rows,
        data_for_json=firewalls,
    )


@app.command()
def get(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Firewall name")],
) -> None:
    """Get firewall details with rules."""
    c: AppContext = ctx.obj
    data = c.client.get("/firewalls", params={"name": name})
    items = data.get("firewalls", [])
    if not items:
        c.output.error(f"Firewall '{name}' not found")
        raise typer.Exit(1)
    fw = items[0]
    rules = fw.get("rules", [])
    applied = fw.get("applied_to", [])

    sections = [
        (
            "Firewall",
            [
                ("Name", fw.get("name", "")),
                ("ID", str(fw.get("id", ""))),
                ("Created", fw.get("created", "")),
                ("Rules", str(len(rules))),
                ("Applied To", str(len(applied))),
            ],
        )
    ]
    for i, rule in enumerate(rules, 1):
        direction = rule.get("direction", "")
        protocol = rule.get("protocol", "")
        port = rule.get("port", "any")
        source_ips = ", ".join(rule.get("source_ips", [])) or "-"
        dest_ips = ", ".join(rule.get("destination_ips", [])) or "-"
        sections.append(
            (
                f"Rule {i}",
                [
                    ("Direction", direction),
                    ("Protocol", protocol),
                    ("Port", str(port)),
                    ("Source IPs", source_ips if direction == "in" else "-"),
                    ("Dest IPs", dest_ips if direction == "out" else "-"),
                ],
            )
        )
    for i, target in enumerate(applied, 1):
        target_type = target.get("type", "")
        if target_type == "server":
            server_info = target.get("server", {})
            server_id = server_info.get("id", "?")
            sections.append(
                (
                    f"Applied To {i}",
                    [
                        ("Type", target_type),
                        ("Server ID", str(server_id)),
                    ],
                )
            )
    c.output.detail(f"Firewall: {name}", sections, data_for_json=fw)


@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Firewall name")],
) -> None:
    """Create a new firewall."""
    c: AppContext = ctx.obj
    result = c.client.post("/firewalls", json={"name": name, "rules": []})
    fw = result.get("firewall", {})
    c.output.success(f"Firewall '{fw.get('name')}' created (ID: {fw.get('id')})")
    if c.output.json_mode:
        c.output.raw_json(result)


@app.command()
def delete(
    ctx: typer.Context,
    firewall_id: Annotated[int, typer.Argument(help="Firewall ID")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete a firewall."""
    c: AppContext = ctx.obj
    if not force:
        typer.confirm(f"Delete firewall {firewall_id}?", abort=True)
    c.client.delete(f"/firewalls/{firewall_id}")
    c.output.success(f"Firewall {firewall_id} deleted")


@app.command()
def update(
    ctx: typer.Context,
    firewall_id: Annotated[int, typer.Argument(help="Firewall ID")],
    name: Annotated[str | None, typer.Option("--name", help="New firewall name")] = None,
    labels: Annotated[str | None, typer.Option("--labels", help="Labels as key=val,key=val")] = None,
) -> None:
    """Update a firewall (name, labels)."""
    c: AppContext = ctx.obj
    payload: dict = {}
    if name is not None:
        payload["name"] = name
    if labels is not None:
        payload["labels"] = parse_labels(labels)
    if not payload:
        c.output.error("Provide at least one option to update (--name, --labels)")
        raise typer.Exit(1)
    result = c.client.put(f"/firewalls/{firewall_id}", json=payload)
    c.output.success(f"Firewall {firewall_id} updated")
    if c.output.json_mode:
        c.output.raw_json(result)


@app.command("add-rule")
def add_rule(
    ctx: typer.Context,
    firewall_id: Annotated[int, typer.Argument(help="Firewall ID")],
    direction: Annotated[str, typer.Option("--direction", help="Rule direction: in or out")],
    protocol: Annotated[str, typer.Option("--protocol", help="Protocol: tcp, udp, or icmp")],
    port: Annotated[str | None, typer.Option("--port", help="Port or port range (e.g. 22, 80-443)")] = None,
    source_ips: Annotated[
        str | None, typer.Option("--source-ips", help="Comma-separated source CIDRs (for inbound)")
    ] = None,
    destination_ips: Annotated[
        str | None, typer.Option("--destination-ips", help="Comma-separated destination CIDRs (for outbound)")
    ] = None,
    description: Annotated[str | None, typer.Option("--description", help="Rule description")] = None,
) -> None:
    """Add a rule to a firewall (appends to existing rules)."""
    c: AppContext = ctx.obj

    # Validate direction
    if direction not in ("in", "out"):
        c.output.error("--direction must be 'in' or 'out'")
        raise typer.Exit(1)

    # Validate protocol
    if protocol not in ("tcp", "udp", "icmp"):
        c.output.error("--protocol must be 'tcp', 'udp', or 'icmp'")
        raise typer.Exit(1)

    # Port is required for tcp/udp
    if protocol != "icmp" and not port:
        c.output.error("--port is required for tcp/udp protocols")
        raise typer.Exit(1)

    # Validate IP lists based on direction
    if direction == "in" and not source_ips:
        c.output.error("--source-ips is required for inbound rules")
        raise typer.Exit(1)
    if direction == "out" and not destination_ips:
        c.output.error("--destination-ips is required for outbound rules")
        raise typer.Exit(1)

    # Fetch existing firewall to get current rules
    data = c.client.get(f"/firewalls/{firewall_id}")
    fw = data.get("firewall", {})
    existing_rules = fw.get("rules", [])

    # Build the new rule
    new_rule: dict = {
        "direction": direction,
        "protocol": protocol,
    }
    if port and protocol != "icmp":
        new_rule["port"] = port
    if description:
        new_rule["description"] = description
    if direction == "in":
        new_rule["source_ips"] = [ip.strip() for ip in (source_ips or "").split(",") if ip.strip()]
    else:
        new_rule["destination_ips"] = [ip.strip() for ip in (destination_ips or "").split(",") if ip.strip()]

    # Append and set all rules
    updated_rules = existing_rules + [new_rule]
    result = c.client.post(f"/firewalls/{firewall_id}/actions/set_rules", json={"rules": updated_rules})
    c.output.success(
        f"Rule added to firewall {firewall_id}: {direction}bound {protocol}{f' port {port}' if port else ''}"
    )
    if c.output.json_mode:
        c.output.raw_json(result)


@app.command("remove-rule")
def remove_rule(
    ctx: typer.Context,
    firewall_id: Annotated[int, typer.Argument(help="Firewall ID")],
    direction: Annotated[str, typer.Option("--direction", help="Rule direction to match: in or out")],
    protocol: Annotated[str, typer.Option("--protocol", help="Protocol to match: tcp, udp, or icmp")],
    port: Annotated[str | None, typer.Option("--port", help="Port to match (optional)")] = None,
) -> None:
    """Remove a matching rule from a firewall."""
    c: AppContext = ctx.obj

    if direction not in ("in", "out"):
        c.output.error("--direction must be 'in' or 'out'")
        raise typer.Exit(1)

    # Fetch existing firewall rules
    data = c.client.get(f"/firewalls/{firewall_id}")
    fw = data.get("firewall", {})
    existing_rules = fw.get("rules", [])

    # Filter out matching rules
    updated_rules = []
    for rule in existing_rules:
        matches = rule.get("direction") == direction and rule.get("protocol") == protocol
        if port:
            matches = matches and rule.get("port") == port
        if not matches:
            updated_rules.append(rule)

    removed_count = len(existing_rules) - len(updated_rules)
    if removed_count == 0:
        c.output.warn(
            f"No matching rule found (direction={direction}, protocol={protocol}{f', port={port}' if port else ''})"
        )
        raise typer.Exit(0)

    result = c.client.post(f"/firewalls/{firewall_id}/actions/set_rules", json={"rules": updated_rules})
    c.output.success(f"Removed {removed_count} rule(s) from firewall {firewall_id}")
    if c.output.json_mode:
        c.output.raw_json(result)


@app.command("apply")
def apply_to_server(
    ctx: typer.Context,
    firewall_id: Annotated[int, typer.Argument(help="Firewall ID")],
    server: Annotated[int, typer.Option("--server", help="Server ID to apply firewall to")],
) -> None:
    """Apply a firewall to a server."""
    c: AppContext = ctx.obj
    payload = {"apply_to": [{"type": "server", "server": {"id": server}}]}
    result = c.client.post(f"/firewalls/{firewall_id}/actions/apply_to_resources", json=payload)
    c.output.success(f"Firewall {firewall_id} applied to server {server}")
    if c.output.json_mode:
        c.output.raw_json(result)


@app.command("remove-from")
def remove_from_server(
    ctx: typer.Context,
    firewall_id: Annotated[int, typer.Argument(help="Firewall ID")],
    server: Annotated[int, typer.Option("--server", help="Server ID to remove firewall from")],
) -> None:
    """Remove a firewall from a server."""
    c: AppContext = ctx.obj
    payload = {"remove_from": [{"type": "server", "server": {"id": server}}]}
    result = c.client.post(f"/firewalls/{firewall_id}/actions/remove_from_resources", json=payload)
    c.output.success(f"Firewall {firewall_id} removed from server {server}")
    if c.output.json_mode:
        c.output.raw_json(result)
