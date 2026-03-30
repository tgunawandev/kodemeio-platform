"""Configuration management commands.

Initialize, view, and manage CLI profiles and connection settings.
Uses service-scoped config: each profile contains per-service sections.
"""

from __future__ import annotations

import os
from typing import Annotated

import typer
from kctl_common.config import (
    CONFIG_FILE,
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

from kctl_claude.core.callbacks import AppContext
from kctl_claude.core.config import SERVICE_KEY, ServiceConfig

app = typer.Typer(help="Manage CLI configuration and profiles.")

ENV_PREFIX = "KCTL_CLAUDE"

_SECRET_KEYS = {"token", "api_key", "password", "secret", "service_account_token", "auth_token", "api_token"}


def _mask_value(key: str, value: object) -> str:
    """Mask sensitive values in config output."""
    if any(secret in key.lower() for secret in _SECRET_KEYS):
        s = str(value)
        if len(s) > 8:
            return s[:4] + "****" + s[-4:]
        return "****"
    if isinstance(value, dict):
        parts = [f"'{k}': {_mask_value(k, v)!r}" for k, v in value.items()]
        return "{" + ", ".join(parts) + "}"
    if isinstance(value, list):
        return str(value)
    return str(value)


VALID_FIELDS = {"config_dir", "backup_dir"}


@app.command()
def init(
    ctx: typer.Context,
    config_dir: Annotated[str | None, typer.Option("--config-dir", help="Path to Claude config directory.")] = None,
    backup_dir: Annotated[str | None, typer.Option("--backup-dir", help="Path to backup directory.")] = None,
    name: Annotated[str | None, typer.Option("--name", "-n", help="Profile name.")] = None,
) -> None:
    """Initialize CLI configuration (interactive if no flags given)."""
    actx: AppContext = ctx.obj
    out = actx.output

    profile_name = name or typer.prompt("Profile name", default="default")
    cfg_dir = config_dir or typer.prompt("Claude config directory", default="~/.claude")
    bak_dir = backup_dir or typer.prompt("Backup directory", default="~/.local/share/kodemeio/claude/backups")

    svc = ServiceConfig(config_dir=cfg_dir, backup_dir=bak_dir)
    set_service_config(profile_name, SERVICE_KEY, svc.model_dump(exclude_defaults=False))

    # Set as default if first profile
    if len(get_profile_names()) <= 1:
        set_default_profile(profile_name)

    out.success(f"Configuration saved to {CONFIG_FILE}")
    out.info(f"Profile: {profile_name}")
    out.info(f"Service: {SERVICE_KEY}")
    out.info(f"Config dir: {cfg_dir}")
    out.info(f"Backup dir: {bak_dir}")


@app.command()
def add(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name (e.g. work, staging)")],
    config_dir: Annotated[str | None, typer.Option("--config-dir", help="Path to Claude config directory.")] = None,
    backup_dir: Annotated[str | None, typer.Option("--backup-dir", help="Path to backup directory.")] = None,
    set_default: Annotated[bool, typer.Option("--default", help="Set as default profile.")] = False,
) -> None:
    """Add or update a profile's Claude configuration.

    Example: kctl-claude config add work --config-dir ~/.claude-work
    """
    actx: AppContext = ctx.obj
    out = actx.output

    cfg_dir = config_dir or typer.prompt("Claude config directory", default="~/.claude")
    bak_dir = backup_dir or typer.prompt("Backup directory", default="~/.local/share/kodemeio/claude/backups")

    # Check if this profile already has claude config
    existing = get_service_config(name, SERVICE_KEY, list(VALID_FIELDS))
    if existing and not typer.confirm(f"Profile '{name}' already has {SERVICE_KEY} config. Overwrite?"):
        raise typer.Exit(0)

    svc = ServiceConfig(config_dir=cfg_dir, backup_dir=bak_dir)
    set_service_config(name, SERVICE_KEY, svc.model_dump(exclude_defaults=False))

    if set_default or len(get_profile_names()) == 1:
        set_default_profile(name)

    out.success(f"Profile '{name}' -> {SERVICE_KEY} configured")
    out.info(f"Config dir: {cfg_dir}")
    out.info(f"Backup dir: {bak_dir}")
    if get_default_profile() == name:
        out.info("Set as default profile")


@app.command()
def use(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name to switch to")],
) -> None:
    """Switch the default profile.

    Example: kctl-claude config use work
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
    out.success(f"Switched to '{name}' (was: {old_default})")


@app.command()
def remove(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name to remove")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
    service_only: Annotated[
        bool, typer.Option("--service-only", help="Only remove claude config, keep other services")
    ] = False,
) -> None:
    """Remove a profile or just its Claude config."""
    actx: AppContext = ctx.obj
    out = actx.output

    profiles = get_profile_names()
    if name not in profiles:
        out.error(f"Profile '{name}' not found")
        raise typer.Exit(1)

    if service_only:
        if not force and not typer.confirm(f"Remove {SERVICE_KEY} config from '{name}'?"):
            raise typer.Exit(0)
        data = load_raw_config()
        profile = data.get("profiles", {}).get(name, {})
        profile.pop(SERVICE_KEY, None)
        save_raw_config(data)
        out.success(f"Removed {SERVICE_KEY} config from profile '{name}'")
    else:
        if not force:
            services = get_all_services_in_profile(name)
            svc_list = ", ".join(services.keys()) if services else "(empty)"
            if not typer.confirm(f"Remove entire profile '{name}' (services: {svc_list})?"):
                raise typer.Exit(0)
        remove_profile(name)
        out.success(f"Profile '{name}' removed")
        new_default = get_default_profile()
        if new_default != name:
            out.info(f"Default is now: {new_default}")


@app.command()
def show(ctx: typer.Context) -> None:
    """Show full configuration."""
    actx: AppContext = ctx.obj
    out = actx.output

    default = get_default_profile()
    profile_list = get_profile_names()

    if out.json_mode:
        data = load_raw_config()
        out.raw_json(data)
        return

    sections: list[tuple[str, list[tuple[str, str]]]] = []

    sections.append(
        (
            "General",
            [
                ("Config file", str(CONFIG_FILE)),
                ("Default profile", default),
                ("Total profiles", str(len(profile_list))),
                ("This CLI", f"kctl-claude -> service key: {SERVICE_KEY}"),
            ],
        )
    )

    for pname in profile_list:
        marker = " [green](default)[/green]" if pname == default else ""
        services = get_all_services_in_profile(pname)

        kvs: list[tuple[str, str]] = []
        for svc_name, svc_data in services.items():
            if not isinstance(svc_data, dict):
                continue
            indicator = "[green]●[/green]" if svc_name == SERVICE_KEY else "[dim]○[/dim]"
            detail_parts = [f"{k}={_mask_value(k, v)}" for k, v in svc_data.items() if v]
            kvs.append((f"{indicator} {svc_name}", ", ".join(detail_parts) if detail_parts else "(empty)"))

        if not kvs:
            kvs.append(("(empty)", "no services configured"))

        sections.append((f"Profile: {pname}{marker}", kvs))

    out.detail("Configuration", sections)


@app.command()
def validate(ctx: typer.Context) -> None:
    """Validate the current configuration."""
    actx: AppContext = ctx.obj
    out = actx.output

    issues: list[str] = []

    # Check config file exists
    if not CONFIG_FILE.exists():
        issues.append(f"Config file not found: {CONFIG_FILE}")
        out.error("Config file not found. Run: kctl-claude config init")
        raise typer.Exit(1)

    # Validate YAML structure
    data = load_raw_config()
    if not data:
        issues.append("Config file is empty")

    if "profiles" not in data:
        issues.append("No profiles section in config")

    # Check active profile has claude config
    default = data.get("default_profile", "default")
    profiles = data.get("profiles", {})

    if default not in profiles:
        issues.append(f"Default profile '{default}' does not exist")

    for pname, pdata in profiles.items():
        if not isinstance(pdata, dict):
            issues.append(f"Profile '{pname}' is not a dict")
            continue

        svc_data = pdata.get(SERVICE_KEY, {})
        if isinstance(svc_data, dict):
            # Validate ServiceConfig fields
            try:
                ServiceConfig(**{k: v for k, v in svc_data.items() if k in VALID_FIELDS})
            except Exception as e:
                issues.append(f"Profile '{pname}' -> {SERVICE_KEY}: {e}")

    if issues:
        out.warn(f"Found {len(issues)} issue(s):")
        for issue in issues:
            out.error(f"  - {issue}")
        raise typer.Exit(1)

    out.success("Configuration is valid")
    out.info(f"Profiles: {', '.join(profiles.keys())}")
    out.info(f"Default: {default}")


@app.command("set")
def set_(
    ctx: typer.Context,
    key: Annotated[str, typer.Argument(help="Config key (e.g. config_dir, backup_dir, default_profile)")],
    value: Annotated[str, typer.Argument(help="Value to set")],
    profile_arg: Annotated[str | None, typer.Option("--profile-name", help="Target profile (default: active)")] = None,
) -> None:
    """Set a configuration value for the current service.

    Examples:
      kctl-claude config set config_dir /path/to/dir
      kctl-claude config set backup_dir /path/to/backups
      kctl-claude config set default_profile work
    """
    actx: AppContext = ctx.obj
    out = actx.output

    if key == "default_profile":
        set_default_profile(value)
        out.success(f"Default profile set to: {value}")
        return

    pname = profile_arg or resolve_active_profile_name(actx.profile, ENV_PREFIX)
    svc_data = get_service_config(pname, SERVICE_KEY, list(VALID_FIELDS))

    if key not in VALID_FIELDS:
        out.error(f"Unknown key: {key}")
        out.info(f"Valid keys: {', '.join(sorted(VALID_FIELDS))}, default_profile")
        raise typer.Exit(1)

    svc_data[key] = value
    set_service_config(pname, SERVICE_KEY, svc_data)
    out.success(f"[{pname}] {SERVICE_KEY}.{key} = {value}")


@app.command()
def profiles(ctx: typer.Context) -> None:
    """List all profiles."""
    actx: AppContext = ctx.obj
    out = actx.output

    profile_names = get_profile_names()
    if not profile_names:
        out.warn("No profiles configured. Run: kctl-claude config init")
        return

    active = resolve_active_profile_name(actx.profile, ENV_PREFIX)
    default = get_default_profile()

    rows: list[list[str]] = []
    json_data: list[dict[str, object]] = []

    for pname in profile_names:
        svc_data = get_service_config(pname, SERVICE_KEY, list(VALID_FIELDS))
        all_services = get_all_services_in_profile(pname)
        other_services = [s for s in all_services if s != SERVICE_KEY]

        is_active = pname == active
        status_marker = "[green]active[/green]" if is_active else ("default" if pname == default else "")

        cfg_dir = svc_data.get("config_dir", "-")
        other_str = ", ".join(other_services) if other_services else "[dim]-[/dim]"

        rows.append([pname, cfg_dir or "-", other_str, status_marker])
        json_data.append(
            {
                "name": pname,
                "config_dir": svc_data.get("config_dir", ""),
                "backup_dir": svc_data.get("backup_dir", ""),
                "other_services": other_services,
                "active": is_active,
                "default": pname == default,
            }
        )

    out.table(
        "Profiles",
        [("Name", "cyan"), ("Config Dir", ""), ("Other Services", "dim"), ("", "green")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def current(ctx: typer.Context) -> None:
    """Show the active profile and its Claude configuration."""
    actx: AppContext = ctx.obj
    out = actx.output

    active = resolve_active_profile_name(actx.profile, ENV_PREFIX)
    svc_data = get_service_config(active, SERVICE_KEY, list(VALID_FIELDS))

    source = "config default"
    if actx.profile:
        source = "--profile flag"
    elif os.environ.get(f"{ENV_PREFIX}_PROFILE"):
        source = f"{ENV_PREFIX}_PROFILE env var"

    sections: list[tuple[str, list[tuple[str, str]]]] = [
        (
            "Active Profile",
            [
                ("Profile", active),
                ("Service", SERVICE_KEY),
                ("Source", source),
                ("Config dir", svc_data.get("config_dir") or "[dim]not set[/dim]"),
                ("Backup dir", svc_data.get("backup_dir") or "[dim]not set[/dim]"),
            ],
        ),
    ]

    # Other services in this profile
    all_services = get_all_services_in_profile(active)
    other = {k: v for k, v in all_services.items() if k != SERVICE_KEY and isinstance(v, dict)}
    if other:
        masked = []
        for svc_name, v in other.items():
            if isinstance(v, dict):
                parts = ", ".join(f"{k}={_mask_value(k, val)}" for k, val in v.items() if val)
                masked.append((svc_name, parts or "(empty)"))
            else:
                masked.append((svc_name, str(v)))
        sections.append(("Other Services in Profile", masked))

    # Other profiles
    all_profiles = [p for p in get_profile_names() if p != active]
    if all_profiles:
        sections.append(("Other Profiles", [(p, "") for p in all_profiles]))

    out.detail(
        "Current Profile",
        sections,
        data_for_json={
            "profile": active,
            "service": SERVICE_KEY,
            "source": source,
            "config_dir": svc_data.get("config_dir", ""),
            "backup_dir": svc_data.get("backup_dir", ""),
        },
    )
