"""Configuration management commands for kctl-mm.

Initialize, view, and manage CLI profiles and Mattermost connection settings.
Uses service-scoped config: each profile contains per-service sections.
"""

from __future__ import annotations

import os
from typing import Annotated, Optional

import typer

from kctl_lib.config import load_raw_config
from kctl_lib.exceptions import KctlError
from kctl_mm.core.callbacks import AppContext
from kctl_mm.core.client import MattermostClient
from kctl_mm.core.config import (
    CONFIG_FILE,
    ENV_PROFILE,
    SERVICE_KEY,
    ServiceConfig,
    get_all_services_in_profile,
    get_default_profile,
    get_profile_names,
    get_service_config,
    remove_profile,
    resolve_active_profile_name,
    resolve_connection,
    save_raw_config,
    set_default_profile,
    set_service_config,
)

app = typer.Typer(help="Manage CLI configuration and Mattermost profiles.")


def _mask_secret(secret: str) -> str:
    if not secret:
        return "[dim]not set[/dim]"
    if len(secret) <= 10:
        return "****"
    return f"{secret[:4]}{'*' * (len(secret) - 8)}{secret[-4:]}"


def _test_connection(url: str, token: str) -> tuple[bool, str]:
    try:
        client = MattermostClient(url=url, token=token)
        data = client.ping()
        client.close()
        if isinstance(data, dict) and data.get("status") == "OK":
            version = data.get("ServerVersion") or data.get("server_version") or "OK"
            return True, str(version)
        return False, f"unexpected ping response: {data!r}"
    except Exception as e:
        return False, str(e)


@app.command()
def init(
    ctx: typer.Context,
    url: Annotated[Optional[str], typer.Option("--url", help="Mattermost base URL.")] = None,
    token: Annotated[Optional[str], typer.Option("--token", help="Personal access token.")] = None,
    team: Annotated[Optional[str], typer.Option("--team", help="Default team slug (optional).")] = None,
    name: Annotated[Optional[str], typer.Option("--name", "-n", help="Profile name.")] = None,
) -> None:
    """Initialize CLI configuration (interactive if no flags given)."""
    actx: AppContext = ctx.obj
    out = actx.output

    profile_name = name or typer.prompt("Profile name", default="default")
    api_url = url or typer.prompt("Mattermost URL", default="https://mm.idtpp.com")
    api_token = token or typer.prompt("Personal access token", hide_input=True)
    api_team = team if team is not None else typer.prompt("Default team slug (blank for none)", default="")

    out.info(f"Testing connection to {api_url}...")
    ok, version = _test_connection(api_url, api_token)
    if ok:
        out.success(f"Connected to Mattermost ({version})")
    else:
        out.error(f"Connection failed: {version}")
        if not typer.confirm("Save configuration anyway?", default=False):
            raise typer.Exit(code=1)

    svc = ServiceConfig(url=api_url, token=api_token, team=api_team)
    set_service_config(profile_name, svc)

    if len(get_profile_names()) <= 1:
        set_default_profile(profile_name)

    out.success(f"Configuration saved to {CONFIG_FILE}")
    out.kv("Profile", profile_name)
    out.kv("Service", SERVICE_KEY)
    out.kv("URL", api_url)
    out.kv("Team", api_team or "(none)")
    out.kv("Token", _mask_secret(api_token))


