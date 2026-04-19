"""Configuration management commands.

Initialize, view, and manage CLI profiles and connection settings.
Uses service-scoped config: each profile contains per-service sections.
"""

from __future__ import annotations

import os
from typing import Annotated

import typer

from kctl_lib.output import mask_secret_fields
from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.client import OdooClient
from kctl_odoo.core.config import (
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
from kctl_odoo.core.exceptions import KctlError

app = typer.Typer(help="Manage CLI configuration and profiles.")

# Register deployment profiles as a sub-group: kctl-odoo config profiles
from kctl_odoo.commands.profiles import app as _profiles_app  # noqa: E402

app.add_typer(_profiles_app, name="profiles")


def _mask_key(key: str) -> str:
    if not key:
        return "[dim]not set[/dim]"
    if len(key) <= 10:
        return "****"
    return f"{key[:4]}{'*' * (len(key) - 8)}{key[-4:]}"


def _test_connection(url: str, database: str, username: str, api_key: str) -> tuple[bool, str]:
    try:
        client = OdooClient(base_url=url, database=database, username=username, api_key=api_key)
        info = client.version_info()
        # Also test authentication
        client.authenticate()
        client.close()
        return True, info.get("server_version", "unknown")
    except Exception as e:
        return False, str(e)


@app.command()
def init(
    ctx: typer.Context,
    url: Annotated[str | None, typer.Option("--url", help="Odoo base URL.")] = None,
    database: Annotated[str | None, typer.Option("--database", "-d", help="Database name.")] = None,
    username: Annotated[str | None, typer.Option("--username", "-u", help="Username.")] = None,
    api_key: Annotated[str | None, typer.Option("--api-key", help="API key.")] = None,
    name: Annotated[str | None, typer.Option("--name", "-n", help="Profile name.")] = None,
) -> None:
    """Initialize CLI configuration (interactive if no flags given)."""
    actx: AppContext = ctx.obj
    out = actx.output

    profile_name = name or typer.prompt("Profile name", default="default")
    api_url = url or typer.prompt("Odoo URL (e.g. https://erp.kodeme.io)")
    db_name = database or typer.prompt("Database name")
    user = username or typer.prompt("Username", default="admin")
    key = api_key or typer.prompt("API key", hide_input=True)

    out.info(f"Testing connection to {api_url}...")
    ok, version = _test_connection(api_url, db_name, user, key)
    if ok:
        out.success(f"Connected to Odoo {version}")
    else:
        out.error(f"Connection failed: {version}")
        if not typer.confirm("Save configuration anyway?", default=False):
            raise typer.Exit(code=1)

    svc = ServiceConfig(url=api_url, database=db_name, username=user, api_key=key)
    set_service_config(profile_name, svc)

    if len(get_profile_names()) <= 1:
        set_default_profile(profile_name)

    out.success(f"Configuration saved to {CONFIG_FILE}")
    out.kv("Profile", profile_name)
    out.kv("Service", SERVICE_KEY)
    out.kv("URL", api_url)
    out.kv("Database", db_name)
    out.kv("Username", user)
    out.kv("API Key", _mask_key(key))


@app.command()
def quick(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name")],
    url: Annotated[str, typer.Argument(help="Odoo URL")],
    database: Annotated[str, typer.Argument(help="Database name")],
    api_key: Annotated[str, typer.Argument(help="API key")],
    username: Annotated[str, typer.Option("--username", "-u", help="Username")] = "admin",
    set_default: Annotated[bool, typer.Option("--default", help="Set as default profile")] = False,
) -> None:
    """Create a profile in one line (no prompts).

    Examples:
        kctl-odoo config quick local http://localhost:8069 odoo_full admin
        kctl-odoo config quick prod https://erp.kodeme.io kodemeio $KEY --default
    """
    actx: AppContext = ctx.obj
    out = actx.output

    out.info(f"Testing connection to {url}...")
    ok, version = _test_connection(url, database, username, api_key)
    if ok:
        out.success(f"Connected to Odoo {version}")
    else:
        out.warn(f"Connection failed: {version} (saving anyway)")

    svc = ServiceConfig(url=url, database=database, username=username, api_key=api_key)
    set_service_config(name, svc)

    if set_default or len(get_profile_names()) == 1:
        set_default_profile(name)

    out.success(f"Profile '{name}' created")
    out.kv("URL", url)
    out.kv("Database", database)
    out.kv("API Key", _mask_key(api_key))


@app.command()
def add(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name (e.g. abcfood, staging)")],
    url: Annotated[str | None, typer.Option("--url", help="Odoo base URL.")] = None,
    database: Annotated[str | None, typer.Option("--database", "-d", help="Database name.")] = None,
    username: Annotated[str | None, typer.Option("--username", "-u", help="Username.")] = None,
    api_key: Annotated[str | None, typer.Option("--api-key", help="API key.")] = None,
    set_default: Annotated[bool, typer.Option("--default", help="Set as default profile.")] = False,
) -> None:
    """Add or update a profile's Odoo connection.

    Example: kctl-odoo config add abcfood --url https://odoo-erp.abcfood.app --database abcfood --api-key $KEY

    This writes to the 'odoo' section within the profile, so other
    kctl-* tools (kctl-ak, kctl-mailcow) can coexist in the same profile.
    """
    actx: AppContext = ctx.obj
    out = actx.output

    api_url = url or typer.prompt("Odoo URL")
    db_name = database or typer.prompt("Database name")
    user = username or typer.prompt("Username", default="admin")
    key = api_key or typer.prompt("API key", hide_input=True)

    out.info(f"Testing connection to {api_url}...")
    ok, version = _test_connection(api_url, db_name, user, key)
    if ok:
        out.success(f"Connected to Odoo {version}")
    else:
        out.error(f"Connection failed: {version}")
        if not typer.confirm("Save anyway?", default=False):
            raise typer.Exit(code=1)

    existing = get_service_config(name)
    if existing.url and not typer.confirm(
        f"Profile '{name}' already has {SERVICE_KEY} config ({existing.url}). Overwrite?"
    ):
        raise typer.Exit(0)

    svc = ServiceConfig(url=api_url, database=db_name, username=user, api_key=key)
    set_service_config(name, svc)

    if set_default or len(get_profile_names()) == 1:
        set_default_profile(name)

    out.success(f"Profile '{name}' -> {SERVICE_KEY} configured")
    out.kv("URL", api_url)
    out.kv("Database", db_name)
    out.kv("Username", user)
    out.kv("API Key", _mask_key(key))
    if get_default_profile() == name:
        out.info("Set as default profile")


@app.command()
def use(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name to switch to")],
) -> None:
    """Switch the default profile.

    Example: kctl-odoo config use abcfood
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
        ok, version = _test_connection(svc.url, svc.database, svc.username, svc.api_key)
        if ok:
            out.success(f"Switched to '{name}' ({svc.url}/{svc.database}) — Odoo {version}")
        else:
            out.warn(f"Switched to '{name}' ({svc.url}/{svc.database}) — connection failed: {version}")
    else:
        out.warn(f"Switched to '{name}' — no {SERVICE_KEY} config in this profile")

    out.info(f"Previous default: {old_default}")


@app.command()
def remove(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name to remove")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
    service_only: Annotated[
        bool, typer.Option("--service-only", help="Only remove odoo config, keep other services")
    ] = False,
) -> None:
    """Remove a profile or just its Odoo config."""
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
def show(
    ctx: typer.Context,
    reveal: Annotated[bool, typer.Option("--reveal", help="Show secrets in plaintext (default: masked).")] = False,
) -> None:
    """Show full configuration (API keys masked by default; use --reveal to see plaintext)."""
    actx: AppContext = ctx.obj
    out = actx.output

    default = get_default_profile()
    profiles = get_profile_names()

    if out.json_mode:
        data = load_raw_config()
        if not reveal:
            for _pname, pdata in data.get("profiles", {}).items():
                for _svc, svc_data in pdata.items():
                    if isinstance(svc_data, dict):
                        masked = mask_secret_fields(svc_data)
                        svc_data.update(masked)
                masked_top = mask_secret_fields({k: v for k, v in pdata.items() if not isinstance(v, dict)})
                pdata.update(masked_top)
        out.raw_json(data)
        return

    def _display_key(raw_key: str) -> str:
        if reveal:
            return raw_key
        return _mask_key(raw_key)

    sections: list[tuple[str, list[tuple[str, str]]]] = []

    sections.append(
        (
            "General",
            [
                ("Config file", str(CONFIG_FILE)),
                ("Default profile", default),
                ("Total profiles", str(len(profiles))),
                ("This CLI", f"kctl-odoo -> service key: {SERVICE_KEY}"),
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
            indicator = "[green]●[/green]" if svc_name == SERVICE_KEY else "[dim]○[/dim]"
            extra = ""
            if svc_name == SERVICE_KEY:
                db = svc_data.get("database", "")
                key = _display_key(svc_data.get("api_key", ""))
                extra = f"  db: {db}  key: {key}"
            else:
                key = _display_key(svc_data.get("token", "") or svc_data.get("api_key", ""))
                extra = f"  key: {key}"
            kvs.append((f"{indicator} {svc_name}", f"{svc_url}{extra}"))

        if not kvs:
            kvs.append(("(empty)", "no services configured"))

        sections.append((f"Profile: {pname}{marker}", kvs))

    out.detail("Configuration", sections)


@app.command("set")
def set_(
    ctx: typer.Context,
    key: Annotated[str, typer.Argument(help="Config key (e.g. url, database, username, api_key, or default_profile)")],
    value: Annotated[str, typer.Argument(help="Value to set")],
    profile_arg: Annotated[str | None, typer.Option("--profile-name", help="Target profile (default: active)")] = None,
) -> None:
    """Set a configuration value for the current service.

    Examples:
      kctl-odoo config set url https://erp.new.io
      kctl-odoo config set database mydb
      kctl-odoo config set api_key new-key-value
      kctl-odoo config set default_profile abcfood
    """
    actx: AppContext = ctx.obj
    out = actx.output

    if key == "default_profile":
        set_default_profile(value)
        out.success(f"Default profile set to: {value}")
        return

    pname = profile_arg or resolve_active_profile_name(actx.profile)
    svc = get_service_config(pname)

    valid_fields = {"url", "database", "username", "api_key", "project_root"}
    if key not in valid_fields:
        out.error(f"Unknown key: {key}")
        out.info(f"Valid keys: {', '.join(sorted(valid_fields))}, default_profile")
        raise typer.Exit(1)

    setattr(svc, key, value)
    set_service_config(pname, svc)

    display = _mask_key(value) if "key" in key else value
    out.success(f"[{pname}] {SERVICE_KEY}.{key} = {display}")


@app.command("list")
def profiles(ctx: typer.Context) -> None:
    """List all profiles with Odoo connection status."""
    actx: AppContext = ctx.obj
    out = actx.output

    profile_names = get_profile_names()
    if not profile_names:
        out.warn("No profiles configured. Run: kctl-odoo config init")
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
            ok, version = _test_connection(svc.url, svc.database, svc.username, svc.api_key)
            conn_status = f"[green]{version}[/green]" if ok else "[red]offline[/red]"
        else:
            conn_status = "[dim]no odoo config[/dim]"

        other_str = ", ".join(other_services) if other_services else "[dim]-[/dim]"

        rows.append([pname, svc.url or "-", svc.database or "-", conn_status, other_str, status_marker])
        json_data.append(
            {
                "name": pname,
                "odoo_url": svc.url,
                "database": svc.database,
                "connected": bool(svc.url) and ok,
                "version": version if svc.url and ok else None,
                "other_services": other_services,
                "active": is_active,
                "default": pname == default,
            }
        )

    out.table(
        "Profiles",
        [
            ("Name", "cyan"),
            ("Odoo URL", ""),
            ("Database", ""),
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
    get_service_config(active)

    resolved_url, resolved_db, resolved_user, resolved_key = resolve_connection(
        profile_name=actx.profile,
        url_override=actx.url_override,
        api_key_override=actx.api_key_override,
        database_override=actx.database_override,
        username_override=actx.username_override,
    )

    ok, version = (
        _test_connection(resolved_url, resolved_db, resolved_user, resolved_key)
        if resolved_url
        else (False, "not configured")
    )

    source = "config default"
    if actx.profile:
        source = "--profile flag"
    elif os.environ.get("KCTL_ODOO_PROFILE"):
        source = "KCTL_ODOO_PROFILE env var"

    sections: list[tuple[str, list[tuple[str, str]]]] = [
        (
            "Active Connection",
            [
                ("Profile", active),
                ("Service", SERVICE_KEY),
                ("Source", source),
                ("URL", resolved_url or "[red]not set[/red]"),
                ("Database", resolved_db or "[red]not set[/red]"),
                ("Username", resolved_user),
                ("API Key", _mask_key(resolved_key)),
                ("Status", f"[green]Connected — Odoo {version}[/green]" if ok else f"[red]{version}[/red]"),
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
        sections.append(("Other Profiles", [(p, get_service_config(p).url or "(no odoo)") for p in all_profiles]))

    out.detail(
        "Current Profile",
        sections,
        data_for_json={
            "profile": active,
            "service": SERVICE_KEY,
            "source": source,
            "url": resolved_url,
            "database": resolved_db,
            "username": resolved_user,
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
    out.info(f"Testing profile '{active}' -> {SERVICE_KEY}")

    try:
        c = actx.client
        info = c.version_info()
        uid = c.authenticate()
    except KctlError as e:
        out.error(f"Connection failed: {e}")
        raise typer.Exit(code=1) from e

    out.detail(
        "Connection Test",
        [
            (
                "Result",
                [
                    ("Profile", active),
                    ("Service", SERVICE_KEY),
                    ("Status", "[green]Connected[/green]"),
                    ("Version", info.get("server_version", "unknown")),
                    ("Protocol", info.get("protocol_version", "unknown")),
                    ("UID", str(uid)),
                    ("Database", c.database),
                ],
            )
        ],
        data_for_json={**info, "uid": uid, "database": c.database},
    )


@app.command()
def migrate(ctx: typer.Context) -> None:
    """Migrate config from flat format to service-scoped format.

    Old:  profiles.production.url -> profiles.production.odoo.url
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


@app.command()
def doctor(ctx: typer.Context) -> None:
    """Diagnose all configured profiles.

    For each profile with Odoo config:
    - Test HTTP connectivity (HEAD request, 5s timeout)
    - Test authentication (JSON-RPC authenticate)
    - Show version and latency
    - Flag issues

    Examples:
        kctl-odoo config doctor
        kctl-odoo config doctor --json
    """
    import time

    actx: AppContext = ctx.obj
    out = actx.output

    profile_names = get_profile_names()
    if not profile_names:
        out.warn("No profiles configured. Run: kctl-odoo config init")
        return

    rows: list[list[str]] = []
    json_data: list[dict] = []

    for pname in profile_names:
        svc = get_service_config(pname)
        if not svc.url:
            rows.append([pname, "[dim]no config[/dim]", "-", "-", "No Odoo URL configured"])
            json_data.append(
                {
                    "profile": pname,
                    "status": "no_config",
                    "version": None,
                    "latency_ms": None,
                    "issues": ["No Odoo URL configured"],
                }
            )
            continue

        issues: list[str] = []
        version = "-"
        latency_str = "-"
        status_label = "[red]FAIL[/red]"

        try:
            start = time.monotonic()
            client = OdooClient(
                base_url=svc.url,
                database=svc.database,
                username=svc.username,
                api_key=svc.api_key,
            )

            # Test version endpoint (HTTP connectivity)
            ver_info = client.version_info()
            version = ver_info.get("server_version", "unknown")

            # Test authentication
            client.authenticate()
            elapsed_ms = round((time.monotonic() - start) * 1000)
            latency_str = f"{elapsed_ms}ms"

            if elapsed_ms > 5000:
                issues.append("High latency (>5s)")
                latency_color = "red"
            elif elapsed_ms > 2000:
                issues.append("Moderate latency (>2s)")
                latency_color = "yellow"
            else:
                latency_color = "green"
            latency_str = f"[{latency_color}]{elapsed_ms}ms[/{latency_color}]"

            if not svc.url.startswith("https://") and "localhost" not in svc.url:
                issues.append("Not using HTTPS")

            client.close()
            status_label = "[green]OK[/green]" if not issues else "[yellow]WARN[/yellow]"

            json_data.append(
                {
                    "profile": pname,
                    "status": "ok" if not issues else "warn",
                    "version": version,
                    "latency_ms": elapsed_ms,
                    "issues": issues,
                }
            )

        except Exception as e:
            error_msg = str(e)[:80]
            issues.append(error_msg)
            json_data.append(
                {
                    "profile": pname,
                    "status": "fail",
                    "version": None,
                    "latency_ms": None,
                    "issues": issues,
                }
            )

        issues_str = "; ".join(issues) if issues else ""
        rows.append([pname, status_label, version, latency_str, issues_str])

    out.table(
        f"Config Doctor ({len(profile_names)} profiles)",
        [("Profile", "cyan"), ("Status", ""), ("Version", ""), ("Latency", ""), ("Issues", "dim")],
        rows,
        data_for_json=json_data,
    )
