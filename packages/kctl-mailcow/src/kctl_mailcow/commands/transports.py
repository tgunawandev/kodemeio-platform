"""Outbound mail transport routing."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_mailcow.core.callbacks import AppContext
from kctl_mailcow.core.helpers import handle_result

app = typer.Typer(help="Manage outbound transport maps.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all transport maps."""
    c: AppContext = ctx.obj
    data = c.client.mc_get("transport/all")
    items = data if isinstance(data, list) else []

    if not items:
        c.output.info("No transport maps configured.")
        if c.json_mode:
            c.output.raw_json([])
        return

    rows = []
    for item in items:
        active = "[green]yes[/green]" if str(item.get("active")) == "1" else "[red]no[/red]"
        rows.append(
            [
                str(item.get("id", "")),
                item.get("destination", ""),
                item.get("nexthop", ""),
                active,
            ]
        )

    c.output.table(
        "Transport Maps",
        [("ID", "dim"), ("Destination", "cyan"), ("Next Hop", ""), ("Active", "")],
        rows,
        data_for_json=items,
    )


@app.command()
def get(
    ctx: typer.Context,
    transport_id: Annotated[str, typer.Argument(help="Transport ID")],
) -> None:
    """Get transport map details."""
    c: AppContext = ctx.obj
    data = c.client.mc_get(f"transport/{transport_id}")
    item = data[0] if isinstance(data, list) and data else data if isinstance(data, dict) else {}
    if not item:
        c.output.error(f"Transport not found: {transport_id}")
        raise typer.Exit(1)

    sections = [
        (
            "Transport Map",
            [
                ("ID", str(item.get("id", ""))),
                ("Destination", str(item.get("destination", ""))),
                ("Next Hop", str(item.get("nexthop", ""))),
                ("Username", str(item.get("username", ""))),
                ("Active", str(item.get("active", ""))),
            ],
        )
    ]
    c.output.detail(f"Transport: {transport_id}", sections, data_for_json=item)


@app.command()
def create(
    ctx: typer.Context,
    destination: Annotated[str, typer.Argument(help="Destination pattern (domain or email)")],
    nexthop: Annotated[str, typer.Option("--nexthop", help="Next hop server (host:port)")],
    username: Annotated[str | None, typer.Option("--username", help="Auth username")] = None,
    password: Annotated[str | None, typer.Option("--password", help="Auth password")] = None,
    active: Annotated[bool, typer.Option("--active/--inactive")] = True,
) -> None:
    """Create a transport map."""
    c: AppContext = ctx.obj
    payload: dict = {
        "destination": destination,
        "nexthop": nexthop,
        "active": "1" if active else "0",
    }
    if username:
        payload["username"] = username
    if password:
        payload["password"] = password
    result = c.client.mc_add("transport", payload)
    handle_result(c, result, f"Transport '{destination}' → '{nexthop}' created")


@app.command()
def update(
    ctx: typer.Context,
    transport_id: Annotated[str, typer.Argument(help="Transport ID")],
    destination: Annotated[str | None, typer.Option("--destination")] = None,
    nexthop: Annotated[str | None, typer.Option("--nexthop")] = None,
    username: Annotated[str | None, typer.Option("--username")] = None,
    password: Annotated[str | None, typer.Option("--password")] = None,
    active: Annotated[bool | None, typer.Option("--active/--inactive")] = None,
) -> None:
    """Update a transport map."""
    c: AppContext = ctx.obj
    attr: dict = {}
    if destination is not None:
        attr["destination"] = destination
    if nexthop is not None:
        attr["nexthop"] = nexthop
    if username is not None:
        attr["username"] = username
    if password is not None:
        attr["password"] = password
    if active is not None:
        attr["active"] = "1" if active else "0"
    if not attr:
        c.output.warn("No fields to update")
        raise typer.Exit(0)

    result = c.client.mc_edit("transport", {"items": [transport_id], "attr": attr})
    handle_result(c, result, f"Transport {transport_id} updated")


@app.command()
def delete(
    ctx: typer.Context,
    transport_id: Annotated[str, typer.Argument(help="Transport ID")],
    force: Annotated[bool, typer.Option("--force")] = False,
) -> None:
    """Delete a transport map."""
    c: AppContext = ctx.obj
    if not force:
        if not typer.confirm(f"Delete transport {transport_id}?"):
            raise typer.Exit(0)
    result = c.client.mc_delete("transport", [transport_id])
    handle_result(c, result, f"Transport {transport_id} deleted")
