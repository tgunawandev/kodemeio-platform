"""Configuration management commands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

import typer
import yaml
from kctl_lib.exceptions import KctlError

from kctl_dbgate.core.callbacks import AppContext
from kctl_dbgate.core.client import DBGateClient
from kctl_dbgate.core.config import (
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
    save_raw_config,
    set_default_profile,
    set_service_config,
)

app = typer.Typer(help="Manage CLI configuration and profiles.")


def _mask(secret: str) -> str:
    if not secret:
        return "[dim]not set[/dim]"
    if len(secret) <= 8:
        return "****"
    return f"{secret[:4]}{'*' * (len(secret) - 8)}{secret[-4:]}"


def _test_connection(url: str, login: str, password: str) -> tuple[bool, str]:
    try:
        client = DBGateClient(base_url=url, login=login, password=password)
        client.login()
        client.close()
        return True, "authenticated"
    except Exception as e:
        return False, str(e)


@app.command()
def init(
    ctx: typer.Context,
    url: Annotated[str | None, typer.Option("--url", help="DBGate base URL")] = None,
    login: Annotated[str | None, typer.Option("--login", help="UI username")] = None,
    password: Annotated[str | None, typer.Option("--password", help="UI password")] = None,
    name: Annotated[str | None, typer.Option("--name", "-n", help="Profile name")] = None,
) -> None:
    """Initialize CLI configuration (interactive if no flags given)."""
    actx: AppContext = ctx.obj
    out = actx.output

    profile_name = name or typer.prompt("Profile name", default="kodemeio")
    api_url = url or typer.prompt("DBGate URL (e.g. https://dbgate.kodeme.io)")
    api_login = login or typer.prompt("Login", default="admin")
    api_password = password or typer.prompt("Password", hide_input=True)

    out.info(f"Testing connection to {api_url}...")
    ok, info = _test_connection(api_url, api_login, api_password)
    if ok:
        out.success(f"Connected: {info}")
    else:
        out.error(f"Connection failed: {info}")
        if not typer.confirm("Save configuration anyway?", default=False):
            raise typer.Exit(code=1)

    svc = ServiceConfig(url=api_url, login=api_login, password=api_password)
    set_service_config(profile_name, svc)

    if len(get_profile_names()) <= 1:
        set_default_profile(profile_name)

    out.success(f"Configuration saved to {CONFIG_FILE}")
    out.kv("Profile", profile_name)
    out.kv("Service", SERVICE_KEY)
    out.kv("URL", api_url)
    out.kv("Login", api_login)
    out.kv("Password", _mask(api_password))


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
                if isinstance(svc_data, dict) and "password" in svc_data:
                    svc_data["password"] = _mask(svc_data["password"])
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
                ("This CLI", f"kctl-dbgate -> service key: {SERVICE_KEY}"),
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
            svc_login = svc_data.get("login", "")
            svc_pwd = _mask(svc_data.get("password", ""))
            indicator = "[green]●[/green]" if svc_name == SERVICE_KEY else "[dim]○[/dim]"
            summary = f"{svc_url}  user: {svc_login}  password: {svc_pwd}" if svc_name == SERVICE_KEY else svc_url
            kvs.append((f"{indicator} {svc_name}", summary))

        if not kvs:
            kvs.append(("(empty)", "no services configured"))

        sections.append((f"Profile: {pname}{marker}", kvs))

    out.detail("Configuration", sections)


@app.command("set")
def set_(
    ctx: typer.Context,
    key: Annotated[str, typer.Argument(help="Config key: url, login, password, or default_profile")],
    value: Annotated[str, typer.Argument(help="Value to set")],
    profile_arg: Annotated[str | None, typer.Option("--profile-name", help="Target profile")] = None,
) -> None:
    """Set a configuration value for the current service."""
    actx: AppContext = ctx.obj
    out = actx.output

    if key == "default_profile":
        set_default_profile(value)
        out.success(f"Default profile set to: {value}")
        return

    valid_fields = {"url", "login", "password"}
    if key not in valid_fields:
        out.error(f"Unknown key: {key}")
        out.info(f"Valid keys: {', '.join(sorted(valid_fields))}, default_profile")
        raise typer.Exit(1)

    pname = profile_arg or resolve_active_profile_name(actx.profile)
    svc = get_service_config(pname)
    setattr(svc, key, value)
    set_service_config(pname, svc)

    display = _mask(value) if key == "password" else value
    out.success(f"[{pname}] {SERVICE_KEY}.{key} = {display}")


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
        ok, info = _test_connection(svc.url, svc.login, svc.password)
        if ok:
            out.success(f"Switched to '{name}' ({svc.url}) — {info}")
        else:
            out.warn(f"Switched to '{name}' ({svc.url}) — {info}")
    else:
        out.warn(f"Switched to '{name}' — no {SERVICE_KEY} config in this profile")

    out.info(f"Previous default: {old_default}")


@app.command()
def remove(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name to remove")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
    service_only: Annotated[bool, typer.Option("--service-only", help=f"Only remove {SERVICE_KEY} config")] = False,
) -> None:
    """Remove a profile or just its DBGate config."""
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


@app.command()
def profiles(ctx: typer.Context) -> None:
    """List all profiles with DBGate connection status."""
    actx: AppContext = ctx.obj
    out = actx.output

    profile_names = get_profile_names()
    if not profile_names:
        out.warn("No profiles configured. Run: kctl-dbgate config init")
        return

    active = resolve_active_profile_name(actx.profile)
    default = get_default_profile()

    rows: list[list[str]] = []
    for pname in profile_names:
        svc = get_service_config(pname)
        is_active = pname == active
        status_marker = "[green]active[/green]" if is_active else ("default" if pname == default else "")
        if svc.url:
            ok, info = _test_connection(svc.url, svc.login, svc.password)
            conn = f"[green]{info}[/green]" if ok else f"[red]{info[:40]}[/red]"
        else:
            conn = f"[dim]no {SERVICE_KEY} config[/dim]"
        rows.append([pname, svc.url or "-", svc.login or "-", conn, status_marker])

    out.table(
        "Profiles",
        [("Name", "cyan"), ("DBGate URL", ""), ("Login", ""), ("Status", ""), ("", "green")],
        rows,
    )


@app.command()
def current(ctx: typer.Context) -> None:
    """Show the active profile and connection status."""
    actx: AppContext = ctx.obj
    out = actx.output

    active = resolve_active_profile_name(actx.profile)
    svc = get_service_config(active)

    out.kv("Active profile", active)
    out.kv("Default profile", get_default_profile())
    out.kv("URL", svc.url or "[dim]not set[/dim]")
    out.kv("Login", svc.login or "[dim]not set[/dim]")
    out.kv("Password", _mask(svc.password))

    if svc.url:
        ok, info = _test_connection(svc.url, svc.login, svc.password)
        if ok:
            out.success(f"Connection OK — {info}")
        else:
            out.error(f"Connection failed: {info}")
    else:
        out.warn(f"No {SERVICE_KEY} config in active profile. Run: kctl-dbgate config init")


# ----------------------------------------------------------------------
# Server-side settings (POST /config/*)
# ----------------------------------------------------------------------


@app.command("server-show")
def server_show(ctx: typer.Context) -> None:
    """Show DBGate's server-side configuration (POST /config/get)."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        cfg = actx.client.call("/config/get")
    except KctlError as e:
        out.error(str(e))
        raise typer.Exit(1) from e

    if not isinstance(cfg, dict):
        out.error(f"Unexpected response: {cfg!r}")
        raise typer.Exit(1)

    rows = [[str(k), str(v)] for k, v in sorted(cfg.items())]
    out.table(
        title="DBGate server configuration",
        columns=[("Key", "cyan"), ("Value", "")],
        rows=rows,
        data_for_json=[cfg],
    )


