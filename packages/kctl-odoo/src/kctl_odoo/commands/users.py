"""User management commands."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.exceptions import RPCError
from kctl_odoo.core.resolve import resolve_id

app = typer.Typer(help="Manage Odoo users.")


@app.command("list")
def list_(
    ctx: typer.Context,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 80,
    active_only: Annotated[bool, typer.Option("--active/--all", help="Active users only")] = True,
) -> None:
    """List Odoo users."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    domain: list = []
    if active_only:
        domain.append(("active", "=", True))
    # Exclude internal system users
    domain.append(("share", "=", False))

    users = c.search_read(
        "res.users",
        domain=domain,
        fields=["id", "login", "name", "active", "company_id", "groups_id"],
        limit=limit,
        order="id",
    )

    rows = []
    json_data = []
    for u in users:
        company = u.get("company_id")
        company_name = company[1] if isinstance(company, list) else str(company or "")
        status = "[green]active[/green]" if u.get("active") else "[red]inactive[/red]"
        groups_count = len(u.get("groups_id", []))
        rows.append([str(u["id"]), u["login"], u["name"], company_name, status, str(groups_count)])
        json_data.append(
            {
                "id": u["id"],
                "login": u["login"],
                "name": u["name"],
                "company": company_name,
                "active": u.get("active"),
                "groups": groups_count,
            }
        )

    out.table(
        f"Users ({len(users)})",
        [("ID", "cyan"), ("Login", ""), ("Name", ""), ("Company", "dim"), ("Status", ""), ("Groups", "dim")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def get(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="User ID or login")],
) -> None:
    """Get user details."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Try numeric ID first, then login
    domain: list = []
    domain = [("id", "=", int(identifier))] if identifier.isdigit() else [("login", "=", identifier)]

    users = c.search_read(
        "res.users",
        domain=domain,
        fields=[
            "id",
            "login",
            "name",
            "email",
            "active",
            "company_id",
            "company_ids",
            "groups_id",
            "lang",
            "tz",
            "create_date",
            "write_date",
        ],
    )

    if not users:
        out.error(f"User not found: {identifier}")
        raise typer.Exit(1)

    u = users[0]
    company = u.get("company_id")
    company_name = company[1] if isinstance(company, list) else str(company or "")

    sections = [
        (
            "User Info",
            [
                ("ID", str(u["id"])),
                ("Login", u["login"]),
                ("Name", u["name"]),
                ("Email", u.get("email") or "-"),
                ("Active", "[green]Yes[/green]" if u.get("active") else "[red]No[/red]"),
                ("Company", company_name),
                ("Companies", str(len(u.get("company_ids", [])))),
                ("Groups", str(len(u.get("groups_id", [])))),
                ("Language", u.get("lang") or "-"),
                ("Timezone", u.get("tz") or "-"),
                ("Created", str(u.get("create_date", ""))),
                ("Updated", str(u.get("write_date", ""))),
            ],
        ),
    ]

    out.detail(f"User: {u['login']}", sections, data_for_json=u)


def _resolve_oauth_provider(c, name: str) -> int:
    """Resolve OAuth provider name to ID (e.g. 'authentik' -> provider id)."""
    providers = c.search_read(
        "auth.oauth.provider",
        domain=[("name", "ilike", name)],
        fields=["id", "name"],
        limit=1,
    )
    if not providers:
        raise typer.BadParameter(f"OAuth provider not found: {name}")
    return providers[0]["id"]


@app.command()
def create(
    ctx: typer.Context,
    login: Annotated[str, typer.Argument(help="Login/username")],
    name: Annotated[str, typer.Option("--name", "-n", help="Full name")] = "",
    email: Annotated[str | None, typer.Option("--email", help="Email address")] = None,
    password: Annotated[str | None, typer.Option("--password", help="Initial password")] = None,
    oauth_uid: Annotated[str | None, typer.Option("--oauth-uid", help="OAuth/OIDC user UID (for SSO mapping)")] = None,
    oauth_provider: Annotated[
        str | None, typer.Option("--oauth-provider", help="OAuth provider name (e.g. 'authentik')")
    ] = None,
    groups: Annotated[str | None, typer.Option("--groups", help="Comma-separated group IDs to assign")] = None,
) -> None:
    """Create a new user."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    vals: dict = {"login": login, "name": name or login}
    if email:
        vals["email"] = email
    if password:
        vals["password"] = password
    if oauth_uid:
        vals["oauth_uid"] = oauth_uid
    if oauth_provider:
        vals["oauth_provider_id"] = _resolve_oauth_provider(c, oauth_provider)
    if groups:
        group_ids = [int(g.strip()) for g in groups.split(",") if g.strip()]
        vals["groups_id"] = [(6, 0, group_ids)]

    user_id = c.create("res.users", vals)
    out.success(f"Created user '{login}' (ID: {user_id})")


