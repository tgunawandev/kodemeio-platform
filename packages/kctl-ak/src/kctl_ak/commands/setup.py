"""Setup wizard commands.

Quickly create OAuth2/Proxy providers with linked applications,
manage admin access, and generate recovery links.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
import yaml

from kctl_ak.core.callbacks import AppContext
from kctl_ak.core.config import resolve_app_registry_path
from kctl_ak.core.exceptions import NotFoundError
from kctl_ak.core.resolve import resolve_user

app = typer.Typer(help="Setup wizards for providers, apps, and admin access.")


def _find_authorization_flow(client) -> dict | None:
    """Find the default authorization flow."""
    flows = client.get_all("flows/instances/", params={"designation": "authorization"})
    if flows:
        # Prefer 'default-provider-authorization-implicit-consent' or first match
        for f in flows:
            if "implicit-consent" in f.get("slug", ""):
                return f
        return flows[0]
    return None


def _find_authentication_flow(client) -> dict | None:
    """Find the default authentication flow."""
    flows = client.get_all("flows/instances/", params={"designation": "authentication"})
    if flows:
        for f in flows:
            if "default-authentication-flow" in f.get("slug", ""):
                return f
        return flows[0]
    return None


def _find_invalidation_flow(client) -> dict | None:
    """Find the default provider invalidation flow."""
    flows = client.get_all("flows/instances/", params={"designation": "invalidation"})
    if flows:
        for f in flows:
            if "default-provider-invalidation-flow" in f.get("slug", ""):
                return f
        return flows[0]
    return None


def _slugify(name: str) -> str:
    """Convert a name to a slug."""
    return name.lower().replace(" ", "-").replace("_", "-")


def _find_signing_cert(client) -> str | None:
    """Find a suitable signing key for an OAuth2 / OIDC provider.

    Returns the ``pk`` (UUID string) of the first RSA self-signed
    certificate keypair with a private key. Preference order:

    1. The default "authentik Self-signed Certificate" (ships with every
       new Authentik install).
    2. Any other keypair whose name contains "self-signed" or "default".
    3. The first keypair with a private key.

    Returns ``None`` only if the instance has no usable keypairs at all,
    which should be impossible on a freshly initialised Authentik.

    OIDC providers REQUIRE a signing key so the id_token can be signed
    with RS256 and the ``/application/o/<slug>/jwks/`` endpoint returns
    real keys. Without this, Odoo's ``auth_oidc`` chokes decoding the
    id_token and every login attempt returns ``?oauth_error=2``.
    """
    try:
        certs = client.get_all("crypto/certificatekeypairs/")
    except Exception:
        return None
    if not certs:
        return None

    def _has_private_key(c: dict) -> bool:
        return bool(c.get("private_key_available") or c.get("key_data"))

    # Preference 1: the default self-signed cert
    for c in certs:
        name = (c.get("name") or "").lower()
        if "authentik self-signed certificate" in name and _has_private_key(c):
            return c.get("pk")
    # Preference 2: any self-signed / default named cert
    for c in certs:
        name = (c.get("name") or "").lower()
        if ("self-signed" in name or "default" in name) and _has_private_key(c):
            return c.get("pk")
    # Preference 3: first keypair with a private key
    for c in certs:
        if _has_private_key(c):
            return c.get("pk")
    return None


@app.command()
def status(ctx: typer.Context) -> None:
    """Show what is currently configured."""
    actx: AppContext = ctx.obj
    c = actx.client
    out = actx.output

    sections: list[tuple[str, list[tuple[str, str]]]] = []

    # Flows
    try:
        flows = c.get_all("flows/instances/")
        flow_kvs: list[tuple[str, str]] = []
        designations: dict[str, int] = {}
        for f in flows:
            d = f.get("designation", "unknown")
            designations[d] = designations.get(d, 0) + 1
        for d, count in sorted(designations.items()):
            flow_kvs.append((d, str(count)))
        flow_kvs.append(("Total", str(len(flows))))
        sections.append(("Flows", flow_kvs))
    except Exception:
        sections.append(("Flows", [("Status", "[red]error[/red]")]))

    # Providers
    try:
        providers = c.get_all("providers/all/")
        prov_kvs: list[tuple[str, str]] = []
        types: dict[str, int] = {}
        for p in providers:
            t = p.get("verbose_name", p.get("component", "unknown"))
            types[t] = types.get(t, 0) + 1
        for t, count in sorted(types.items()):
            prov_kvs.append((t, str(count)))
        prov_kvs.append(("Total", str(len(providers))))
        sections.append(("Providers", prov_kvs))
    except Exception:
        sections.append(("Providers", [("Status", "[red]error[/red]")]))

    # Applications
    try:
        apps = c.get_all("core/applications/")
        app_kvs: list[tuple[str, str]] = []
        for a in apps:
            name = a.get("name", "")
            slug = a.get("slug", "")
            provider = a.get("provider_obj", {})
            prov_name = ""
            if isinstance(provider, dict) and provider:
                prov_name = provider.get("name", "")
            app_kvs.append((name, f"{slug} -> {prov_name}" if prov_name else slug))
        app_kvs.append(("Total", str(len(apps))))
        sections.append(("Applications", app_kvs))
    except Exception:
        sections.append(("Applications", [("Status", "[red]error[/red]")]))

    # Outposts
    try:
        outposts = c.get_all("outposts/instances/")
        out_kvs: list[tuple[str, str]] = []
        for o in outposts:
            name = o.get("name", "")
            otype = o.get("type", "")
            provider_count = len(o.get("providers", []))
            out_kvs.append((name, f"{otype} ({provider_count} providers)"))
        sections.append(("Outposts", out_kvs))
    except Exception:
        sections.append(("Outposts", [("Status", "[red]error[/red]")]))

    out.detail("Setup Status", sections)


@app.command()
def oauth2(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Application/provider name.")],
    redirect_uri: Annotated[str, typer.Argument(help="OAuth2 redirect URI.")],
    client_type: Annotated[
        str, typer.Option("--client-type", help="Client type: confidential or public.")
    ] = "confidential",
    slug: Annotated[str | None, typer.Option("--slug", help="Custom slug (default: auto-generated from name).")] = None,
) -> None:
    """Create an OAuth2 provider and linked application."""
    actx: AppContext = ctx.obj
    c = actx.client
    out = actx.output

    app_slug = slug or _slugify(name)

    # Find authorization flow
    auth_flow = _find_authorization_flow(c)
    if not auth_flow:
        out.error("No authorization flow found. Create one first.")
        raise typer.Exit(code=1)

    # Find authentication flow
    authn_flow = _find_authentication_flow(c)

    out.info(f"Using authorization flow: {auth_flow['slug']}")

    # Find invalidation flow
    inval_flow = _find_invalidation_flow(c)

    # Find a signing key so the id_token can be RS256-signed and the
    # JWKS endpoint serves real keys. Missing this is the single most
    # common "Login with Authentik → oauth_error=2" cause for Odoo's
    # auth_oidc integration.
    signing_key = _find_signing_cert(c)
    if not signing_key:
        out.warn(
            "No signing certificate found. The provider will be created "
            "without one; id_token signing will fail until you attach a "
            "keypair manually under Applications → Providers."
        )

    # Create OAuth2 provider
    #
    # sub_mode = "user_uuid" makes the OIDC `sub` claim stable across
    # renames and unique per user even when emails collide. Odoo's
    # auth_oauth matches users by oauth_uid, and UUID is the only
    # subject mode that survives the Authentik email-collision case.
    provider_data: dict = {
        "name": f"{name} Provider",
        "authorization_flow": auth_flow["pk"],
        "redirect_uris": [{"matching_mode": "strict", "url": redirect_uri}],
        "client_type": client_type,
        "signing_key": signing_key,
        "sub_mode": "user_uuid",
        "issuer_mode": "per_provider",
    }
    if authn_flow:
        provider_data["authentication_flow"] = authn_flow["pk"]
    if inval_flow:
        provider_data["invalidation_flow"] = inval_flow["pk"]

    try:
        provider = c.post("providers/oauth2/", data=provider_data)
    except Exception as e:
        out.error(f"Failed to create provider: {e}")
        raise typer.Exit(code=1)

    out.success(f"Created OAuth2 provider: {provider.get('name', '')}")

    # Create application
    app_data = {
        "name": name,
        "slug": app_slug,
        "provider": provider["pk"],
    }

    try:
        application = c.post("core/applications/", data=app_data)
    except Exception as e:
        out.error(f"Failed to create application: {e}")
        raise typer.Exit(code=1)

    out.success(f"Created application: {application.get('name', '')}")

    # Display credentials
    sections: list[tuple[str, list[tuple[str, str]]]] = [
        (
            "Application",
            [
                ("Name", application.get("name", "")),
                ("Slug", application.get("slug", "")),
            ],
        ),
        (
            "OAuth2 Provider",
            [
                ("Client ID", provider.get("client_id", "")),
                ("Client Secret", provider.get("client_secret", "")),
                ("Redirect URI", redirect_uri),
                ("Client Type", client_type),
                ("Authorization Flow", auth_flow["slug"]),
            ],
        ),
    ]

    json_data = {
        "application": application,
        "provider": provider,
    }

    out.detail(f"OAuth2 Setup: {name}", sections, data_for_json=json_data)


@app.command()
def proxy(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Application/provider name.")],
    external_host: Annotated[str, typer.Argument(help="External host URL (e.g. https://app.kodeme.io).")],
    internal_host: Annotated[
        str | None, typer.Option("--internal-host", help="Internal host (for forward_domain mode).")
    ] = None,
    slug: Annotated[str | None, typer.Option("--slug", help="Custom slug.")] = None,
) -> None:
    """Create a proxy provider (forward auth) and linked application."""
    actx: AppContext = ctx.obj
    c = actx.client
    out = actx.output

    app_slug = slug or _slugify(name)

    # Find authorization flow
    auth_flow = _find_authorization_flow(c)
    if not auth_flow:
        out.error("No authorization flow found. Create one first.")
        raise typer.Exit(code=1)

    out.info(f"Using authorization flow: {auth_flow['slug']}")

    # Create proxy provider
    provider_data: dict = {
        "name": f"{name} Proxy Provider",
        "authorization_flow": auth_flow["pk"],
        "external_host": external_host,
        "mode": "forward_single",
    }
    if internal_host:
        provider_data["internal_host"] = internal_host
        provider_data["mode"] = "forward_domain"

    try:
        provider = c.post("providers/proxy/", data=provider_data)
    except Exception as e:
        out.error(f"Failed to create proxy provider: {e}")
        raise typer.Exit(code=1)

    out.success(f"Created proxy provider: {provider.get('name', '')}")

    # Create application
    app_data = {
        "name": name,
        "slug": app_slug,
        "provider": provider["pk"],
    }

    try:
        application = c.post("core/applications/", data=app_data)
    except Exception as e:
        out.error(f"Failed to create application: {e}")
        raise typer.Exit(code=1)

    out.success(f"Created application: {application.get('name', '')}")

    sections: list[tuple[str, list[tuple[str, str]]]] = [
        (
            "Application",
            [
                ("Name", application.get("name", "")),
                ("Slug", application.get("slug", "")),
            ],
        ),
        (
            "Proxy Provider",
            [
                ("Provider PK", str(provider.get("pk", ""))),
                ("Mode", provider.get("mode", "")),
                ("External Host", external_host),
            ],
        ),
        (
            "Next Steps",
            [
                ("1", "Add provider to 'authentik Embedded Outpost'"),
                ("2", "Add Traefik forwardAuth middleware labels to the target service"),
            ],
        ),
    ]

    json_data = {
        "application": application,
        "provider": provider,
    }

    out.detail(f"Proxy Setup: {name}", sections, data_for_json=json_data)


@app.command()
def admin(
    ctx: typer.Context,
    username: Annotated[str, typer.Argument(help="Username to make admin.")],
) -> None:
    """Grant admin/superuser status to a user."""
    actx: AppContext = ctx.obj
    c = actx.client
    out = actx.output

    # Resolve user
    try:
        user_pk = resolve_user(c, username)
    except NotFoundError:
        out.error(f"User not found: {username}")
        raise typer.Exit(code=1)

    # Get user details
    user = c.get(f"core/users/{user_pk}/")

    # Find or create admin group
    admin_groups = c.get_all("core/groups/", params={"name": "authentik Admins"})
    if admin_groups:
        admin_group = admin_groups[0]
    else:
        # Try alternate name
        admin_groups = c.get_all("core/groups/", params={"search": "admin"})
        admin_group = None
        for g in admin_groups:
            if g.get("is_superuser", False):
                admin_group = g
                break
        if not admin_group:
            # Create admin group
            admin_group = c.post(
                "core/groups/",
                data={
                    "name": "authentik Admins",
                    "is_superuser": True,
                },
            )
            out.success("Created admin group: authentik Admins")

    # Add user to admin group
    group_pk = admin_group["pk"]
    existing_users = [u.get("pk") for u in admin_group.get("users_obj", [])]
    if user_pk not in existing_users:
        c.post(f"core/groups/{group_pk}/add_user/", data={"pk": user_pk})
        out.success(f"Added {user.get('username', username)} to admin group.")
    else:
        out.info(f"User {user.get('username', username)} is already in admin group.")

    # Also set is_superuser on the user directly
    if not user.get("is_superuser", False):
        c.patch(f"core/users/{user_pk}/", data={"is_superuser": True})
        out.success(f"Set superuser flag on {user.get('username', username)}.")
    else:
        out.info(f"User {user.get('username', username)} is already a superuser.")


@app.command()
def recovery(
    ctx: typer.Context,
    username: Annotated[str, typer.Argument(help="Username to generate recovery link for.")],
) -> None:
    """Generate a recovery link for a user."""
    actx: AppContext = ctx.obj
    c = actx.client
    out = actx.output

    # Resolve user
    try:
        user_pk = resolve_user(c, username)
    except NotFoundError:
        out.error(f"User not found: {username}")
        raise typer.Exit(code=1)

    try:
        result = c.get(f"core/users/{user_pk}/recovery/")
        link = result.get("link", "")
    except Exception as e:
        out.error(f"Failed to generate recovery link: {e}")
        raise typer.Exit(code=1)

    if out.json_mode:
        out.raw_json({"username": username, "recovery_link": link})
    else:
        out.success(f"Recovery link for {username}:")
        out.text(f"  {link}")
        out.warn("This link expires shortly. Share it securely.")


@app.command("app")
def app_create(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Application name.")],
    slug: Annotated[str, typer.Argument(help="Application slug.")],
    app_type: Annotated[str, typer.Option("--type", "-t", help="Provider type: oauth2 or proxy.")] = "oauth2",
    redirect: Annotated[str | None, typer.Option("--redirect", help="OAuth2 redirect URI.")] = None,
    external: Annotated[str | None, typer.Option("--external", help="Proxy external host.")] = None,
) -> None:
    """Create an application with a provider (shortcut for oauth2/proxy commands)."""
    actx: AppContext = ctx.obj
    out = actx.output

    if app_type == "oauth2":
        if not redirect:
            out.error("--redirect is required for oauth2 type.")
            raise typer.Exit(code=1)
        # Delegate to the oauth2 command logic
        ctx.invoke(oauth2, name=name, redirect_uri=redirect, slug=slug)
    elif app_type == "proxy":
        if not external:
            out.error("--external is required for proxy type.")
            raise typer.Exit(code=1)
        ctx.invoke(proxy, name=name, external_host=external, slug=slug)
    else:
        out.error(f"Unknown app type: {app_type}. Use 'oauth2' or 'proxy'.")
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# Redirect URI patterns per app type
# ---------------------------------------------------------------------------

_REDIRECT_PATTERNS: dict[str, str] = {
    "react-spa": "{launch_url}/callback",
    "odoo": "{launch_url}/auth_oauth/signin",
    "nextjs": "{launch_url}/api/auth/callback/oidc",
}

_OAUTH_APP_TYPES = frozenset(_REDIRECT_PATTERNS.keys())


def _build_env_block(
    app_type: str,
    slug: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    base_url: str,
) -> str:
    """Return env-var block for a given app type."""
    lines: list[str] = [f"# === {slug} ({app_type}) ==="]

    if app_type == "react-spa":
        # Derive APP_UPPER from slug: last segment after last '-'
        # e.g. mac-react-wms -> WMS
        parts = slug.rsplit("-", 1)
        app_upper = parts[-1].upper() if len(parts) > 1 else slug.upper()
        lines += [
            "VITE_AUTH_MODE=oidc",
            f"VITE_OIDC_AUTHORITY={base_url}/application/o/{slug}/",
            f"VITE_{app_upper}_OIDC_CLIENT_ID={client_id}",
            f"VITE_{app_upper}_OIDC_REDIRECT_URI={redirect_uri}",
        ]
    elif app_type == "odoo":
        lines += [
            "ODOO_OAUTH_PROVIDER_NAME=Authentik",
            f"ODOO_OAUTH_CLIENT_ID={client_id}",
            f"ODOO_OAUTH_AUTH_ENDPOINT={base_url}/application/o/authorize/",
            f"ODOO_OAUTH_TOKEN_ENDPOINT={base_url}/application/o/token/",
            f"ODOO_OAUTH_USERINFO_ENDPOINT={base_url}/application/o/userinfo/",
        ]
    elif app_type == "nextjs":
        lines += [
            f"NEXT_PUBLIC_OIDC_ISSUER={base_url}/application/o/{slug}/",
            f"OIDC_CLIENT_ID={client_id}",
            f"OIDC_CLIENT_SECRET={client_secret}",
            f"OIDC_REDIRECT_URI={redirect_uri}",
        ]

    return "\n".join(lines)


@app.command()
def batch(
    ctx: typer.Context,
    dry_run: Annotated[bool, typer.Option("--dry-run/--no-dry-run", help="Preview without applying")] = True,
    output_env: Annotated[bool, typer.Option("--output-env", help="Print env vars for each app")] = False,
    file: Annotated[Path | None, typer.Option(help="Path to app-registry.yaml")] = None,
) -> None:
    """Bulk create OAuth2 providers for all apps in app-registry.yaml."""
    actx: AppContext = ctx.obj
    c = actx.client
    out = actx.output
    base_url = c._root_url.rstrip("/")

    # --- Load registry -------------------------------------------------------
    if file:
        ar_path = file
    else:
        ar_path = resolve_app_registry_path()
        if ar_path is None:
            out.error("app-registry.yaml not found. Use --file to specify path.")
            raise typer.Exit(code=1)

    with open(ar_path) as fh:
        registry = yaml.safe_load(fh) or {}

    apps_list: list[dict] = registry.get("apps", [])
    if not apps_list:
        out.warn("No apps found in registry.")
        return

    # --- Fetch existing Authentik apps ---------------------------------------
    existing_apps = c.get_all("core/applications/")
    app_by_slug: dict[str, dict] = {a["slug"]: a for a in existing_apps}

    # --- Find flows ----------------------------------------------------------
    auth_flow = _find_authorization_flow(c)
    if not auth_flow:
        out.error("No authorization flow found. Create one first.")
        raise typer.Exit(code=1)

    authn_flow = _find_authentication_flow(c)
    inval_flow = _find_invalidation_flow(c)

    # Resolve once up front — same cert for all providers in the batch.
    signing_key = _find_signing_cert(c)
    if not signing_key:
        out.warn(
            "No signing certificate found. Providers will be created "
            "without one; id_token signing will fail until a keypair is "
            "attached manually."
        )

    # --- Process each app ----------------------------------------------------
    created: list[str] = []
    skipped: list[str] = []
    env_blocks: list[str] = []

    for entry in apps_list:
        slug = entry.get("slug", "")
        app_type = entry.get("type", "")
        launch_url = entry.get("launch_url", "").rstrip("/")

        if app_type not in _OAUTH_APP_TYPES:
            skipped.append(f"{slug} (type={app_type or 'none'}, not oauth)")
            continue

        if slug not in app_by_slug:
            skipped.append(f"{slug} (not in Authentik — run apps sync first)")
            continue

        ak_app = app_by_slug[slug]
        if ak_app.get("provider") is not None:
            skipped.append(f"{slug} (already has provider)")
            continue

        redirect_uri = _REDIRECT_PATTERNS[app_type].format(launch_url=launch_url)
        client_type = "public" if app_type == "react-spa" else "confidential"

        if dry_run:
            out.info(f"[dry-run] Would create OAuth2 provider for {slug} ({app_type})")
            out.info(f"  redirect_uri: {redirect_uri}")
            out.info(f"  client_type:  {client_type}")
            created.append(slug)
            continue

        # Create provider. `signing_key` + `sub_mode=user_uuid` are
        # mandatory for working OIDC — see _find_signing_cert docstring.
        provider_data: dict = {
            "name": f"{slug} Provider",
            "authorization_flow": auth_flow["pk"],
            "redirect_uris": [{"matching_mode": "strict", "url": redirect_uri}],
            "client_type": client_type,
            "signing_key": signing_key,
            "sub_mode": "user_uuid",
            "issuer_mode": "per_provider",
        }
        if authn_flow:
            provider_data["authentication_flow"] = authn_flow["pk"]
        if inval_flow:
            provider_data["invalidation_flow"] = inval_flow["pk"]

        try:
            provider = c.post("providers/oauth2/", data=provider_data)
        except Exception as e:
            out.error(f"Failed to create provider for {slug}: {e}")
            continue

        # Link provider to app
        try:
            c.patch(f"core/applications/{slug}/", data={"provider": provider["pk"]})
        except Exception as e:
            out.error(f"Failed to link provider to {slug}: {e}")
            continue

        client_id = provider.get("client_id", "")
        client_secret = provider.get("client_secret", "")
        out.success(f"Created OAuth2 provider for {slug} (client_id={client_id})")
        created.append(slug)

        if output_env:
            env_blocks.append(_build_env_block(app_type, slug, client_id, client_secret, redirect_uri, base_url))

    # --- Summary -------------------------------------------------------------
    out.info(f"Created: {len(created)}, Skipped: {len(skipped)}")
    for s in skipped:
        out.info(f"  skip: {s}")

    if env_blocks:
        out.text("")
        out.text("\n\n".join(env_blocks))
