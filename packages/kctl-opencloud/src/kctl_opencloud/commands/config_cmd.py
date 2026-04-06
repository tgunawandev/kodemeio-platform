"""Configuration management commands for kctl-opencloud."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_opencloud.core.callbacks import AppContext
from kctl_opencloud.core.config import (
    SERVICE_KEY,
    ServiceConfig,
    get_default_profile,
    get_profile_names,
    get_service_config,
    remove_profile,
    resolve_active_profile_name,
    set_default_profile,
    set_service_config,
)

app = typer.Typer(help="Configuration and profile management.")


def _mask_token(token: str) -> str:
    """Mask a token for display."""
    if not token or len(token) < 8:
        return "****" if token else ""
    return token[:4] + "****" + token[-4:]


@app.command()
def init(
    ctx: typer.Context,
    url: Annotated[str, typer.Option("--url", help="OpenCloud API URL")] = "",
    token: Annotated[str, typer.Option("--token", help="Machine auth API key")] = "",
    profile_name: Annotated[str, typer.Option("--profile", "-p", help="Profile name")] = "default",
) -> None:
    """Initialize configuration with API credentials."""
    c: AppContext = ctx.obj

    if not url:
        url = typer.prompt("OpenCloud URL", default="https://cloud.kodeme.io")
    if not token:
        token = typer.prompt("Machine Auth API Key", hide_input=True)

    svc = ServiceConfig(url=url, token=token)
    set_service_config(profile_name, svc)
    set_default_profile(profile_name)

    # Test connection
    try:
        from kctl_opencloud.core.client import OpenCloudClient

        client = OpenCloudClient(base_url=url, credential=token)
        status = client.check_health()
        if status == 200:
            c.output.success(f"Connected to {url}")
        elif status == 0:
            c.output.warn(f"Could not reach {url} (connection error)")
        else:
            c.output.warn(f"Connection returned HTTP {status}")
    except Exception as e:
        c.output.warn(f"Could not verify connection: {e}")

    c.output.success(f"Configuration saved to profile '{profile_name}'")


@app.command()
def show(ctx: typer.Context) -> None:
    """Show current configuration."""
    c: AppContext = ctx.obj
    pname = resolve_active_profile_name(c.profile)
    svc = get_service_config(pname)

    data = {
        "profile": pname,
        "service_key": SERVICE_KEY,
        "url": svc.url or "(not set)",
        "token": _mask_token(svc.token),
        "container_name": svc.container_name or "(default)",
    }

    sections = [
        (
            "Configuration",
            [
                ("Profile", data["profile"]),
                ("Service Key", data["service_key"]),
                ("URL", data["url"]),
                ("Token", data["token"]),
                ("Container", data["container_name"]),
            ],
        ),
    ]
    c.output.detail("OpenCloud Config", sections, data_for_json=data)


@app.command()
def current(ctx: typer.Context) -> None:
    """Show the active profile name."""
    c: AppContext = ctx.obj
    pname = resolve_active_profile_name(c.profile)
    c.output.text(pname)


@app.command("set")
def set_(
    ctx: typer.Context,
    key: Annotated[str, typer.Argument(help="Config key (url, token, container_name)")],
    value: Annotated[str, typer.Argument(help="Config value")],
) -> None:
    """Set a configuration value."""
    c: AppContext = ctx.obj
    valid_fields = set(ServiceConfig.model_fields.keys())
    if key not in valid_fields:
        c.output.error(f"Invalid key '{key}'. Valid keys: {', '.join(sorted(valid_fields))}")
        raise typer.Exit(code=1)

    pname = resolve_active_profile_name(c.profile)
    svc = get_service_config(pname)
    setattr(svc, key, value)
    set_service_config(pname, svc)
    display_value = _mask_token(value) if "token" in key else value
    c.output.success(f"Set {key} = {display_value}")


@app.command()
def profiles(ctx: typer.Context) -> None:
    """List all configuration profiles."""
    c: AppContext = ctx.obj
    names = get_profile_names()
    default = get_default_profile()

    rows = []
    for name in names:
        svc = get_service_config(name)
        marker = "*" if name == default else ""
        rows.append([marker, name, svc.url or "(not set)"])

    c.output.table(
        "Profiles",
        [("", "cyan"), ("Name", "green"), ("URL", "white")],
        rows,
        data_for_json=[{"name": n, "default": n == default} for n in names],
    )


@app.command("use")
def use_(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name to activate")],
) -> None:
    """Switch to a different profile."""
    c: AppContext = ctx.obj
    names = get_profile_names()
    if name not in names:
        c.output.error(f"Profile '{name}' not found. Available: {', '.join(names)}")
        raise typer.Exit(code=1)
    set_default_profile(name)
    c.output.success(f"Switched to profile '{name}'")


@app.command()
def remove(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name to remove")],
) -> None:
    """Remove a configuration profile."""
    c: AppContext = ctx.obj
    remove_profile(name)
    c.output.success(f"Removed profile '{name}'")


@app.command()
def test(ctx: typer.Context) -> None:
    """Test the current connection."""
    c: AppContext = ctx.obj
    try:
        status = c.client.check_health()
        if status == 200:
            c.output.success("Connection OK")
            version = c.client.get_version()
            if version:
                c.output.info(f"OpenCloud {version}")
        else:
            c.output.error(f"Connection failed (HTTP {status})")
            raise typer.Exit(code=1)
    except Exception as e:
        c.output.error(f"Connection failed: {e}")
        raise typer.Exit(code=1)
