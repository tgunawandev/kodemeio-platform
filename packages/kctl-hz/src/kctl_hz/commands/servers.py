"""Server management commands."""

from __future__ import annotations

from datetime import UTC
from typing import Annotated

import typer

from kctl_hz.core.callbacks import AppContext
from kctl_hz.core.resolve import resolve_server as _resolve_server_by_id
from kctl_hz.core.utils import parse_labels

app = typer.Typer(help="Manage Hetzner Cloud servers.")


def _resolve_server(c: AppContext, name: str) -> dict:
    """Resolve server by name or numeric ID."""
    return _resolve_server_by_id(c.client, name, c.output)


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all servers."""
    c: AppContext = ctx.obj
    servers = c.client.get_all("/servers", "servers")
    rows = []
    for s in servers:
        public_net = s.get("public_net", {})
        ipv4 = public_net.get("ipv4", {}).get("ip", "-")
        rows.append(
            [
                str(s.get("id", "")),
                s.get("name", ""),
                s.get("status", ""),
                s.get("server_type", {}).get("name", ""),
                s.get("datacenter", {}).get("name", ""),
                ipv4,
            ]
        )
    c.output.table(
        "Servers",
        [("ID", "dim"), ("Name", "cyan"), ("Status", "green"), ("Type", ""), ("DC", ""), ("IPv4", "")],
        rows,
        data_for_json=servers,
    )


def _parse_price(price_str: str | None) -> float:
    if not price_str:
        return 0.0
    try:
        return float(price_str)
    except (ValueError, TypeError):
        return 0.0


_INVENTORY_SORT_KEYS = {
    "name": "name",
    "server": "name",
    "type": "type",
    "ram": "ram",
    "memory": "ram",
    "disk": "disk",
    "cpu": "vcpu",
    "vcpu": "vcpu",
    "cost": "cost",
    "status": "status",
    "location": "dc",
    "dc": "dc",
}


def _ssh_metrics(ip: str, timeout: int = 5) -> dict[str, str]:
    """Fetch live RAM and disk usage via SSH. Returns empty dict on failure."""
    import subprocess

    cmd = "free -m | awk '/^Mem:/{printf \"%d %d\", $3, $2}';echo;df -BG / | awk 'NR==2{printf \"%d %d\", $3, $2}'"
    try:
        result = subprocess.run(
            ["ssh", "-o", f"ConnectTimeout={timeout}", "-o", "StrictHostKeyChecking=no", f"root@{ip}", cmd],
            capture_output=True,
            text=True,
            timeout=timeout + 3,
        )
        if result.returncode != 0:
            return {}
        lines = result.stdout.strip().split("\n")
        if len(lines) < 2:
            return {}
        ram_parts = lines[0].split()
        disk_parts = lines[1].split()
        return {
            "ram_used_mb": int(ram_parts[0]),
            "ram_total_mb": int(ram_parts[1]),
            "disk_used_gb": int(disk_parts[0]),
            "disk_total_gb": int(disk_parts[1]),
        }
    except Exception:
        return {}


@app.command()
def inventory(
    ctx: typer.Context,
    sort: Annotated[
        str,
        typer.Option("--sort", "-s", help="Sort by: name, type, ram, disk, vcpu, cost, status, dc"),
    ] = "name",
    live: Annotated[
        bool,
        typer.Option("--live", "-l", help="Fetch live RAM/disk usage via SSH (slower)"),
    ] = False,
) -> None:
    """Server inventory: specs, cost, volumes, and status."""
    c: AppContext = ctx.obj

    servers = c.client.get_all("/servers", "servers")
    volumes = c.client.get_all("/volumes", "volumes")

    # Build volume lookup: server_id -> total GB
    vol_by_server: dict[int, int] = {}
    for v in volumes:
        sid = v.get("server")
        if sid:
            vol_by_server[sid] = vol_by_server.get(sid, 0) + v.get("size", 0)

    items: list[dict] = []
    for s in servers:
        stype = s.get("server_type", {})
        public_net = s.get("public_net", {})
        ipv4 = public_net.get("ipv4", {}).get("ip", "-")
        status = s.get("status", "unknown")
        server_id = s.get("id", 0)

        vcpu = stype.get("cores", 0)
        ram = stype.get("memory", 0)
        disk = stype.get("disk", 0)
        extra_vol = vol_by_server.get(server_id, 0)

        prices = stype.get("prices", [])
        monthly = _parse_price(prices[0].get("price_monthly", {}).get("gross", "0")) if prices else 0.0

        items.append(
            {
                "name": s.get("name", ""),
                "type": stype.get("name", ""),
                "type_desc": stype.get("description", ""),
                "vcpu": vcpu,
                "ram": ram,
                "disk": disk,
                "extra_vol": extra_vol,
                "total_disk": disk + extra_vol,
                "dc": s.get("datacenter", {}).get("name", ""),
                "location": s.get("datacenter", {}).get("location", {}).get("city", ""),
                "ipv4": ipv4,
                "status": status,
                "cost": monthly,
                "labels": s.get("labels", {}),
            }
        )

    # Fetch live metrics via SSH if requested
    if live:
        if not c.quiet:
            c.output.info("Fetching live metrics via SSH...")
        for item in items:
            if item["ipv4"] != "-" and item["status"] == "running":
                metrics = _ssh_metrics(item["ipv4"])
                item["live"] = metrics

    sort_key = _INVENTORY_SORT_KEYS.get(sort.lower(), "name")
    items.sort(key=lambda x: (x.get(sort_key, ""), x.get("name", "")))

    rows: list[list[str]] = []
    total_vcpu = 0
    total_ram = 0.0
    total_disk = 0
    total_cost = 0.0
    total_ram_used = 0
    total_disk_used = 0

    for item in items:
        status_label = "[green]running[/green]" if item["status"] == "running" else f"[red]{item['status']}[/red]"
        vol_note = f" +{item['extra_vol']}v" if item["extra_vol"] else ""

        metrics = item.get("live", {})

        if metrics:
            ram_used = metrics["ram_used_mb"] // 1024
            ram_total = metrics["ram_total_mb"] // 1024
            ram_pct = metrics["ram_used_mb"] / metrics["ram_total_mb"] * 100
            ram_color = "[red]" if ram_pct >= 85 else ("[yellow]" if ram_pct >= 70 else "[green]")
            ram_str = f"{ram_color}{ram_used}/{ram_total}GB {ram_pct:.0f}%[/{ram_color[1:]}"

            disk_used = metrics["disk_used_gb"]
            disk_total = metrics["disk_total_gb"]
            disk_pct = disk_used / disk_total * 100 if disk_total else 0
            disk_color = "[red]" if disk_pct >= 85 else ("[yellow]" if disk_pct >= 70 else "[green]")
            disk_str = f"{disk_color}{disk_used}/{disk_total}GB {disk_pct:.0f}%[/{disk_color[1:]}"

            total_ram_used += metrics["ram_used_mb"]
            total_disk_used += metrics["disk_used_gb"]
        else:
            ram_str = f"{item['ram']:.0f}GB"
            disk_str = f"{item['disk']}GB{vol_note}"

        rows.append(
            [
                item["name"],
                item["type"],
                str(item["vcpu"]),
                ram_str,
                disk_str,
                item["ipv4"],
                item["dc"],
                f"€{item['cost']:.0f}",
                status_label,
            ]
        )

        total_vcpu += item["vcpu"]
        total_ram += item["ram"]
        total_disk += item["total_disk"]
        total_cost += item["cost"]

    # Totals row
    if live and total_ram_used:
        ram_total_str = f"[bold]{total_ram_used // 1024}/{total_ram:.0f}GB[/bold]"
        disk_total_str = f"[bold]{total_disk_used}/{total_disk}GB[/bold]"
    else:
        ram_total_str = f"[bold]{total_ram:.0f}GB[/bold]"
        disk_total_str = f"[bold]{total_disk}GB[/bold]"

    rows.append(
        [
            f"[bold]TOTAL ({len(items)} servers)[/bold]",
            "",
            f"[bold]{total_vcpu}[/bold]",
            ram_total_str,
            disk_total_str,
            "",
            "",
            f"[bold]€{total_cost:.0f}[/bold]",
            "",
        ]
    )

    json_data = {
        "servers": items,
        "totals": {
            "count": len(items),
            "vcpu": total_vcpu,
            "ram_gb": total_ram,
            "disk_gb": total_disk,
            "monthly_eur": round(total_cost, 2),
        },
    }

    label = "live" if live else "specs"
    c.output.table(
        f"Server Inventory ({len(items)} servers, {label}, sorted by {sort_key})",
        [
            ("Server", "cyan"),
            ("Type", ""),
            ("vCPU", ""),
            ("RAM", "green"),
            ("Disk", "green"),
            ("IPv4", "dim"),
            ("DC", "dim"),
            ("Cost/mo", "yellow"),
            ("Status", ""),
        ],
        rows,
        data_for_json=json_data,
    )


@app.command()
def get(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Server name")],
) -> None:
    """Get server details."""
    c: AppContext = ctx.obj
    s = _resolve_server(c, name)
    public_net = s.get("public_net", {})
    sections = [
        (
            "Server",
            [
                ("Name", s.get("name", "")),
                ("ID", str(s.get("id", ""))),
                ("Status", s.get("status", "")),
                ("Type", s.get("server_type", {}).get("description", "")),
                ("Cores", str(s.get("server_type", {}).get("cores", ""))),
                ("Memory", f"{s.get('server_type', {}).get('memory', '')} GB"),
                ("Disk", f"{s.get('server_type', {}).get('disk', '')} GB"),
                ("Datacenter", s.get("datacenter", {}).get("name", "")),
                ("IPv4", public_net.get("ipv4", {}).get("ip", "-")),
                ("IPv6", public_net.get("ipv6", {}).get("ip", "-")),
                ("Created", s.get("created", "")),
            ],
        )
    ]
    c.output.detail(f"Server: {name}", sections, data_for_json=s)


@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Server name")],
    server_type: Annotated[str, typer.Option("--type", help="Server type (e.g. cx22, cx32)")] = "cx22",
    image: Annotated[str, typer.Option("--image", help="OS image")] = "ubuntu-24.04",
    location: Annotated[str, typer.Option("--location", help="Location (e.g. fsn1, nbg1, hel1)")] = "fsn1",
    ssh_keys: Annotated[list[str] | None, typer.Option("--ssh-key", help="SSH key names (repeatable)")] = None,
) -> None:
    """Create a new server."""
    c: AppContext = ctx.obj
    payload: dict = {
        "name": name,
        "server_type": server_type,
        "image": image,
        "location": location,
    }
    if ssh_keys:
        payload["ssh_keys"] = ssh_keys

    result = c.client.post("/servers", json=payload)
    server = result.get("server", {})
    ipv4 = server.get("public_net", {}).get("ipv4", {}).get("ip", "-")
    c.output.success(f"Server '{server.get('name')}' created (ID: {server.get('id')}, IPv4: {ipv4})")
    if c.output.json_mode:
        c.output.raw_json(result)


@app.command()
def delete(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Server name")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete a server."""
    c: AppContext = ctx.obj
    s = _resolve_server(c, name)
    server_id = s["id"]
    if not force:
        typer.confirm(f"Delete server '{name}' (ID: {server_id})?", abort=True)
    c.client.delete(f"/servers/{server_id}")
    c.output.success(f"Server '{name}' deleted")


