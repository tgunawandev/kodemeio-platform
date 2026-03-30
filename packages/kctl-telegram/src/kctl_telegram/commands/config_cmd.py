"""Configuration management commands.

Initialize, view, and manage CLI profiles and connection settings.
Uses service-scoped config: each profile contains per-service sections.
"""

from __future__ import annotations

import os
from typing import Annotated

import typer

from kctl_telegram.core.callbacks import AppContext
from kctl_telegram.core.client import TelegramClient
from kctl_telegram.core.config import (
    CONFIG_FILE,
    ENV_PREFIX,
    SERVICE_KEY,
    ServiceConfig,
    get_all_services_in_profile,
    get_default_profile,
    get_profile_names,
    get_service_config,
    load_raw_config,
    remove_profile,
    resolve_active_profile_name,
    resolve_connection,
    save_raw_config,
    set_default_profile,
    set_service_config,
)
from kctl_telegram.core.exceptions import KctlError

app = typer.Typer(help="Manage CLI configuration and profiles.")


def _mask_key(api_key: str) -> str:
    if not api_key:
        return "[dim]not set[/dim]"
    if len(api_key) <= 10:
        return "****"
    return f"{api_key[:4]}{'*' * (len(api_key) - 8)}{api_key[-4:]}"


def _test_connection(url: str, api_key: str) -> tuple[bool, str]:
    try:
        client = TelegramClient(base_url=url, api_key=api_key)
        health_data = client.check_health()
        client.close()
        status = health_data.get("status", "unknown")
        if status in ("healthy", "ok"):
            version = health_data.get("version", "unknown")
            return True, version
        return False, f"status: {status}"
    except Exception as e:
        return False, str(e)


@app.command()
def init(
    ctx: typer.Context,
    url: Annotated[str | None, typer.Option("--url", help="Telegram gateway base URL.")] = None,
    api_key: Annotated[str | None, typer.Option("--api-key", help="API key.")] = None,
    name: Annotated[str | None, typer.Option("--name", "-n", help="Profile name.")] = None,
) -> None:
    """Initialize CLI configuration (interactive if no flags given)."""
    actx: AppContext = ctx.obj
    out = actx.output

    profile_name = name or typer.prompt("Profile name", default="default")
    api_url = url or typer.prompt("Telegram gateway URL (e.g. https://telegram.kodeme.io)")
    key = api_key or typer.prompt("API key", hide_input=True)

    out.info(f"Testing connection to {api_url}...")
    ok, version = _test_connection(api_url, key)
    if ok:
        out.success(f"Connected to Telegram gateway {version}")
    else:
        out.error(f"Connection failed: {version}")
        if not typer.confirm("Save configuration anyway?", default=False):
            raise typer.Exit(code=1)

    svc = ServiceConfig(url=api_url, api_key=key)
    set_service_config(profile_name, svc)

    # Set as default if first profile
    if len(get_profile_names()) <= 1:
        set_default_profile(profile_name)

    out.success(f"Configuration saved to {CONFIG_FILE}")
    out.kv("Profile", profile_name)
    out.kv("Service", SERVICE_KEY)
    out.kv("URL", api_url)
    out.kv("API Key", _mask_key(key))


