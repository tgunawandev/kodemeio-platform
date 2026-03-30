"""Configuration management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_cloudflare.core.callbacks import AppContext
from kctl_cloudflare.core.config import (
    CONFIG_FILE,
    SERVICE_KEY,
    ServiceConfig,
    get_all_services_in_profile,
    get_default_profile,
    get_profile_names,
    resolve_active_profile_name,
    set_default_profile,
    set_service_config,
)
from kctl_cloudflare.core.exceptions import KctlError

app = typer.Typer(help="Manage CLI configuration and profiles.")


def _mask(val: str) -> str:
    if not val:
        return "[dim]not set[/dim]"
    return f"{val[:4]}{'*' * max(0, len(val) - 8)}{val[-4:]}" if len(val) > 10 else "****"


@app.command()
def init(
    ctx: typer.Context,
    api_token: Annotated[str | None, typer.Option("--api-token")] = None,
    account_id: Annotated[str | None, typer.Option("--account-id")] = None,
    name: Annotated[str | None, typer.Option("--name", "-n")] = None,
) -> None:
    """Initialize CLI configuration."""
    c: AppContext = ctx.obj
    out = c.output
    profile_name = name or typer.prompt("Profile name", default="kodemeio")
    token = api_token or typer.prompt("Cloudflare API token", hide_input=True)
    acct = account_id or typer.prompt("Account ID")

    svc = ServiceConfig(api_token=token, account_id=acct)
    set_service_config(profile_name, svc)
    if len(get_profile_names()) <= 1:
        set_default_profile(profile_name)
    out.success(f"Configuration saved to {CONFIG_FILE}")
    out.kv("Profile", profile_name)
    out.kv("Token", _mask(token))
    out.kv("Account ID", acct)


@app.command()
def show(ctx: typer.Context) -> None:
    """Show configuration."""
    c: AppContext = ctx.obj
    out = c.output
    default = get_default_profile()
    sections = [
        (
            "General",
            [
                ("Config file", str(CONFIG_FILE)),
                ("Default profile", default),
                ("Service key", SERVICE_KEY),
            ],
        )
    ]
    for pname in get_profile_names():
        marker = " [green](default)[/green]" if pname == default else ""
        services = get_all_services_in_profile(pname)
        kvs = []
        for svc_name, svc_data in services.items():
            if not isinstance(svc_data, dict):
                continue
            indicator = "[green]●[/green]" if svc_name == SERVICE_KEY else "[dim]○[/dim]"
            kvs.append(
                (f"{indicator} {svc_name}", f"token: {_mask(svc_data.get('api_token', svc_data.get('token', '')))}")
            )
        sections.append((f"Profile: {pname}{marker}", kvs or [("(empty)", "")]))
    out.detail("Configuration", sections)


@app.command()
def test(ctx: typer.Context) -> None:
    """Test API connection."""
    c: AppContext = ctx.obj
    out = c.output
    active = resolve_active_profile_name(c.profile)
    out.info(f"Testing profile '{active}' → {SERVICE_KEY}")
    try:
        result = c.client.check_health()
        status = result.get("status", "unknown") if isinstance(result, dict) else "ok"
        out.success(f"Connected — token status: {status}")
    except KctlError as e:
        out.error(f"Connection failed: {e}")
        raise typer.Exit(1) from e


@app.command()
def use(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name")],
) -> None:
    """Switch default profile."""
    c: AppContext = ctx.obj
    if name not in get_profile_names():
        c.output.error(f"Profile '{name}' not found")
        raise typer.Exit(1)
    set_default_profile(name)
    c.output.success(f"Switched to '{name}'")