@app.command()
def update(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="User ID or login")],
    name: Annotated[str | None, typer.Option("--name", "-n", help="Full name")] = None,
    email: Annotated[str | None, typer.Option("--email", help="Email")] = None,
    lang: Annotated[str | None, typer.Option("--lang", help="Language code")] = None,
    tz: Annotated[str | None, typer.Option("--tz", help="Timezone")] = None,
    oauth_uid: Annotated[
        str | None, typer.Option("--oauth-uid", help="OAuth/OIDC user UID (set empty string to clear)")
    ] = None,
    oauth_provider: Annotated[
        str | None,
        typer.Option("--oauth-provider", help="OAuth provider name (e.g. 'authentik', empty string to clear)"),
    ] = None,
) -> None:
    """Update an existing user."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    user_id = resolve_id(c, "res.users", search_field="login", identifier=identifier)
    vals: dict = {}
    if name is not None:
        vals["name"] = name
    if email is not None:
        vals["email"] = email
    if lang is not None:
        vals["lang"] = lang
    if tz is not None:
        vals["tz"] = tz
    if oauth_uid is not None:
        vals["oauth_uid"] = oauth_uid or False
    if oauth_provider is not None:
        vals["oauth_provider_id"] = _resolve_oauth_provider(c, oauth_provider) if oauth_provider else False

    if not vals:
        out.warn("No fields to update")
        return

    c.write("res.users", [user_id], vals)
    out.success(f"Updated user {identifier} (ID: {user_id})")


@app.command()
def activate(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="User ID or login")],
) -> None:
    """Activate a user."""
    actx: AppContext = ctx.obj
    c = actx.client
    user_id = resolve_id(c, "res.users", search_field="login", identifier=identifier)
    c.write("res.users", [user_id], {"active": True})
    actx.output.success(f"Activated user {identifier}")


@app.command()
def deactivate(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="User ID or login")],
) -> None:
    """Deactivate a user."""
    actx: AppContext = ctx.obj
    c = actx.client
    user_id = resolve_id(c, "res.users", search_field="login", identifier=identifier)
    c.write("res.users", [user_id], {"active": False})
    actx.output.success(f"Deactivated user {identifier}")


@app.command("reset-password")
def reset_password(
    ctx: typer.Context,
    login: Annotated[str, typer.Argument(help="User login to reset password for")],
) -> None:
    """Send a password reset email to a user."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    user_id = resolve_id(c, "res.users", search_field="login", identifier=login)
    c.execute_kw("res.users", "action_reset_password", [[user_id]])
    out.success(f"Password reset triggered for user '{login}' (ID: {user_id})")


