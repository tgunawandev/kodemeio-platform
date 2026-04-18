"""Collection management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_outline.core.callbacks import AppContext

app = typer.Typer(help="Collection management.")


@app.command("list")
def list_(
    ctx: typer.Context,
    offset: Annotated[int, typer.Option(help="Pagination offset")] = 0,
    limit: Annotated[int, typer.Option(help="Results per page")] = 25,
) -> None:
    """List all collections."""
    c: AppContext = ctx.obj
    result = c.client.post("collections.list", data={"offset": offset, "limit": limit})
    collections = result.get("data", [])

    rows = [
        [
            col.get("id", "")[:8],
            col.get("name", ""),
            (col.get("description") or "")[:40] or "-",
            str(col.get("documents", {}).get("count", 0) if isinstance(col.get("documents"), dict) else ""),
            col.get("permission", "") or "member",
            (col.get("updatedAt") or "")[:10],
        ]
        for col in collections
    ]

    c.output.table(
        f"Collections ({len(collections)})",
        [
            ("ID", "cyan"),
            ("Name", "green"),
            ("Description", "dim"),
            ("Docs", ""),
            ("Permission", "dim"),
            ("Updated", "dim"),
        ],
        rows,
        data_for_json=collections,
    )


@app.command()
def get(
    ctx: typer.Context,
    collection_id: Annotated[str, typer.Argument(help="Collection ID")],
) -> None:
    """Get collection details."""
    c: AppContext = ctx.obj
    result = c.client.post("collections.info", data={"id": collection_id})
    col = result.get("data", {})

    c.output.detail(
        f"Collection: {col.get('name', '')}",
        [
            (
                "Details",
                [
                    ("ID", col.get("id", "")),
                    ("Name", col.get("name", "")),
                    ("Description", col.get("description", "") or "-"),
                    ("Permission", col.get("permission", "") or "member"),
                    ("Color", col.get("color", "") or "-"),
                    ("Sharing", str(col.get("sharing", False))),
                ],
            ),
            (
                "Dates",
                [
                    ("Created", col.get("createdAt", "")),
                    ("Updated", col.get("updatedAt", "")),
                ],
            ),
        ],
        data_for_json=col,
    )


@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Collection name")],
    description: Annotated[str, typer.Option("--description", "-d", help="Description")] = "",
    permission: Annotated[
        str, typer.Option("--permission", help="Default permission: read, read_write")
    ] = "read_write",
    color: Annotated[str | None, typer.Option("--color", help="Hex color (e.g. #FF0000)")] = None,
) -> None:
    """Create a new collection."""
    c: AppContext = ctx.obj
    data: dict = {"name": name, "permission": permission}
    if description:
        data["description"] = description
    if color:
        data["color"] = color

    result = c.client.post("collections.create", data=data)
    col = result.get("data", {})

    c.output.detail(
        "Collection Created",
        [
            (
                "Details",
                [
                    ("ID", col.get("id", "")),
                    ("Name", col.get("name", "")),
                    ("Permission", col.get("permission", "")),
                ],
            )
        ],
        data_for_json=col,
    )


@app.command()
def update(
    ctx: typer.Context,
    collection_id: Annotated[str, typer.Argument(help="Collection ID")],
    name: Annotated[str | None, typer.Option("--name", help="New name")] = None,
    description: Annotated[str | None, typer.Option("--description", "-d", help="New description")] = None,
    permission: Annotated[str | None, typer.Option("--permission", help="Default permission")] = None,
    color: Annotated[str | None, typer.Option("--color", help="Hex color")] = None,
) -> None:
    """Update a collection."""
    c: AppContext = ctx.obj
    data: dict = {"id": collection_id}
    if name:
        data["name"] = name
    if description is not None:
        data["description"] = description
    if permission:
        data["permission"] = permission
    if color:
        data["color"] = color

    result = c.client.post("collections.update", data=data)
    col = result.get("data", {})
    c.output.success(f"Collection updated: {col.get('name', collection_id)}")


@app.command()
def delete(
    ctx: typer.Context,
    collection_id: Annotated[str, typer.Argument(help="Collection ID")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete a collection."""
    c: AppContext = ctx.obj

    if not force:
        info = c.client.post("collections.info", data={"id": collection_id})
        col = info.get("data", {})
        if not typer.confirm(
            f"Delete collection '{col.get('name', collection_id)}'? This deletes all documents inside."
        ):
            raise typer.Abort()

    c.client.post("collections.delete", data={"id": collection_id})
    c.output.success(f"Collection {collection_id} deleted")


@app.command("export")
def export_(
    ctx: typer.Context,
    collection_id: Annotated[str, typer.Argument(help="Collection ID")],
) -> None:
    """Export a collection (triggers async export)."""
    c: AppContext = ctx.obj
    result = c.client.post("collections.export", data={"id": collection_id})
    fc = result.get("data", {}).get("fileOperation", {})

    c.output.detail(
        "Collection Export",
        [
            (
                "Details",
                [
                    ("File Operation ID", fc.get("id", "")),
                    ("State", fc.get("state", "")),
                ],
            )
        ],
        data_for_json=fc,
    )
    c.output.info("Export is processing. Check file operations for download link.")