@app.command("server-set")
def server_set(
    ctx: typer.Context,
    key: Annotated[str, typer.Option("--key", help="Setting key")],
    value: Annotated[str, typer.Option("--value", help="Setting value")],
) -> None:
    """Update a single server-side setting (POST /config/update-settings)."""
    actx: AppContext = ctx.obj
    out = actx.output
    payload: dict[str, Any] = {key: value}
    try:
        actx.client.call("/config/update-settings", payload)
    except KctlError as e:
        out.error(str(e))
        raise typer.Exit(1) from e
    out.success(f"Setting {key} updated")


@app.command("server-changelog")
def server_changelog(ctx: typer.Context) -> None:
    """Show DBGate server changelog (POST /config/changelog)."""
    actx: AppContext = ctx.obj
    out = actx.output
    try:
        result = actx.client.call("/config/changelog")
    except KctlError as e:
        out.error(str(e))
        raise typer.Exit(1) from e
    if isinstance(result, str):
        out.text(result)
    else:
        out.text(str(result))


@app.command("server-export")
def server_export(
    ctx: typer.Context,
    outfile: Annotated[Path, typer.Argument(help="Path to write YAML dump to")],
) -> None:
    """Dump the server's /config/get response to a YAML file.

    NOTE: DBGate exposes no true export endpoint, so this dumps the
    read-only config snapshot. Use `server-import` with a file from
    `import-connections-and-settings` producer if available.
    """
    actx: AppContext = ctx.obj
    out = actx.output
    try:
        cfg = actx.client.call("/config/get")
    except KctlError as e:
        out.error(str(e))
        raise typer.Exit(1) from e
    outfile.write_text(yaml.safe_dump(cfg, sort_keys=True))
    out.success(f"Server config exported to {outfile}")


@app.command("server-import")
def server_import(
    ctx: typer.Context,
    infile: Annotated[Path, typer.Argument(help="YAML file to import")],
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Don't send; just show what would be sent")] = False,
) -> None:
    """Import connections + settings from a YAML file.

    Calls POST /config/import-connections-and-settings.
    """
    actx: AppContext = ctx.obj
    out = actx.output

    if not infile.exists():
        out.error(f"File not found: {infile}")
        raise typer.Exit(1)

    payload = yaml.safe_load(infile.read_text()) or {}

    if dry_run:
        out.header("Dry-run payload")
        out.text(yaml.safe_dump(payload, sort_keys=True))
        out.info("No API call made (--dry-run)")
        return

    try:
        actx.client.call("/config/import-connections-and-settings", payload)
    except KctlError as e:
        out.error(str(e))
        raise typer.Exit(1) from e
    out.success(f"Imported from {infile}")
