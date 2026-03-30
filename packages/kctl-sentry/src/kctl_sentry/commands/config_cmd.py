"""Configuration management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_sentry.core.callbacks import AppContext
from kctl_sentry.core.config import (
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
from kctl_sentry.core.exceptions import KctlError

app = typer.Typer(help="Manage CLI configuration and profiles.")


def _mask(val: str) -> str:
    """Mask a secret value for display."""
    if not val:
        return "[dim]not set[/dim]"
    return f"{val[:4]}{'*' * max(0, len(val) - 8)}{val[-4:]}" if len(val) > 10 else "****"


@app.command()
def init(
    ctx: typer.Context,
    auth_token: Annotated[str | None, typer.Option("--auth-token", help="Sentry auth token")] = None,
    organization: Annotated[str | None, typer.Option("--organization", "--org", help="Organization slug")] = None,
    url: Annotated[str | None, typer.Option("--url", help="Sentry URL")] = None,
    default_project: Annotated[str | None, typer.Option("--default-project", help="Default project slug")] = None,
    name: Annotated[str | None, typer.Option("--name", "-n", help="Profile name")] = None,
) -> None:
    """Initialize CLI configuration."""
    c: AppContext = ctx.obj
    out = c.output
    profile_name = name or typer.prompt("Profile name", default="kodemeio")
    token = auth_token or typer.prompt("Sentry auth token", hide_input=True)
    org = organization or typer.prompt("Organization slug")
    sentry_url = url or typer.prompt("Sentry URL", default="https://sentry.io")
    proj = default_project or typer.prompt("Default project slug (optional)", default="")

    svc = ServiceConfig(
        url=sentry_url,
        auth_token=token,
        organization=org,
        default_project=proj,
    )
    set_service_config(profile_name, svc)
    if len(get_profile_names()) <= 1:
        set_default_profile(profile_name)
    out.success(f"Configuration saved to {CONFIG_FILE}")
    out.kv("Profile", profile_name)
    out.kv("URL", sentry_url)
    out.kv("Token", _mask(token))
    out.kv("Organization", org)
    if proj:
        out.kv("Default project", proj)


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
        kvs: list[tuple[str, str]] = []
        for svc_name, svc_data in services.items():
            if not isinstance(svc_data, dict):
                continue
            indicator = "[green]●[/green]" if svc_name == SERVICE_KEY else "[dim]○[/dim]"
            token_val = svc_data.get("auth_token", svc_data.get("token", ""))
            kvs.append((f"{indicator} {svc_name}", f"token: {_mask(token_val)}"))
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
        org_name = result.get("name", "unknown")
        out.success(f"Connected — organization: {org_name}")
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
