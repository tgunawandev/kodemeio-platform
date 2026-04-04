"""BCC map management for compliance copies."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_mailcow.core.callbacks import AppContext
from kctl_mailcow.core.helpers import handle_result

app = typer.Typer(help="Manage BCC maps (compliance copies).")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all BCC maps."""
    c: AppContext = ctx.obj
    data = c.client.mc_get("bcc/all")
    items = data if isinstance(data, list) else []
    if not items:
        c.output.info("No BCC maps configured.")
        if c.json_mode:
            c.output.raw_json([])
        return

    rows = []
    for item in items:
        active = "[green]yes[/green]" if str(item.get("active")) == "1" else "[red]no[/red]"
        rows.append(
            [
                str(item.get("id", "")),
                item.get("local_dest", ""),
                item.get("bcc_dest", ""),
                item.get("type", ""),
                active,
            ]
        )

    c.output.table(
        "BCC Maps",
        [("ID", "dim"), ("Source", "cyan"), ("BCC To", ""), ("Type", ""), ("Active", "")],
        rows,
        data_for_json=items,
    )


@app.command()
def create(
    ctx: typer.Context,
    local_dest: Annotated[str, typer.Argument(help="Source address/domain to BCC from")],
    bcc_dest: Annotated[str, typer.Argument(help="BCC destination address")],
    bcc_type: Annotated[str, typer.Option("--type", help="sender or rcpt")] = "sender",
    active: Annotated[bool, typer.Option("--active/--inactive")] = True,
) -> None:
    """Create a BCC map."""
    c: AppContext = ctx.obj
    payload = {"local_dest": local_dest, "bcc_dest": bcc_dest, "type": bcc_type, "active": "1" if active else "0"}
    result = c.client.mc_add("bcc", payload)
    handle_result(c, result, f"BCC map '{local_dest}' → '{bcc_dest}' created")


@app.command()
def update(
    ctx: typer.Context,
    bcc_id: Annotated[str, typer.Argument(help="BCC map ID")],
    local_dest: Annotated[str | None, typer.Option("--local-dest")] = None,
    bcc_dest: Annotated[str | None, typer.Option("--bcc-dest")] = None,
    bcc_type: Annotated[str | None, typer.Option("--type")] = None,
    active: Annotated[bool | None, typer.Option("--active/--inactive")] = None,
) -> None:
    """Update a BCC map."""
    c: AppContext = ctx.obj
    attr: dict = {}
    if local_dest is not None:
        attr["local_dest"] = local_dest
    if bcc_dest is not None:
        attr["bcc_dest"] = bcc_dest
    if bcc_type is not None:
        attr["type"] = bcc_type
    if active is not None:
        attr["active"] = "1" if active else "0"
    if not attr:
        c.output.warn("No fields to update")
        raise typer.Exit(0)
    result = c.client.mc_edit("bcc", {"items": [bcc_id], "attr": attr})
    handle_result(c, result, f"BCC map {bcc_id} updated")


@app.command()
def delete(
    ctx: typer.Context,
    bcc_id: Annotated[str, typer.Argument(help="BCC map ID")],
    force: Annotated[bool, typer.Option("--force")] = False,
) -> None:
    """Delete a BCC map."""
    c: AppContext = ctx.obj
    if not force:
        if not typer.confirm(f"Delete BCC map {bcc_id}?"):
            raise typer.Exit(0)
    result = c.client.mc_delete("bcc", [bcc_id])
    handle_result(c, result, f"BCC map {bcc_id} deleted")
