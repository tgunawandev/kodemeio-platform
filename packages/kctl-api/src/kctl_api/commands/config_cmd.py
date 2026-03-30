"""Config management commands for kctl-api.

Manage connection profiles, switch environments, and test connectivity.
"""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_api.core.callbacks import AppContext
from kctl_api.core.config import (
    CONFIG_FILE,
    SERVICE_KEY,
    ServiceConfig,
    _is_service_scoped,
    get_all_services_in_profile,
    get_default_profile,
    get_profile_names,
    get_service_config,
    load_raw_config,
    remove_profile,
    resolve_active_profile_name,
    save_raw_config,
    set_default_profile,
    set_service_config,
)
from kctl_api.core.utils import mask_secret

app = typer.Typer(name="config", help="Manage connection profiles and configuration.", no_args_is_help=True)


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------
@app.command()
def init(ctx: typer.Context) -> None:
    """Interactive setup wizard: prompt for URL, email, password; login to get JWT; save profile."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.header("kctl-api Setup Wizard")

    profile_name = typer.prompt("Profile name", default="default")
    url = typer.prompt("API URL (api-main)", default="http://localhost:8000")
    ai_url = typer.prompt("AI URL (ai-main, optional)", default="")
    email = typer.prompt("Email")
    password = typer.prompt("Password", hide_input=True)

    out.info(f"Authenticating against {url} ...")

    from kctl_api.core.client import ApiClient

    try:
        client = ApiClient(base_url=url)
        tokens = client.login(email, password)
        client.close()
    except Exception as e:
        out.error(f"Login failed: {e}")
        raise typer.Exit(1) from None

    api_key = tokens.get("access_token", "")
    svc = ServiceConfig(url=url, ai_url=ai_url, api_key=api_key)
    set_service_config(profile_name, svc)
    set_default_profile(profile_name)

    out.success(f"Profile '{profile_name}' created and set as default.")
    out.info(f"Config saved to {CONFIG_FILE}")

    if actx.json_mode:
        out.raw_json(
            {
                "profile": profile_name,
                "url": url,
                "ai_url": ai_url,
                "authenticated": True,
                "config_file": str(CONFIG_FILE),
            }
        )


# ---------------------------------------------------------------------------
# add
# ---------------------------------------------------------------------------
@app.command()
def add(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name to create.")],
    url: Annotated[str, typer.Option("--url", help="API base URL.")] = "",
    ai_url: Annotated[str, typer.Option("--ai-url", help="AI API base URL.")] = "",
    api_key: Annotated[str, typer.Option("--api-key", help="API key or JWT token.")] = "",
    database_url: Annotated[str, typer.Option("--database-url", help="PostgreSQL async URL.")] = "",
    redis_url: Annotated[str, typer.Option("--redis-url", help="Redis URL.")] = "",
    default: Annotated[bool, typer.Option("--default", help="Set as default profile.")] = False,
) -> None:
    """Add a new connection profile."""
    actx: AppContext = ctx.obj
    out = actx.output

    existing = get_profile_names()
    if name in existing:
        out.warn(f"Profile '{name}' already exists and will be overwritten.")

    svc = ServiceConfig(
        url=url,
        ai_url=ai_url,
        api_key=api_key,
        database_url=database_url,
        redis_url=redis_url,
    )
    set_service_config(name, svc)

    if default:
        set_default_profile(name)
        out.success(f"Profile '{name}' added and set as default.")
    else:
        out.success(f"Profile '{name}' added.")

    if actx.json_mode:
        out.raw_json({"profile": name, "default": default})


# ---------------------------------------------------------------------------
# use
# ---------------------------------------------------------------------------
@app.command()
def use(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name to activate.")],
) -> None:
    """Switch the default profile."""
    actx: AppContext = ctx.obj
    out = actx.output

    existing = get_profile_names()
    if name not in existing:
        out.error(f"Profile '{name}' does not exist. Available: {', '.join(existing) or '(none)'}")
        raise typer.Exit(1)

    set_default_profile(name)
    out.success(f"Default profile set to '{name}'.")

    if actx.json_mode:
        out.raw_json({"default_profile": name})


# ---------------------------------------------------------------------------
# remove
# ---------------------------------------------------------------------------
@app.command(name="remove")
def remove_cmd(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name to delete.")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation.")] = False,
) -> None:
    """Delete a connection profile."""
    actx: AppContext = ctx.obj
    out = actx.output

    existing = get_profile_names()
    if name not in existing:
        out.error(f"Profile '{name}' does not exist.")
        raise typer.Exit(1)

    if not force:
        confirm = typer.confirm(f"Delete profile '{name}'?", default=False)
        if not confirm:
            out.info("Cancelled.")
            raise typer.Exit(0)

    remove_profile(name)
    out.success(f"Profile '{name}' removed.")

    if actx.json_mode:
        out.raw_json({"removed": name})


# ---------------------------------------------------------------------------
# test
# ---------------------------------------------------------------------------
@app.command()
def test(ctx: typer.Context) -> None:
    """Test current profile connectivity (GET /api/v1/health)."""
    actx: AppContext = ctx.obj
    out = actx.output

    profile_name = resolve_active_profile_name(actx.profile)
    svc = get_service_config(profile_name)

    if not svc.url:
        out.error(f"Profile '{profile_name}' has no URL configured. Run: kctl-api config add {profile_name} --url ...")
        raise typer.Exit(1)

    out.info(f"Testing connectivity to {svc.url} (profile: {profile_name}) ...")

    from kctl_api.core.client import ApiClient

    try:
        client = ApiClient(base_url=svc.url, api_key=svc.api_key)
        healthy, details = client.health_check()
        client.close()
    except Exception as e:
        out.error(f"Connection failed: {e}")
        if actx.json_mode:
            out.raw_json({"profile": profile_name, "url": svc.url, "healthy": False, "error": str(e)})
        raise typer.Exit(1) from None

    status = details.get("status", "unknown")
    if healthy:
        out.success(f"API is healthy (status: {status})")
    else:
        out.error(f"API returned unhealthy status: {status}")

    if actx.json_mode:
        out.raw_json({"profile": profile_name, "url": svc.url, "healthy": healthy, **details})
    elif not healthy:
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# current
# ---------------------------------------------------------------------------
@app.command()
def current(ctx: typer.Context) -> None:
    """Show active profile name and connection status."""
    actx: AppContext = ctx.obj
    out = actx.output

    profile_name = resolve_active_profile_name(actx.profile)
    svc = get_service_config(profile_name)

    connected = False
    status_text = "not tested"
    if svc.url:
        from kctl_api.core.client import ApiClient

        try:
            client = ApiClient(base_url=svc.url, api_key=svc.api_key)
            healthy, _details = client.health_check()
            client.close()
            connected = healthy
            status_text = "[green]connected[/green]" if healthy else "[red]unreachable[/red]"
        except Exception:
            status_text = "[red]unreachable[/red]"

    data = {
        "profile": profile_name,
        "url": svc.url or "(not set)",
        "connected": connected,
    }

    out.detail(
        title="Active Profile",
        sections=[
            (
                "Connection",
                [
                    ("Profile", profile_name),
                    ("URL", svc.url or "(not set)"),
                    ("Status", status_text),
                    ("Default", str(profile_name == get_default_profile())),
                ],
            ),
        ],
        data_for_json=data,
    )


# ---------------------------------------------------------------------------
# show
# ---------------------------------------------------------------------------
@app.command()
def show(ctx: typer.Context) -> None:
    """Show full configuration with masked secrets."""
    actx: AppContext = ctx.obj
    out = actx.output

    profile_name = resolve_active_profile_name(actx.profile)
    all_services = get_all_services_in_profile(profile_name)

    sections: list[tuple[str, list[tuple[str, str]]]] = []
    json_data: dict[str, object] = {"profile": profile_name, "config_file": str(CONFIG_FILE), "services": {}}

    sections.append(
        (
            "General",
            [
                ("Profile", profile_name),
                ("Config File", str(CONFIG_FILE)),
                ("Default Profile", get_default_profile()),
            ],
        )
    )

    for svc_name, svc_data in all_services.items():
        kvs: list[tuple[str, str]] = []
        svc_json: dict[str, str] = {}
        for key, value in svc_data.items():
            display_val = str(value) if value else "(not set)"
            if key in ("api_key", "database_url", "redis_url") and value:
                display_val = mask_secret(str(value))
            kvs.append((key, display_val))
            svc_json[key] = (
                mask_secret(str(value)) if key in ("api_key", "database_url", "redis_url") and value else str(value)
            )
        sections.append((f"Service: {svc_name}", kvs))
        if isinstance(json_data["services"], dict):
            json_data["services"][svc_name] = svc_json

    out.detail(title=f"Config — {profile_name}", sections=sections, data_for_json=json_data)


# ---------------------------------------------------------------------------
# set
# ---------------------------------------------------------------------------
@app.command(name="set")
def set_cmd(
    ctx: typer.Context,
    key: Annotated[str, typer.Argument(help="Config key: url, ai_url, api_key, database_url, redis_url.")],
    value: Annotated[str, typer.Argument(help="Config value.")],
) -> None:
    """Set a config value on the active profile."""
    actx: AppContext = ctx.obj
    out = actx.output

    valid_keys = set(ServiceConfig.model_fields.keys())
    if key not in valid_keys:
        out.error(f"Invalid key '{key}'. Valid keys: {', '.join(sorted(valid_keys))}")
        raise typer.Exit(1)

    profile_name = resolve_active_profile_name(actx.profile)
    svc = get_service_config(profile_name)
    svc_dict = svc.model_dump()
    svc_dict[key] = value
    updated = ServiceConfig(**svc_dict)
    set_service_config(profile_name, updated)

    display_val = mask_secret(value) if key in ("api_key", "database_url", "redis_url") else value
    out.success(f"Set {key}={display_val} on profile '{profile_name}'.")

    if actx.json_mode:
        out.raw_json({"profile": profile_name, "key": key, "value": display_val})


# ---------------------------------------------------------------------------
# profiles
# ---------------------------------------------------------------------------
@app.command()
def profiles(ctx: typer.Context) -> None:
    """List all connection profiles."""
    actx: AppContext = ctx.obj
    out = actx.output

    names = get_profile_names()
    default = get_default_profile()

    if not names:
        out.info("No profiles configured. Run: kctl-api config init")
        if actx.json_mode:
            out.raw_json([])
        return

    rows: list[list[str]] = []
    json_data: list[dict[str, object]] = []

    for name in names:
        svc = get_service_config(name)
        is_default = name == default
        marker = "[green]*[/green]" if is_default else ""
        services = get_all_services_in_profile(name)
        svc_names = ", ".join(sorted(services.keys())) if services else "(empty)"

        rows.append(
            [
                f"{marker} {name}" if marker else name,
                svc.url or "(not set)",
                svc_names,
                "yes" if is_default else "",
            ]
        )
        json_data.append(
            {
                "name": name,
                "url": svc.url,
                "services": list(services.keys()),
                "default": is_default,
            }
        )

    out.table(
        title="Profiles",
        columns=[
            ("Name", "bold"),
            ("URL", ""),
            ("Services", "dim"),
            ("Default", "green"),
        ],
        rows=rows,
        data_for_json=json_data,
    )


# ---------------------------------------------------------------------------
# migrate
# ---------------------------------------------------------------------------
@app.command()
def migrate(ctx: typer.Context) -> None:
    """Migrate from old flat format to service-scoped YAML."""
    actx: AppContext = ctx.obj
    out = actx.output

    raw = load_raw_config()
    profiles_data = raw.get("profiles", {})

    if not profiles_data:
        out.info("No profiles found. Nothing to migrate.")
        return

    migrated_count = 0
    for _name, profile_data in profiles_data.items():
        if not isinstance(profile_data, dict):
            continue
        if _is_service_scoped(profile_data):
            continue

        # Flat format detected — wrap under SERVICE_KEY
        old_data = dict(profile_data)
        profile_data.clear()
        profile_data[SERVICE_KEY] = old_data
        migrated_count += 1

    if migrated_count == 0:
        out.info("All profiles already use service-scoped format. Nothing to migrate.")
        if actx.json_mode:
            out.raw_json({"migrated": 0})
        return

    save_raw_config(raw)
    out.success(f"Migrated {migrated_count} profile(s) to service-scoped format.")

    if actx.json_mode:
        out.raw_json({"migrated": migrated_count, "profiles": list(profiles_data.keys())})
