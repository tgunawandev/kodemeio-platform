"""Configuration management commands."""

from __future__ import annotations

import os
from typing import Annotated

import typer

from kctl_sentry.core.callbacks import AppContext
from kctl_sentry.core.config import (
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
from kctl_sentry.core.exceptions import KctlError

app = typer.Typer(help="Manage CLI configuration and profiles.")


def _mask(val: str) -> str:
    """Mask a secret value for display."""
    if not val:
        return "[dim]not set[/dim]"
    return f"{val[:4]}{'*' * max(0, len(val) - 8)}{val[-4:]}" if len(val) > 10 else "****"


@app.command()
def init(
    ctx: typer.Context,
    auth_token: Annotated[str | None, typer.Option("--auth-token", help="Sentry auth token")] = None,
    organization: Annotated[str | None, typer.Option("--organization", "--org", help="Organization slug")] = None,
    url: Annotated[str | None, typer.Option("--url", help="Sentry URL")] = None,
    default_project: Annotated[str | None, typer.Option("--default-project", help="Default project slug")] = None,
    name: Annotated[str | None, typer.Option("--name", "-n", help="Profile name")] = None,
) -> None:
    """Initialize CLI configuration."""
    c: AppContext = ctx.obj
    out = c.output
    profile_name = name or typer.prompt("Profile name", default="kodemeio")
    token = auth_token or typer.prompt("Sentry auth token", hide_input=True)
    org = organization or typer.prompt("Organization slug")
    sentry_url = url or typer.prompt("Sentry URL", default="https://sentry.io")
    proj = default_project or typer.prompt("Default project slug (optional)", default="")

    svc = ServiceConfig(
        url=sentry_url,
        auth_token=token,
        organization=org,
        default_project=proj,
    )
    set_service_config(profile_name, svc)
    if len(get_profile_names()) <= 1:
        set_default_profile(profile_name)
    out.success(f"Configuration saved to {CONFIG_FILE}")
    out.kv("Profile", profile_name)
    out.kv("URL", sentry_url)
    out.kv("Token", _mask(token))
    out.kv("Organization", org)
    if proj:
        out.kv("Default project", proj)


@app.command()
def add(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name (e.g. kodemeio, staging)")],
    auth_token: Annotated[str | None, typer.Option("--auth-token", help="Sentry auth token")] = None,
    organization: Annotated[str | None, typer.Option("--organization", "--org", help="Organization slug")] = None,
    url: Annotated[str | None, typer.Option("--url", help="Sentry URL")] = None,
    default_project: Annotated[str | None, typer.Option("--default-project", help="Default project slug")] = None,
    set_default: Annotated[bool, typer.Option("--default", help="Set as default profile.")] = False,
) -> None:
    """Add or update a profile's Sentry connection."""
    c: AppContext = ctx.obj
    out = c.output

    token = auth_token or typer.prompt("Sentry auth token", hide_input=True)
    org = organization or typer.prompt("Organization slug")
    sentry_url = url or typer.prompt("Sentry URL", default="https://sentry.io")
    proj = default_project or typer.prompt("Default project slug (optional)", default="")

    existing = get_service_config(name)
    if existing.auth_token:
        if not typer.confirm(f"Profile '{name}' already has {SERVICE_KEY} config ({existing.url}). Overwrite?"):
            raise typer.Exit(0)

    svc = ServiceConfig(
        url=sentry_url,
        auth_token=token,
        organization=org,
        default_project=proj,
    )
    set_service_config(name, svc)

    if set_default or len(get_profile_names()) == 1:
        set_default_profile(name)

    out.success(f"Profile '{name}' -> {SERVICE_KEY} configured")
    out.kv("URL", sentry_url)
    out.kv("Token", _mask(token))
    out.kv("Organization", org)
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
    service_only: Annotated[bool, typer.Option("--service-only", help="Only remove sentry config")] = False,
) -> None:
    """Remove a profile or just its Sentry config."""
    c: AppContext = ctx.obj
    out = c.output

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
    """Show configuration."""
    c: AppContext = ctx.obj
    out = c.output
    default = get_default_profile()

    if out.json_mode:
        data = load_raw_config()
        for _pname, pdata in data.get("profiles", {}).items():
            for _svc, svc_data in pdata.items():
                if isinstance(svc_data, dict):
                    for key in ("auth_token", "token"):
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
        kvs: list[tuple[str, str]] = []
        for svc_name, svc_data in services.items():
            if not isinstance(svc_data, dict):
                continue
            indicator = "[green]●[/green]" if svc_name == SERVICE_KEY else "[dim]○[/dim]"
            token_val = svc_data.get("auth_token", svc_data.get("token", ""))
            kvs.append((f"{indicator} {svc_name}", f"token: {_mask(token_val)}"))
        sections.append((f"Profile: {pname}{marker}", kvs or [("(empty)", "")]))
    out.detail("Configuration", sections)


