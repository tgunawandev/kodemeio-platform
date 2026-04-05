"""Config profile management commands for kctl-redis."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_redis.core.callbacks import AppContext
from kctl_redis.core.config import (
    ServiceConfig,
    get_profile_names,
    get_service_config,
    remove_profile,
    resolve_active_profile_name,
    set_default_profile,
    set_service_config,
)
from kctl_redis.core.exceptions import KctlError

app = typer.Typer(help="Manage kctl-redis configuration profiles.", no_args_is_help=True)


@app.command()
def init(
    ctx: typer.Context,
    profile: Annotated[str, typer.Option("--profile", "-p", help="Profile name")] = "production",
    host: Annotated[str | None, typer.Option(help="Redis host (private IP)")] = None,
    port: Annotated[int, typer.Option(help="Redis port")] = 6379,
    username: Annotated[str, typer.Option(help="Redis username")] = "default",
    password: Annotated[str | None, typer.Option(help="Redis password")] = None,
    db: Annotated[int, typer.Option(help="Redis database number")] = 0,
    ssh_host: Annotated[str | None, typer.Option(help="SSH jump host")] = None,
    ssh_port: Annotated[int, typer.Option(help="SSH port")] = 22,
    ssh_user: Annotated[str, typer.Option(help="SSH username")] = "root",
    ssh_key: Annotated[str, typer.Option(help="SSH private key path")] = "~/.ssh/id_ed25519",
) -> None:
    """Initialize kctl-redis configuration."""
    app_ctx: AppContext = ctx.obj
    out = app_ctx.output

    if not host:
        host = typer.prompt("Redis host (private IP)")
    if not password:
        password = typer.prompt("Redis password", hide_input=True)
    if not ssh_host:
        ssh_host = typer.prompt("SSH jump host (public IP)")

    svc = ServiceConfig(
        host=host,
        port=port,
        username=username,
        password=password,
        db=db,
        ssh_host=ssh_host,
        ssh_port=ssh_port,
        ssh_user=ssh_user,
        ssh_key=ssh_key,
    )
    set_service_config(profile, svc)
    set_default_profile(profile)
    out.success(f"Profile '{profile}' created and set as default.")


@app.command()
def add(
    ctx: typer.Context,
    profile: Annotated[str, typer.Argument(help="Profile name")],
    host: Annotated[str, typer.Option(help="Redis host")] = "",
    port: Annotated[int, typer.Option(help="Redis port")] = 6379,
    username: Annotated[str, typer.Option(help="Redis username")] = "default",
    password: Annotated[str, typer.Option(help="Redis password")] = "",
    db: Annotated[int, typer.Option(help="Redis database number")] = 0,
    ssh_host: Annotated[str, typer.Option(help="SSH jump host")] = "",
    ssh_port: Annotated[int, typer.Option(help="SSH port")] = 22,
    ssh_user: Annotated[str, typer.Option(help="SSH username")] = "root",
    ssh_key: Annotated[str, typer.Option(help="SSH key path")] = "~/.ssh/id_ed25519",
) -> None:
    """Add or update a profile."""
    app_ctx: AppContext = ctx.obj
    out = app_ctx.output
    svc = ServiceConfig(
        host=host,
        port=port,
        username=username,
        password=password,
        db=db,
        ssh_host=ssh_host,
        ssh_port=ssh_port,
        ssh_user=ssh_user,
        ssh_key=ssh_key,
    )
    set_service_config(profile, svc)
    out.success(f"Profile '{profile}' saved.")


@app.command()
def use(
    ctx: typer.Context,
    profile: Annotated[str, typer.Argument(help="Profile to activate")],
) -> None:
    """Switch the default profile."""
    app_ctx: AppContext = ctx.obj
    out = app_ctx.output
    names = get_profile_names()
    if profile not in names:
        out.error(f"Profile '{profile}' not found. Available: {', '.join(names)}")
        raise typer.Exit(1)
    set_default_profile(profile)
    out.success(f"Default profile set to '{profile}'.")


@app.command(name="remove")
def remove_(
    ctx: typer.Context,
    profile: Annotated[str, typer.Argument(help="Profile to remove")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Remove a profile."""
    app_ctx: AppContext = ctx.obj
    out = app_ctx.output
    if not force:
        typer.confirm(f"Remove profile '{profile}'?", abort=True)
    remove_profile(profile)
    out.success(f"Profile '{profile}' removed.")