@app.command()
def add(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name (e.g. staging, production)")],
    url: Annotated[Optional[str], typer.Option("--url", help="Mattermost base URL.")] = None,
    token: Annotated[Optional[str], typer.Option("--token", help="Personal access token.")] = None,
    team: Annotated[Optional[str], typer.Option("--team", help="Default team slug.")] = None,
    set_default: Annotated[bool, typer.Option("--default", help="Set as default profile.")] = False,
) -> None:
    """Add or update a profile's Mattermost connection."""
    actx: AppContext = ctx.obj
    out = actx.output

    api_url = url or typer.prompt("Mattermost URL", default="https://mm.idtpp.com")
    api_token = token or typer.prompt("Personal access token", hide_input=True)
    api_team = team if team is not None else typer.prompt("Default team slug (blank for none)", default="")

    out.info(f"Testing connection to {api_url}...")
    ok, version = _test_connection(api_url, api_token)
    if ok:
        out.success(f"Connected to Mattermost ({version})")
    else:
        out.error(f"Connection failed: {version}")
        if not typer.confirm("Save anyway?", default=False):
            raise typer.Exit(code=1)

    existing = get_service_config(name)
    if existing.url and existing.token:
        if not typer.confirm(f"Profile '{name}' already has {SERVICE_KEY} config ({existing.url}). Overwrite?"):
            raise typer.Exit(0)

    svc = ServiceConfig(url=api_url, token=api_token, team=api_team)
    set_service_config(name, svc)

    if set_default or len(get_profile_names()) == 1:
        set_default_profile(name)

    out.success(f"Profile '{name}' -> {SERVICE_KEY} configured")
    out.kv("URL", api_url)
    out.kv("Team", api_team or "(none)")
    out.kv("Token", _mask_secret(api_token))
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
    if svc.url and svc.token:
        ok, version = _test_connection(svc.url, svc.token)
        if ok:
            out.success(f"Switched to '{name}' ({svc.url}) -- Mattermost {version}")
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
        bool,
        typer.Option("--service-only", help="Only remove mattermost config, keep other services"),
    ] = False,
) -> None:
    """Remove a profile or just its Mattermost config."""
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
            svc_list = ", ".join(services.keys()) or "(empty)"
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
            if not isinstance(pdata, dict):
                continue
            for _svc, svc_data in pdata.items():
                if isinstance(svc_data, dict):
                    if "token" in svc_data:
                        svc_data["token"] = _mask_secret(svc_data["token"])
                    if "api_key" in svc_data:
                        svc_data["api_key"] = _mask_secret(svc_data["api_key"])
            if "token" in pdata:
                pdata["token"] = _mask_secret(pdata["token"])
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
                ("This CLI", f"kctl-mm -> service key: {SERVICE_KEY}"),
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
            svc_team = svc_data.get("team", "")
            indicator = "[green]●[/green]" if svc_name == SERVICE_KEY else "[dim]○[/dim]"
            detail = svc_url
            if svc_name == SERVICE_KEY and svc_team:
                detail = f"{svc_url}  team: {svc_team}"
            kvs.append((f"{indicator} {svc_name}", detail))

        if not kvs:
            kvs.append(("(empty)", "no services configured"))

        sections.append((f"Profile: {pname}{marker}", kvs))

    out.detail("Configuration", sections)


@app.command()
def validate(ctx: typer.Context) -> None:
    """Validate the active profile's Mattermost connection."""
    actx: AppContext = ctx.obj
    out = actx.output

    active = resolve_active_profile_name(actx.profile)
    out.info(f"Validating profile '{active}' -> {SERVICE_KEY}")

    try:
        settings = resolve_connection(actx.profile)
    except KctlError as e:
        out.error(str(e))
        raise typer.Exit(code=1) from e

    url = str(settings.get("url", ""))
    token = str(settings.get("token", ""))

    if not url or not token:
        out.error("Profile is missing required fields (url and token)")
        raise typer.Exit(code=1)

    ok, version = _test_connection(url, token)
    if not ok:
        out.error(f"Connection failed: {version}")
        raise typer.Exit(code=1)

    out.detail(
        "Validation",
        [
            (
                "Result",
                [
                    ("Profile", active),
                    ("Service", SERVICE_KEY),
                    ("URL", url),
                    ("Status", "[green]Connected[/green]"),
                    ("Version", version),
                ],
            )
        ],
        data_for_json={"profile": active, "url": url, "connected": True, "version": version},
    )


