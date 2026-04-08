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
                ("Client ID", str(item.get("client_id", ""))),
                ("Authorize URL", str(item.get("authorize_url", ""))),
                ("Token URL", str(item.get("token_url", ""))),
                ("Userinfo URL", str(item.get("userinfo_url", ""))),
                # Mailcow uses client_scopes; older versions used scopes
                ("Scopes", str(item.get("client_scopes") or item.get("scopes", ""))),
                ("Redirect URI", str(item.get("redirect_url", ""))),
                ("Login Provisioning", "yes" if item.get("login_provisioning") else "no"),
                ("Ignore SSL Errors", "yes" if item.get("ignore_ssl_error") else "no"),
            ],
        )
    ]
    c.output.detail("Identity Provider Config", sections, data_for_json=item)


@app.command("set")
def set_(
    ctx: typer.Context,
    server_url: Annotated[
        str,
        typer.Option(
            "--server-url",
            help="OIDC provider URL (e.g. https://auth.kodeme.io/application/o/<slug>/)",
        ),
    ],
    client_id: Annotated[str, typer.Option("--client-id", help="OAuth2 client ID")],
    client_secret: Annotated[
        str,
        typer.Option("--client-secret", help="OAuth2 client secret", prompt=True, hide_input=True),
    ],
    authorize_url: Annotated[str, typer.Option("--authorize-url", help="Authorization endpoint")],
    token_url: Annotated[str, typer.Option("--token-url", help="Token endpoint")],
    userinfo_url: Annotated[str, typer.Option("--userinfo-url", help="Userinfo endpoint")],
    redirect_url: Annotated[str, typer.Option("--redirect-uri", help="Redirect URI (Mailcow base URL)")],
    scopes: Annotated[str, typer.Option("--scopes", help="OAuth2 scopes")] = "openid profile email",
    authsource: Annotated[
        str,
        typer.Option("--authsource", help="Mailcow auth source type (generic-oidc, keycloak, ldap, etc.)"),
    ] = "generic-oidc",
    login_provisioning: Annotated[
        bool,
        typer.Option(
            "--login-provisioning/--no-login-provisioning",
            help="Auto-create mailbox on first SSO login",
        ),
    ] = True,
    ignore_ssl_error: Annotated[
        bool,
        typer.Option("--ignore-ssl-error/--verify-ssl", help="Ignore TLS verification errors"),
    ] = False,
) -> None:
    """Configure external OIDC identity provider for Mailcow admin/user SSO.

    Mailcow's edit endpoint is "set or replace" — partial updates are not
    supported. Always pass all required URLs.

    Example:
      kctl-mailcow identity-provider set \\
        --server-url https://auth.idtpp.com/application/o/mailcow/ \\
        --client-id <id> --client-secret <secret> \\
        --authorize-url https://auth.idtpp.com/application/o/authorize/ \\
        --token-url https://auth.idtpp.com/application/o/token/ \\
        --userinfo-url https://auth.idtpp.com/application/o/userinfo/ \\
        --redirect-uri https://mail.idtpp.com/
    """
    c: AppContext = ctx.obj
    attr = {
        "authsource": authsource,
        "server_url": server_url,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_url": redirect_url,
        "authorize_url": authorize_url,
        "token_url": token_url,
        "userinfo_url": userinfo_url,
        "client_scopes": scopes,
        "login_provisioning": "1" if login_provisioning else "0",
        "ignore_ssl_error": "1" if ignore_ssl_error else "0",
    }
    # Mailcow edit API expects {"attr": {...}} envelope (no items needed for IdP)
    result = c.client.mc_edit("identity-provider", {"attr": attr})
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
