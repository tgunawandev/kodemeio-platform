"""Whole-domain alias management."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_mailcow.core.callbacks import AppContext
from kctl_mailcow.core.helpers import handle_result

app = typer.Typer(help="Manage domain aliases (whole-domain aliasing).")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all domain aliases."""
    c: AppContext = ctx.obj
    data = c.client.mc_get("alias-domain/all")
    items = data if isinstance(data, list) else []
    if not items:
        c.output.info("No domain aliases configured.")
        if c.json_mode:
            c.output.raw_json([])
        return

    rows = []
    for item in items:
        active = "[green]yes[/green]" if str(item.get("active")) == "1" else "[red]no[/red]"
        rows.append([item.get("alias_domain", ""), item.get("target_domain", ""), active])

    c.output.table(
        "Domain Aliases", [("Alias Domain", "cyan"), ("Target Domain", ""), ("Active", "")], rows, data_for_json=items
    )


@app.command()
def create(
    ctx: typer.Context,
    alias_domain: Annotated[str, typer.Argument(help="Alias domain name")],
    target_domain: Annotated[str, typer.Argument(help="Target domain name")],
    active: Annotated[bool, typer.Option("--active/--inactive")] = True,
) -> None:
    """Create a domain alias."""
    c: AppContext = ctx.obj
    payload = {"alias_domain": alias_domain, "target_domain": target_domain, "active": "1" if active else "0"}
    result = c.client.mc_add("alias-domain", payload)
    handle_result(c, result, f"Domain alias '{alias_domain}' → '{target_domain}' created")


@app.command()
def update(
    ctx: typer.Context,
    alias_domain: Annotated[str, typer.Argument(help="Alias domain")],
    target_domain: Annotated[str | None, typer.Option("--target-domain")] = None,
    active: Annotated[bool | None, typer.Option("--active/--inactive")] = None,
) -> None:
    """Update a domain alias."""
    c: AppContext = ctx.obj
    attr: dict = {}
    if target_domain is not None:
        attr["target_domain"] = target_domain
    if active is not None:
        attr["active"] = "1" if active else "0"
    if not attr:
        c.output.warn("No fields to update")
        raise typer.Exit(0)
    result = c.client.mc_edit("alias-domain", {"items": [alias_domain], "attr": attr})
    handle_result(c, result, f"Domain alias '{alias_domain}' updated")


@app.command()
def delete(
    ctx: typer.Context,
    alias_domain: Annotated[str, typer.Argument(help="Alias domain")],
    force: Annotated[bool, typer.Option("--force")] = False,
) -> None:
    """Delete a domain alias."""
    c: AppContext = ctx.obj
    if not force:
        if not typer.confirm(f"Delete domain alias '{alias_domain}'?"):
            raise typer.Exit(0)
    result = c.client.mc_delete("alias-domain", [alias_domain])
    handle_result(c, result, f"Domain alias '{alias_domain}' deleted")
