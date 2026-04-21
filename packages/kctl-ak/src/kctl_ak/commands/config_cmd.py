"""Configuration management commands.

Initialize, view, and manage CLI profiles and connection settings.
Uses service-scoped config: each profile contains per-service sections.
"""

from __future__ import annotations

import os
from typing import Annotated

import typer

from kctl_ak.core.callbacks import AppContext
from kctl_ak.core.client import AuthentikClient
from kctl_ak.core.config import (
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
from kctl_ak.core.exceptions import KctlError

app = typer.Typer(help="Manage CLI configuration and profiles.")


def _mask_token(token: str) -> str:
    if not token:
        return "[dim]not set[/dim]"
    if len(token) <= 10:
        return "****"
    return f"{token[:4]}{'*' * (len(token) - 8)}{token[-4:]}"


def _test_connection(url: str, token: str) -> tuple[bool, str]:
    try:
        client = AuthentikClient(base_url=url, credential=token)
        version_data = client.get("admin/version/")
        client.close()
        return True, version_data.get("version_current", "unknown")
    except Exception as e:
        return False, str(e)


@app.command()
def init(
    ctx: typer.Context,
    url: Annotated[str | None, typer.Option("--url", help="Authentik base URL.")] = None,
    token: Annotated[str | None, typer.Option("--token", help="API token.")] = None,
    name: Annotated[str | None, typer.Option("--name", "-n", help="Profile name.")] = None,
) -> None:
    """Initialize CLI configuration (interactive if no flags given)."""
    actx: AppContext = ctx.obj
    out = actx.output

    profile_name = name or typer.prompt("Profile name", default="default")
    api_url = url or typer.prompt("Authentik URL (e.g. https://auth.kodeme.io)")
    api_token = token or typer.prompt("API token", hide_input=True)

    out.info(f"Testing connection to {api_url}...")
    ok, version = _test_connection(api_url, api_token)
    if ok:
        out.success(f"Connected to Authentik {version}")
    else:
        out.error(f"Connection failed: {version}")
        if not typer.confirm("Save configuration anyway?", default=False):
            raise typer.Exit(code=1)

    svc = ServiceConfig(url=api_url, token=api_token)
    set_service_config(profile_name, svc)

    # Set as default if first profile
    if len(get_profile_names()) <= 1:
        set_default_profile(profile_name)

    out.success(f"Configuration saved to {CONFIG_FILE}")
    out.kv("Profile", profile_name)
    out.kv("Service", SERVICE_KEY)
    out.kv("URL", api_url)
    out.kv("Token", _mask_token(api_token))


@app.command()
def add(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name (e.g. abcfood, staging)")],
    url: Annotated[str | None, typer.Option("--url", help="Authentik base URL.")] = None,
    token: Annotated[str | None, typer.Option("--token", help="API token.")] = None,
    roles_dir: Annotated[str | None, typer.Option("--roles-dir", help="Path to roles directory.")] = None,
    group_structure: Annotated[
        str | None, typer.Option("--group-structure", help="Path to group-structure.yaml.")
    ] = None,
    set_default: Annotated[bool, typer.Option("--default", help="Set as default profile.")] = False,
) -> None:
    """Add or update a profile's Authentik connection.

    Example: kctl-ak config add abcfood --url https://auth.abcfood.app --token $TOKEN

    This writes to the 'authentik' section within the profile, so other
    kctl-* tools (kctl-odoo, kctl-mailcow) can coexist in the same profile.
    """
    actx: AppContext = ctx.obj
    out = actx.output

    api_url = url or typer.prompt("Authentik URL")
    api_token = token or typer.prompt("API token", hide_input=True)

    out.info(f"Testing connection to {api_url}...")
    ok, version = _test_connection(api_url, api_token)
    if ok:
        out.success(f"Connected to Authentik {version}")
    else:
        out.error(f"Connection failed: {version}")
        if not typer.confirm("Save anyway?", default=False):
            raise typer.Exit(code=1)

    # Check if this profile already has authentik config
    existing = get_service_config(name)
    if existing.url:
        if not typer.confirm(f"Profile '{name}' already has {SERVICE_KEY} config ({existing.url}). Overwrite?"):
            raise typer.Exit(0)

    svc = ServiceConfig(url=api_url, token=api_token)
    if roles_dir:
        svc.roles_dir = roles_dir
    if group_structure:
        svc.group_structure = group_structure

    set_service_config(name, svc)

    if set_default or len(get_profile_names()) == 1:
        set_default_profile(name)

    out.success(f"Profile '{name}' → {SERVICE_KEY} configured")
    out.kv("URL", api_url)
    out.kv("Token", _mask_token(api_token))
    if roles_dir:
        out.kv("Roles dir", roles_dir)
    if get_default_profile() == name:
        out.info("Set as default profile")


@app.command()
def use(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name to switch to")],
) -> None:
    """Switch the default profile.

    Example: kctl-ak config use abcfood
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
        ok, version = _test_connection(svc.url, svc.token)
        if ok:
            out.success(f"Switched to '{name}' ({svc.url}) — Authentik {version}")
        else:
            out.warn(f"Switched to '{name}' ({svc.url}) — connection failed: {version}")
    else:
        out.warn(f"Switched to '{name}' — no {SERVICE_KEY} config in this profile")

    out.info(f"Previous default: {old_default}")


@app.command()
def remove(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name to remove")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
    service_only: Annotated[
        bool, typer.Option("--service-only", help="Only remove authentik config, keep other services")
    ] = False,
) -> None:
    """Remove a profile or just its Authentik config."""
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
    """Show full configuration (tokens masked)."""
    actx: AppContext = ctx.obj
    out = actx.output

    default = get_default_profile()
    profiles = get_profile_names()

    if out.json_mode:
        data = load_raw_config()
        # Mask tokens
        for _pname, pdata in data.get("profiles", {}).items():
            for _svc, svc_data in pdata.items():
                if isinstance(svc_data, dict) and "token" in svc_data:
                    svc_data["token"] = _mask_token(svc_data["token"])
                if isinstance(svc_data, dict) and isinstance(svc_data.get("smtp"), dict):
                    svc_data["smtp"]["password"] = "****"
            # Also handle flat format
            if "token" in pdata:
                pdata["token"] = _mask_token(pdata["token"])
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
                ("This CLI", f"kctl-ak → service key: {SERVICE_KEY}"),
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
            svc_token = _mask_token(svc_data.get("token", ""))
            indicator = "[green]●[/green]" if svc_name == SERVICE_KEY else "[dim]○[/dim]"
            kvs.append((f"{indicator} {svc_name}", f"{svc_url}  token: {svc_token}"))

            # Show extras for our service
            if svc_name == SERVICE_KEY:
                if svc_data.get("roles_dir"):
                    kvs.append(("  roles_dir", svc_data["roles_dir"]))
                if svc_data.get("smtp"):
                    smtp = svc_data["smtp"]
                    kvs.append(("  smtp", f"{smtp.get('host', '')}:{smtp.get('port', 587)}"))

        if not kvs:
            kvs.append(("(empty)", "no services configured"))

        sections.append((f"Profile: {pname}{marker}", kvs))

    out.detail("Configuration", sections)


@app.command("set")
def set_(
    ctx: typer.Context,
    key: Annotated[str, typer.Argument(help="Config key (e.g. url, token, roles_dir, or default_profile)")],
    value: Annotated[str, typer.Argument(help="Value to set")],
    profile_arg: Annotated[str | None, typer.Option("--profile-name", help="Target profile (default: active)")] = None,
) -> None:
    """Set a configuration value for the current service.

    Examples:
      kctl-ak config set url https://auth.new.io
      kctl-ak config set token new-token-value
      kctl-ak config set roles_dir /path/to/roles
      kctl-ak config set default_profile abcfood
    """
    actx: AppContext = ctx.obj
    out = actx.output

    if key == "default_profile":
        set_default_profile(value)
        out.success(f"Default profile set to: {value}")
        return

    pname = profile_arg or resolve_active_profile_name(actx.profile)
    svc = get_service_config(pname)

    valid_fields = {"url", "token", "container_name", "roles_dir", "group_structure"}
    if key not in valid_fields:
        out.error(f"Unknown key: {key}")
        out.info(f"Valid keys: {', '.join(sorted(valid_fields))}, default_profile")
        raise typer.Exit(1)

    setattr(svc, key, value)
    set_service_config(pname, svc)

    display = _mask_token(value) if "token" in key else value
    out.success(f"[{pname}] {SERVICE_KEY}.{key} = {display}")


@app.command()
def profiles(ctx: typer.Context) -> None:
    """List all profiles with Authentik connection status."""
    actx: AppContext = ctx.obj
    out = actx.output

    profile_names = get_profile_names()
    if not profile_names:
        out.warn("No profiles configured. Run: kctl-ak config init")
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

        if svc.url:
            ok, version = _test_connection(svc.url, svc.token)
            conn_status = f"[green]{version}[/green]" if ok else "[red]offline[/red]"
        else:
            conn_status = "[dim]no authentik config[/dim]"

        other_str = ", ".join(other_services) if other_services else "[dim]-[/dim]"

        rows.append([pname, svc.url or "-", conn_status, other_str, status_marker])
        json_data.append(
            {
                "name": pname,
                "authentik_url": svc.url,
                "connected": bool(svc.url) and ok if svc.url else False,
                "version": version if svc.url and ok else None,
                "other_services": other_services,
                "active": is_active,
                "default": pname == default,
            }
        )

    out.table(
        "Profiles",
        [("Name", "cyan"), ("Authentik URL", ""), ("Status", ""), ("Other Services", "dim"), ("", "green")],
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

    resolved_url, resolved_token = resolve_connection(
        profile_name=actx.profile,
        url_override=actx.url_override,
        token_override=actx.token_override,
    )

    ok, version = _test_connection(resolved_url, resolved_token) if resolved_url else (False, "not configured")

    source = "config default"
    if actx.profile:
        source = "--profile flag"
    elif os.environ.get("KCTL_AK_PROFILE"):
        source = "KCTL_AK_PROFILE env var"

    sections: list[tuple[str, list[tuple[str, str]]]] = [
        (
            "Active Connection",
            [
                ("Profile", active),
                ("Service", SERVICE_KEY),
                ("Source", source),
                ("URL", resolved_url or "[red]not set[/red]"),
                ("Token", _mask_token(resolved_token)),
                ("Status", f"[green]Connected — Authentik {version}[/green]" if ok else f"[red]{version}[/red]"),
            ],
        ),
    ]

    extras: list[tuple[str, str]] = []
    if svc.roles_dir:
        extras.append(("Roles dir", svc.roles_dir))
    if svc.group_structure:
        extras.append(("Group structure", svc.group_structure))
    if svc.smtp:
        extras.append(("SMTP", f"{svc.smtp.host}:{svc.smtp.port}"))
    if extras:
        sections.append(("Service Settings", extras))

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
        sections.append(("Other Profiles", [(p, get_service_config(p).url or "(no authentik)") for p in all_profiles]))

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

    active = resolve_active_profile_name(actx.profile)
    out.info(f"Testing profile '{active}' → {SERVICE_KEY}")

    try:
        c = actx.client
        version_data = c.get("admin/version/")
    except KctlError as e:
        out.error(f"Connection failed: {e}")
        raise typer.Exit(code=1)

    out.detail(
        "Connection Test",
        [
            (
                "Result",
                [
                    ("Profile", active),
                    ("Service", SERVICE_KEY),
                    ("Status", "[green]Connected[/green]"),
                    ("Version", version_data.get("version_current", "unknown")),
                    ("Latest", version_data.get("version_latest", "unknown")),
                ],
            )
        ],
        data_for_json=version_data,
    )


@app.command()
def migrate(ctx: typer.Context) -> None:
    """Migrate config from flat format to service-scoped format.

    Old:  profiles.production.url → profiles.production.authentik.url
    """
    actx: AppContext = ctx.obj
    out = actx.output

    data = load_raw_config()
    profiles = data.get("profiles", {})
    migrated = 0

    for pname, pdata in profiles.items():
        if not isinstance(pdata, dict):
            continue
        # Check if flat format (has 'url' or 'token' at top level, not inside a service key)
        if "url" in pdata and not any(
            isinstance(v, dict) and "url" in v
            for v in pdata.values()
            if isinstance(v, dict) and v is not pdata.get("smtp")
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
