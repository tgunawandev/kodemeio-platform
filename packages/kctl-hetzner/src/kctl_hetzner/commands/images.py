"""Image management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_hetzner.core.callbacks import AppContext
from kctl_hetzner.core.utils import parse_labels

app = typer.Typer(help="Manage Hetzner Cloud images (OS, snapshots, backups).")


@app.command("list")
def list_(
    ctx: typer.Context,
    image_type: Annotated[
        str | None, typer.Option("--type", help="Filter by type: system, snapshot, backup, app")
    ] = None,
    architecture: Annotated[str | None, typer.Option("--architecture", help="Filter by architecture: x86, arm")] = None,
) -> None:
    """List images (optionally filtered by type)."""
    c: AppContext = ctx.obj
    params: dict = {}
    if image_type:
        params["type"] = image_type
    if architecture:
        params["architecture"] = architecture

    images = c.client.get_all("/images", "images", params=params)
    rows = []
    for img in images:
        created_from = img.get("created_from", {})
        source = created_from.get("name", "-") if created_from else "-"
        rows.append(
            [
                str(img.get("id", "")),
                img.get("type", ""),
                img.get("name", "") or img.get("description", "") or "-",
                img.get("os_flavor", "-"),
                img.get("architecture", "-"),
                f"{img.get('image_size', 0):.1f} GB" if img.get("image_size") else "-",
                img.get("status", ""),
                source,
            ]
        )
    c.output.table(
        "Images",
        [
            ("ID", "dim"),
            ("Type", "cyan"),
            ("Name", ""),
            ("OS", ""),
            ("Arch", ""),
            ("Size", ""),
            ("Status", "green"),
            ("Source", ""),
        ],
        rows,
        data_for_json=images,
    )


@app.command()
def get(
    ctx: typer.Context,
    image_id: Annotated[int, typer.Argument(help="Image ID")],
) -> None:
    """Get details of an image."""
    c: AppContext = ctx.obj
    data = c.client.get(f"/images/{image_id}")
    img = data.get("image", {})
    if not img:
        c.output.error(f"Image {image_id} not found")
        raise typer.Exit(1)

    created_from = img.get("created_from", {})
    source_name = created_from.get("name", "-") if created_from else "-"
    source_id = created_from.get("id", "-") if created_from else "-"
    labels = img.get("labels", {})
    labels_str = ", ".join(f"{k}={v}" for k, v in labels.items()) if labels else "-"
    protection = img.get("protection", {})

    sections = [
        (
            "Image",
            [
                ("ID", str(img.get("id", ""))),
                ("Type", img.get("type", "")),
                ("Name", img.get("name", "") or "-"),
                ("Description", img.get("description", "") or "-"),
                ("Status", img.get("status", "")),
                ("OS Flavor", img.get("os_flavor", "-")),
                ("OS Version", img.get("os_version", "-") or "-"),
                ("Architecture", img.get("architecture", "-")),
                ("Image Size", f"{img.get('image_size', 0):.1f} GB" if img.get("image_size") else "-"),
                ("Disk Size", f"{img.get('disk_size', 0)} GB" if img.get("disk_size") else "-"),
                ("Rapid Deploy", str(img.get("rapid_deploy", False))),
                ("Source Server", source_name),
                ("Source ID", str(source_id)),
                ("Delete Protection", str(protection.get("delete", False))),
                ("Labels", labels_str),
                ("Created", img.get("created", "")),
                ("Deprecated", img.get("deprecated", "-") or "-"),
            ],
        )
    ]
    c.output.detail(f"Image: {image_id}", sections, data_for_json=img)


@app.command()
def delete(
    ctx: typer.Context,
    image_id: Annotated[int, typer.Argument(help="Image ID (only snapshots can be deleted)")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete an image (only snapshots can be deleted)."""
    c: AppContext = ctx.obj
    if not force:
        typer.confirm(f"Delete image {image_id}?", abort=True)
    c.client.delete(f"/images/{image_id}")
    c.output.success(f"Image {image_id} deleted")


@app.command()
def update(
    ctx: typer.Context,
    image_id: Annotated[int, typer.Argument(help="Image ID")],
    description: Annotated[str | None, typer.Option("--description", help="New description")] = None,
    image_type: Annotated[str | None, typer.Option("--type", help="New type (e.g. snapshot)")] = None,
    labels: Annotated[str | None, typer.Option("--labels", help="Labels as key=val,key=val")] = None,
) -> None:
    """Update an image (description, type, labels)."""
    c: AppContext = ctx.obj
    payload: dict = {}
    if description is not None:
        payload["description"] = description
    if image_type is not None:
        payload["type"] = image_type
    if labels is not None:
        payload["labels"] = parse_labels(labels)

    if not payload:
        c.output.error("Provide at least one option to update (--description, --type, --labels)")
        raise typer.Exit(1)

    result = c.client.put(f"/images/{image_id}", json=payload)
    c.output.success(f"Image {image_id} updated")
    if c.output.json_mode:
        c.output.raw_json(result)
