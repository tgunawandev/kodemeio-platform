"""IP address management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_hetzner.core.callbacks import AppContext
from kctl_hetzner.core.utils import parse_labels

app = typer.Typer(help="Manage Hetzner Cloud IP addresses.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all floating and primary IPs."""
    c: AppContext = ctx.obj

    floating_ips = c.client.get_all("/floating_ips", "floating_ips")
    primary_ips = c.client.get_all("/primary_ips", "primary_ips")

    rows = []
    all_ips = []

    for ip in floating_ips:
        server_id = ip.get("server")
        server_str = str(server_id) if server_id else "-"
        rows.append(
            [
                str(ip.get("id", "")),
                "floating",
                ip.get("type", ""),
                ip.get("ip", ""),
                ip.get("home_location", {}).get("name", "-"),
                server_str,
            ]
        )
        all_ips.append({**ip, "_kind": "floating"})

    for ip in primary_ips:
        assignee = ip.get("assignee_id")
        assignee_str = str(assignee) if assignee else "-"
        rows.append(
            [
                str(ip.get("id", "")),
                "primary",
                ip.get("type", ""),
                ip.get("ip", ""),
                ip.get("datacenter", {}).get("location", {}).get("name", "-"),
                assignee_str,
            ]
        )
        all_ips.append({**ip, "_kind": "primary"})

    c.output.table(
        "IP Addresses",
        [("ID", "dim"), ("Kind", "cyan"), ("Type", ""), ("IP", "green"), ("Location", ""), ("Assigned To", "")],
        rows,
        data_for_json=all_ips,
    )


# ---------------------------------------------------------------------------
# Floating IP operations
# ---------------------------------------------------------------------------


@app.command("get")
def get_floating(
    ctx: typer.Context,
    ip_id: Annotated[int, typer.Argument(help="Floating IP ID")],
) -> None:
    """Get details of a floating IP."""
    c: AppContext = ctx.obj
    data = c.client.get(f"/floating_ips/{ip_id}")
    fip = data.get("floating_ip", {})
    if not fip:
        c.output.error(f"Floating IP {ip_id} not found")
        raise typer.Exit(1)

    server_id = fip.get("server")
    rdns = fip.get("dns_ptr", [])
    rdns_strs = ", ".join(f"{e.get('ip', '')} -> {e.get('dns_ptr', '')}" for e in rdns) if rdns else "-"
    labels = fip.get("labels", {})
    labels_str = ", ".join(f"{k}={v}" for k, v in labels.items()) if labels else "-"

    sections = [
        (
            "Floating IP",
            [
                ("ID", str(fip.get("id", ""))),
                ("IP", fip.get("ip", "")),
                ("Type", fip.get("type", "")),
                ("Name", fip.get("name", "") or "-"),
                ("Description", fip.get("description", "") or "-"),
                ("Location", fip.get("home_location", {}).get("name", "-")),
                ("Server", str(server_id) if server_id else "-"),
                ("Blocked", str(fip.get("blocked", False))),
                ("Labels", labels_str),
                ("rDNS", rdns_strs),
                ("Created", fip.get("created", "")),
            ],
        )
    ]
    c.output.detail(f"Floating IP: {ip_id}", sections, data_for_json=fip)


@app.command("create-floating")
def create_floating(
    ctx: typer.Context,
    ip_type: Annotated[str, typer.Option("--type", help="IP type: ipv4 or ipv6")],
    location: Annotated[str, typer.Option("--location", help="Location (e.g. fsn1, nbg1, hel1)")],
    server: Annotated[int | None, typer.Option("--server", help="Server ID to assign to")] = None,
    description: Annotated[str | None, typer.Option("--description", help="Description")] = None,
    name: Annotated[str | None, typer.Option("--name", help="Name for the floating IP")] = None,
) -> None:
    """Create a new floating IP."""
    c: AppContext = ctx.obj

    if ip_type not in ("ipv4", "ipv6"):
        c.output.error("--type must be 'ipv4' or 'ipv6'")
        raise typer.Exit(1)

    payload: dict = {"type": ip_type, "home_location": location}
    if server:
        payload["server"] = server
    if description:
        payload["description"] = description
    if name:
        payload["name"] = name

    result = c.client.post("/floating_ips", json=payload)
    fip = result.get("floating_ip", {})
    c.output.success(f"Floating IP created: {fip.get('ip', '')} (ID: {fip.get('id')}, Type: {ip_type})")
    if c.output.json_mode:
        c.output.raw_json(result)


