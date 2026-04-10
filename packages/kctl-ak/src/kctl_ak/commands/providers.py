"""Provider management commands (OAuth2, LDAP, SAML, Proxy)."""

from __future__ import annotations

from typing import Annotated, Any

import typer

app = typer.Typer(help="Provider management")
oauth2_app = typer.Typer(help="OAuth2 providers")
ldap_app = typer.Typer(help="LDAP providers")
saml_app = typer.Typer(help="SAML providers")
proxy_app = typer.Typer(help="Proxy providers")

app.add_typer(oauth2_app, name="oauth2")
app.add_typer(ldap_app, name="ldap")
app.add_typer(saml_app, name="saml")
app.add_typer(proxy_app, name="proxy")

PROVIDER_ENDPOINTS = {
    "oauth2": "providers/oauth2/",
    "ldap": "providers/ldap/",
    "saml": "providers/saml/",
    "proxy": "providers/proxy/",
}


def _get_authorization_flow(client) -> str:
    """Fetch the first authorization flow PK."""
    data = client.get("flows/instances/", params={"designation": "authorization"})
    results = data.get("results", [])
    if not results:
        raise typer.BadParameter("No authorization flow found. Create one first.")
    return results[0]["pk"]


# ── Top-level commands ──────────────────────────────────────────────


@app.command("list")
def list_(
    ctx: typer.Context,
    type_: Annotated[str | None, typer.Option("--type", help="Filter by type: oauth2, ldap, saml, proxy")] = None,
) -> None:
    """List all providers across types."""
    c = ctx.obj
    all_providers = []

    endpoints = {type_: PROVIDER_ENDPOINTS[type_]} if type_ and type_ in PROVIDER_ENDPOINTS else PROVIDER_ENDPOINTS

    for ptype, endpoint in endpoints.items():
        providers = c.client.get_all(endpoint)
        for p in providers:
            p["_type"] = ptype
        all_providers.extend(providers)

    rows = []
    for p in all_providers:
        rows.append(
            [
                str(p.get("pk", "")),
                p.get("_type", ""),
                p.get("name", ""),
                p.get("assigned_application_name", "") or "-",
            ]
        )

    c.output.table(
        "Providers",
        [("ID", "cyan"), ("Type", "yellow"), ("Name", ""), ("Application", "dim")],
        rows,
        data_for_json=all_providers,
    )


# ── OAuth2 ──────────────────────────────────────────────────────────


@oauth2_app.command("list")
def oauth2_list(ctx: typer.Context) -> None:
    """List OAuth2 providers."""
    c = ctx.obj
    providers = c.client.get_all("providers/oauth2/")
    rows = []
    for p in providers:
        rows.append(
            [
                str(p.get("pk", "")),
                p.get("name", ""),
                p.get("client_id", ""),
                p.get("client_type", ""),
                p.get("redirect_uris", "") or "-",
            ]
        )
    c.output.table(
        "OAuth2 Providers",
        [("ID", "cyan"), ("Name", ""), ("Client ID", "dim"), ("Type", ""), ("Redirect URIs", "dim")],
        rows,
        data_for_json=providers,
    )


@oauth2_app.command("get")
def oauth2_get(
    ctx: typer.Context,
    id_: Annotated[int, typer.Argument(metavar="ID", help="Provider ID")],
) -> None:
    """Get OAuth2 provider details."""
    c = ctx.obj
    p = c.client.get(f"providers/oauth2/{id_}/")
    c.output.detail(
        p.get("name", str(id_)),
        [
            (
                "Provider",
                [
                    ("ID", str(p.get("pk", ""))),
                    ("Name", p.get("name", "")),
                    ("Client type", p.get("client_type", "")),
                    ("Client ID", p.get("client_id", "")),
                    ("Redirect URIs", p.get("redirect_uris", "") or "-"),
                ],
            ),
            (
                "Settings",
                [
                    ("Authorization flow", p.get("authorization_flow", "-")),
                    ("Sub mode", p.get("sub_mode", "-")),
                    ("Access token validity", p.get("access_token_validity", "-")),
                ],
            ),
        ],
        data_for_json=p,
    )


@oauth2_app.command("create")
def oauth2_create(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Provider name")],
    redirect_uri: Annotated[str, typer.Argument(help="Redirect URI")],
    client_type: Annotated[str, typer.Option("--client-type", help="Client type")] = "confidential",
) -> None:
    """Create an OAuth2 provider."""
    c = ctx.obj
    flow_pk = _get_authorization_flow(c.client)
    payload = {
        "name": name,
        "redirect_uris": redirect_uri,
        "client_type": client_type,
        "authorization_flow": flow_pk,
    }
    result = c.client.post("providers/oauth2/", data=payload)
    c.output.success(f"Created OAuth2 provider '{result.get('name', name)}' (ID: {result.get('pk', '?')})")
    c.output.info(f"Client ID: {result.get('client_id', '')}")
    if result.get("client_secret"):
        c.output.info(f"Client Secret: {result['client_secret']}")