@app.command()
def add(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name (e.g. abcfood, staging)")],
    url: Annotated[str | None, typer.Option("--url", help="Telegram gateway base URL.")] = None,
    api_key: Annotated[str | None, typer.Option("--api-key", help="API key.")] = None,
    set_default: Annotated[bool, typer.Option("--default", help="Set as default profile.")] = False,
) -> None:
    """Add or update a profile's Telegram connection.

    Example: kctl-telegram config add abcfood --url https://telegram.abcfood.app --api-key $KEY

    This writes to the 'telegram' section within the profile, so other
    kctl-* tools (kctl-ak, kctl-odoo) can coexist in the same profile.
    """
    actx: AppContext = ctx.obj
    out = actx.output

    api_url = url or typer.prompt("Telegram gateway URL")
    key = api_key or typer.prompt("API key", hide_input=True)

    out.info(f"Testing connection to {api_url}...")
    ok, version = _test_connection(api_url, key)
    if ok:
        out.success(f"Connected to Telegram gateway {version}")
    else:
        out.error(f"Connection failed: {version}")
        if not typer.confirm("Save anyway?", default=False):
            raise typer.Exit(code=1)

    # Check if this profile already has telegram config
    existing = get_service_config(name)
    if existing.url and not typer.confirm(
        f"Profile '{name}' already has {SERVICE_KEY} config ({existing.url}). Overwrite?"
    ):
        raise typer.Exit(0)

    svc = ServiceConfig(url=api_url, api_key=key)
    set_service_config(name, svc)

    if set_default or len(get_profile_names()) == 1:
        set_default_profile(name)

    out.success(f"Profile '{name}' -> {SERVICE_KEY} configured")
    out.kv("URL", api_url)
    out.kv("API Key", _mask_key(key))
    if get_default_profile() == name:
        out.info("Set as default profile")


@app.command()
def use(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name to switch to")],
) -> None:
    """Switch the default profile.

    Example: kctl-telegram config use abcfood
    """
    actx: AppContext = ctx.obj
    out = actx.output

    profiles = get_profile_names()
    if name not in profiles:
        out.error(f"Profile '{name}' not found")
        out.info(f"Available: {', '.join(profiles)}")
        raise typer.Exit(1)

    old_default = get_default_profile()
    set_default_profile(name)

    svc = get_service_config(name)
    if svc.url:
        ok, version = _test_connection(svc.url, svc.api_key)
        if ok:
            out.success(f"Switched to '{name}' ({svc.url}) -- Telegram gateway {version}")
        else:
            out.warn(f"Switched to '{name}' ({svc.url}) -- connection failed: {version}")
    else:
        out.warn(f"Switched to '{name}' -- no {SERVICE_KEY} config in this profile")

    out.info(f"Previous default: {old_default}")


@app.command()
def remove(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name to remove")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
    service_only: Annotated[
        bool, typer.Option("--service-only", help="Only remove telegram config, keep other services")
    ] = False,
) -> None:
    """Remove a profile or just its Telegram config."""
    actx: AppContext = ctx.obj
    out = actx.output

    profiles = get_profile_names()
    if name not in profiles:
        out.error(f"Profile '{name}' not found")
        raise typer.Exit(1)

    if service_only:
        if not force:
            svc = get_service_config(name)
            if not typer.confirm(f"Remove {SERVICE_KEY} config from '{name}' ({svc.url})?"):
                raise typer.Exit(0)
        data = load_raw_config()
        profile = data.get("profiles", {}).get(name, {})
        profile.pop(SERVICE_KEY, None)
        save_raw_config(data)
        out.success(f"Removed {SERVICE_KEY} config from profile '{name}'")
    else:
        if not force:
            services = get_all_services_in_profile(name)
            svc_list = ", ".join(services.keys())
            if not typer.confirm(f"Remove entire profile '{name}' (services: {svc_list})?"):
                raise typer.Exit(0)
        remove_profile(name)
        out.success(f"Profile '{name}' removed")
        new_default = get_default_profile()
        if new_default != name:
            out.info(f"Default is now: {new_default}")