@app.command("update-floating")
def update_floating(
    ctx: typer.Context,
    ip_id: Annotated[int, typer.Argument(help="Floating IP ID")],
    name: Annotated[str | None, typer.Option("--name", help="New name")] = None,
    description: Annotated[str | None, typer.Option("--description", help="New description")] = None,
    labels: Annotated[str | None, typer.Option("--labels", help="Labels as key=val,key=val")] = None,
) -> None:
    """Update a floating IP (name, description, labels)."""
    c: AppContext = ctx.obj
    payload: dict = {}
    if name is not None:
        payload["name"] = name
    if description is not None:
        payload["description"] = description
    if labels is not None:
        payload["labels"] = parse_labels(labels)
    if not payload:
        c.output.error("Provide at least one option to update (--name, --description, --labels)")
        raise typer.Exit(1)
    result = c.client.put(f"/floating_ips/{ip_id}", json=payload)
    c.output.success(f"Floating IP {ip_id} updated")
    if c.output.json_mode:
        c.output.raw_json(result)


@app.command("delete-floating")
def delete_floating(
    ctx: typer.Context,
    ip_id: Annotated[int, typer.Argument(help="Floating IP ID")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete a floating IP."""
    c: AppContext = ctx.obj
    if not force:
        typer.confirm(f"Delete floating IP {ip_id}?", abort=True)
    c.client.delete(f"/floating_ips/{ip_id}")
    c.output.success(f"Floating IP {ip_id} deleted")


@app.command("assign")
def assign_floating(
    ctx: typer.Context,
    ip_id: Annotated[int, typer.Argument(help="Floating IP ID")],
    server: Annotated[int, typer.Option("--server", help="Server ID to assign to")],
) -> None:
    """Assign a floating IP to a server."""
    c: AppContext = ctx.obj
    result = c.client.post(f"/floating_ips/{ip_id}/actions/assign", json={"server": server})
    c.output.success(f"Floating IP {ip_id} assigned to server {server}")
    if c.output.json_mode:
        c.output.raw_json(result)


@app.command("unassign")
def unassign_floating(
    ctx: typer.Context,
    ip_id: Annotated[int, typer.Argument(help="Floating IP ID")],
) -> None:
    """Unassign a floating IP from its server."""
    c: AppContext = ctx.obj
    result = c.client.post(f"/floating_ips/{ip_id}/actions/unassign")
    c.output.success(f"Floating IP {ip_id} unassigned")
    if c.output.json_mode:
        c.output.raw_json(result)


# ---------------------------------------------------------------------------
# Primary IP operations
# ---------------------------------------------------------------------------


@app.command("get-primary")
def get_primary(
    ctx: typer.Context,
    ip_id: Annotated[int, typer.Argument(help="Primary IP ID")],
) -> None:
    """Get details of a primary IP."""
    c: AppContext = ctx.obj
    data = c.client.get(f"/primary_ips/{ip_id}")
    pip = data.get("primary_ip", {})
    if not pip:
        c.output.error(f"Primary IP {ip_id} not found")
        raise typer.Exit(1)

    assignee = pip.get("assignee_id")
    rdns = pip.get("dns_ptr", [])
    rdns_strs = ", ".join(f"{e.get('ip', '')} -> {e.get('dns_ptr', '')}" for e in rdns) if rdns else "-"
    labels = pip.get("labels", {})
    labels_str = ", ".join(f"{k}={v}" for k, v in labels.items()) if labels else "-"

    sections = [
        (
            "Primary IP",
            [
                ("ID", str(pip.get("id", ""))),
                ("IP", pip.get("ip", "")),
                ("Type", pip.get("type", "")),
                ("Name", pip.get("name", "") or "-"),
                ("Datacenter", pip.get("datacenter", {}).get("name", "-")),
                ("Assignee ID", str(assignee) if assignee else "-"),
                ("Assignee Type", pip.get("assignee_type", "-")),
                ("Auto Delete", str(pip.get("auto_delete", False))),
                ("Blocked", str(pip.get("blocked", False))),
                ("Labels", labels_str),
                ("rDNS", rdns_strs),
                ("Created", pip.get("created", "")),
            ],
        )
    ]
    c.output.detail(f"Primary IP: {ip_id}", sections, data_for_json=pip)


@app.command("create-primary")
def create_primary(
    ctx: typer.Context,
    ip_type: Annotated[str, typer.Option("--type", help="IP type: ipv4 or ipv6")],
    assignee_type: Annotated[str, typer.Option("--assignee-type", help="Assignee type (e.g. server)")] = "server",
    assignee_id: Annotated[int | None, typer.Option("--assignee-id", help="Assignee (server) ID")] = None,
    datacenter: Annotated[str | None, typer.Option("--datacenter", help="Datacenter (e.g. fsn1-dc14)")] = None,
    name: Annotated[str | None, typer.Option("--name", help="Name for the primary IP")] = None,
    auto_delete: Annotated[bool, typer.Option("--auto-delete/--no-auto-delete", help="Auto-delete with server")] = True,
) -> None:
    """Create a new primary IP."""
    c: AppContext = ctx.obj

    if ip_type not in ("ipv4", "ipv6"):
        c.output.error("--type must be 'ipv4' or 'ipv6'")
        raise typer.Exit(1)

    payload: dict = {
        "type": ip_type,
        "assignee_type": assignee_type,
        "auto_delete": auto_delete,
    }
    if assignee_id:
        payload["assignee_id"] = assignee_id
    if datacenter:
        payload["datacenter"] = datacenter
    if name:
        payload["name"] = name

    result = c.client.post("/primary_ips", json=payload)
    pip = result.get("primary_ip", {})
    c.output.success(f"Primary IP created: {pip.get('ip', '')} (ID: {pip.get('id')}, Type: {ip_type})")
    if c.output.json_mode:
        c.output.raw_json(result)


@app.command("update-primary")
def update_primary(
    ctx: typer.Context,
    ip_id: Annotated[int, typer.Argument(help="Primary IP ID")],
    name: Annotated[str | None, typer.Option("--name", help="New name")] = None,
    auto_delete: Annotated[
        bool | None, typer.Option("--auto-delete/--no-auto-delete", help="Auto-delete with server")
    ] = None,
    labels: Annotated[str | None, typer.Option("--labels", help="Labels as key=val,key=val")] = None,
) -> None:
    """Update a primary IP (name, auto-delete, labels)."""
    c: AppContext = ctx.obj
    payload: dict = {}
    if name is not None:
        payload["name"] = name
    if auto_delete is not None:
        payload["auto_delete"] = auto_delete
    if labels is not None:
        payload["labels"] = parse_labels(labels)

    if not payload:
        c.output.error("Provide at least one option to update (--name, --auto-delete, --labels)")
        raise typer.Exit(1)

    result = c.client.put(f"/primary_ips/{ip_id}", json=payload)
    c.output.success(f"Primary IP {ip_id} updated")
    if c.output.json_mode:
        c.output.raw_json(result)


@app.command("delete-primary")
def delete_primary(
    ctx: typer.Context,
    ip_id: Annotated[int, typer.Argument(help="Primary IP ID")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete a primary IP."""
    c: AppContext = ctx.obj
    if not force:
        typer.confirm(f"Delete primary IP {ip_id}?", abort=True)
    c.client.delete(f"/primary_ips/{ip_id}")
    c.output.success(f"Primary IP {ip_id} deleted")
