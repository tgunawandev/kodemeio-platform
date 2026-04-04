"""OAuth2 client management — Mailcow as OAuth2 provider."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_mailcow.core.callbacks import AppContext
from kctl_mailcow.core.helpers import handle_result

app = typer.Typer(help="Manage OAuth2 clients (Mailcow as provider).")


@app.command("list")
def list_(ctx: typer.Context) -> None:
    """List all OAuth2 clients."""
    c: AppContext = ctx.obj
    data = c.client.mc_get("oauth2-client/all")
    items = data if isinstance(data, list) else []

    if not items:
        c.output.info("No OAuth2 clients configured.")
        if c.json_mode:
            c.output.raw_json([])
        return

    rows = []
    for item in items:
        rows.append(
            [
                str(item.get("id", "")),
                item.get("client_id", ""),
                item.get("redirect_uri", ""),
                item.get("scope", ""),
            ]
        )

    c.output.table(
        "OAuth2 Clients",
        [("ID", "dim"), ("Client ID", "cyan"), ("Redirect URI", ""), ("Scope", "")],
        rows,
        data_for_json=items,
    )


@app.command()
def get(
    ctx: typer.Context,
    client_id: Annotated[str, typer.Argument(help="Client ID")],
) -> None:
    """Get OAuth2 client details."""
    c: AppContext = ctx.obj
    data = c.client.mc_get(f"oauth2-client/{client_id}")
    item = data[0] if isinstance(data, list) and data else data if isinstance(data, dict) else {}

    if not item:
        c.output.error(f"OAuth2 client not found: {client_id}")
        raise typer.Exit(1)

    sections = [
        (
            "OAuth2 Client",
            [
                ("ID", str(item.get("id", ""))),
                ("Client ID", str(item.get("client_id", ""))),
                ("Redirect URI", str(item.get("redirect_uri", ""))),
                ("Scope", str(item.get("scope", ""))),
            ],
        )
    ]
    c.output.detail(f"OAuth2 Client: {client_id}", sections, data_for_json=item)


@app.command()
def create(
    ctx: typer.Context,
    redirect_uri: Annotated[str, typer.Option("--redirect-uri", "-r", help="OAuth2 redirect URI")],
    scope: Annotated[str, typer.Option("--scope", help="Allowed scopes")] = "profile",
) -> None:
    """Create a new OAuth2 client."""
    c: AppContext = ctx.obj
    payload = {
        "redirect_uri": redirect_uri,
        "scope": scope,
    }
    result = c.client.mc_add("oauth2-client", payload)
    handle_result(c, result, "OAuth2 client created")


@app.command()
def delete(
    ctx: typer.Context,
    client_id: Annotated[str, typer.Argument(help="Client ID to delete")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete an OAuth2 client."""
    c: AppContext = ctx.obj
    if not force:
        if not typer.confirm(f"Delete OAuth2 client '{client_id}'?"):
            raise typer.Exit(0)
    result = c.client.mc_delete("oauth2-client", [client_id])
    handle_result(c, result, f"OAuth2 client '{client_id}' deleted")