@app.command("set")
def set_(
    ctx: typer.Context,
    key: Annotated[
        str,
        typer.Argument(
            help="Config key (url, token, team, ssh_host, ssh_user, compose_path, compose_service, timeout, or default_profile)"
        ),
    ],
    value: Annotated[str, typer.Argument(help="Value to set")],
    profile_arg: Annotated[
        Optional[str], typer.Option("--profile-name", help="Target profile (default: active)")
    ] = None,
) -> None:
    """Set a configuration value for the Mattermost service.

    Examples:
      kctl-mm config set url https://mm.new.io
      kctl-mm config set token new-token-value
      kctl-mm config set default_profile production
    """
    actx: AppContext = ctx.obj
    out = actx.output

    if key == "default_profile":
        set_default_profile(value)
        out.success(f"Default profile set to: {value}")
        return

    pname = profile_arg or resolve_active_profile_name(actx.profile)
    svc = get_service_config(pname)

    valid_fields = set(ServiceConfig.model_fields.keys())
    if key not in valid_fields:
        out.error(f"Unknown key: {key}")
        out.info(f"Valid keys: {', '.join(sorted(valid_fields))}, default_profile")
        raise typer.Exit(1)

    setattr(svc, key, value)
    set_service_config(pname, svc)

    display = _mask_secret(value) if key == "token" else value
    out.success(f"[{pname}] {SERVICE_KEY}.{key} = {display}")


@app.command()
def profiles(ctx: typer.Context) -> None:
    """List all profiles with Mattermost connection status."""
    actx: AppContext = ctx.obj
    out = actx.output

    profile_names = get_profile_names()
    if not profile_names:
        out.warn("No profiles configured. Run: kctl-mm config init")
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
        if svc.url and svc.token:
            ok, version = _test_connection(svc.url, svc.token)
            conn_status = f"[green]{version}[/green]" if ok else "[red]offline[/red]"
        else:
            conn_status = "[dim]no mattermost config[/dim]"

        other_str = ", ".join(other_services) if other_services else "[dim]-[/dim]"

        rows.append([pname, svc.url or "-", conn_status, other_str, status_marker])
        json_data.append(
            {
                "name": pname,
                "mattermost_url": svc.url,
                "connected": bool(svc.url and svc.token) and ok,
                "version": version if (svc.url and svc.token and ok) else None,
                "other_services": other_services,
                "active": is_active,
                "default": pname == default,
            }
        )

    out.table(
        "Profiles",
        [
            ("Name", "cyan"),
            ("Mattermost URL", ""),
            ("Status", ""),
            ("Other Services", "dim"),
            ("", "green"),
        ],
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

    source = "config default"
    if actx.profile:
        source = "--profile flag"
    elif os.environ.get(ENV_PROFILE):
        source = f"{ENV_PROFILE} env var"

    ok, version = _test_connection(svc.url, svc.token) if (svc.url and svc.token) else (False, "not configured")

    sections: list[tuple[str, list[tuple[str, str]]]] = [
        (
            "Active Connection",
            [
                ("Profile", active),
                ("Service", SERVICE_KEY),
                ("Source", source),
                ("URL", svc.url or "[red]not set[/red]"),
                ("Team", svc.team or "(none)"),
                ("Token", _mask_secret(svc.token)),
                ("SSH Host", svc.ssh_host or "[dim]not set[/dim]"),
                ("Compose Path", svc.compose_path or "[dim]not set[/dim]"),
                (
                    "Status",
                    f"[green]Connected -- {version}[/green]" if ok else f"[red]{version}[/red]",
                ),
            ],
        ),
    ]

    all_services = get_all_services_in_profile(active)
    other = {k: v for k, v in all_services.items() if k != SERVICE_KEY and isinstance(v, dict)}
    if other:
        sections.append(
            (
                "Other Services in Profile",
                [(svc_name, v.get("url", "(no url)")) for svc_name, v in other.items()],
            )
        )

    all_profiles = [p for p in get_profile_names() if p != active]
    if all_profiles:
        sections.append(
            (
                "Other Profiles",
                [(p, get_service_config(p).url or "(no mattermost)") for p in all_profiles],
            )
        )

    out.detail(
        "Current Profile",
        sections,
        data_for_json={
            "profile": active,
            "service": SERVICE_KEY,
            "source": source,
            "url": svc.url,
            "team": svc.team,
            "connected": ok,
            "version": version if ok else None,
        },
    )
