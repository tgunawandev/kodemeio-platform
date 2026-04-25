"""Configuration management commands for kctl-litellm.

Manage profiles and LiteLLM connection settings.
"""

from __future__ import annotations

import os
from typing import Annotated

import typer
from rich import print as rprint
from rich.table import Table

from kctl_litellm.core.callbacks import AppContext
from kctl_litellm.core.config import (
    SERVICE_KEY,
    ServiceConfig,
    get_all_services_in_profile,
    get_default_profile,
    get_profile_names,
    get_service_config,
    remove_profile,
    resolve_active_profile_name,
    set_default_profile,
    set_service_config,
)

app = typer.Typer(help="Manage CLI configuration and profiles.")


def _mask_secret(secret: str) -> str:
    """Mask a secret, showing only last 8 chars."""
    if not secret:
        return "[dim]not set[/dim]"
    if len(secret) <= 8:
        return "****"
    return f"{'*' * (len(secret) - 8)}{secret[-8:]}"


@app.command()
def profiles(ctx: typer.Context) -> None:
    """List all profiles with their LiteLLM configuration."""
    actx: AppContext = ctx.obj
    out = actx.output

    profile_names = get_profile_names()
    if not profile_names:
        out.warn("No profiles configured.")
        return

    default = get_default_profile()
    active = resolve_active_profile_name(actx.profile)

    table = Table(title="Profiles", show_header=True, header_style="bold cyan")
    table.add_column("Name", style="cyan")
    table.add_column("URL")
    table.add_column("Default")

    for pname in profile_names:
        svc = get_service_config(pname)
        is_default = pname == default
        is_active = pname == active
        default_marker = "[green]yes[/green]" if is_default else ""
        if is_active and not is_default:
            default_marker = "[yellow]active[/yellow]"
        elif is_active and is_default:
            default_marker = "[green]yes (active)[/green]"
        table.add_row(pname, svc.url or "[dim]-[/dim]", default_marker)

    rprint(table)


@app.command()
def show(
    ctx: typer.Context,
    name: Annotated[str | None, typer.Argument(help="Profile name (default: active profile)")] = None,
) -> None:
    """Show current profile config (secrets masked)."""
    actx: AppContext = ctx.obj
    out = actx.output

    profile_name = name or resolve_active_profile_name(actx.profile)
    svc = get_service_config(profile_name)

    out.kv("Profile", profile_name)
    out.kv("Service", SERVICE_KEY)
    out.kv("URL", svc.url or "[dim]not set[/dim]")
    out.kv("Master Key", _mask_secret(svc.master_key))
    out.kv("Salt Key", _mask_secret(svc.salt_key))
    out.kv("DB URL", _mask_secret(svc.db_url))
    out.kv("SSH Host", svc.ssh_host or "[dim]not set[/dim]")
    out.kv("SSH Port", str(svc.ssh_port))
    out.kv("SSH User", svc.ssh_user)
    out.kv("SSH Key", svc.ssh_key)
    out.kv("Container Name", svc.container_name or "[dim]not set[/dim]")


@app.command()
def current(ctx: typer.Context) -> None:
    """Show the active profile name."""
    actx: AppContext = ctx.obj
    out = actx.output

    active = resolve_active_profile_name(actx.profile)
    default = get_default_profile()

    source = "config default"
    if actx.profile:
        source = "--profile flag"
    elif os.environ.get("KCTL_LITELLM_PROFILE"):
        source = "KCTL_LITELLM_PROFILE env var"

    out.kv("Active Profile", active)
    out.kv("Default Profile", default)
    out.kv("Source", source)


@app.command()
def add(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name (e.g. production, staging)")],
    url: Annotated[str | None, typer.Option("--url", help="LiteLLM proxy URL.")] = None,
    master_key: Annotated[str | None, typer.Option("--master-key", help="Master key for API access.")] = None,
    salt_key: Annotated[str | None, typer.Option("--salt-key", help="Salt key for hashing.")] = None,
    db_url: Annotated[str | None, typer.Option("--db-url", help="Database connection URL.")] = None,
    ssh_host: Annotated[str | None, typer.Option("--ssh-host", help="SSH host (public IP).")] = None,
    ssh_user: Annotated[str, typer.Option("--ssh-user", help="SSH username.")] = "root",
    container_name: Annotated[str | None, typer.Option("--container-name", help="Docker container name.")] = None,
    set_default: Annotated[bool, typer.Option("--default", help="Set as default profile.")] = False,
) -> None:
    """Add or update a LiteLLM profile.

    Example: kctl-litellm config add production --url https://litellm.kodeme.io --master-key sk-...
    """
    actx: AppContext = ctx.obj
    out = actx.output

    existing = get_service_config(name)
    if existing.url:
        if not typer.confirm(f"Profile '{name}' already has {SERVICE_KEY} config ({existing.url}). Overwrite?"):
            raise typer.Exit(0)

    svc = ServiceConfig(
        url=url or "",
        master_key=master_key or "",
        salt_key=salt_key or "",
        db_url=db_url or "",
        ssh_host=ssh_host or "",
        ssh_user=ssh_user,
        container_name=container_name or "",
    )

    set_service_config(name, svc)

    if set_default or len(get_profile_names()) == 1:
        set_default_profile(name)

    out.success(f"Profile '{name}' -> {SERVICE_KEY} configured")
    out.kv("URL", svc.url or "[dim]not set[/dim]")
    if svc.ssh_host:
        out.kv("SSH", f"{ssh_user}@{svc.ssh_host}")
    if get_default_profile() == name:
        out.info("Set as default profile")


@app.command("remove")
def remove_(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name to remove")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Remove a profile."""
    actx: AppContext = ctx.obj
    out = actx.output

    profile_names = get_profile_names()
    if name not in profile_names:
        out.error(f"Profile '{name}' not found")
        out.info(f"Available: {', '.join(profile_names)}")
        raise typer.Exit(1)

    if not force:
        services = get_all_services_in_profile(name)
        svc_list = ", ".join(services.keys()) if services else "empty"
        if not typer.confirm(f"Remove entire profile '{name}' (services: {svc_list})?"):
            raise typer.Exit(0)

    remove_profile(name)
    out.success(f"Profile '{name}' removed")

    new_default = get_default_profile()
    if new_default and new_default != name:
        out.info(f"Default is now: {new_default}")


@app.command()
def use(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name to switch to")],
) -> None:
    """Set the default profile.

    Example: kctl-litellm config use production
    """
    actx: AppContext = ctx.obj
    out = actx.output

    profile_names = get_profile_names()
    if name not in profile_names:
        out.error(f"Profile '{name}' not found")
        out.info(f"Available: {', '.join(profile_names)}")
        raise typer.Exit(1)

    old_default = get_default_profile()
    set_default_profile(name)

    svc = get_service_config(name)
    if svc.url:
        out.success(f"Switched to '{name}' ({svc.url})")
    else:
        out.warn(f"Switched to '{name}' -- no {SERVICE_KEY} config in this profile")

    if old_default and old_default != name:
        out.info(f"Previous default: {old_default}")