@app.command()
def show(ctx: typer.Context) -> None:
    """Show full configuration (API keys masked)."""
    actx: AppContext = ctx.obj
    out = actx.output

    default = get_default_profile()
    profiles = get_profile_names()

    if out.json_mode:
        data = load_raw_config()
        # Mask API keys
        for _pname, pdata in data.get("profiles", {}).items():
            for _svc, svc_data in pdata.items():
                if isinstance(svc_data, dict) and "api_key" in svc_data:
                    svc_data["api_key"] = _mask_key(svc_data["api_key"])
                if isinstance(svc_data, dict) and "token" in svc_data:
                    svc_data["token"] = _mask_key(svc_data["token"])
            # Also handle flat format
            if "api_key" in pdata:
                pdata["api_key"] = _mask_key(pdata["api_key"])
        out.raw_json(data)
        return

    sections: list[tuple[str, list[tuple[str, str]]]] = []

    sections.append(
        (
            "General",
            [
                ("Config file", str(CONFIG_FILE)),
                ("Default profile", default),
                ("Total profiles", str(len(profiles))),
                ("This CLI", f"kctl-telegram -> service key: {SERVICE_KEY}"),
            ],
        )
    )

    for pname in profiles:
        marker = " [green](default)[/green]" if pname == default else ""
        services = get_all_services_in_profile(pname)

        kvs: list[tuple[str, str]] = []
        for svc_name, svc_data in services.items():
            if not isinstance(svc_data, dict):
                continue
            svc_url = svc_data.get("url", "")
            svc_key = _mask_key(svc_data.get("api_key", svc_data.get("token", "")))
            indicator = "[green]●[/green]" if svc_name == SERVICE_KEY else "[dim]○[/dim]"
            kvs.append((f"{indicator} {svc_name}", f"{svc_url}  key: {svc_key}"))

        if not kvs:
            kvs.append(("(empty)", "no services configured"))

        sections.append((f"Profile: {pname}{marker}", kvs))

    out.detail("Configuration", sections)


@app.command("set")
def set_(
    ctx: typer.Context,
    key: Annotated[str, typer.Argument(help="Config key (e.g. url, api_key, or default_profile)")],
    value: Annotated[str, typer.Argument(help="Value to set")],
    profile_arg: Annotated[str | None, typer.Option("--profile-name", help="Target profile (default: active)")] = None,
) -> None:
    """Set a configuration value for the current service.

    Examples:
      kctl-telegram config set url https://telegram.new.io
      kctl-telegram config set api_key new-key-value
      kctl-telegram config set default_profile abcfood
    """
    actx: AppContext = ctx.obj
    out = actx.output

    if key == "default_profile":
        set_default_profile(value)
        out.success(f"Default profile set to: {value}")
        return

    pname = profile_arg or resolve_active_profile_name(actx.profile, ENV_PREFIX)
    svc = get_service_config(pname)

    valid_fields = {"url", "api_key", "container_name"}
    if key not in valid_fields:
        out.error(f"Unknown key: {key}")
        out.info(f"Valid keys: {', '.join(sorted(valid_fields))}, default_profile")
        raise typer.Exit(1)

    setattr(svc, key, value)
    set_service_config(pname, svc)

    display = _mask_key(value) if "key" in key else value
    out.success(f"[{pname}] {SERVICE_KEY}.{key} = {display}")


