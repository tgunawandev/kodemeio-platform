"""Resource management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_mailcow.core.callbacks import AppContext
from kctl_mailcow.core.helpers import handle_result

app = typer.Typer(help="Manage Mailcow resources.")


_handle_result = handle_result


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all resources."""
    c: AppContext = ctx.obj
    data = c.client.mc_get("resource/all")
    items = data if isinstance(data, list) else []

    if not items:
        c.output.info("No resources found.")
        return

    rows = []
    for item in items:
        active = "[green]yes[/green]" if str(item.get("active")) == "1" else "[red]no[/red]"
        rows.append(
            [
                str(item.get("name", "")),
                item.get("description", "-") or "-",
                item.get("kind", "-") or "-",
                str(item.get("multiple_bookings", "-")),
                active,
            ]
        )

    c.output.table(
        f"Resources ({len(items)})",
        [("Name", "cyan"), ("Description", ""), ("Kind", ""), ("Multiple Bookings", "dim"), ("Active", "")],
        rows,
        data_for_json=items,
    )


@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Resource name (unique identifier)")],
    description: Annotated[str | None, typer.Option("--description", "-d", help="Resource description")] = None,
    kind: Annotated[str, typer.Option("--kind", help="Resource kind (room, equipment, etc.)")] = "room",
    active: Annotated[bool, typer.Option("--active/--inactive", help="Active state")] = True,
    multiple_bookings: Annotated[
        int, typer.Option("--multiple-bookings", help="Number of simultaneous bookings allowed")
    ] = -1,
) -> None:
    """Create a resource."""
    c: AppContext = ctx.obj
    payload = {
        "name": name,
        "description": description or name,
        "kind": kind,
        "active": "1" if active else "0",
        "multiple_bookings": str(multiple_bookings),
    }
    result = c.client.mc_add("resource", payload)
    _handle_result(c, result, f"Resource '{name}' created")


@app.command()
def delete(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Resource name to delete")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete a resource."""
    c: AppContext = ctx.obj
    if not force:
        if not typer.confirm(f"Delete resource '{name}'?"):
            raise typer.Exit(0)

    result = c.client.mc_delete("resource", [name])
    _handle_result(c, result, f"Resource '{name}' deleted")