@app.command()
def show(ctx: typer.Context) -> None:
    """Show current configuration (passwords masked)."""
    app_ctx: AppContext = ctx.obj
    out = app_ctx.output
    try:
        pname = resolve_active_profile_name(app_ctx.profile)
    except KctlError:
        out.error("No profile configured. Run: kctl-redis config init")
        raise typer.Exit(1)

    svc = get_service_config(pname)
    masked_pass = _mask(svc.password)
    rows = [
        {"key": "profile", "value": pname},
        {"key": "host", "value": svc.host or "(not set)"},
        {"key": "port", "value": str(svc.port)},
        {"key": "username", "value": svc.username},
        {"key": "password", "value": masked_pass},
        {"key": "db", "value": str(svc.db)},
        {"key": "ssh_host", "value": svc.ssh_host or "(not set)"},
        {"key": "ssh_port", "value": str(svc.ssh_port)},
        {"key": "ssh_user", "value": svc.ssh_user},
        {"key": "ssh_key", "value": svc.ssh_key},
    ]
    out.table(rows, columns=["key", "value"], title="Redis Configuration")


@app.command(name="set")
def set_field(
    ctx: typer.Context,
    key: Annotated[str, typer.Argument(help="Config field name")],
    value: Annotated[str, typer.Argument(help="Config field value")],
) -> None:
    """Set a configuration value."""
    app_ctx: AppContext = ctx.obj
    out = app_ctx.output
    pname = resolve_active_profile_name(app_ctx.profile)
    svc = get_service_config(pname)
    valid_fields = set(ServiceConfig.model_fields.keys())
    if key not in valid_fields:
        out.error(f"Unknown field '{key}'. Valid: {', '.join(sorted(valid_fields))}")
        raise typer.Exit(1)
    field_info = ServiceConfig.model_fields[key]
    if field_info.annotation is int:
        setattr(svc, key, int(value))
    else:
        setattr(svc, key, value)
    set_service_config(pname, svc)
    out.success(f"Set {key} = {_mask(value) if 'pass' in key else value}")


@app.command()
def profiles(ctx: typer.Context) -> None:
    """List all profiles."""
    app_ctx: AppContext = ctx.obj
    out = app_ctx.output
    names = get_profile_names()
    if not names:
        out.info("No profiles configured. Run: kctl-redis config init")
        return
    try:
        active = resolve_active_profile_name(app_ctx.profile)
    except KctlError:
        active = ""
    rows = []
    for name in names:
        svc = get_service_config(name)
        rows.append(
            {
                "name": name,
                "active": "*" if name == active else "",
                "host": svc.host or "(not set)",
                "ssh_host": svc.ssh_host or "(not set)",
            }
        )
    out.table(rows, columns=["name", "active", "host", "ssh_host"], title="Profiles")


@app.command()
def current(ctx: typer.Context) -> None:
    """Show the active profile name."""
    app_ctx: AppContext = ctx.obj
    out = app_ctx.output
    try:
        pname = resolve_active_profile_name(app_ctx.profile)
        out.text(pname)
    except KctlError:
        out.error("No profile configured.")
        raise typer.Exit(1)


@app.command()
def test(ctx: typer.Context) -> None:
    """Test Redis connection."""
    app_ctx: AppContext = ctx.obj
    out = app_ctx.output
    try:
        client = app_ctx.client
        version = client.server_version
        info = client.info("server")
        out.success(f"Connected to Redis {version}")
        out.kv("Uptime", f"{info.get('uptime_in_days', '?')} days")
        out.kv("Role", info.get("role", "unknown"))
        app_ctx.close()
    except KctlError as e:
        out.error(f"Connection failed: {e}")
        raise typer.Exit(1)


def _mask(value: str) -> str:
    """Mask a password: first4****last4."""
    if not value or len(value) <= 8:
        return "****"
    return f"{value[:4]}****{value[-4:]}"
