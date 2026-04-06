"""Configuration management commands.

Initialize, view, and manage CLI profiles and connection settings.
Uses service-scoped config: each profile contains per-service sections.
"""

from __future__ import annotations

import os

import typer
from typing import Annotated, Optional

from kctl_zulip.core.callbacks import AppContext
from kctl_zulip.core.client import ZulipClient
from kctl_zulip.core.config import (
    CONFIG_FILE,
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
from kctl_lib.exceptions import KctlError

app = typer.Typer(help="Manage CLI configuration and profiles.")


def _mask_secret(secret: str) -> str:
    if not secret:
        return "[dim]not set[/dim]"
    if len(secret) <= 10:
        return "****"
    return f"{secret[:4]}{'*' * (len(secret) - 8)}{secret[-4:]}"


def _test_connection(url: str, email: str, api_key: str) -> tuple[bool, str]:
    try:
        client = ZulipClient(base_url=url, email=email, api_key=api_key)
        data = client.get("server_settings")
        client.close()
        version = data.get("zulip_version", "unknown")
        return True, version
    except Exception as e:
        return False, str(e)


@app.command()
def init(
    ctx: typer.Context,
    url: Annotated[Optional[str], typer.Option("--url", help="Zulip base URL.")] = None,
    email: Annotated[Optional[str], typer.Option("--email", help="Bot/user email.")] = None,
    api_key: Annotated[Optional[str], typer.Option("--api-key", help="API key.")] = None,
    name: Annotated[Optional[str], typer.Option("--name", "-n", help="Profile name.")] = None,
) -> None:
    """Initialize CLI configuration (interactive if no flags given)."""
    actx: AppContext = ctx.obj
    out = actx.output

    profile_name = name or typer.prompt("Profile name", default="default")
    api_url = url or typer.prompt("Zulip URL (e.g. https://zulip.kodeme.io)")
    api_email = email or typer.prompt("Bot/user email (e.g. admin@kodeme.io)")
    key = api_key or typer.prompt("API key", hide_input=True)

    out.info(f"Testing connection to {api_url}...")
    ok, version = _test_connection(api_url, api_email, key)
    if ok:
        out.success(f"Connected to Zulip {version}")
    else:
        out.error(f"Connection failed: {version}")
        if not typer.confirm("Save configuration anyway?", default=False):
            raise typer.Exit(code=1)

    svc = ServiceConfig(url=api_url, email=api_email, api_key=key)
    set_service_config(profile_name, svc)

    if len(get_profile_names()) <= 1:
        set_default_profile(profile_name)

    out.success(f"Configuration saved to {CONFIG_FILE}")
    out.kv("Profile", profile_name)
    out.kv("Service", SERVICE_KEY)
    out.kv("URL", api_url)
    out.kv("Email", api_email)
    out.kv("API Key", _mask_secret(key))


@app.command()
def add(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name (e.g. staging, abcfood)")],
    url: Annotated[Optional[str], typer.Option("--url", help="Zulip base URL.")] = None,
    email: Annotated[Optional[str], typer.Option("--email", help="Bot/user email.")] = None,
    api_key: Annotated[Optional[str], typer.Option("--api-key", help="API key.")] = None,
    set_default: Annotated[bool, typer.Option("--default", help="Set as default profile.")] = False,
) -> None:
    """Add or update a profile's Zulip connection.

    Example: kctl-zulip config add production --url https://zulip.kodeme.io --email bot@kodeme.io --api-key $KEY
    """
    actx: AppContext = ctx.obj
    out = actx.output

    api_url = url or typer.prompt("Zulip URL")
    api_email = email or typer.prompt("Bot/user email")
    key = api_key or typer.prompt("API key", hide_input=True)

    out.info(f"Testing connection to {api_url}...")
    ok, version = _test_connection(api_url, api_email, key)
    if ok:
        out.success(f"Connected to Zulip {version}")
    else:
        out.error(f"Connection failed: {version}")
        if not typer.confirm("Save anyway?", default=False):
            raise typer.Exit(code=1)

    existing = get_service_config(name)
    if existing.url:
        if not typer.confirm(f"Profile '{name}' already has {SERVICE_KEY} config ({existing.url}). Overwrite?"):
            raise typer.Exit(0)

    svc = ServiceConfig(url=api_url, email=api_email, api_key=key)
    set_service_config(name, svc)

    if set_default or len(get_profile_names()) == 1:
        set_default_profile(name)

    out.success(f"Profile '{name}' -> {SERVICE_KEY} configured")
    out.kv("URL", api_url)
    out.kv("Email", api_email)
    out.kv("API Key", _mask_secret(key))
    if get_default_profile() == name:
        out.info("Set as default profile")


@app.command()
def use(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name to switch to")],
) -> None:
    """Switch the default profile."""
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
        ok, version = _test_connection(svc.url, svc.email, svc.api_key)
        if ok:
            out.success(f"Switched to '{name}' ({svc.url}) -- Zulip {version}")
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
    service_only: Annotated[bool, typer.Option("--service-only", help="Only remove zulip config, keep other services")] = False,
) -> None:
    """Remove a profile or just its Zulip config."""
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
    """Show full configuration (secrets masked)."""
    actx: AppContext = ctx.obj
    out = actx.output

    default = get_default_profile()
    profiles = get_profile_names()

    if out.json_mode:
        data = load_raw_config()
        for _pname, pdata in data.get("profiles", {}).items():
            for _svc, svc_data in pdata.items():
                if isinstance(svc_data, dict) and "api_key" in svc_data:
                    svc_data["api_key"] = _mask_secret(svc_data["api_key"])
                if isinstance(svc_data, dict) and "token" in svc_data:
                    svc_data["token"] = _mask_secret(svc_data["token"])
            if "api_key" in pdata:
                pdata["api_key"] = _mask_secret(pdata["api_key"])
        out.raw_json(data)
        return

    sections: list[tuple[str, list[tuple[str, str]]]] = []

    sections.append(("General", [
        ("Config file", str(CONFIG_FILE)),
        ("Default profile", default),
        ("Total profiles", str(len(profiles))),
        ("This CLI", f"kctl-zulip -> service key: {SERVICE_KEY}"),
    ]))

    for pname in profiles:
        marker = " [green](default)[/green]" if pname == default else ""
        services = get_all_services_in_profile(pname)

        kvs: list[tuple[str, str]] = []
        for svc_name, svc_data in services.items():
            if not isinstance(svc_data, dict):
                continue
            svc_url = svc_data.get("url", "")
            svc_email = svc_data.get("email", "")
            indicator = "[green]●[/green]" if svc_name == SERVICE_KEY else "[dim]○[/dim]"
            kvs.append((f"{indicator} {svc_name}", f"{svc_url}  email: {svc_email}"))

        if not kvs:
            kvs.append(("(empty)", "no services configured"))

        sections.append((f"Profile: {pname}{marker}", kvs))

    out.detail("Configuration", sections)


