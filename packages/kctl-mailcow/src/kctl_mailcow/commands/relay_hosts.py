"""Sender-dependent relay host management."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_mailcow.core.callbacks import AppContext
from kctl_mailcow.core.helpers import handle_result

app = typer.Typer(help="Manage sender-dependent relay hosts.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all relay hosts."""
    c: AppContext = ctx.obj
    data = c.client.mc_get("relayhost/all")
    items = data if isinstance(data, list) else []
    if not items:
        c.output.info("No relay hosts configured.")
        if c.json_mode:
            c.output.raw_json([])
        return

    rows = []
    for item in items:
        active = "[green]yes[/green]" if str(item.get("active")) == "1" else "[red]no[/red]"
        rows.append([str(item.get("id", "")), item.get("hostname", ""), str(item.get("used_by_domains", "")), active])

    c.output.table(
        "Relay Hosts", [("ID", "dim"), ("Hostname", "cyan"), ("Used By", ""), ("Active", "")], rows, data_for_json=items
    )


@app.command()
def get(ctx: typer.Context, relay_id: Annotated[str, typer.Argument(help="Relay host ID")]) -> None:
    """Get relay host details."""
    c: AppContext = ctx.obj
    data = c.client.mc_get(f"relayhost/{relay_id}")
    item = data[0] if isinstance(data, list) and data else data if isinstance(data, dict) else {}
    if not item:
        c.output.error(f"Relay host not found: {relay_id}")
        raise typer.Exit(1)
    sections = [
        (
            "Relay Host",
            [
                ("ID", str(item.get("id", ""))),
                ("Hostname", str(item.get("hostname", ""))),
                ("Username", str(item.get("username", ""))),
                ("Active", str(item.get("active", ""))),
                ("Used By Domains", str(item.get("used_by_domains", ""))),
            ],
        )
    ]
    c.output.detail(f"Relay Host: {relay_id}", sections, data_for_json=item)


@app.command()
def create(
    ctx: typer.Context,
    hostname: Annotated[str, typer.Argument(help="Relay hostname:port")],
    username: Annotated[str | None, typer.Option("--username")] = None,
    password: Annotated[str | None, typer.Option("--password")] = None,
    active: Annotated[bool, typer.Option("--active/--inactive")] = True,
) -> None:
    """Create a relay host."""
    c: AppContext = ctx.obj
    payload: dict = {"hostname": hostname, "active": "1" if active else "0"}
    if username:
        payload["username"] = username
    if password:
        payload["password"] = password
    result = c.client.mc_add("relayhost", payload)
    handle_result(c, result, f"Relay host '{hostname}' created")


@app.command()
def update(
    ctx: typer.Context,
    relay_id: Annotated[str, typer.Argument(help="Relay host ID")],
    hostname: Annotated[str | None, typer.Option("--hostname")] = None,
    username: Annotated[str | None, typer.Option("--username")] = None,
    password: Annotated[str | None, typer.Option("--password")] = None,
    active: Annotated[bool | None, typer.Option("--active/--inactive")] = None,
) -> None:
    """Update a relay host."""
    c: AppContext = ctx.obj
    attr: dict = {}
    if hostname is not None:
        attr["hostname"] = hostname
    if username is not None:
        attr["username"] = username
    if password is not None:
        attr["password"] = password
    if active is not None:
        attr["active"] = "1" if active else "0"
    if not attr:
        c.output.warn("No fields to update")
        raise typer.Exit(0)
    result = c.client.mc_edit("relayhost", {"items": [relay_id], "attr": attr})
    handle_result(c, result, f"Relay host {relay_id} updated")


@app.command()
def delete(
    ctx: typer.Context,
    relay_id: Annotated[str, typer.Argument(help="Relay host ID")],
    force: Annotated[bool, typer.Option("--force")] = False,
) -> None:
    """Delete a relay host."""
    c: AppContext = ctx.obj
    if not force:
        if not typer.confirm(f"Delete relay host {relay_id}?"):
            raise typer.Exit(0)
    result = c.client.mc_delete("relayhost", [relay_id])
    handle_result(c, result, f"Relay host {relay_id} deleted")
