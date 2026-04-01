"""Configuration management commands."""

from __future__ import annotations

import os
from typing import Annotated

import typer
from kctl_lib import KctlError
from kctl_lib.config import (
    CONFIG_FILE,
    get_all_services_in_profile,
    load_raw_config,
    save_raw_config,
)

from kctl_rmm.core.callbacks import AppContext
from kctl_rmm.core.client import RMMClient
from kctl_rmm.core.config import (
    SERVICE_KEY,
    ServiceConfig,
    get_default_profile,
    get_profile_names,
    get_service_config,
    remove_profile,
    resolve_active_profile_name,
    resolve_connection,
    set_default_profile,
    set_service_config,
)

app = typer.Typer(help="Manage CLI configuration and profiles.")


def _mask_key(key: str) -> str:
    if not key:
        return "[dim]not set[/dim]"
    if len(key) <= 10:
        return "****"
    return f"{key[:4]}{'*' * (len(key) - 8)}{key[-4:]}"


def _test_connection(url: str, api_key: str) -> tuple[bool, str]:
    try:
        client = RMMClient(base_url=url, api_key=api_key)
        status, body = client.check_health()
        if status != 200:
            client.close()
            return False, f"API unreachable (HTTP {status})"
        auth_ok, auth_msg = client.check_auth()
        client.close()
        return auth_ok, "ok" if auth_ok else f"auth failed: {auth_msg}"
    except Exception as e:
        return False, str(e)


@app.command()
def init(
    ctx: typer.Context,
    url: Annotated[str | None, typer.Option("--url", help="Tactical RMM API URL.")] = None,
    api_key: Annotated[str | None, typer.Option("--api-key", help="X-API-KEY value.")] = None,
    mesh_url: Annotated[str | None, typer.Option("--mesh-url", help="MeshCentral URL.")] = None,
    name: Annotated[str | None, typer.Option("--name", "-n", help="Profile name.")] = None,
) -> None:
    """Initialize CLI configuration (interactive if no flags given)."""
    actx: AppContext = ctx.obj
    out = actx.output

    profile_name = name or typer.prompt("Profile name", default="default")
    api_url = url or typer.prompt("Tactical RMM API URL (e.g. https://api-rmm.kodeme.io)")
    key = api_key or typer.prompt("API key (X-API-KEY)", hide_input=True)
    mesh = mesh_url or typer.prompt("MeshCentral URL (e.g. https://mesh.kodeme.io)", default="")

    out.info(f"Testing connection to {api_url}...")
    ok, status = _test_connection(api_url, key)
    if ok:
        out.success(f"Connected — {status}")
    else:
        out.error(f"Connection failed: {status}")
        if not typer.confirm("Save configuration anyway?", default=False):
            raise typer.Exit(code=1)

    svc = ServiceConfig(url=api_url, api_key=key, mesh_url=mesh)
    set_service_config(profile_name, svc)

    if len(get_profile_names()) <= 1:
        set_default_profile(profile_name)

    out.success(f"Configuration saved to {CONFIG_FILE}")
    out.kv("Profile", profile_name)
    out.kv("Service", SERVICE_KEY)
    out.kv("URL", api_url)
    out.kv("API Key", _mask_key(key))
    if mesh:
        out.kv("MeshCentral", mesh)


@app.command()
def add(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name (e.g. production, staging)")],
    url: Annotated[str | None, typer.Option("--url", help="Tactical RMM API URL.")] = None,
    api_key: Annotated[str | None, typer.Option("--api-key", help="X-API-KEY value.")] = None,
    mesh_url: Annotated[str | None, typer.Option("--mesh-url", help="MeshCentral URL.")] = None,
    set_default: Annotated[bool, typer.Option("--default", help="Set as default profile.")] = False,
) -> None:
    """Add or update a profile's RMM connection."""
    actx: AppContext = ctx.obj
    out = actx.output

    api_url = url or typer.prompt("Tactical RMM API URL")
    key = api_key or typer.prompt("API key (X-API-KEY)", hide_input=True)
    mesh = mesh_url or typer.prompt("MeshCentral URL", default="")

    out.info(f"Testing connection to {api_url}...")
    ok, status = _test_connection(api_url, key)
    if ok:
        out.success(f"Connected — {status}")
    else:
        out.error(f"Connection failed: {status}")
        if not typer.confirm("Save anyway?", default=False):
            raise typer.Exit(code=1)

    existing = get_service_config(name)
    if existing.url and not typer.confirm(
        f"Profile '{name}' already has {SERVICE_KEY} config ({existing.url}). Overwrite?"
    ):
        raise typer.Exit(0)

    svc = ServiceConfig(url=api_url, api_key=key, mesh_url=mesh)
    set_service_config(name, svc)

    if set_default or len(get_profile_names()) == 1:
        set_default_profile(name)

    out.success(f"Profile '{name}' -> {SERVICE_KEY} configured")
    out.kv("URL", api_url)
    out.kv("API Key", _mask_key(key))
    if mesh:
        out.kv("MeshCentral", mesh)
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
        ok, status = _test_connection(svc.url, svc.api_key)
        if ok:
            out.success(f"Switched to '{name}' ({svc.url}) — {status}")
        else:
            out.warn(f"Switched to '{name}' ({svc.url}) — connection failed: {status}")
    else:
        out.warn(f"Switched to '{name}' — no {SERVICE_KEY} config in this profile")

    out.info(f"Previous default: {old_default}")