@app.command("set")
def set_(
    ctx: typer.Context,
    key: Annotated[
        str, typer.Argument(help="Config key (e.g. url, auth_token, organization, default_project, or default_profile)")
    ],
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

    valid_fields = {"url", "auth_token", "organization", "default_project"}
    if key not in valid_fields:
        out.error(f"Unknown key: {key}")
        out.info(f"Valid keys: {', '.join(sorted(valid_fields))}, default_profile")
        raise typer.Exit(1)

    setattr(svc, key, value)
    set_service_config(pname, svc)

    display = _mask(value) if "token" in key else value
    out.success(f"[{pname}] {SERVICE_KEY}.{key} = {display}")


@app.command()
def profiles(ctx: typer.Context) -> None:
    """List all profiles with Sentry connection status."""
    c: AppContext = ctx.obj
    out = c.output

    profile_names = get_profile_names()
    if not profile_names:
        out.warn("No profiles configured. Run: kctl-sentry config init")
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

        rows.append([pname, svc.url or "-", svc.organization or "-", other_str, status_marker])
        json_data.append(
            {
                "name": pname,
                "url": svc.url,
                "organization": svc.organization,
                "has_token": bool(svc.auth_token),
                "other_services": other_services,
                "active": is_active,
                "default": pname == default,
            }
        )

    out.table(
        "Profiles",
        [("Name", "cyan"), ("URL", ""), ("Organization", ""), ("Other Services", "dim"), ("", "green")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def current(ctx: typer.Context) -> None:
    """Show the active profile and connection status."""
    c: AppContext = ctx.obj
    out = c.output

    active = resolve_active_profile_name(c.profile)

    sentry_url, auth_token, organization, default_project = resolve_connection(
        profile_name=c.profile,
        auth_token_override=c.auth_token_override,
    )

    source = "config default"
    if c.profile:
        source = "--profile flag"
    elif os.environ.get("KCTL_SENTRY_PROFILE"):
        source = "KCTL_SENTRY_PROFILE env var"

    sections: list[tuple[str, list[tuple[str, str]]]] = [
        (
            "Active Connection",
            [
                ("Profile", active),
                ("Service", SERVICE_KEY),
                ("Source", source),
                ("URL", sentry_url or "[red]not set[/red]"),
                ("Auth Token", _mask(auth_token)),
                ("Organization", organization or "[red]not set[/red]"),
                ("Default Project", default_project or "[dim]not set[/dim]"),
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
        sections.append(("Other Profiles", [(p, get_service_config(p).url or "(no sentry)") for p in all_profiles]))

    out.detail(
        "Current Profile",
        sections,
        data_for_json={
            "profile": active,
            "service": SERVICE_KEY,
            "source": source,
            "url": sentry_url,
            "organization": organization,
            "has_token": bool(auth_token),
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
        result = c.client.check_health()
        org_name = result.get("name", "unknown")
        out.success(f"Connected — organization: {org_name}")
    except KctlError as e:
        out.error(f"Connection failed: {e}")
        raise typer.Exit(1) from e


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
        if "auth_token" in pdata and not any(
            isinstance(v, dict) and ("auth_token" in v or "url" in v) for v in pdata.values() if isinstance(v, dict)
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