def _server_action(c: AppContext, name: str, action: str, payload: dict | None = None) -> dict:
    """Execute a server action by name and return the result."""
    s = _resolve_server(c, name)
    server_id = s["id"]
    result = c.client.post(f"/servers/{server_id}/actions/{action}", json=payload)
    c.output.success(f"Server '{name}': {action} initiated")
    if c.output.json_mode:
        c.output.raw_json(result)
    return result


@app.command()
def reboot(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Server name")],
) -> None:
    """Reboot a server (soft reboot)."""
    c: AppContext = ctx.obj
    _server_action(c, name, "reboot")


@app.command()
def shutdown(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Server name")],
) -> None:
    """Gracefully shut down a server."""
    c: AppContext = ctx.obj
    _server_action(c, name, "shutdown")


@app.command("power-off")
def power_off(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Server name")],
) -> None:
    """Force power off a server."""
    c: AppContext = ctx.obj
    _server_action(c, name, "poweroff")


@app.command()
def reset(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Server name")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Hard reset a server (like pulling power)."""
    c: AppContext = ctx.obj
    if not force:
        typer.confirm(f"Hard reset server '{name}'? This is like pulling the power plug.", abort=True)
    _server_action(c, name, "reset")


@app.command()
def rebuild(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Server name")],
    image: Annotated[str, typer.Option("--image", help="Image to rebuild with")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Rebuild a server with a new image (destroys all data)."""
    c: AppContext = ctx.obj
    s = _resolve_server(c, name)
    server_id = s["id"]
    if not force:
        typer.confirm(f"Rebuild server '{name}' with image '{image}'? This destroys all data.", abort=True)
    result = c.client.post(f"/servers/{server_id}/actions/rebuild", json={"image": image})
    root_password = result.get("root_password")
    c.output.success(f"Server '{name}' rebuild initiated with image '{image}'")
    if root_password:
        c.output.warn(f"New root password: {root_password}")
    if c.output.json_mode:
        c.output.raw_json(result)


@app.command()
def resize(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Server name")],
    server_type: Annotated[str, typer.Option("--type", help="New server type (e.g. cx32)")],
    upgrade_disk: Annotated[bool, typer.Option("--upgrade-disk", help="Also upgrade disk (irreversible)")] = False,
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Resize a server to a different type. Server must be powered off."""
    c: AppContext = ctx.obj
    s = _resolve_server(c, name)
    server_id = s["id"]
    extra = " (disk upgrade is irreversible)" if upgrade_disk else ""
    if not force:
        typer.confirm(f"Resize server '{name}' to type '{server_type}'{extra}?", abort=True)
    payload = {"server_type": server_type, "upgrade_disk": upgrade_disk}
    result = c.client.post(f"/servers/{server_id}/actions/change_type", json=payload)
    c.output.success(f"Server '{name}' resize to '{server_type}' initiated")
    if c.output.json_mode:
        c.output.raw_json(result)


@app.command()
def update(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Server name")],
    new_name: Annotated[str | None, typer.Option("--name", help="New server name")] = None,
    labels: Annotated[str | None, typer.Option("--labels", help="Labels as key=val,key=val")] = None,
) -> None:
    """Update a server (name, labels)."""
    c: AppContext = ctx.obj
    s = _resolve_server(c, name)
    server_id = s["id"]
    payload: dict = {}
    if new_name is not None:
        payload["name"] = new_name
    if labels is not None:
        payload["labels"] = parse_labels(labels)
    if not payload:
        c.output.error("Provide at least one option to update (--name, --labels)")
        raise typer.Exit(1)
    result = c.client.put(f"/servers/{server_id}", json=payload)
    server = result.get("server", {})
    if new_name:
        c.output.success(f"Server '{name}' renamed to '{server.get('name', new_name)}'")
    else:
        c.output.success(f"Server '{name}' updated")
    if c.output.json_mode:
        c.output.raw_json(result)


@app.command("enable-rescue")
def enable_rescue(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Server name")],
    ssh_key: Annotated[list[str] | None, typer.Option("--ssh-key", help="SSH key names (repeatable)")] = None,
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Enable rescue mode on a server. Reboot to enter rescue system."""
    c: AppContext = ctx.obj
    s = _resolve_server(c, name)
    server_id = s["id"]
    if not force:
        typer.confirm(f"Enable rescue mode for server '{name}'?", abort=True)
    payload: dict = {"type": "linux64"}
    if ssh_key:
        # Resolve SSH key names to IDs
        all_keys = c.client.get_all("/ssh_keys", "ssh_keys")
        key_map = {k["name"]: k["id"] for k in all_keys}
        key_ids = []
        for kname in ssh_key:
            if kname not in key_map:
                c.output.error(f"SSH key '{kname}' not found")
                raise typer.Exit(1)
            key_ids.append(key_map[kname])
        payload["ssh_keys"] = key_ids
    result = c.client.post(f"/servers/{server_id}/actions/enable_rescue", json=payload)
    root_password = result.get("root_password")
    c.output.success(f"Rescue mode enabled for server '{name}'")
    if root_password:
        c.output.warn(f"Rescue root password: {root_password}")
        c.output.info("Reboot the server to enter rescue system.")
    if c.output.json_mode:
        c.output.raw_json(result)


@app.command("disable-rescue")
def disable_rescue(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Server name")],
) -> None:
    """Disable rescue mode on a server."""
    c: AppContext = ctx.obj
    _server_action(c, name, "disable_rescue")


@app.command()
def console(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Server name")],
) -> None:
    """Request a VNC console URL for a server."""
    c: AppContext = ctx.obj
    s = _resolve_server(c, name)
    server_id = s["id"]
    result = c.client.post(f"/servers/{server_id}/actions/request_console")
    wss_url = result.get("wss_url", "")
    password = result.get("password", "")
    c.output.success(f"Console ready for server '{name}'")
    if wss_url:
        c.output.info(f"Console URL: {wss_url}")
    if password:
        c.output.info(f"Console password: {password}")
    if c.output.json_mode:
        c.output.raw_json(result)


@app.command()
def metrics(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Server name")],
    metric_type: Annotated[str, typer.Option("--type", help="Metric type: cpu, disk, network")] = "cpu",
    start: Annotated[str, typer.Option("--start", help="Start time (ISO 8601, e.g. 2024-01-01T00:00:00Z)")] = "",
    end: Annotated[str, typer.Option("--end", help="End time (ISO 8601)")] = "",
) -> None:
    """Fetch server metrics (cpu, disk, network)."""
    c: AppContext = ctx.obj
    s = _resolve_server(c, name)
    server_id = s["id"]

    if not start or not end:
        # Default to last hour
        from datetime import datetime, timedelta

        now = datetime.now(tz=UTC)
        if not end:
            end = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        if not start:
            start = (now - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

    params = {"type": metric_type, "start": start, "end": end}
    result = c.client.get(f"/servers/{server_id}/metrics", params=params)

    if c.output.json_mode:
        c.output.raw_json(result)
        return

    metrics_data = result.get("metrics", {})
    timeseries = metrics_data.get("timeseries", {})

    if not timeseries:
        c.output.info(f"No {metric_type} metrics available for server '{name}'")
        return

    sections = [("Metrics", [("Server", name), ("Type", metric_type), ("Start", start), ("End", end)])]
    for series_name, series_data in timeseries.items():
        values = series_data.get("values", [])
        if values:
            last_val = values[-1]
            sections.append(
                (
                    series_name,
                    [
                        ("Data Points", str(len(values))),
                        ("Latest Value", str(last_val[1]) if len(last_val) > 1 else "-"),
                        ("Latest Time", str(last_val[0]) if last_val else "-"),
                    ],
                )
            )
    c.output.detail(f"Server Metrics: {name}", sections, data_for_json=result)
