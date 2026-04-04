"""Alias management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_mailcow.core.callbacks import AppContext
from kctl_mailcow.core.helpers import handle_result

app = typer.Typer(help="Manage email aliases.")


@app.command("list")
def list_(
    ctx: typer.Context,
    domain: Annotated[str | None, typer.Option("--domain", "-d", help="Filter by domain")] = None,
) -> None:
    """List all aliases."""
    c: AppContext = ctx.obj
    data = c.client.mc_get("alias/all")
    items = data if isinstance(data, list) else []

    if domain:
        items = [a for a in items if a.get("domain", "") == domain]

    rows = []
    for a in items:
        active = "[green]yes[/green]" if str(a.get("active")) == "1" else "[red]no[/red]"
        rows.append(
            [
                str(a.get("id", "")),
                a.get("address", ""),
                a.get("goto", ""),
                active,
            ]
        )

    c.output.table(
        "Aliases",
        [("ID", "dim"), ("Address", "cyan"), ("Goto", ""), ("Active", "")],
        rows,
        data_for_json=items,
    )


@app.command()
def get(
    ctx: typer.Context,
    alias_id: Annotated[str, typer.Argument(help="Alias ID")],
) -> None:
    """Get alias details."""
    c: AppContext = ctx.obj
    data = c.client.mc_get(f"alias/{alias_id}")

    if isinstance(data, list) and data:
        item = data[0]
    elif isinstance(data, dict) and data:
        item = data
    else:
        c.output.error(f"Alias not found: {alias_id}")
        raise typer.Exit(1)

    sections = [
        (
            "Alias Info",
            [
                ("ID", str(item.get("id", ""))),
                ("Address", str(item.get("address", ""))),
                ("Goto", str(item.get("goto", ""))),
                ("Domain", str(item.get("domain", ""))),
                ("Active", str(item.get("active", ""))),
                ("Created", str(item.get("created", ""))),
                ("Modified", str(item.get("modified", ""))),
            ],
        )
    ]

    c.output.detail(f"Alias: {item.get('address', alias_id)}", sections, data_for_json=item)


@app.command()
def add(
    ctx: typer.Context,
    address: Annotated[str, typer.Argument(help="Alias address (e.g. alias@domain.com)")],
    goto: Annotated[str, typer.Argument(help="Destination address(es), comma-separated")],
    active: Annotated[bool, typer.Option("--active/--inactive", help="Active state")] = True,
) -> None:
    """Add a new alias."""
    c: AppContext = ctx.obj
    payload = {
        "address": address,
        "goto": goto,
        "active": "1" if active else "0",
    }
    result = c.client.mc_add("alias", payload)
    _handle_result(c, result, f"Alias '{address}' -> '{goto}' added")


@app.command()
def update(
    ctx: typer.Context,
    alias_id: Annotated[str, typer.Argument(help="Alias ID to update")],
    address: Annotated[str | None, typer.Option("--address")] = None,
    goto: Annotated[str | None, typer.Option("--goto")] = None,
    active: Annotated[bool | None, typer.Option("--active/--inactive")] = None,
) -> None:
    """Update alias settings."""
    c: AppContext = ctx.obj
    attr: dict = {}
    if address is not None:
        attr["address"] = address
    if goto is not None:
        attr["goto"] = goto
    if active is not None:
        attr["active"] = "1" if active else "0"

    if not attr:
        c.output.warn("No fields to update")
        raise typer.Exit(0)

    payload = {
        "items": [alias_id],
        "attr": attr,
    }
    result = c.client.mc_edit("alias", payload)
    _handle_result(c, result, f"Alias {alias_id} updated")


@app.command()
def delete(
    ctx: typer.Context,
    alias_id: Annotated[str, typer.Argument(help="Alias ID to delete")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete an alias."""
    c: AppContext = ctx.obj
    if not force:
        if not typer.confirm(f"Delete alias {alias_id}?"):
            raise typer.Exit(0)

    result = c.client.mc_delete("alias", [alias_id])
    _handle_result(c, result, f"Alias {alias_id} deleted")


_handle_result = handle_result