@app.command("set")
def set_(
    ctx: typer.Context,
    key: Annotated[str, typer.Argument(help="Config key (e.g. url, email, api_key, or default_profile)")],
    value: Annotated[str, typer.Argument(help="Value to set")],
    profile_arg: Annotated[Optional[str], typer.Option("--profile-name", help="Target profile (default: active)")] = None,
) -> None:
    """Set a configuration value for the current service.

    Examples:
      kctl-zulip config set url https://zulip.new.io
      kctl-zulip config set email bot@new.io
      kctl-zulip config set api_key new-key-value
      kctl-zulip config set default_profile production
    """
    actx: AppContext = ctx.obj
    out = actx.output

    if key == "default_profile":
        set_default_profile(value)
        out.success(f"Default profile set to: {value}")
        return

    pname = profile_arg or resolve_active_profile_name(actx.profile)
    svc = get_service_config(pname)

    valid_fields = {"url", "email", "api_key"}
    if key not in valid_fields:
        out.error(f"Unknown key: {key}")
        out.info(f"Valid keys: {', '.join(sorted(valid_fields))}, default_profile")
        raise typer.Exit(1)

    setattr(svc, key, value)
    set_service_config(pname, svc)

    display = _mask_secret(value) if "key" in key else value
    out.success(f"[{pname}] {SERVICE_KEY}.{key} = {display}")


