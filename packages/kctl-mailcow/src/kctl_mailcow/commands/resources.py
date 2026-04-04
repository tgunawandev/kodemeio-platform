"""Resource management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_mailcow.core.callbacks import AppContext

app = typer.Typer(help="Manage Mailcow resources.")


def _handle_result(c: AppContext, result: dict | list, success_msg: str) -> None:
    """Handle Mailcow API result."""
    if isinstance(result, list):
        errors = [r for r in result if isinstance(r, dict) and r.get("type") == "danger"]
        if errors:
            for e in errors:
                c.output.error(str(e.get("msg", e)))
            raise typer.Exit(1)
        c.output.success(success_msg)
        if c.json_mode:
            c.output.raw_json(result)
    elif isinstance(result, dict):
        if result.get("type") == "danger":
            c.output.error(str(result.get("msg", result)))
            raise typer.Exit(1)
        c.output.success(success_msg)
        if c.json_mode:
            c.output.raw_json(result)
    else:
        c.output.success(success_msg)


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
    description: Annotated[str, typer.Option("--description", "-d", help="Resource description")],
    kind: Annotated[str, typer.Option("--kind", help="Resource kind (room, equipment, etc.)")] = "room",
    active: Annotated[bool, typer.Option("--active/--inactive", help="Active state")] = True,
    multiple_bookings: Annotated[
        int, typer.Option("--multiple-bookings", help="Number of simultaneous bookings allowed")
    ] = -1,
) -> None:
    """Create a resource."""
    c: AppContext = ctx.obj
    payload = {
        "description": description,
        "kind": kind,
        "active": "1" if active else "0",
        "multiple_bookings": str(multiple_bookings),
    }
    result = c.client.mc_add("resource", payload)
    _handle_result(c, result, f"Resource '{description}' created")


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
