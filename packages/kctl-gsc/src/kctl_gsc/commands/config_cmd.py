"""Config subcommands for kctl-gsc."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from kctl_gsc.core.config import (
    ServiceConfig,
    get_profile_names,
    get_service_config,
    remove_profile,
    resolve_active_profile_name,
    set_service_config,
)

app = typer.Typer(help="Configuration management.")


@app.command()
def init(ctx: typer.Context) -> None:
    """Interactive first-time setup."""
    out = ctx.obj.output
    profile = typer.prompt("Profile name", default="kodemeio-kod-infra-gsc")
    creds = typer.prompt("Service-account JSON path", default="~/.config/kodemeio/gsc-sa.json")
    prop = typer.prompt("Default property (e.g. sc-domain:kodeme.io)", default="sc-domain:kodeme.io")
    set_service_config(profile, ServiceConfig(credentials_file=creds, default_property=prop))
    out.success(f"Profile '{profile}' written")


@app.command()
def add(
    ctx: typer.Context,
    name: str,
    credentials_file: Annotated[str, typer.Option("--credentials-file")],
    default_property: Annotated[str, typer.Option("--default-property")],
) -> None:
    """Add a profile non-interactively."""
    set_service_config(name, ServiceConfig(credentials_file=credentials_file, default_property=default_property))
    ctx.obj.output.success(f"Profile '{name}' added")


@app.command()
def use(ctx: typer.Context, name: str) -> None:
    """Print export line for setting the active profile."""
    ctx.obj.output.info(f"export KCTL_GSC_PROFILE={name}")


@app.command()
def show(ctx: typer.Context) -> None:
    """Show resolved config for the active profile."""
    out = ctx.obj.output
    pname = resolve_active_profile_name(ctx.obj.profile)
    svc = get_service_config(pname)
    out.detail(
        f"Profile: {pname}",
        [
            (
                "GSC",
                [
                    ("credentials_file", svc.credentials_file or "(not set)"),
                    ("default_property", svc.default_property or "(not set)"),
                ],
            )
        ],
        data_for_json={
            "profile": pname,
            "credentials_file": svc.credentials_file,
            "default_property": svc.default_property,
        },
    )


@app.command()
def validate(ctx: typer.Context) -> None:
    """Validate the active profile: credentials file exists and is JSON."""
    import json

    out = ctx.obj.output
    pname = resolve_active_profile_name(ctx.obj.profile)
    svc = get_service_config(pname)
    path = Path(svc.credentials_file).expanduser()
    if not path.is_file():
        out.error(f"credentials_file not found: {path}")
        raise typer.Exit(code=1)
    try:
        data = json.loads(path.read_text())
    except Exception as e:
        out.error(f"credentials_file not JSON: {e}")
        raise typer.Exit(code=1) from e
    if data.get("type") != "service_account":
        out.error("credentials_file is not a service-account key")
        raise typer.Exit(code=1)
    if not svc.default_property:
        out.warn("default_property is empty")
    out.success(f"Profile '{pname}' valid — SA {data.get('client_email', '?')}")


@app.command()
def remove(ctx: typer.Context, name: str) -> None:
    """Delete a profile."""
    remove_profile(name)
    ctx.obj.output.success(f"Profile '{name}' removed")


@app.command("set")
def set_field(
    ctx: typer.Context,
    key: Annotated[str, typer.Argument(help="credentials_file | default_property")],
    value: str,
) -> None:
    """Set a single field on the active profile."""
    pname = resolve_active_profile_name(ctx.obj.profile)
    svc = get_service_config(pname)
    if key == "credentials_file":
        svc.credentials_file = value
    elif key == "default_property":
        svc.default_property = value
    else:
        ctx.obj.output.error(f"Unknown key: {key}")
        raise typer.Exit(code=1)
    set_service_config(pname, svc)
    ctx.obj.output.success(f"{pname}.{key} updated")


@app.command()
def profiles(ctx: typer.Context) -> None:
    """List all profiles."""
    names = get_profile_names()
    ctx.obj.output.table(
        "Profiles",
        columns=[("Profile", "cyan")],
        rows=[[n] for n in names],
        data_for_json=[{"profile": n} for n in names],
    )


@app.command()
def current(ctx: typer.Context) -> None:
    """Show active profile name + source."""
    import os

    out = ctx.obj.output
    if ctx.obj.profile:
        out.info(f"{ctx.obj.profile} (via --profile)")
        return
    if env := os.environ.get("KCTL_GSC_PROFILE"):
        out.info(f"{env} (via KCTL_GSC_PROFILE)")
        return
    out.error("No active profile (pass -p or set KCTL_GSC_PROFILE)")
    raise typer.Exit(code=1)
