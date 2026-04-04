"""Per-mailbox application password management."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_mailcow.core.callbacks import AppContext
from kctl_mailcow.core.helpers import handle_result

app = typer.Typer(help="Manage per-mailbox app passwords.")


@app.command("list")
def list_(
    ctx: typer.Context,
    mailbox: Annotated[str | None, typer.Option("--mailbox", "-m", help="Filter by mailbox")] = None,
) -> None:
    """List app passwords."""
    c: AppContext = ctx.obj
    data = c.client.mc_get("app-passwd/all")
    items = data if isinstance(data, list) else []

    if mailbox:
        items = [p for p in items if p.get("mailbox", "") == mailbox]

    if not items:
        c.output.info("No app passwords found.")
        if c.json_mode:
            c.output.raw_json([])
        return

    rows = []
    for item in items:
        active = "[green]yes[/green]" if str(item.get("active")) == "1" else "[red]no[/red]"
        rows.append(
            [
                str(item.get("id", "")),
                item.get("mailbox", ""),
                item.get("name", ""),
                active,
                item.get("created", ""),
            ]
        )

    c.output.table(
        "App Passwords",
        [("ID", "dim"), ("Mailbox", "cyan"), ("Name", ""), ("Active", ""), ("Created", "dim")],
        rows,
        data_for_json=items,
    )


@app.command()
def create(
    ctx: typer.Context,
    mailbox: Annotated[str, typer.Argument(help="Mailbox email address")],
    name: Annotated[str, typer.Option("--name", "-n", help="App password name/label")],
    password: Annotated[str, typer.Option("--password", prompt=True, hide_input=True, help="App password")],
    active: Annotated[bool, typer.Option("--active/--inactive")] = True,
) -> None:
    """Create an app password for a mailbox."""
    c: AppContext = ctx.obj
    payload = {
        "username": mailbox,
        "name": name,
        "password": password,
        "password2": password,
        "active": "1" if active else "0",
    }
    result = c.client.mc_add("app-passwd", payload)
    handle_result(c, result, f"App password '{name}' created for {mailbox}")


@app.command()
def delete(
    ctx: typer.Context,
    password_id: Annotated[str, typer.Argument(help="App password ID")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete an app password."""
    c: AppContext = ctx.obj
    if not force:
        if not typer.confirm(f"Delete app password {password_id}?"):
            raise typer.Exit(0)
    result = c.client.mc_delete("app-passwd", [password_id])
    handle_result(c, result, f"App password {password_id} deleted")
