"""Space/drive management commands for kctl-opencloud."""

from __future__ import annotations

from typing import Annotated, Any

import typer

from kctl_opencloud.core.callbacks import AppContext

app = typer.Typer(help="Drive and space management.")


def _format_bytes(size: float) -> str:
    """Format bytes to human readable."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


@app.command("list")
def list_(
    ctx: typer.Context,
    type_filter: Annotated[str | None, typer.Option("--type", "-t", help="Filter by type (personal, project)")] = None,
) -> None:
    """List all spaces/drives."""
    c: AppContext = ctx.obj
    spaces = c.client.get_all("drives")

    if type_filter:
        spaces = [s for s in spaces if s.get("driveType") == type_filter]

    rows = []
    for s in spaces:
        quota = s.get("quota", {})
        used = quota.get("used", 0)
        total = quota.get("total", 0)
        rows.append(
            [
                s.get("id", ""),
                s.get("name", "-"),
                s.get("driveType", "-"),
                _format_bytes(used),
                _format_bytes(total) if total > 0 else "unlimited",
            ]
        )

    c.output.table(
        "Spaces",
        [("ID", "cyan"), ("Name", "green"), ("Type", "yellow"), ("Used", "white"), ("Quota", "white")],
        rows,
        data_for_json=spaces,
    )


@app.command()
def get(
    ctx: typer.Context,
    space_id: Annotated[str, typer.Argument(help="Space/drive ID")],
) -> None:
    """Get space details."""
    c: AppContext = ctx.obj
    space = c.client.get(f"drives/{space_id}")

    quota = space.get("quota", {})
    sections = [
        (
            "Space",
            [
                ("ID", space.get("id", "")),
                ("Name", space.get("name", "-")),
                ("Type", space.get("driveType", "-")),
                ("Description", space.get("description", "-")),
                ("Used", _format_bytes(quota.get("used", 0))),
                ("Total", _format_bytes(quota.get("total", 0)) if quota.get("total", 0) > 0 else "unlimited"),
                ("State", space.get("root", {}).get("deleted", {}).get("state", "active")),
            ],
        ),
    ]
    c.output.detail("Space Details", sections, data_for_json=space)


@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Space name")],
    description: Annotated[str, typer.Option("--description", "-d", help="Space description")] = "",
    quota: Annotated[int | None, typer.Option("--quota", "-q", help="Quota in bytes")] = None,
) -> None:
    """Create a project space."""
    c: AppContext = ctx.obj
    space_data: dict[str, Any] = {
        "name": name,
        "driveType": "project",
    }
    if description:
        space_data["description"] = description
    if quota is not None:
        space_data["quota"] = {"total": quota}

    space = c.client.post("drives", data=space_data)
    c.output.success(f"Space created: {space.get('name', name)}")


@app.command()
def update(
    ctx: typer.Context,
    space_id: Annotated[str, typer.Argument(help="Space ID")],
    name: Annotated[str | None, typer.Option("--name", "-n", help="New name")] = None,
    description: Annotated[str | None, typer.Option("--description", "-d", help="New description")] = None,
    quota_val: Annotated[int | None, typer.Option("--quota", "-q", help="New quota in bytes")] = None,
) -> None:
    """Update a space."""
    c: AppContext = ctx.obj
    patch_data: dict[str, Any] = {}
    if name is not None:
        patch_data["name"] = name
    if description is not None:
        patch_data["description"] = description
    if quota_val is not None:
        patch_data["quota"] = {"total": quota_val}

    if not patch_data:
        c.output.warn("No changes specified")
        return

    c.client.patch(f"drives/{space_id}", data=patch_data)
    c.output.success(f"Space {space_id} updated")


@app.command()
def delete(
    ctx: typer.Context,
    space_id: Annotated[str, typer.Argument(help="Space ID")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Delete a space."""
    c: AppContext = ctx.obj
    if not force:
        typer.confirm(f"Delete space {space_id}?", abort=True)
    c.client.delete(f"drives/{space_id}")
    c.output.success(f"Space {space_id} deleted")


@app.command("quota")
def quota_cmd(
    ctx: typer.Context,
    space_id: Annotated[str, typer.Argument(help="Space ID")],
) -> None:
    """Show space quota usage."""
    c: AppContext = ctx.obj
    space = c.client.get(f"drives/{space_id}")
    q = space.get("quota", {})

    used = q.get("used", 0)
    total = q.get("total", 0)
    remaining = q.get("remaining", total - used if total > 0 else 0)

    sections = [
        (
            "Quota",
            [
                ("Space", space.get("name", space_id)),
                ("Used", _format_bytes(used)),
                ("Total", _format_bytes(total) if total > 0 else "unlimited"),
                ("Remaining", _format_bytes(remaining) if total > 0 else "unlimited"),
                ("Usage", f"{(used / total * 100):.1f}%" if total > 0 else "N/A"),
            ],
        ),
    ]
    c.output.detail("Space Quota", sections, data_for_json=q)