@app.command()
def profiles(ctx: typer.Context) -> None:
    """List all profiles with Zulip connection status."""
    actx: AppContext = ctx.obj
    out = actx.output

    profile_names = get_profile_names()
    if not profile_names:
        out.warn("No profiles configured. Run: kctl-zulip config init")
        return

    active = resolve_active_profile_name(actx.profile)
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
            ok, version = _test_connection(svc.url, svc.email, svc.api_key)
            conn_status = f"[green]{version}[/green]" if ok else "[red]offline[/red]"
        else:
            conn_status = "[dim]no zulip config[/dim]"

        other_str = ", ".join(other_services) if other_services else "[dim]-[/dim]"

        rows.append([pname, svc.url or "-", conn_status, other_str, status_marker])
        json_data.append({
            "name": pname,
            "zulip_url": svc.url,
            "connected": bool(svc.url) and ok,
            "version": version if svc.url and ok else None,
            "other_services": other_services,
            "active": is_active,
            "default": pname == default,
        })

    out.table(
        "Profiles",
        [("Name", "cyan"), ("Zulip URL", ""), ("Status", ""), ("Other Services", "dim"), ("", "green")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def current(ctx: typer.Context) -> None:
    """Show the active profile and connection status."""
    actx: AppContext = ctx.obj
    out = actx.output

    active = resolve_active_profile_name(actx.profile)
    svc = get_service_config(active)

    resolved_url, resolved_email, resolved_key = resolve_connection(
        profile_name=actx.profile,
        url_override=actx.url_override,
        email_override=actx.email_override,
        api_key_override=actx.api_key_override,
    )

    ok, version = _test_connection(resolved_url, resolved_email, resolved_key) if resolved_url else (False, "not configured")

    source = "config default"
    if actx.profile:
        source = "--profile flag"
    elif os.environ.get("KCTL_ZULIP_PROFILE"):
        source = "KCTL_ZULIP_PROFILE env var"

    sections: list[tuple[str, list[tuple[str, str]]]] = [
        ("Active Connection", [
            ("Profile", active),
            ("Service", SERVICE_KEY),
            ("Source", source),
            ("URL", resolved_url or "[red]not set[/red]"),
            ("Email", resolved_email or "[red]not set[/red]"),
            ("API Key", _mask_secret(resolved_key)),
            ("Status", f"[green]Connected -- Zulip {version}[/green]" if ok else f"[red]{version}[/red]"),
        ]),
    ]

    # Other services in this profile
    all_services = get_all_services_in_profile(active)
    other = {k: v for k, v in all_services.items() if k != SERVICE_KEY and isinstance(v, dict)}
    if other:
        sections.append(("Other Services in Profile", [
            (svc_name, v.get("url", "(no url)")) for svc_name, v in other.items()
        ]))

    # Other profiles
    all_profiles = [p for p in get_profile_names() if p != active]
    if all_profiles:
        sections.append(("Other Profiles", [
            (p, get_service_config(p).url or "(no zulip)") for p in all_profiles
        ]))

    out.detail("Current Profile", sections, data_for_json={
        "profile": active,
        "service": SERVICE_KEY,
        "source": source,
        "url": resolved_url,
        "email": resolved_email,
        "connected": ok,
        "version": version if ok else None,
    })


@app.command()
def test(ctx: typer.Context) -> None:
    """Test API connection with current configuration."""
    actx: AppContext = ctx.obj
    out = actx.output

    active = resolve_active_profile_name(actx.profile)
    out.info(f"Testing profile '{active}' -> {SERVICE_KEY}")

    try:
        c = actx.client
        data = c.get("server_settings")
    except KctlError as e:
        out.error(f"Connection failed: {e}")
        raise typer.Exit(code=1)

    out.detail(
        "Connection Test",
        [("Result", [
            ("Profile", active),
            ("Service", SERVICE_KEY),
            ("Status", "[green]Connected[/green]"),
            ("Zulip Version", data.get("zulip_version", "unknown")),
            ("Feature Level", str(data.get("zulip_feature_level", "unknown"))),
        ])],
        data_for_json=data,
    )


@app.command()
def migrate(ctx: typer.Context) -> None:
    """Migrate config from flat format to service-scoped format.

    Old:  profiles.production.url -> profiles.production.zulip.url
    """
    actx: AppContext = ctx.obj
    out = actx.output

    data = load_raw_config()
    profiles = data.get("profiles", {})
    migrated = 0

    for pname, pdata in profiles.items():
        if not isinstance(pdata, dict):
            continue
        if "url" in pdata and not any(isinstance(v, dict) for v in pdata.values()):
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
