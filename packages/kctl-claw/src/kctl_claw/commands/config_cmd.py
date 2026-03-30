"""Config management commands."""

from __future__ import annotations

import json
from typing import Annotated

import typer

from kctl_claw.core.callbacks import AppContext
from kctl_claw.core.config_manager import ConfigFile

app = typer.Typer(help="Manage OpenClaw configuration files.")

_FILE_MAP: dict[str, ConfigFile] = {
    "openclaw": ConfigFile.OPENCLAW,
    "mcp": ConfigFile.MCP_REGISTRY,
    "cron": ConfigFile.CRON_JOBS,
    "auth": ConfigFile.AUTH_PROFILES,
}


@app.command()
def validate(ctx: typer.Context) -> None:
    """Validate all JSON config files against expected schema."""
    actx: AppContext = ctx.obj
    out = actx.output
    mgr = actx.config_mgr

    all_ok = True
    for name, cf in _FILE_MAP.items():
        if not mgr.exists(cf):
            out.info(f"{name}: skipped (file not found)")
            continue
        errors = mgr.validate_json(cf)
        if errors:
            all_ok = False
            for err in errors:
                out.error(f"{name}: {err}")
        else:
            out.success(f"{name}: OK")

    if not all_ok:
        raise typer.Exit(1)


@app.command()
def show(
    ctx: typer.Context,
    file: Annotated[str, typer.Argument(help="Config file: openclaw, mcp, cron, auth")],
) -> None:
    """Pretty-print a config file."""
    actx: AppContext = ctx.obj
    out = actx.output
    mgr = actx.config_mgr

    cf = _FILE_MAP.get(file)
    if cf is None:
        out.error(f"Unknown config file: {file!r}. Valid: {', '.join(_FILE_MAP)}")
        raise typer.Exit(1)

    try:
        data = mgr.read(cf)
    except FileNotFoundError as e:
        out.error(f"Config file not found: {cf.value}")
        raise typer.Exit(1) from e

    if out.json_mode or out.format == "json":
        typer.echo(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        typer.echo(json.dumps(data, indent=2, ensure_ascii=False))


@app.command()
def reload(ctx: typer.Context) -> None:
    """Reload config by restarting the gateway container."""
    actx: AppContext = ctx.obj
    out = actx.output

    from kctl_claw.core.exceptions import DockerError

    try:
        actx.docker.restart()
        out.success("Gateway restarted successfully.")
    except DockerError as e:
        out.error(f"Docker error: {e}")
        out.info("Is Docker running? Check with: docker compose ps")
        raise typer.Exit(1) from e


@app.command()
def add(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name")],
    project_root: Annotated[str, typer.Option("--root", help="Project root path")] = "",
    gateway_url: Annotated[str, typer.Option("--gateway-url", help="Gateway URL")] = "",
) -> None:
    """Add a new config profile."""
    actx = ctx.obj
    out = actx.output
    from kctl_claw.core.config import ServiceConfig, set_service_config

    if not project_root:
        project_root = typer.prompt("Project root path")
    svc = ServiceConfig(project_root=project_root, gateway_url=gateway_url)
    set_service_config(name, svc)
    out.success(f"Profile '{name}' added")


@app.command()
def use(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name to activate")],
) -> None:
    """Switch active config profile."""
    actx = ctx.obj
    out = actx.output
    from kctl_claw.core.config import get_profile_names, set_default_profile

    available = get_profile_names()
    if name not in available:
        out.error(f"Profile '{name}' not found. Available: {', '.join(available)}")
        raise typer.Exit(1)
    set_default_profile(name)
    out.success(f"Switched to profile '{name}'")


@app.command()
def remove(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name to remove")],
) -> None:
    """Remove a config profile."""
    actx = ctx.obj
    out = actx.output
    from kctl_claw.core.config import get_profile_names, remove_profile

    available = get_profile_names()
    if name not in available:
        out.error(f"Profile '{name}' not found. Available: {', '.join(available)}")
        raise typer.Exit(1)
    remove_profile(name)
    out.success(f"Profile '{name}' removed")


@app.command("set")
def set_(
    ctx: typer.Context,
    key: Annotated[str, typer.Argument(help="Config key")],
    value: Annotated[str, typer.Argument(help="Config value")],
) -> None:
    """Set a single config value in the active profile."""
    actx = ctx.obj
    out = actx.output
    from kctl_claw.core.config import ServiceConfig, get_service_config, resolve_active_profile, set_service_config

    active = resolve_active_profile(actx.profile)
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
    actx = ctx.obj
    out = actx.output
    from kctl_claw.core.config import get_profile_names, resolve_active_profile

    active = resolve_active_profile(actx.profile)
    names = get_profile_names()
    if out.json_mode:
        out.raw_json({"profiles": names, "active": active})
        return
    rows = [[name, "active" if name == active else ""] for name in names]
    out.table("Profiles", [("Name", "cyan"), ("Status", "green")], rows)


@app.command()
def current(ctx: typer.Context) -> None:
    """Show active profile and resolved context."""
    actx = ctx.obj
    out = actx.output
    from kctl_claw.core.config import get_service_config, resolve_active_profile

    active = resolve_active_profile(actx.profile)
    svc = get_service_config(active)
    if out.json_mode:
        out.raw_json({"profile": active, **svc.model_dump()})
        return
    sections = [
        (
            "Active Profile",
            [
                ("Name", active),
                ("Project Root", svc.project_root or "(not set)"),
                ("Gateway URL", svc.gateway_url or "(not set)"),
            ],
        )
    ]
    out.detail("Current Config", sections)


@app.command("init")
def init_(
    ctx: typer.Context,
    profile_name: Annotated[str, typer.Argument(help="Profile name")] = "default",
    gateway_url: Annotated[str, typer.Option("--gateway-url", help="Gateway URL")] = "https://openclaw.kodeme.io",
    gateway_token: Annotated[str, typer.Option("--gateway-token", help="Gateway token")] = "",
) -> None:
    """Initialize profile in ~/.config/kodemeio/config.yaml."""
    actx: AppContext = ctx.obj
    out = actx.output

    from kctl_claw.core.config import ServiceConfig, set_service_config

    svc = ServiceConfig(
        project_root=str(actx.project_root),
        gateway_url=gateway_url,
        gateway_token=gateway_token,
        compose_file="docker-compose.prod.yml",
        env_file=".env.prod",
    )
    set_service_config(profile_name, svc)
    out.success(f"Profile '{profile_name}' saved to ~/.config/kodemeio/config.yaml")
    out.info(f"  project_root: {svc.project_root}")
    out.info(f"  gateway_url: {svc.gateway_url}")


@app.command()
def test(ctx: typer.Context) -> None:
    """Verify configuration is valid."""
    actx: AppContext = ctx.obj
    out = actx.output
    from kctl_claw.core.config import SERVICE_KEY, get_service_config, resolve_active_profile

    active = resolve_active_profile(actx.profile)
    out.info(f"Testing profile '{active}' \u2192 {SERVICE_KEY}")
    svc = get_service_config(active)
    if not svc or not svc.project_root:
        out.error("No configuration found. Run: kctl-claw config init")
        raise typer.Exit(1)
    out.success(f"Configuration valid for profile '{active}'")