@app.command("groups")
def user_groups(
    ctx: typer.Context,
    login: Annotated[str, typer.Argument(help="User login or ID")],
) -> None:
    """Show all groups assigned to a user."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    user_id = resolve_id(c, "res.users", search_field="login", identifier=login)
    users = c.read("res.users", [user_id], fields=["id", "login", "name", "groups_id"])
    if not users:
        out.error(f"User not found: {login}")
        raise typer.Exit(1)

    u = users[0]
    group_ids = u.get("groups_id", [])

    if not group_ids:
        out.info(f"User '{u['login']}' has no groups assigned.")
        if actx.json_mode:
            out.raw_json({"user": u["login"], "groups": []})
        return

    groups_data = c.read("res.groups", group_ids, fields=["id", "full_name", "category_id"])

    rows = []
    json_data = []
    for g in sorted(groups_data, key=lambda x: x.get("full_name") or ""):
        cat = g.get("category_id")
        cat_name = cat[1] if isinstance(cat, list) else str(cat or "-")
        rows.append([str(g["id"]), g.get("full_name") or str(g["id"]), cat_name])
        json_data.append(
            {
                "id": g["id"],
                "name": g.get("full_name") or str(g["id"]),
                "category": cat_name,
            }
        )

    out.table(
        f"Groups for {u['login']} ({len(groups_data)})",
        [("ID", "cyan"), ("Group", ""), ("Category", "dim")],
        rows,
        data_for_json=json_data,
    )


@app.command("list-apikeys")
def apikey_list(
    ctx: typer.Context,
    login: Annotated[str, typer.Argument(help="User login or ID")],
) -> None:
    """List API keys for a user."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    user_id = resolve_id(c, "res.users", search_field="login", identifier=login)

    # Try res.users.apikeys first (Odoo 16+), fall back to api.key
    records: list[dict] = []
    model_name = "res.users.apikeys"
    try:
        records = c.search_read(
            model_name,
            domain=[("user_id", "=", user_id)],
            fields=["id", "name", "scope", "create_date", "write_date"],
            order="create_date desc",
        )
    except RPCError:
        model_name = "api.key"
        try:
            records = c.search_read(
                model_name,
                domain=[("user_id", "=", user_id)],
                fields=["id", "name", "scope", "create_date", "write_date"],
                order="create_date desc",
            )
        except RPCError:
            out.error("API key model not available on this Odoo instance.")
            raise typer.Exit(1) from None

    if not records:
        out.info(f"No API keys found for user '{login}' (ID: {user_id}).")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for r in records:
        rows.append(
            [
                str(r["id"]),
                r.get("name") or "-",
                r.get("scope") or "-",
                str(r.get("create_date") or "-"),
            ]
        )
        json_data.append(
            {
                "id": r["id"],
                "name": r.get("name"),
                "scope": r.get("scope"),
                "create_date": r.get("create_date"),
            }
        )

    out.table(
        f"API Keys for user {login} ({len(records)})",
        [("ID", "cyan"), ("Name", ""), ("Scope", "dim"), ("Created", "dim")],
        rows,
        data_for_json=json_data,
    )


@app.command("create-apikey")
def apikey_generate(
    ctx: typer.Context,
    login: Annotated[str, typer.Argument(help="User login or ID")],
    name: Annotated[str, typer.Option("--name", "-n", help="API key description")] = "kctl-generated",
) -> None:
    """Generate a new API key for a user."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    user_id = resolve_id(c, "res.users", search_field="login", identifier=login)

    # Try res.users.apikeys first, fall back to api.key
    model_name = "res.users.apikeys"
    try:
        key_id = c.create(model_name, {"name": name, "user_id": user_id})
    except RPCError:
        model_name = "api.key"
        try:
            key_id = c.create(model_name, {"name": name, "user_id": user_id})
        except RPCError:
            out.error("API key model not available on this Odoo instance.")
            raise typer.Exit(1) from None

    out.success(f"Created API key '{name}' (ID: {key_id}) for user '{login}'")
    if actx.json_mode:
        out.raw_json({"id": key_id, "name": name, "user_id": user_id, "model": model_name})


@app.command("revoke-apikey")
def apikey_revoke(
    ctx: typer.Context,
    key_id: Annotated[int, typer.Argument(help="API key record ID")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Revoke (delete) an API key by record ID."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if not force and not typer.confirm(f"Revoke API key ID {key_id}?"):
        raise typer.Exit(0)

    # Try res.users.apikeys first, fall back to api.key
    revoked = False
    for model_name in ("res.users.apikeys", "api.key"):
        try:
            c.unlink(model_name, [key_id])
            revoked = True
            break
        except RPCError:
            continue

    if not revoked:
        out.error(f"Could not revoke API key {key_id}. Model not available or key not found.")
        raise typer.Exit(1)

    out.success(f"Revoked API key ID {key_id}")


@app.command("set-password")
def set_password(
    ctx: typer.Context,
    login: Annotated[str, typer.Argument(help="User login")],
    password: Annotated[str, typer.Argument(help="New password")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Set a user's password directly.

    Use reset-password for email-based reset instead.

    Examples:
        kctl-odoo users set-password john newpass123 --force
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Find user
    users = c.search_read("res.users", domain=[("login", "=", login)], fields=["id", "name", "login"], limit=1)
    if not users:
        out.error(f"User not found: {login}")
        raise typer.Exit(1)

    user = users[0]

    if not force:
        if not typer.confirm(f"Set password for {user['name']} ({user['login']})?"):
            out.info("Cancelled.")
            raise typer.Exit(0)

    try:
        c.execute_kw("res.users", "write", [[user["id"]], {"password": password}])
        out.success(f"Password updated for {user['name']} ({login})")
    except Exception as e:
        out.error(f"Failed to set password: {e}")
        raise typer.Exit(1)