@oauth2_app.command("credentials")
def oauth2_credentials(
    ctx: typer.Context,
    id_: Annotated[int, typer.Argument(metavar="ID", help="Provider ID")],
) -> None:
    """Show client_id and client_secret for an OAuth2 provider."""
    c = ctx.obj
    p = c.client.get(f"providers/oauth2/{id_}/")
    if c.output.json_mode:
        c.output.raw_json(
            {
                "client_id": p.get("client_id", ""),
                "client_secret": p.get("client_secret", ""),
            }
        )
    else:
        c.output.header(f"Credentials: {p.get('name', str(id_))}")
        c.output.kv("Client ID", p.get("client_id", ""))
        c.output.kv("Client Secret", p.get("client_secret", "") or "(not available)")


@oauth2_app.command("delete")
def oauth2_delete(
    ctx: typer.Context,
    id_: Annotated[int, typer.Argument(metavar="ID", help="Provider ID")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete an OAuth2 provider."""
    if not force:
        typer.confirm(f"Delete OAuth2 provider {id_}?", abort=True)
    c = ctx.obj
    c.client.delete(f"providers/oauth2/{id_}/")
    c.output.success(f"Deleted OAuth2 provider {id_}")


_SUB_MODES = {
    "hashed_user_id",
    "user_id",
    "user_uuid",
    "user_username",
    "user_email",
    "user_upn",
}


@oauth2_app.command("update")
def oauth2_update(
    ctx: typer.Context,
    provider_id: Annotated[int, typer.Argument(help="Provider ID")],
    client_type: Annotated[
        str | None, typer.Option("--client-type", help="Client type: public or confidential")
    ] = None,
    name: Annotated[str | None, typer.Option("--name", help="Provider name")] = None,
    redirect_uris: Annotated[str | None, typer.Option("--redirect-uri", help="Redirect URI")] = None,
    signing_key: Annotated[
        str | None,
        typer.Option(
            "--signing-key",
            help="Signing key UUID. Providers without a signing key return empty JWKS "
            "and break OIDC clients (e.g. Odoo auth_oidc) — use `--sign-with-default` "
            "to auto-pick the first self-signed cert.",
        ),
    ] = None,
    sign_with_default: Annotated[
        bool,
        typer.Option(
            "--sign-with-default",
            help="Auto-pick the default self-signed certificate as the signing key.",
        ),
    ] = False,
    sub_mode: Annotated[
        str | None,
        typer.Option(
            "--sub-mode",
            help=(
                "OIDC `sub` claim mode: "
                "hashed_user_id | user_id | user_uuid | user_username | user_email | user_upn. "
                "Use `user_uuid` for Odoo auth_oidc so oauth_uid is stable and unique."
            ),
        ),
    ] = None,
    issuer_mode: Annotated[
        str | None,
        typer.Option(
            "--issuer-mode",
            help="Issuer mode: per_provider | global",
        ),
    ] = None,
) -> None:
    """Update an OAuth2 provider.

    Common fix for broken Odoo OIDC:

        kctl-ak providers oauth2 update 42 --sign-with-default --sub-mode user_uuid
    """
    c = ctx.obj

    payload: dict[str, Any] = {}
    if client_type is not None:
        if client_type not in ("public", "confidential"):
            c.output.error("client_type must be 'public' or 'confidential'")
            raise typer.Exit(1)
        payload["client_type"] = client_type
    if name is not None:
        payload["name"] = name
    if redirect_uris is not None:
        payload["redirect_uris"] = redirect_uris

    # Resolve signing key: --signing-key takes precedence over --sign-with-default
    if signing_key and sign_with_default:
        c.output.error("Use either --signing-key or --sign-with-default, not both")
        raise typer.Exit(1)
    if signing_key is not None:
        payload["signing_key"] = signing_key
    elif sign_with_default:
        # Import inside the function to avoid a circular import with setup.py
        from kctl_ak.commands.setup import _find_signing_cert

        resolved = _find_signing_cert(c.client)
        if not resolved:
            c.output.error(
                "No signing certificate available on this Authentik instance. "
                "Create one under System → Certificates first."
            )
            raise typer.Exit(1)
        payload["signing_key"] = resolved
        c.output.info(f"Auto-selected signing key: {resolved}")

    if sub_mode is not None:
        if sub_mode not in _SUB_MODES:
            c.output.error(f"sub_mode must be one of: {', '.join(sorted(_SUB_MODES))}")
            raise typer.Exit(1)
        payload["sub_mode"] = sub_mode

    if issuer_mode is not None:
        if issuer_mode not in ("per_provider", "global"):
            c.output.error("issuer_mode must be 'per_provider' or 'global'")
            raise typer.Exit(1)
        payload["issuer_mode"] = issuer_mode

    if not payload:
        c.output.error(
            "No fields to update. Use --client-type / --name / --redirect-uri / "
            "--signing-key / --sign-with-default / --sub-mode / --issuer-mode"
        )
        raise typer.Exit(1)

    # AuthentikClient.patch takes positional `data`, not `json` kwarg.
    result = c.client.patch(f"providers/oauth2/{provider_id}/", data=payload)

    if c.output.json_mode:
        c.output.raw_json(result)
        return

    c.output.success(f"Provider {provider_id} updated")
    if isinstance(result, dict):
        c.output.info(f"  Name: {result.get('name', '?')}")
        c.output.info(f"  Client type: {result.get('client_type', '?')}")
        if "signing_key" in payload:
            c.output.info(f"  Signing key: {result.get('signing_key', '?')}")
        if "sub_mode" in payload:
            c.output.info(f"  Sub mode: {result.get('sub_mode', '?')}")


# ── LDAP ────────────────────────────────────────────────────────────


@ldap_app.command("list")
def ldap_list(ctx: typer.Context) -> None:
    """List LDAP providers."""
    c = ctx.obj
    providers = c.client.get_all("providers/ldap/")
    rows = []
    for p in providers:
        rows.append(
            [
                str(p.get("pk", "")),
                p.get("name", ""),
                p.get("base_dn", ""),
            ]
        )
    c.output.table(
        "LDAP Providers",
        [("ID", "cyan"), ("Name", ""), ("Base DN", "dim")],
        rows,
        data_for_json=providers,
    )


@ldap_app.command("get")
def ldap_get(
    ctx: typer.Context,
    id_: Annotated[int, typer.Argument(metavar="ID", help="Provider ID")],
) -> None:
    """Get LDAP provider details."""
    c = ctx.obj
    p = c.client.get(f"providers/ldap/{id_}/")
    c.output.detail(
        p.get("name", str(id_)),
        [
            (
                "Provider",
                [
                    ("ID", str(p.get("pk", ""))),
                    ("Name", p.get("name", "")),
                    ("Base DN", p.get("base_dn", "")),
                    ("Authorization flow", p.get("authorization_flow", "-")),
                ],
            ),
        ],
        data_for_json=p,
    )


@ldap_app.command("create")
def ldap_create(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Provider name")],
    base_dn: Annotated[str, typer.Argument(help="Base DN")],
) -> None:
    """Create an LDAP provider."""
    c = ctx.obj
    flow_pk = _get_authorization_flow(c.client)
    payload = {
        "name": name,
        "base_dn": base_dn,
        "authorization_flow": flow_pk,
    }
    result = c.client.post("providers/ldap/", data=payload)
    c.output.success(f"Created LDAP provider '{result.get('name', name)}' (ID: {result.get('pk', '?')})")


@ldap_app.command("delete")
def ldap_delete(
    ctx: typer.Context,
    id_: Annotated[int, typer.Argument(metavar="ID", help="Provider ID")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete an LDAP provider."""
    if not force:
        typer.confirm(f"Delete LDAP provider {id_}?", abort=True)
    c = ctx.obj
    c.client.delete(f"providers/ldap/{id_}/")
    c.output.success(f"Deleted LDAP provider {id_}")


# ── SAML ────────────────────────────────────────────────────────────


@saml_app.command("list")
def saml_list(ctx: typer.Context) -> None:
    """List SAML providers."""
    c = ctx.obj
    providers = c.client.get_all("providers/saml/")
    rows = []
    for p in providers:
        rows.append(
            [
                str(p.get("pk", "")),
                p.get("name", ""),
                p.get("acs_url", "") or "-",
                p.get("issuer", "") or "-",
            ]
        )
    c.output.table(
        "SAML Providers",
        [("ID", "cyan"), ("Name", ""), ("ACS URL", "dim"), ("Issuer", "dim")],
        rows,
        data_for_json=providers,
    )


@saml_app.command("get")
def saml_get(
    ctx: typer.Context,
    id_: Annotated[int, typer.Argument(metavar="ID", help="Provider ID")],
) -> None:
    """Get SAML provider details."""
    c = ctx.obj
    p = c.client.get(f"providers/saml/{id_}/")
    c.output.detail(
        p.get("name", str(id_)),
        [
            (
                "Provider",
                [
                    ("ID", str(p.get("pk", ""))),
                    ("Name", p.get("name", "")),
                    ("ACS URL", p.get("acs_url", "") or "-"),
                    ("Issuer", p.get("issuer", "") or "-"),
                    ("Authorization flow", p.get("authorization_flow", "-")),
                ],
            ),
        ],
        data_for_json=p,
    )


@saml_app.command("create")
def saml_create(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Provider name")],
    acs_url: Annotated[str, typer.Argument(help="ACS URL")],
) -> None:
    """Create a SAML provider."""
    c = ctx.obj
    flow_pk = _get_authorization_flow(c.client)
    payload = {
        "name": name,
        "acs_url": acs_url,
        "authorization_flow": flow_pk,
    }
    result = c.client.post("providers/saml/", data=payload)
    c.output.success(f"Created SAML provider '{result.get('name', name)}' (ID: {result.get('pk', '?')})")


@saml_app.command("metadata")
def saml_metadata(
    ctx: typer.Context,
    id_: Annotated[int, typer.Argument(metavar="ID", help="Provider ID")],
) -> None:
    """Get SAML metadata XML."""
    c = ctx.obj
    resp = c.client.request("GET", f"providers/saml/{id_}/metadata/")
    content_type = resp.headers.get("content-type", "")
    if "xml" in content_type or resp.text.strip().startswith("<?xml"):
        typer.echo(resp.text)
    else:
        data = resp.json()
        if c.output.json_mode:
            c.output.raw_json(data)
        else:
            typer.echo(data.get("metadata", resp.text))


@saml_app.command("delete")
def saml_delete(
    ctx: typer.Context,
    id_: Annotated[int, typer.Argument(metavar="ID", help="Provider ID")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete a SAML provider."""
    if not force:
        typer.confirm(f"Delete SAML provider {id_}?", abort=True)
    c = ctx.obj
    c.client.delete(f"providers/saml/{id_}/")
    c.output.success(f"Deleted SAML provider {id_}")


# ── Proxy ───────────────────────────────────────────────────────────


@proxy_app.command("list")
def proxy_list(ctx: typer.Context) -> None:
    """List Proxy providers."""
    c = ctx.obj
    providers = c.client.get_all("providers/proxy/")
    rows = []
    for p in providers:
        rows.append(
            [
                str(p.get("pk", "")),
                p.get("name", ""),
                p.get("external_host", ""),
                p.get("mode", ""),
            ]
        )
    c.output.table(
        "Proxy Providers",
        [("ID", "cyan"), ("Name", ""), ("External Host", ""), ("Mode", "dim")],
        rows,
        data_for_json=providers,
    )


@proxy_app.command("get")
def proxy_get(
    ctx: typer.Context,
    id_: Annotated[int, typer.Argument(metavar="ID", help="Provider ID")],
) -> None:
    """Get Proxy provider details."""
    c = ctx.obj
    p = c.client.get(f"providers/proxy/{id_}/")
    c.output.detail(
        p.get("name", str(id_)),
        [
            (
                "Provider",
                [
                    ("ID", str(p.get("pk", ""))),
                    ("Name", p.get("name", "")),
                    ("External host", p.get("external_host", "")),
                    ("Internal host", p.get("internal_host", "") or "-"),
                    ("Mode", p.get("mode", "")),
                    ("Authorization flow", p.get("authorization_flow", "-")),
                ],
            ),
        ],
        data_for_json=p,
    )


@proxy_app.command("create")
def proxy_create(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Provider name")],
    external_host: Annotated[str, typer.Argument(help="External host URL")],
    internal_host: Annotated[str | None, typer.Option("--internal-host", help="Internal host URL")] = None,
    mode: Annotated[str, typer.Option("--mode", help="Proxy mode")] = "forward_single",
) -> None:
    """Create a Proxy provider."""
    c = ctx.obj
    flow_pk = _get_authorization_flow(c.client)
    payload: dict = {
        "name": name,
        "external_host": external_host,
        "mode": mode,
        "authorization_flow": flow_pk,
    }
    if internal_host is not None:
        payload["internal_host"] = internal_host
    result = c.client.post("providers/proxy/", data=payload)
    c.output.success(f"Created Proxy provider '{result.get('name', name)}' (ID: {result.get('pk', '?')})")


@proxy_app.command("delete")
def proxy_delete(
    ctx: typer.Context,
    id_: Annotated[int, typer.Argument(metavar="ID", help="Provider ID")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete a Proxy provider."""
    if not force:
        typer.confirm(f"Delete Proxy provider {id_}?", abort=True)
    c = ctx.obj
    c.client.delete(f"providers/proxy/{id_}/")
    c.output.success(f"Deleted Proxy provider {id_}")
