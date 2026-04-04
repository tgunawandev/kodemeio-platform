"""Inbound recipient map management."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_mailcow.core.callbacks import AppContext
from kctl_mailcow.core.helpers import handle_result

app = typer.Typer(help="Manage recipient maps (inbound address rewriting).")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all recipient maps."""
    c: AppContext = ctx.obj
    data = c.client.mc_get("recipient_map/all")
    items = data if isinstance(data, list) else []
    if not items:
        c.output.info("No recipient maps configured.")
        if c.json_mode:
            c.output.raw_json([])
        return

    rows = []
    for item in items:
        active = "[green]yes[/green]" if str(item.get("active")) == "1" else "[red]no[/red]"
        rows.append([str(item.get("id", "")), item.get("old_dest", ""), item.get("new_dest", ""), active])

    c.output.table(
        "Recipient Maps",
        [("ID", "dim"), ("Old Dest", "cyan"), ("New Dest", ""), ("Active", "")],
        rows,
        data_for_json=items,
    )


@app.command()
def create(
    ctx: typer.Context,
    old_dest: Annotated[str, typer.Argument(help="Original recipient address")],
    new_dest: Annotated[str, typer.Argument(help="New recipient address")],
    active: Annotated[bool, typer.Option("--active/--inactive")] = True,
) -> None:
    """Create a recipient map."""
    c: AppContext = ctx.obj
    payload = {"old_dest": old_dest, "new_dest": new_dest, "active": "1" if active else "0"}
    result = c.client.mc_add("recipient_map", payload)
    handle_result(c, result, f"Recipient map '{old_dest}' → '{new_dest}' created")


@app.command()
def delete(
    ctx: typer.Context,
    map_id: Annotated[str, typer.Argument(help="Recipient map ID")],
    force: Annotated[bool, typer.Option("--force")] = False,
) -> None:
    """Delete a recipient map."""
    c: AppContext = ctx.obj
    if not force:
        if not typer.confirm(f"Delete recipient map {map_id}?"):
            raise typer.Exit(0)
    result = c.client.mc_delete("recipient_map", [map_id])
    handle_result(c, result, f"Recipient map {map_id} deleted")
