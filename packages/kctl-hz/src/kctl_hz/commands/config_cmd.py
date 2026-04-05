"""Configuration management commands."""

from __future__ import annotations

import os
from typing import Annotated

import typer
from kctl_lib.exceptions import KctlError

from kctl_hz.core.callbacks import AppContext
from kctl_hz.core.config import (
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

app = typer.Typer(help="Manage CLI configuration and profiles.")


def _mask(val: str) -> str:
    if not val:
        return "[dim]not set[/dim]"
    return f"{val[:4]}{'*' * max(0, len(val) - 8)}{val[-4:]}" if len(val) > 10 else "****"


@app.command()
def init(
    ctx: typer.Context,
    cloud_token: Annotated[str | None, typer.Option("--token")] = None,
    dns_token: Annotated[str | None, typer.Option("--dns-token")] = None,
    name: Annotated[str | None, typer.Option("--name", "-n")] = None,
) -> None:
    """Initialize CLI configuration."""
    c: AppContext = ctx.obj
    out = c.output
    profile_name = name or typer.prompt("Profile name", default="kodemeio")
    token = cloud_token or typer.prompt("Hetzner Cloud API token", hide_input=True)
    dns = dns_token or typer.prompt("Hetzner DNS token (optional, Enter to skip)", default="", hide_input=True)

    svc = ServiceConfig(token=token, dns_token=dns)
    set_service_config(profile_name, svc)
    if len(get_profile_names()) <= 1:
        set_default_profile(profile_name)
    out.success(f"Configuration saved to {CONFIG_FILE}")
    out.kv("Profile", profile_name)
    out.kv("Cloud Token", _mask(token))
    out.kv("DNS Token", _mask(dns) if dns else "[dim]not set[/dim]")


@app.command()
def add(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name (e.g. kodemeio, staging)")],
    cloud_token: Annotated[str | None, typer.Option("--token")] = None,
    dns_token: Annotated[str | None, typer.Option("--dns-token")] = None,
    set_default: Annotated[bool, typer.Option("--default", help="Set as default profile.")] = False,
) -> None:
    """Add or update a profile's Hetzner connection."""
    c: AppContext = ctx.obj
    out = c.output

    token = cloud_token or typer.prompt("Hetzner Cloud API token", hide_input=True)
    dns = dns_token or typer.prompt("Hetzner DNS token (optional, Enter to skip)", default="", hide_input=True)

    existing = get_service_config(name)
    if existing.token:
        if not typer.confirm(f"Profile '{name}' already has {SERVICE_KEY} config. Overwrite?"):
            raise typer.Exit(0)

    svc = ServiceConfig(token=token, dns_token=dns)
    set_service_config(name, svc)

    if set_default or len(get_profile_names()) == 1:
        set_default_profile(name)

    out.success(f"Profile '{name}' -> {SERVICE_KEY} configured")
    out.kv("Cloud Token", _mask(token))
    out.kv("DNS Token", _mask(dns) if dns else "[dim]not set[/dim]")
    if get_default_profile() == name:
        out.info("Set as default profile")


@app.command()
def use(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name")],
) -> None:
    """Switch default profile."""
    c: AppContext = ctx.obj
    profiles = get_profile_names()
    if name not in profiles:
        c.output.error(f"Profile '{name}' not found")
        c.output.info(f"Available: {', '.join(profiles)}")
        raise typer.Exit(1)
    old_default = get_default_profile()
    set_default_profile(name)
    c.output.success(f"Switched to '{name}'")
    c.output.info(f"Previous default: {old_default}")


@app.command()
def remove(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name to remove")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
    service_only: Annotated[bool, typer.Option("--service-only", help="Only remove hetzner config")] = False,
) -> None:
    """Remove a profile or just its Hetzner config."""
    c: AppContext = ctx.obj
    out = c.output

    profiles = get_profile_names()
    if name not in profiles:
        out.error(f"Profile '{name}' not found")
        raise typer.Exit(1)

    if service_only:
        if not force:
            if not typer.confirm(f"Remove {SERVICE_KEY} config from '{name}'?"):
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
    """Show configuration."""
    c: AppContext = ctx.obj
    out = c.output
    default = get_default_profile()

    if out.json_mode:
        data = load_raw_config()
        for _pname, pdata in data.get("profiles", {}).items():
            for _svc, svc_data in pdata.items():
                if isinstance(svc_data, dict):
                    for key in ("token", "dns_token", "s3_secret_key"):
                        if key in svc_data:
                            svc_data[key] = _mask(svc_data[key])
        out.raw_json(data)
        return

    sections = [
        (
            "General",
            [
                ("Config file", str(CONFIG_FILE)),
                ("Default profile", default),
                ("Service key", SERVICE_KEY),
            ],
        )
    ]
    for pname in get_profile_names():
        marker = " [green](default)[/green]" if pname == default else ""
        services = get_all_services_in_profile(pname)
        kvs = []
        for svc_name, svc_data in services.items():
            if not isinstance(svc_data, dict):
                continue
            indicator = "[green]●[/green]" if svc_name == SERVICE_KEY else "[dim]○[/dim]"
            kvs.append((f"{indicator} {svc_name}", f"token: {_mask(svc_data.get('token', ''))}"))
        sections.append((f"Profile: {pname}{marker}", kvs or [("(empty)", "")]))
    out.detail("Configuration", sections)


@app.command("set")
def set_(
    ctx: typer.Context,
    key: Annotated[str, typer.Argument(help="Config key (e.g. token, dns_token, s3_access_key, or default_profile)")],
    value: Annotated[str, typer.Argument(help="Value to set")],
    profile_arg: Annotated[str | None, typer.Option("--profile-name", help="Target profile")] = None,
) -> None:
    """Set a configuration value for the current service."""
    c: AppContext = ctx.obj
    out = c.output

    if key == "default_profile":
        set_default_profile(value)
        out.success(f"Default profile set to: {value}")
        return

    pname = profile_arg or resolve_active_profile_name(c.profile)
    svc = get_service_config(pname)

    valid_fields = set(ServiceConfig.model_fields.keys())
    if key not in valid_fields:
        out.error(f"Unknown key: {key}")
        out.info(f"Valid keys: {', '.join(sorted(valid_fields))}, default_profile")
        raise typer.Exit(1)

    setattr(svc, key, value)
    set_service_config(pname, svc)

    display = _mask(value) if "token" in key or "secret" in key else value
    out.success(f"[{pname}] {SERVICE_KEY}.{key} = {display}")


@app.command()
def profiles(ctx: typer.Context) -> None:
    """List all profiles with Hetzner connection status."""
    c: AppContext = ctx.obj
    out = c.output

    profile_names = get_profile_names()
    if not profile_names:
        out.warn("No profiles configured. Run: kctl-hz config init")
        return

    active = resolve_active_profile_name(c.profile)
    default = get_default_profile()

    rows: list[list[str]] = []
    json_data: list[dict] = []

    for pname in profile_names:
        svc = get_service_config(pname)
        all_services = get_all_services_in_profile(pname)
        other_services = [s for s in all_services if s != SERVICE_KEY]

        is_active = pname == active
        status_marker = "[green]active[/green]" if is_active else ("default" if pname == default else "")

        other_str = ", ".join(other_services) if other_services else "[dim]-[/dim]"

        rows.append([pname, _mask(svc.token), _mask(svc.dns_token), other_str, status_marker])
        json_data.append(
            {
                "name": pname,
                "has_token": bool(svc.token),
                "has_dns_token": bool(svc.dns_token),
                "other_services": other_services,
                "active": is_active,
                "default": pname == default,
            }
        )

    out.table(
        "Profiles",
        [("Name", "cyan"), ("Cloud Token", ""), ("DNS Token", ""), ("Other Services", "dim"), ("", "green")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def current(ctx: typer.Context) -> None:
    """Show the active profile and connection status."""
    c: AppContext = ctx.obj
    out = c.output

    active = resolve_active_profile_name(c.profile)

    cloud_token, dns_token = resolve_connection(
        profile_name=c.profile,
        token_override=c.token_override,
        dns_token_override=c.dns_token_override,
    )

    source = "config default"
    if c.profile:
        source = "--profile flag"
    elif os.environ.get("KCTL_HZ_PROFILE"):
        source = "KCTL_HZ_PROFILE env var"

    sections: list[tuple[str, list[tuple[str, str]]]] = [
        (
            "Active Connection",
            [
                ("Profile", active),
                ("Service", SERVICE_KEY),
                ("Source", source),
                ("Cloud Token", _mask(cloud_token)),
                ("DNS Token", _mask(dns_token)),
            ],
        ),
    ]

    all_services = get_all_services_in_profile(active)
    other = {k: v for k, v in all_services.items() if k != SERVICE_KEY and isinstance(v, dict)}
    if other:
        sections.append(
            ("Other Services in Profile", [(svc_name, v.get("url", "(no url)")) for svc_name, v in other.items()])
        )

    all_profiles = [p for p in get_profile_names() if p != active]
    if all_profiles:
        sections.append(
            (
                "Other Profiles",
                [
                    (p, _mask(get_service_config(p).token) if get_service_config(p).token else "(no hetzner)")
                    for p in all_profiles
                ],
            )
        )

    out.detail(
        "Current Profile",
        sections,
        data_for_json={
            "profile": active,
            "service": SERVICE_KEY,
            "source": source,
            "has_cloud_token": bool(cloud_token),
            "has_dns_token": bool(dns_token),
        },
    )


@app.command()
def test(ctx: typer.Context) -> None:
    """Test API connection."""
    c: AppContext = ctx.obj
    out = c.output
    active = resolve_active_profile_name(c.profile)
    out.info(f"Testing profile '{active}' → {SERVICE_KEY}")
    try:
        c.client.get("/servers", params={"per_page": "1"})
        out.success("Connected to Hetzner Cloud API")
    except KctlError as e:
        out.error(f"Cloud API failed: {e}")
        raise typer.Exit(1) from None


@app.command()
def migrate(ctx: typer.Context) -> None:
    """Migrate config from flat format to service-scoped format."""
    c: AppContext = ctx.obj
    out = c.output

    data = load_raw_config()
    config_profiles = data.get("profiles", {})
    migrated = 0

    for pname, pdata in config_profiles.items():
        if not isinstance(pdata, dict):
            continue
        if "token" in pdata and not any(
            isinstance(v, dict) and "token" in v for v in pdata.values() if isinstance(v, dict)
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
