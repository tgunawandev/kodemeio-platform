"""Domain admin management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_mailcow.core.callbacks import AppContext
from kctl_mailcow.core.helpers import handle_result

app = typer.Typer(help="Manage domain administrators.")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all domain admins."""
    c: AppContext = ctx.obj
    data = c.client.mc_get("domain-admin/all")
    items = data if isinstance(data, list) else []

    if not items:
        c.output.info("No domain admins found.")
        if c.json_mode:
            c.output.raw_json([])
        return

    rows = []
    for item in items:
        active = "[green]yes[/green]" if str(item.get("active")) == "1" else "[red]no[/red]"
        domains = ", ".join(item.get("selected_domains", []))
        rows.append([item.get("username", ""), domains, active])

    c.output.table(
        "Domain Admins",
        [("Username", "cyan"), ("Domains", ""), ("Active", "")],
        rows,
        data_for_json=items,
    )


@app.command()
def get(
    ctx: typer.Context,
    username: Annotated[str, typer.Argument(help="Admin username")],
) -> None:
    """Get domain admin details."""
    c: AppContext = ctx.obj
    data = c.client.mc_get(f"domain-admin/{username}")
    item = data[0] if isinstance(data, list) and data else data if isinstance(data, dict) else {}

    if not item:
        c.output.error(f"Domain admin not found: {username}")
        raise typer.Exit(1)

    sections = [
        (
            "Domain Admin",
            [
                ("Username", str(item.get("username", ""))),
                ("Domains", ", ".join(item.get("selected_domains", []))),
                ("Active", str(item.get("active", ""))),
                ("Created", str(item.get("created", ""))),
            ],
        )
    ]
    c.output.detail(f"Domain Admin: {username}", sections, data_for_json=item)


@app.command()
def create(
    ctx: typer.Context,
    username: Annotated[str, typer.Argument(help="Admin username")],
    password: Annotated[str, typer.Option("--password", prompt=True, hide_input=True)],
    domains: Annotated[str, typer.Option("--domains", help="Comma-separated domain list")],
    active: Annotated[bool, typer.Option("--active/--inactive")] = True,
) -> None:
    """Create a domain admin."""
    c: AppContext = ctx.obj
    payload = {
        "username": username,
        "password": password,
        "password2": password,
        "domains": domains,
        "active": "1" if active else "0",
    }
    result = c.client.mc_add("domain-admin", payload)
    handle_result(c, result, f"Domain admin '{username}' created")


@app.command()
def update(
    ctx: typer.Context,
    username: Annotated[str, typer.Argument(help="Admin username")],
    password: Annotated[str | None, typer.Option("--password")] = None,
    domains: Annotated[str | None, typer.Option("--domains")] = None,
    active: Annotated[bool | None, typer.Option("--active/--inactive")] = None,
) -> None:
    """Update domain admin settings."""
    c: AppContext = ctx.obj
    attr: dict = {}
    if password is not None:
        attr["password"] = password
        attr["password2"] = password
    if domains is not None:
        attr["domains"] = domains
    if active is not None:
        attr["active"] = "1" if active else "0"

    if not attr:
        c.output.warn("No fields to update")
        raise typer.Exit(0)

    payload = {"items": [username], "attr": attr}
    result = c.client.mc_edit("domain-admin", payload)
    handle_result(c, result, f"Domain admin '{username}' updated")


@app.command()
def delete(
    ctx: typer.Context,
    username: Annotated[str, typer.Argument(help="Admin username")],
    force: Annotated[bool, typer.Option("--force")] = False,
) -> None:
    """Delete a domain admin."""
    c: AppContext = ctx.obj
    if not force:
        if not typer.confirm(f"Delete domain admin '{username}'?"):
            raise typer.Exit(0)
    result = c.client.mc_delete("domain-admin", [username])
    handle_result(c, result, f"Domain admin '{username}' deleted")
