"""Config profile management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_github.core.callbacks import AppContext
from kctl_github.core.config import (
    ServiceConfig,
    get_all_services_in_profile,
    get_profile_names,
    get_service_config,
    remove_profile,
    resolve_active_profile_name,
    set_default_profile,
    set_service_config,
)

app = typer.Typer(help="Profile and configuration management.")


@app.command()
def init(ctx: typer.Context) -> None:
    """Interactive config setup."""
    actx: AppContext = ctx.obj
    out = actx.output
    profile_name = typer.prompt("Profile name", default="default")
    token = typer.prompt("GitHub token (PAT)", default="", hide_input=True)
    organization = typer.prompt("GitHub organization/user", default="tgunawandev")
    repo_prefix = typer.prompt("Repository prefix filter", default="kodemeio-")
    svc = ServiceConfig(token=token, organization=organization, repo_prefix=repo_prefix)
    set_service_config(profile_name, svc)
    set_default_profile(profile_name)
    out.success(f"Config saved to profile '{profile_name}'")


@app.command()
def add(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name")],
) -> None:
    """Add a new config profile."""
    actx: AppContext = ctx.obj
    out = actx.output
    token = typer.prompt("GitHub token (PAT)", default="", hide_input=True)
    organization = typer.prompt("GitHub organization/user", default="tgunawandev")
    repo_prefix = typer.prompt("Repository prefix filter", default="kodemeio-")
    svc = ServiceConfig(token=token, organization=organization, repo_prefix=repo_prefix)
    set_service_config(name, svc)
    out.success(f"Profile '{name}' added")


@app.command()
def use(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name to activate")],
) -> None:
    """Switch active config profile."""
    actx: AppContext = ctx.obj
    out = actx.output
    available = get_profile_names()
    if name not in available:
        out.error(f"Profile '{name}' not found. Available: {', '.join(available)}")
        raise typer.Exit(1)
    set_default_profile(name)
    out.success(f"Switched to profile '{name}'")


@app.command()
def show(ctx: typer.Context) -> None:
    """Show current configuration."""
    actx: AppContext = ctx.obj
    out = actx.output
    active = resolve_active_profile_name(actx.profile)
    profiles = get_profile_names()
    if out.json_mode:
        out.raw_json({"active_profile": active, "profiles": {n: get_all_services_in_profile(n) for n in profiles}})
        return
    out.header("Configuration")
    out.kv("Active profile", active)
    for name in profiles:
        marker = " (active)" if name == active else ""
        out.header(f"Profile: {name}{marker}")
        services = get_all_services_in_profile(name)
        for svc_name, svc_data in services.items():
            out.text(f"  [bold]{svc_name}:[/bold]")
            if isinstance(svc_data, dict):
                for k, v in svc_data.items():
                    out.kv(f"    {k}", str(v))


@app.command()
def validate(ctx: typer.Context) -> None:
    """Validate current config completeness."""
    actx: AppContext = ctx.obj
    out = actx.output
    active = resolve_active_profile_name(actx.profile)
    svc = get_service_config(active)
    issues: list[str] = []
    if not svc.token:
        issues.append("token is not set")
    if not svc.organization:
        issues.append("organization is not set")
    if out.json_mode:
        out.raw_json({"profile": active, "valid": len(issues) == 0, "issues": issues})
        return
    if issues:
        out.error(f"Profile '{active}' has {len(issues)} issue(s):")
        for issue in issues:
            out.text(f"  - {issue}")
        raise typer.Exit(1)
    out.success(f"Profile '{active}' is valid")


@app.command()
def remove(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name to remove")],
) -> None:
    """Remove a config profile."""
    actx: AppContext = ctx.obj
    out = actx.output
    available = get_profile_names()
    if name not in available:
        out.error(f"Profile '{name}' not found")
        raise typer.Exit(1)
    remove_profile(name)
    out.success(f"Profile '{name}' removed")


@app.command("set")
def set_(
    ctx: typer.Context,
    key: Annotated[str, typer.Argument(help="Config key")],
    value: Annotated[str, typer.Argument(help="Config value")],
) -> None:
    """Set a single config value."""
    actx: AppContext = ctx.obj
    out = actx.output
    active = resolve_active_profile_name(actx.profile)
    svc = get_service_config(active)
    if key not in ServiceConfig.model_fields:
        out.error(f"Unknown key '{key}'. Valid: {', '.join(ServiceConfig.model_fields)}")
        raise typer.Exit(1)
    data = svc.model_dump()
    data[key] = value
    set_service_config(active, ServiceConfig(**data))
    out.success(f"Set {key}={value} in profile '{active}'")


@app.command()
def profiles(ctx: typer.Context) -> None:
    """List all config profiles."""
    actx: AppContext = ctx.obj
    out = actx.output
    active = resolve_active_profile_name(actx.profile)
    names = get_profile_names()
    if out.json_mode:
        out.raw_json({"profiles": names, "active": active})
        return
    rows = [[name, "active" if name == active else ""] for name in names]
    out.table("Profiles", [("Name", "cyan"), ("Status", "green")], rows)


@app.command()
def current(ctx: typer.Context) -> None:
    """Show active profile and resolved context."""
    actx: AppContext = ctx.obj
    out = actx.output
    active = resolve_active_profile_name(actx.profile)
    svc = get_service_config(active)
    if out.json_mode:
        out.raw_json({"profile": active, **svc.model_dump()})
        return
    fields = [(k, str(v) or "(not set)") for k, v in svc.model_dump().items()]
    sections = [("Active Profile", [("Name", active)] + fields)]
    out.detail("Current Config", sections)
