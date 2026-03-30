"""Configuration management commands.

Initialize, view, and manage CLI profiles and connection settings.
Uses service-scoped config: each profile contains per-service sections.
"""

from __future__ import annotations

import os
from typing import Annotated

import typer

from kctl_pg.core.callbacks import AppContext
from kctl_pg.core.client import PostgresClient
from kctl_pg.core.config import (
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
from kctl_pg.core.exceptions import KctlError

app = typer.Typer(help="Manage CLI configuration and profiles.")


def _mask_secret(secret: str) -> str:
    if not secret:
        return "[dim]not set[/dim]"
    if len(secret) <= 10:
        return "****"
    return f"{secret[:4]}{'*' * (len(secret) - 8)}{secret[-4:]}"


def _test_connection(config: ServiceConfig) -> tuple[bool, str]:
    """Test PostgreSQL connection through SSH tunnel."""
    try:
        with PostgresClient(config=config) as client:
            return True, client.short_version
    except Exception as e:
        return False, str(e)


@app.command()
def init(
    ctx: typer.Context,
    host: Annotated[str | None, typer.Option("--host", help="PostgreSQL host (private IP).")] = None,
    port: Annotated[int, typer.Option("--port", help="PostgreSQL port.")] = 5432,
    user: Annotated[str | None, typer.Option("--user", "-U", help="PostgreSQL user.")] = None,
    password: Annotated[str | None, typer.Option("--password", help="PostgreSQL password.")] = None,
    ssh_host: Annotated[str | None, typer.Option("--ssh-host", help="SSH host (public IP).")] = None,
    ssh_port: Annotated[int, typer.Option("--ssh-port", help="SSH port.")] = 22,
    ssh_user: Annotated[str, typer.Option("--ssh-user", help="SSH username.")] = "root",
    ssh_key: Annotated[str, typer.Option("--ssh-key", help="SSH private key path.")] = "~/.ssh/id_ed25519",
    name: Annotated[str | None, typer.Option("--name", "-n", help="Profile name.")] = None,
) -> None:
    """Initialize CLI configuration (interactive if no flags given)."""
    actx: AppContext = ctx.obj
    out = actx.output

    profile_name = name or typer.prompt("Profile name", default="default")
    pg_host = host or typer.prompt("PostgreSQL host (private IP)")
    pg_user = user or typer.prompt("PostgreSQL user", default="postgres")
    pg_password = password or typer.prompt("PostgreSQL password", hide_input=True)
    pg_ssh_host = ssh_host or typer.prompt("SSH host (public IP)")

    svc = ServiceConfig(
        host=pg_host,
        port=port,
        user=pg_user,
        password=pg_password,
        ssh_host=pg_ssh_host,
        ssh_port=ssh_port,
        ssh_user=ssh_user,
        ssh_key=ssh_key,
    )

    out.info(f"Testing connection via SSH tunnel to {pg_ssh_host}...")
    ok, version = _test_connection(svc)
    if ok:
        out.success(f"Connected to PostgreSQL {version}")
    else:
        out.error(f"Connection failed: {version}")
        if not typer.confirm("Save configuration anyway?", default=False):
            raise typer.Exit(code=1)

    set_service_config(profile_name, svc)

    if len(get_profile_names()) <= 1:
        set_default_profile(profile_name)

    out.success(f"Configuration saved to {CONFIG_FILE}")
    out.kv("Profile", profile_name)
    out.kv("Service", SERVICE_KEY)
    out.kv("Host", f"{pg_host}:{port}")
    out.kv("SSH", f"{ssh_user}@{pg_ssh_host}:{ssh_port}")
    out.kv("User", pg_user)
    out.kv("Password", _mask_secret(pg_password))


@app.command()
def add(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name (e.g. abcfood, staging)")],
    host: Annotated[str | None, typer.Option("--host", help="PostgreSQL host.")] = None,
    port: Annotated[int, typer.Option("--port", help="PostgreSQL port.")] = 5432,
    user: Annotated[str | None, typer.Option("--user", "-U", help="PostgreSQL user.")] = None,
    password: Annotated[str | None, typer.Option("--password", help="PostgreSQL password.")] = None,
    ssh_host: Annotated[str | None, typer.Option("--ssh-host", help="SSH host.")] = None,
    ssh_port: Annotated[int, typer.Option("--ssh-port", help="SSH port.")] = 22,
    ssh_user: Annotated[str, typer.Option("--ssh-user", help="SSH username.")] = "root",
    ssh_key: Annotated[str, typer.Option("--ssh-key", help="SSH private key path.")] = "~/.ssh/id_ed25519",
    databases: Annotated[str | None, typer.Option("--databases", help="Comma-separated database list.")] = None,
    set_default: Annotated[bool, typer.Option("--default", help="Set as default profile.")] = False,
) -> None:
    """Add or update a profile's PostgreSQL connection.

    Example: kctl-pg config add abcfood --host 10.0.0.3 --ssh-host 1.2.3.4 --password $PG_PASS
    """
    actx: AppContext = ctx.obj
    out = actx.output

    pg_host = host or typer.prompt("PostgreSQL host")
    pg_user = user or typer.prompt("PostgreSQL user", default="postgres")
    pg_password = password or typer.prompt("PostgreSQL password", hide_input=True)
    pg_ssh_host = ssh_host or typer.prompt("SSH host")

    existing = get_service_config(name)
    if existing.host:
        if not typer.confirm(f"Profile '{name}' already has {SERVICE_KEY} config ({existing.host}). Overwrite?"):
            raise typer.Exit(0)

    db_list = [d.strip() for d in databases.split(",")] if databases else []

    svc = ServiceConfig(
        host=pg_host,
        port=port,
        user=pg_user,
        password=pg_password,
        ssh_host=pg_ssh_host,
        ssh_port=ssh_port,
        ssh_user=ssh_user,
        ssh_key=ssh_key,
        databases=db_list,
    )

    out.info(f"Testing connection via SSH tunnel to {pg_ssh_host}...")
    ok, version = _test_connection(svc)
    if ok:
        out.success(f"Connected to PostgreSQL {version}")
    else:
        out.error(f"Connection failed: {version}")
        if not typer.confirm("Save anyway?", default=False):
            raise typer.Exit(code=1)

    set_service_config(name, svc)

    if set_default or len(get_profile_names()) == 1:
        set_default_profile(name)

    out.success(f"Profile '{name}' -> {SERVICE_KEY} configured")
    out.kv("Host", f"{pg_host}:{port}")
    out.kv("SSH", f"{ssh_user}@{pg_ssh_host}:{ssh_port}")
    if db_list:
        out.kv("Databases", ", ".join(db_list))
    if get_default_profile() == name:
        out.info("Set as default profile")


@app.command()
def use(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name to switch to")],
) -> None:
    """Switch the default profile.

    Example: kctl-pg config use abcfood
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
    if svc.host:
        ok, version = _test_connection(svc)
        if ok:
            out.success(f"Switched to '{name}' ({svc.host}:{svc.port}) -- PostgreSQL {version}")
        else:
            out.warn(f"Switched to '{name}' ({svc.host}:{svc.port}) -- connection failed: {version}")
    else:
        out.warn(f"Switched to '{name}' -- no {SERVICE_KEY} config in this profile")

    out.info(f"Previous default: {old_default}")


@app.command("remove")
def remove_(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name to remove")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
    service_only: Annotated[
        bool, typer.Option("--service-only", help="Only remove postgres config, keep other services")
    ] = False,
) -> None:
    """Remove a profile or just its PostgreSQL config."""
    actx: AppContext = ctx.obj
    out = actx.output

    profiles = get_profile_names()
    if name not in profiles:
        out.error(f"Profile '{name}' not found")
        raise typer.Exit(1)

    if service_only:
        if not force:
            svc = get_service_config(name)
            if not typer.confirm(f"Remove {SERVICE_KEY} config from '{name}' ({svc.host})?"):
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
    """Show full configuration (passwords masked)."""
    actx: AppContext = ctx.obj
    out = actx.output

    default = get_default_profile()
    all_profiles = get_profile_names()

    if out.json_mode:
        data = load_raw_config()
        for _pname, pdata in data.get("profiles", {}).items():
            for _svc, svc_data in pdata.items():
                if isinstance(svc_data, dict) and "password" in svc_data:
                    svc_data["password"] = _mask_secret(svc_data["password"])
            if "password" in pdata:
                pdata["password"] = _mask_secret(pdata["password"])
        out.raw_json(data)
        return

    sections: list[tuple[str, list[tuple[str, str]]]] = []

    sections.append(
        (
            "General",
            [
                ("Config file", str(CONFIG_FILE)),
                ("Default profile", default),
                ("Total profiles", str(len(all_profiles))),
                ("This CLI", f"kctl-pg -> service key: {SERVICE_KEY}"),
            ],
        )
    )

    for pname in all_profiles:
        marker = " [green](default)[/green]" if pname == default else ""
        services = get_all_services_in_profile(pname)

        kvs: list[tuple[str, str]] = []
        for svc_name, svc_data in services.items():
            if not isinstance(svc_data, dict):
                continue
            if svc_name == SERVICE_KEY:
                indicator = "[green]●[/green]"
                svc_host = svc_data.get("host", "")
                svc_port = svc_data.get("port", 5432)
                svc_ssh = svc_data.get("ssh_host", "")
                svc_pass = _mask_secret(svc_data.get("password", ""))
                kvs.append((f"{indicator} {svc_name}", f"{svc_host}:{svc_port}  via {svc_ssh}  pass: {svc_pass}"))
                if svc_data.get("databases"):
                    kvs.append(("  databases", ", ".join(svc_data["databases"])))
            else:
                indicator = "[dim]o[/dim]"
                svc_url = svc_data.get("url", svc_data.get("host", ""))
                kvs.append((f"{indicator} {svc_name}", svc_url))

        if not kvs:
            kvs.append(("(empty)", "no services configured"))

        sections.append((f"Profile: {pname}{marker}", kvs))

    out.detail("Configuration", sections)


@app.command("set")
def set_(
    ctx: typer.Context,
    key: Annotated[str, typer.Argument(help="Config key (e.g. host, port, user, password, ssh_host)")],
    value: Annotated[str, typer.Argument(help="Value to set")],
    profile_arg: Annotated[str | None, typer.Option("--profile-name", help="Target profile (default: active)")] = None,
) -> None:
    """Set a configuration value for the current service.

    Examples:
      kctl-pg config set host 10.0.0.3
      kctl-pg config set password new-password
      kctl-pg config set ssh_host 49.13.14.79
      kctl-pg config set default_profile abcfood
    """
    actx: AppContext = ctx.obj
    out = actx.output

    if key == "default_profile":
        set_default_profile(value)
        out.success(f"Default profile set to: {value}")
        return

    pname = profile_arg or resolve_active_profile_name(actx.profile)
    svc = get_service_config(pname)

    valid_fields = {"host", "port", "user", "password", "ssh_host", "ssh_port", "ssh_user", "ssh_key"}
    if key not in valid_fields:
        out.error(f"Unknown key: {key}")
        out.info(f"Valid keys: {', '.join(sorted(valid_fields))}, default_profile")
        raise typer.Exit(1)

    # Convert int fields
    if key in ("port", "ssh_port"):
        setattr(svc, key, int(value))
    else:
        setattr(svc, key, value)
    set_service_config(pname, svc)

    display = _mask_secret(value) if "password" in key else value
    out.success(f"[{pname}] {SERVICE_KEY}.{key} = {display}")


@app.command()
def profiles(ctx: typer.Context) -> None:
    """List all profiles with PostgreSQL connection status."""
    actx: AppContext = ctx.obj
    out = actx.output

    profile_names = get_profile_names()
    if not profile_names:
        out.warn("No profiles configured. Run: kctl-pg config init")
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
        if svc.host:
            ok, version = _test_connection(svc)
            conn_status = f"[green]{version}[/green]" if ok else "[red]offline[/red]"
        else:
            conn_status = "[dim]no postgres config[/dim]"

        other_str = ", ".join(other_services) if other_services else "[dim]-[/dim]"

        rows.append(
            [
                pname,
                f"{svc.host}:{svc.port}" if svc.host else "-",
                svc.ssh_host or "-",
                conn_status,
                other_str,
                status_marker,
            ]
        )
        json_data.append(
            {
                "name": pname,
                "host": svc.host,
                "port": svc.port,
                "ssh_host": svc.ssh_host,
                "connected": ok,
                "version": version if ok else None,
                "other_services": other_services,
                "active": is_active,
                "default": pname == default,
            }
        )

    out.table(
        "Profiles",
        [("Name", "cyan"), ("PG Host", ""), ("SSH Host", ""), ("Status", ""), ("Other Services", "dim"), ("", "green")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def current(ctx: typer.Context) -> None:
    """Show the active profile and connection status."""
    actx: AppContext = ctx.obj
    out = actx.output

    active = resolve_active_profile_name(actx.profile)
    resolved = resolve_connection(
        profile_name=actx.profile,
        host_override=actx.host_override,
        port_override=actx.port_override,
        user_override=actx.user_override,
        password_override=actx.password_override,
    )

    ok, version = _test_connection(resolved) if resolved.host else (False, "not configured")

    source = "config default"
    if actx.profile:
        source = "--profile flag"
    elif os.environ.get("KCTL_PG_PROFILE"):
        source = "KCTL_PG_PROFILE env var"

    sections: list[tuple[str, list[tuple[str, str]]]] = [
        (
            "Active Connection",
            [
                ("Profile", active),
                ("Service", SERVICE_KEY),
                ("Source", source),
                ("Host", f"{resolved.host}:{resolved.port}" if resolved.host else "[red]not set[/red]"),
                ("User", resolved.user),
                ("Password", _mask_secret(resolved.password)),
                (
                    "SSH",
                    f"{resolved.ssh_user}@{resolved.ssh_host}:{resolved.ssh_port}"
                    if resolved.ssh_host
                    else "[red]not set[/red]",
                ),
                ("SSH Key", resolved.ssh_key),
                ("Status", f"[green]Connected -- PostgreSQL {version}[/green]" if ok else f"[red]{version}[/red]"),
            ],
        ),
    ]

    if resolved.databases:
        sections.append(("Configured Databases", [(db, "") for db in resolved.databases]))

    # Other services in this profile
    all_services = get_all_services_in_profile(active)
    other = {k: v for k, v in all_services.items() if k != SERVICE_KEY and isinstance(v, dict)}
    if other:
        sections.append(
            (
                "Other Services in Profile",
                [(svc_name, v.get("url", v.get("host", "(no url)"))) for svc_name, v in other.items()],
            )
        )

    # Other profiles
    all_profile_names = [p for p in get_profile_names() if p != active]
    if all_profile_names:
        sections.append(
            ("Other Profiles", [(p, f"{get_service_config(p).host or '(no postgres)'}") for p in all_profile_names])
        )

    out.detail(
        "Current Profile",
        sections,
        data_for_json={
            "profile": active,
            "service": SERVICE_KEY,
            "source": source,
            "host": resolved.host,
            "port": resolved.port,
            "ssh_host": resolved.ssh_host,
            "user": resolved.user,
            "connected": ok,
            "version": version if ok else None,
            "databases": resolved.databases,
        },
    )


@app.command()
def test(ctx: typer.Context) -> None:
    """Test PostgreSQL connection with current configuration."""
    actx: AppContext = ctx.obj
    out = actx.output

    active = resolve_active_profile_name(actx.profile)
    out.info(f"Testing profile '{active}' -> {SERVICE_KEY}")

    try:
        c = actx.client
        version = c.short_version
        full_version = c.server_version
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
                    ("Version", version),
                    ("Full Version", full_version),
                ],
            )
        ],
        data_for_json={"version": version, "full_version": full_version, "connected": True},
    )
