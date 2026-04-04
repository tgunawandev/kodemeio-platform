"""Identity provider (OIDC/OAuth2) configuration for Mailcow admin SSO."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_mailcow.core.callbacks import AppContext
from kctl_mailcow.core.helpers import handle_result

app = typer.Typer(help="Manage external identity provider (OIDC SSO) for admin login.")


@app.command()
def get(ctx: typer.Context) -> None:
    """Show current identity provider configuration."""
    c: AppContext = ctx.obj
    data = c.client.mc_get("identity-provider")

    if not data or (isinstance(data, dict) and not data.get("authsource")):
        c.output.info("No identity provider configured.")
        if c.json_mode:
            c.output.raw_json(data or {})
        return

    item = data if isinstance(data, dict) else {}
    sections = [
        (
            "Identity Provider",
            [
                ("Auth Source", str(item.get("authsource", ""))),
                ("Server URL", str(item.get("server_url", ""))),
                ("Client ID", str(item.get("client_id", ""))),
                ("Authorize URL", str(item.get("authorize_url", ""))),
                ("Token URL", str(item.get("token_url", ""))),
                ("Userinfo URL", str(item.get("userinfo_url", ""))),
                ("Scopes", str(item.get("scopes", ""))),
                ("Redirect URI", str(item.get("redirect_url", ""))),
            ],
        )
    ]
    c.output.detail("Identity Provider Config", sections, data_for_json=item)


@app.command("set")
def set_(
    ctx: typer.Context,
    server_url: Annotated[str, typer.Option("--server-url", help="OIDC provider URL (e.g. https://auth.kodeme.io)")],
    client_id: Annotated[str, typer.Option("--client-id", help="OAuth2 client ID")],
    client_secret: Annotated[
        str, typer.Option("--client-secret", help="OAuth2 client secret", prompt=True, hide_input=True)
    ],
    redirect_url: Annotated[str | None, typer.Option("--redirect-uri", help="Redirect URI")] = None,
    authorize_url: Annotated[str | None, typer.Option("--authorize-url", help="Authorization endpoint")] = None,
    token_url: Annotated[str | None, typer.Option("--token-url", help="Token endpoint")] = None,
    userinfo_url: Annotated[str | None, typer.Option("--userinfo-url", help="Userinfo endpoint")] = None,
    scopes: Annotated[str, typer.Option("--scopes", help="OAuth2 scopes")] = "openid profile email",
) -> None:
    """Configure external OIDC identity provider for Mailcow admin SSO."""
    c: AppContext = ctx.obj
    payload: dict = {
        "authsource": "oidc",
        "server_url": server_url,
        "client_id": client_id,
        "client_secret": client_secret,
        "scopes": scopes,
    }
    if redirect_url:
        payload["redirect_url"] = redirect_url
    if authorize_url:
        payload["authorize_url"] = authorize_url
    if token_url:
        payload["token_url"] = token_url
    if userinfo_url:
        payload["userinfo_url"] = userinfo_url

    result = c.client.mc_edit("identity-provider", payload)
    handle_result(c, result, "Identity provider configured")


@app.command()
def delete(
    ctx: typer.Context,
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Remove identity provider configuration."""
    c: AppContext = ctx.obj
    if not force:
        if not typer.confirm("Remove identity provider configuration?"):
            raise typer.Exit(0)
    result = c.client.mc_delete("identity-provider", ["oidc"])
    handle_result(c, result, "Identity provider removed")


@app.command()
def test(ctx: typer.Context) -> None:
    """Test identity provider connectivity."""
    c: AppContext = ctx.obj
    try:
        data = c.client.mc_get("identity-provider")
        if isinstance(data, dict) and data.get("authsource"):
            c.output.success(f"Identity provider configured: {data.get('server_url', 'unknown')}")
        else:
            c.output.warn("No identity provider configured")
    except Exception as e:
        c.output.error(f"Test failed: {e}")
        raise typer.Exit(1)