@app.command()
def profiles(ctx: typer.Context) -> None:
    """List all profiles with Telegram connection status."""
    actx: AppContext = ctx.obj
    out = actx.output

    profile_names = get_profile_names()
    if not profile_names:
        out.warn("No profiles configured. Run: kctl-telegram config init")
        return

    active = resolve_active_profile_name(actx.profile, ENV_PREFIX)
    default = get_default_profile()

    rows: list[list[str]] = []
    json_data: list[dict] = []

    for pname in profile_names:
        svc = get_service_config(pname)
        all_services = get_all_services_in_profile(pname)
        other_services = [s for s in all_services if s != SERVICE_KEY]

        is_active = pname == active
        status_marker = "[green]active[/green]" if is_active else ("default" if pname == default else "")

        ok = False
        version = ""
        if svc.url:
            ok, version = _test_connection(svc.url, svc.api_key)
            conn_status = f"[green]{version}[/green]" if ok else "[red]offline[/red]"
        else:
            conn_status = "[dim]no telegram config[/dim]"

        other_str = ", ".join(other_services) if other_services else "[dim]-[/dim]"

        rows.append([pname, svc.url or "-", conn_status, other_str, status_marker])
        json_data.append(
            {
                "name": pname,
                "telegram_url": svc.url,
                "connected": bool(svc.url) and ok,
                "version": version if svc.url and ok else None,
                "other_services": other_services,
                "active": is_active,
                "default": pname == default,
            }
        )

    out.table(
        "Profiles",
        [("Name", "cyan"), ("Telegram URL", ""), ("Status", ""), ("Other Services", "dim"), ("", "green")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def current(ctx: typer.Context) -> None:
    """Show the active profile and connection status."""
    actx: AppContext = ctx.obj
    out = actx.output

    active = resolve_active_profile_name(actx.profile, ENV_PREFIX)
    get_service_config(active)

    resolved_url, resolved_key = resolve_connection(
        profile_name=actx.profile,
        url_override=actx.url_override,
        api_key_override=actx.api_key_override,
    )

    ok, version = _test_connection(resolved_url, resolved_key) if resolved_url else (False, "not configured")

    source = "config default"
    if actx.profile:
        source = "--profile flag"
    elif os.environ.get("KCTL_TELEGRAM_PROFILE"):
        source = "KCTL_TELEGRAM_PROFILE env var"

    sections: list[tuple[str, list[tuple[str, str]]]] = [
        (
            "Active Connection",
            [
                ("Profile", active),
                ("Service", SERVICE_KEY),
                ("Source", source),
                ("URL", resolved_url or "[red]not set[/red]"),
                ("API Key", _mask_key(resolved_key)),
                (
                    "Status",
                    f"[green]Connected -- Telegram gateway {version}[/green]" if ok else f"[red]{version}[/red]",
                ),
            ],
        ),
    ]

    # Other services in this profile
    all_services = get_all_services_in_profile(active)
    other = {k: v for k, v in all_services.items() if k != SERVICE_KEY and isinstance(v, dict)}
    if other:
        sections.append(
            ("Other Services in Profile", [(svc_name, v.get("url", "(no url)")) for svc_name, v in other.items()])
        )

    # Other profiles
    all_profiles = [p for p in get_profile_names() if p != active]
    if all_profiles:
        sections.append(("Other Profiles", [(p, get_service_config(p).url or "(no telegram)") for p in all_profiles]))

    out.detail(
        "Current Profile",
        sections,
        data_for_json={
            "profile": active,
            "service": SERVICE_KEY,
            "source": source,
            "url": resolved_url,
            "connected": ok,
            "version": version if ok else None,
        },
    )


@app.command()
def test(ctx: typer.Context) -> None:
    """Test API connection with current configuration."""
    actx: AppContext = ctx.obj
    out = actx.output

    active = resolve_active_profile_name(actx.profile, ENV_PREFIX)
    out.info(f"Testing profile '{active}' -> {SERVICE_KEY}")

    try:
        c = actx.client
        health_data = c.check_health()
    except KctlError as e:
        out.error(f"Connection failed: {e}")
        raise typer.Exit(code=1) from e

    status = health_data.get("status", "unknown")
    version = health_data.get("version", "unknown")

    out.detail(
        "Connection Test",
        [
            (
                "Result",
                [
                    ("Profile", active),
                    ("Service", SERVICE_KEY),
                    (
                        "Status",
                        "[green]Connected[/green]" if status in ("healthy", "ok") else f"[yellow]{status}[/yellow]",
                    ),
                    ("Version", version),
                ],
            )
        ],
        data_for_json=health_data,
    )


@app.command()
def migrate(ctx: typer.Context) -> None:
    """Migrate config from flat format to service-scoped format.

    Old:  profiles.production.url -> profiles.production.telegram.url
    """
    actx: AppContext = ctx.obj
    out = actx.output

    data = load_raw_config()
    profiles = data.get("profiles", {})
    migrated = 0

    for pname, pdata in profiles.items():
        if not isinstance(pdata, dict):
            continue
        # Check if flat format (has 'url' or 'api_key' at top level, not inside a service key)
        if "url" in pdata and not any(
            isinstance(v, dict) and "url" in v for v in pdata.values() if isinstance(v, dict)
        ):
            old_data = dict(pdata)
            pdata.clear()
            pdata[SERVICE_KEY] = old_data
            migrated += 1
            out.info(f"Migrated: {pname}")

    if migrated:
        save_raw_config(data)
        out.success(f"Migrated {migrated} profile(s) to service-scoped format")
    else:
        out.success("All profiles already in service-scoped format")
