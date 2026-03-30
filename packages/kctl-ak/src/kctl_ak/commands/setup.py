"""Setup wizard commands.

Quickly create OAuth2/Proxy providers with linked applications,
manage admin access, and generate recovery links.
"""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_ak.core.callbacks import AppContext
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


def _slugify(name: str) -> str:
    """Convert a name to a slug."""
    return name.lower().replace(" ", "-").replace("_", "-")


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

    # Create OAuth2 provider
    provider_data: dict = {
        "name": f"{name} Provider",
        "authorization_flow": auth_flow["pk"],
        "redirect_uris": redirect_uri,
        "client_type": client_type,
        "signing_key": None,
    }
    if authn_flow:
        provider_data["authentication_flow"] = authn_flow["pk"]

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
