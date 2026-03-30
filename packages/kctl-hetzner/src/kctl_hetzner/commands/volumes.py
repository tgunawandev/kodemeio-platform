"""Volume management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_hetzner.core.callbacks import AppContext
from kctl_hetzner.core.utils import parse_labels

app = typer.Typer(help="Manage Hetzner Cloud volumes.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all volumes."""
    c: AppContext = ctx.obj
    volumes = c.client.get_all("/volumes", "volumes")
    rows = []
    for v in volumes:
        server_id = v.get("server")
        server_str = str(server_id) if server_id else "-"
        rows.append(
            [
                str(v.get("id", "")),
                v.get("name", ""),
                f"{v.get('size', '')} GB",
                server_str,
                v.get("location", {}).get("name", "-"),
                v.get("status", ""),
            ]
        )
    c.output.table(
        "Volumes",
        [("ID", "dim"), ("Name", "cyan"), ("Size", ""), ("Server", ""), ("Location", ""), ("Status", "green")],
        rows,
        data_for_json=volumes,
    )


@app.command()
def get(
    ctx: typer.Context,
    volume_id: Annotated[int, typer.Argument(help="Volume ID")],
) -> None:
    """Get volume details."""
    c: AppContext = ctx.obj
    data = c.client.get(f"/volumes/{volume_id}")
    vol = data.get("volume", {})
    if not vol:
        c.output.error(f"Volume {volume_id} not found")
        raise typer.Exit(1)

    server_id = vol.get("server")
    labels = vol.get("labels", {})
    labels_str = ", ".join(f"{k}={v}" for k, v in labels.items()) if labels else "-"
    protection = vol.get("protection", {})

    sections = [
        (
            "Volume",
            [
                ("ID", str(vol.get("id", ""))),
                ("Name", vol.get("name", "")),
                ("Size", f"{vol.get('size', '')} GB"),
                ("Status", vol.get("status", "")),
                ("Server", str(server_id) if server_id else "-"),
                ("Location", vol.get("location", {}).get("name", "-")),
                ("Format", vol.get("format", "-") or "-"),
                ("Linux Device", vol.get("linux_device", "-") or "-"),
                ("Delete Protection", str(protection.get("delete", False))),
                ("Labels", labels_str),
                ("Created", vol.get("created", "")),
            ],
        )
    ]
    c.output.detail(f"Volume: {vol.get('name', volume_id)}", sections, data_for_json=vol)


@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Volume name")],
    size: Annotated[int, typer.Option("--size", help="Size in GB")] = 10,
    server: Annotated[str | None, typer.Option("--server", help="Server name to attach to")] = None,
    location: Annotated[str, typer.Option("--location", help="Location (e.g. fsn1, nbg1, hel1)")] = "fsn1",
) -> None:
    """Create a new volume."""
    c: AppContext = ctx.obj
    payload: dict = {
        "name": name,
        "size": size,
        "automount": False,
        "format": "ext4",
    }
    if server:
        # Resolve server name to ID
        servers = c.client.get("/servers", params={"name": server})
        items = servers.get("servers", [])
        if not items:
            c.output.error(f"Server '{server}' not found")
            raise typer.Exit(1)
        payload["server"] = items[0]["id"]
    else:
        payload["location"] = location

    result = c.client.post("/volumes", json=payload)
    vol = result.get("volume", {})
    c.output.success(f"Volume '{vol.get('name')}' created (ID: {vol.get('id')}, Size: {size} GB)")
    if c.output.json_mode:
        c.output.raw_json(result)


@app.command()
def attach(
    ctx: typer.Context,
    volume_id: Annotated[int, typer.Argument(help="Volume ID")],
    server_id: Annotated[int, typer.Option("--server", help="Server ID to attach to")],
) -> None:
    """Attach a volume to a server."""
    c: AppContext = ctx.obj
    result = c.client.post(f"/volumes/{volume_id}/actions/attach", json={"server": server_id, "automount": True})
    c.output.success(f"Volume {volume_id} attached to server {server_id}")
    if c.output.json_mode:
        c.output.raw_json(result)


@app.command()
def detach(
    ctx: typer.Context,
    volume_id: Annotated[int, typer.Argument(help="Volume ID")],
) -> None:
    """Detach a volume from its server."""
    c: AppContext = ctx.obj
    result = c.client.post(f"/volumes/{volume_id}/actions/detach")
    c.output.success(f"Volume {volume_id} detached")
    if c.output.json_mode:
        c.output.raw_json(result)


@app.command()
def delete(
    ctx: typer.Context,
    volume_id: Annotated[int, typer.Argument(help="Volume ID")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete a volume."""
    c: AppContext = ctx.obj
    if not force:
        typer.confirm(f"Delete volume {volume_id}?", abort=True)
    c.client.delete(f"/volumes/{volume_id}")
    c.output.success(f"Volume {volume_id} deleted")


@app.command()
def update(
    ctx: typer.Context,
    volume_id: Annotated[int, typer.Argument(help="Volume ID")],
    name: Annotated[str | None, typer.Option("--name", help="New volume name")] = None,
    labels: Annotated[str | None, typer.Option("--labels", help="Labels as key=val,key=val")] = None,
) -> None:
    """Update a volume (name, labels)."""
    c: AppContext = ctx.obj
    payload: dict = {}
    if name is not None:
        payload["name"] = name
    if labels is not None:
        payload["labels"] = parse_labels(labels)
    if not payload:
        c.output.error("Provide at least one option to update (--name, --labels)")
        raise typer.Exit(1)
    result = c.client.put(f"/volumes/{volume_id}", json=payload)
    c.output.success(f"Volume {volume_id} updated")
    if c.output.json_mode:
        c.output.raw_json(result)


@app.command()
def extend(
    ctx: typer.Context,
    volume_id: Annotated[int, typer.Argument(help="Volume ID")],
    size: Annotated[int, typer.Option("--size", help="New size in GB (must be larger than current)")],
) -> None:
    """Extend (resize) a volume to a larger size."""
    c: AppContext = ctx.obj
    result = c.client.post(f"/volumes/{volume_id}/actions/resize", json={"size": size})
    c.output.success(f"Volume {volume_id} extended to {size} GB")
    if c.output.json_mode:
        c.output.raw_json(result)


@app.command()
def protect(
    ctx: typer.Context,
    volume_id: Annotated[int, typer.Argument(help="Volume ID")],
    enable: Annotated[bool, typer.Option("--enable/--disable", help="Enable or disable delete protection")] = True,
) -> None:
    """Enable or disable delete protection on a volume."""
    c: AppContext = ctx.obj
    result = c.client.post(
        f"/volumes/{volume_id}/actions/change_protection",
        json={"delete": enable},
    )
    state = "enabled" if enable else "disabled"
    c.output.success(f"Delete protection {state} for volume {volume_id}")
    if c.output.json_mode:
        c.output.raw_json(result)
