"""Snapshot management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_hetzner.core.callbacks import AppContext
from kctl_hetzner.core.utils import parse_labels

app = typer.Typer(help="Manage Hetzner Cloud snapshots.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all snapshots."""
    c: AppContext = ctx.obj
    snapshots = c.client.get_all("/images", "images", params={"type": "snapshot"})
    rows = []
    for snap in snapshots:
        created_from = snap.get("created_from", {})
        server_name = created_from.get("name", "-") if created_from else "-"
        rows.append(
            [
                str(snap.get("id", "")),
                snap.get("description", "") or "-",
                server_name,
                f"{snap.get('image_size', 0):.1f} GB",
                snap.get("created", ""),
            ]
        )
    c.output.table(
        "Snapshots",
        [("ID", "dim"), ("Description", "cyan"), ("Server", ""), ("Size", ""), ("Created", "")],
        rows,
        data_for_json=snapshots,
    )


@app.command()
def get(
    ctx: typer.Context,
    snapshot_id: Annotated[int, typer.Argument(help="Snapshot ID")],
) -> None:
    """Get snapshot details."""
    c: AppContext = ctx.obj
    data = c.client.get(f"/images/{snapshot_id}")
    snap = data.get("image", {})
    if not snap:
        c.output.error(f"Snapshot {snapshot_id} not found")
        raise typer.Exit(1)

    created_from = snap.get("created_from", {})
    server_name = created_from.get("name", "-") if created_from else "-"
    server_id = created_from.get("id", "-") if created_from else "-"
    labels = snap.get("labels", {})
    labels_str = ", ".join(f"{k}={v}" for k, v in labels.items()) if labels else "-"
    protection = snap.get("protection", {})

    sections = [
        (
            "Snapshot",
            [
                ("ID", str(snap.get("id", ""))),
                ("Description", snap.get("description", "") or "-"),
                ("Type", snap.get("type", "")),
                ("Status", snap.get("status", "")),
                ("Image Size", f"{snap.get('image_size', 0):.1f} GB"),
                ("Disk Size", f"{snap.get('disk_size', 0)} GB"),
                ("OS Flavor", snap.get("os_flavor", "-")),
                ("OS Version", snap.get("os_version", "-") or "-"),
                ("Architecture", snap.get("architecture", "-")),
                ("Server Name", server_name),
                ("Server ID", str(server_id)),
                ("Delete Protection", str(protection.get("delete", False))),
                ("Labels", labels_str),
                ("Created", snap.get("created", "")),
            ],
        )
    ]
    c.output.detail(f"Snapshot: {snapshot_id}", sections, data_for_json=snap)


@app.command()
def create(
    ctx: typer.Context,
    server_id: Annotated[int, typer.Argument(help="Server ID to snapshot")],
    description: Annotated[str | None, typer.Option("--description", help="Snapshot description")] = None,
) -> None:
    """Create a snapshot from a server."""
    c: AppContext = ctx.obj

    payload: dict = {"type": "snapshot"}
    if description:
        payload["description"] = description

    result = c.client.post(f"/servers/{server_id}/actions/create_image", json=payload)
    image = result.get("image", {})
    c.output.success(f"Snapshot created (ID: {image.get('id')}) from server {server_id}")
    if c.output.json_mode:
        c.output.raw_json(result)


@app.command()
def delete(
    ctx: typer.Context,
    snapshot_id: Annotated[int, typer.Argument(help="Snapshot ID")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete a snapshot."""
    c: AppContext = ctx.obj
    if not force:
        typer.confirm(f"Delete snapshot {snapshot_id}?", abort=True)
    c.client.delete(f"/images/{snapshot_id}")
    c.output.success(f"Snapshot {snapshot_id} deleted")


@app.command()
def restore(
    ctx: typer.Context,
    server_id: Annotated[int, typer.Argument(help="Server ID to restore to")],
    image: Annotated[int, typer.Option("--image", help="Snapshot/image ID to restore from")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Restore a server from a snapshot (rebuilds the server)."""
    c: AppContext = ctx.obj
    if not force:
        typer.confirm(
            f"Rebuild server {server_id} from image {image}? This will DESTROY all data on the server.",
            abort=True,
        )
    result = c.client.post(f"/servers/{server_id}/actions/rebuild", json={"image": image})
    c.output.success(f"Server {server_id} rebuild started from image {image}")
    if c.output.json_mode:
        c.output.raw_json(result)


@app.command()
def update(
    ctx: typer.Context,
    snapshot_id: Annotated[int, typer.Argument(help="Snapshot ID")],
    description: Annotated[str | None, typer.Option("--description", help="New description")] = None,
    labels: Annotated[str | None, typer.Option("--labels", help="Labels as key=val,key=val")] = None,
) -> None:
    """Update a snapshot (description, labels)."""
    c: AppContext = ctx.obj
    payload: dict = {}
    if description is not None:
        payload["description"] = description
    if labels is not None:
        payload["labels"] = parse_labels(labels)

    if not payload:
        c.output.error("Provide at least one option to update (--description, --labels)")
        raise typer.Exit(1)

    result = c.client.put(f"/images/{snapshot_id}", json=payload)
    c.output.success(f"Snapshot {snapshot_id} updated")
    if c.output.json_mode:
        c.output.raw_json(result)