@app.command()
def remove(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name to remove")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
    service_only: Annotated[
        bool, typer.Option("--service-only", help="Only remove rmm config, keep other services")
    ] = False,
) -> None:
    """Remove a profile or just its RMM config."""
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
        for _pname, pdata in data.get("profiles", {}).items():
            for _svc, svc_data in pdata.items():
                if isinstance(svc_data, dict) and "api_key" in svc_data:
                    svc_data["api_key"] = _mask_key(svc_data["api_key"])
                if isinstance(svc_data, dict) and "token" in svc_data:
                    svc_data["token"] = _mask_key(svc_data["token"])
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
                ("This CLI", f"kctl-rmm -> service key: {SERVICE_KEY}"),
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
            indicator = "[green]@[/green]" if svc_name == SERVICE_KEY else "[dim]o[/dim]"
            kvs.append((f"{indicator} {svc_name}", f"{svc_url}  key: {svc_key}"))

            if svc_name == SERVICE_KEY and svc_data.get("mesh_url"):
                kvs.append(("  mesh_url", svc_data["mesh_url"]))

        if not kvs:
            kvs.append(("(empty)", "no services configured"))

        sections.append((f"Profile: {pname}{marker}", kvs))

    out.detail("Configuration", sections)


@app.command("set")
def set_(
    ctx: typer.Context,
    key: Annotated[str, typer.Argument(help="Config key (e.g. url, api_key, mesh_url, or default_profile)")],
    value: Annotated[str, typer.Argument(help="Value to set")],
    profile_arg: Annotated[str | None, typer.Option("--profile-name", help="Target profile (default: active)")] = None,
) -> None:
    """Set a configuration value for the current service."""
    actx: AppContext = ctx.obj
    out = actx.output

    if key == "default_profile":
        set_default_profile(value)
        out.success(f"Default profile set to: {value}")
        return

    pname = profile_arg or resolve_active_profile_name(actx.profile)
    svc = get_service_config(pname)

    valid_fields = {"url", "api_key", "mesh_url"}
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
    """List all profiles with RMM connection status."""
    actx: AppContext = ctx.obj
    out = actx.output

    profile_names = get_profile_names()
    if not profile_names:
        out.warn("No profiles configured. Run: kctl-rmm config init")
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
        conn_status = "[dim]no rmm config[/dim]"
        if svc.url:
            ok, status = _test_connection(svc.url, svc.api_key)
            conn_status = f"[green]{status}[/green]" if ok else "[red]offline[/red]"

        other_str = ", ".join(other_services) if other_services else "[dim]-[/dim]"

        rows.append([pname, svc.url or "-", conn_status, other_str, status_marker])
        json_data.append(
            {
                "name": pname,
                "rmm_url": svc.url,
                "connected": ok,
                "other_services": other_services,
                "active": is_active,
                "default": pname == default,
            }
        )

    out.table(
        "Profiles",
        [("Name", "cyan"), ("RMM URL", ""), ("Status", ""), ("Other Services", "dim"), ("", "green")],
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

    resolved_url, resolved_key = resolve_connection(
        profile_name=actx.profile,
        url_override=actx.url_override,
        api_key_override=actx.api_key_override,
    )

    ok, status = _test_connection(resolved_url, resolved_key) if resolved_url else (False, "not configured")

    source = "config default"
    if actx.profile:
        source = "--profile flag"
    elif os.environ.get("KCTL_RMM_PROFILE"):
        source = "KCTL_RMM_PROFILE env var"

    sections: list[tuple[str, list[tuple[str, str]]]] = [
        (
            "Active Connection",
            [
                ("Profile", active),
                ("Service", SERVICE_KEY),
                ("Source", source),
                ("URL", resolved_url or "[red]not set[/red]"),
                ("API Key", _mask_key(resolved_key)),
                ("MeshCentral", svc.mesh_url or "[dim]not set[/dim]"),
                ("Status", f"[green]Connected — {status}[/green]" if ok else f"[red]{status}[/red]"),
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
        sections.append(("Other Profiles", [(p, get_service_config(p).url or "(no rmm)") for p in all_profiles]))

    out.detail(
        "Current Profile",
        sections,
        data_for_json={
            "profile": active,
            "service": SERVICE_KEY,
            "source": source,
            "url": resolved_url,
            "mesh_url": svc.mesh_url,
            "connected": ok,
        },
    )


@app.command()
def test(ctx: typer.Context) -> None:
    """Test API connection with current configuration."""
    actx: AppContext = ctx.obj
    out = actx.output

    active = resolve_active_profile_name(actx.profile)
    out.info(f"Testing profile '{active}' -> {SERVICE_KEY}")

    try:
        c = actx.client
        status, body = c.check_health()
        auth_ok, auth_msg = c.check_auth()
    except KctlError as e:
        out.error(f"Connection failed: {e}")
        raise typer.Exit(code=1) from e

    api_ok = status == 200
    out.detail(
        "Connection Test",
        [
            (
                "Result",
                [
                    ("Profile", active),
                    ("Service", SERVICE_KEY),
                    ("API", "[green]reachable[/green]" if api_ok else f"[red]HTTP {status}[/red]"),
                    ("Auth", "[green]OK[/green]" if auth_ok else f"[red]{auth_msg}[/red]"),
                ],
            )
        ],
        data_for_json={"profile": active, "service": SERVICE_KEY, "api_reachable": api_ok, "authenticated": auth_ok},
    )


@app.command()
def migrate(ctx: typer.Context) -> None:
    """Migrate config from flat format to service-scoped format."""
    actx: AppContext = ctx.obj
    out = actx.output

    data = load_raw_config()
    profiles_data = data.get("profiles", {})
    migrated = 0

    for pname, pdata in profiles_data.items():
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
