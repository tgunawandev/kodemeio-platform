"""Configuration management commands.

Initialize, view, and manage CLI profiles and connection settings.
"""

from __future__ import annotations

import os
from typing import Annotated

import typer

from kctl_react.core.callbacks import AppContext
from kctl_react.core.config import (
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
    resolve_project_root,
    save_raw_config,
    set_default_profile,
    set_service_config,
)

app = typer.Typer(help="Manage CLI configuration and profiles.")


@app.command()
def init(
    ctx: typer.Context,
    root: Annotated[str | None, typer.Option("--root", help="Monorepo root directory.")] = None,
    api_url: Annotated[str | None, typer.Option("--api-url", help="Backend API URL.")] = None,
    name: Annotated[str | None, typer.Option("--name", "-n", help="Profile name.")] = None,
) -> None:
    """Initialize CLI configuration (interactive if no flags given)."""
    actx: AppContext = ctx.obj
    out = actx.output

    profile_name = name or typer.prompt("Profile name", default="default")
    project_root = root or str(resolve_project_root())
    backend_url = api_url or typer.prompt("Backend API URL", default="https://api.kodeme.io")

    # Verify project root
    from pathlib import Path

    root_path = Path(project_root)
    if (root_path / "turbo.json").exists():
        out.success(f"Monorepo detected at {project_root}")
    else:
        out.warn(f"No turbo.json found at {project_root}")
        if not typer.confirm("Save configuration anyway?", default=False):
            raise typer.Exit(code=1)

    svc = ServiceConfig(project_root=project_root, api_url=backend_url)
    set_service_config(profile_name, svc)

    if len(get_profile_names()) <= 1:
        set_default_profile(profile_name)

    out.success(f"Configuration saved to {CONFIG_FILE}")
    out.kv("Profile", profile_name)
    out.kv("Service", SERVICE_KEY)
    out.kv("Project root", project_root)
    out.kv("API URL", backend_url)


@app.command()
def add(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name (e.g. abcfood, staging)")],
    root: Annotated[str | None, typer.Option("--root", help="Monorepo root directory.")] = None,
    api_url: Annotated[str | None, typer.Option("--api-url", help="Backend API URL.")] = None,
    odoo_url: Annotated[str | None, typer.Option("--odoo-url", help="Odoo URL.")] = None,
    odoo_db: Annotated[str | None, typer.Option("--odoo-db", help="Odoo database name.")] = None,
    set_default: Annotated[bool, typer.Option("--default", help="Set as default profile.")] = False,
) -> None:
    """Add or update a profile's React monorepo connection."""
    actx: AppContext = ctx.obj
    out = actx.output

    project_root = root or typer.prompt("Monorepo root", default=str(resolve_project_root()))
    backend_url = api_url or typer.prompt("Backend API URL", default="https://api.kodeme.io")

    existing = get_service_config(name)
    if existing.project_root and not typer.confirm(f"Profile '{name}' already has {SERVICE_KEY} config. Overwrite?"):
        raise typer.Exit(0)

    svc = ServiceConfig(project_root=project_root, api_url=backend_url)
    if odoo_url:
        svc.odoo_url = odoo_url
    if odoo_db:
        svc.odoo_db = odoo_db

    set_service_config(name, svc)

    if set_default or len(get_profile_names()) == 1:
        set_default_profile(name)

    out.success(f"Profile '{name}' -> {SERVICE_KEY} configured")
    out.kv("Root", project_root)
    out.kv("API URL", backend_url)


@app.command()
def use(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name to switch to")],
) -> None:
    """Switch the default profile."""
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
    out.success(f"Switched to '{name}' (root: {svc.project_root or 'auto-detect'})")
    out.info(f"Previous default: {old_default}")


@app.command()
def remove(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name to remove")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
    service_only: Annotated[bool, typer.Option("--service-only", help="Only remove react config")] = False,
) -> None:
    """Remove a profile or just its React config."""
    actx: AppContext = ctx.obj
    out = actx.output

    profiles = get_profile_names()
    if name not in profiles:
        out.error(f"Profile '{name}' not found")
        raise typer.Exit(1)

    if service_only:
        if not force and not typer.confirm(f"Remove {SERVICE_KEY} config from '{name}'?"):
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


@app.command()
def show(ctx: typer.Context) -> None:
    """Show full configuration."""
    actx: AppContext = ctx.obj
    out = actx.output

    default = get_default_profile()
    profiles = get_profile_names()

    if out.json_mode:
        out.raw_json(load_raw_config())
        return

    sections: list[tuple[str, list[tuple[str, str]]]] = []

    sections.append(
        (
            "General",
            [
                ("Config file", str(CONFIG_FILE)),
                ("Default profile", default),
                ("Total profiles", str(len(profiles))),
                ("This CLI", f"kctl-react -> service key: {SERVICE_KEY}"),
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
            indicator = "[green]●[/green]" if svc_name == SERVICE_KEY else "[dim]○[/dim]"
            svc_root = svc_data.get("project_root", svc_data.get("url", ""))
            kvs.append((f"{indicator} {svc_name}", svc_root))

        if not kvs:
            kvs.append(("(empty)", "no services configured"))

        sections.append((f"Profile: {pname}{marker}", kvs))

    out.detail("Configuration", sections)


@app.command("set")
def set_(
    ctx: typer.Context,
    key: Annotated[str, typer.Argument(help="Config key (e.g. project_root, api_url, odoo_url, odoo_db)")],
    value: Annotated[str, typer.Argument(help="Value to set")],
) -> None:
    """Set a configuration value."""
    actx: AppContext = ctx.obj
    out = actx.output

    if key == "default_profile":
        set_default_profile(value)
        out.success(f"Default profile set to: {value}")
        return

    pname = resolve_active_profile_name(actx.profile)
    svc = get_service_config(pname)

    valid_fields = {"project_root", "api_url", "odoo_url", "odoo_db"}
    if key not in valid_fields:
        out.error(f"Unknown key: {key}")
        out.info(f"Valid keys: {', '.join(sorted(valid_fields))}, default_profile")
        raise typer.Exit(1)

    setattr(svc, key, value)
    set_service_config(pname, svc)
    out.success(f"[{pname}] {SERVICE_KEY}.{key} = {value}")


@app.command()
def profiles(ctx: typer.Context) -> None:
    """List all profiles."""
    actx: AppContext = ctx.obj
    out = actx.output

    profile_names = get_profile_names()
    if not profile_names:
        out.warn("No profiles configured. Run: kctl-react config init")
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

        other_str = ", ".join(other_services) if other_services else "[dim]-[/dim]"

        rows.append([pname, svc.project_root or "-", svc.api_url or "-", other_str, status_marker])
        json_data.append(
            {
                "name": pname,
                "project_root": svc.project_root,
                "api_url": svc.api_url,
                "other_services": other_services,
                "active": is_active,
                "default": pname == default,
            }
        )

    out.table(
        "Profiles",
        [("Name", "cyan"), ("Project Root", ""), ("API URL", ""), ("Other Services", "dim"), ("", "green")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def current(ctx: typer.Context) -> None:
    """Show the active profile and project root."""
    actx: AppContext = ctx.obj
    out = actx.output

    active = resolve_active_profile_name(actx.profile)
    svc = get_service_config(active)
    root = resolve_project_root(profile_name=actx.profile, root_override=actx.root_override)

    source = "config default"
    if actx.profile:
        source = "--profile flag"
    elif os.environ.get("KCTL_REACT_PROFILE"):
        source = "KCTL_REACT_PROFILE env var"

    turbo_exists = (root / "turbo.json").exists()

    sections: list[tuple[str, list[tuple[str, str]]]] = [
        (
            "Active Connection",
            [
                ("Profile", active),
                ("Service", SERVICE_KEY),
                ("Source", source),
                ("Project root", str(root)),
                ("Monorepo detected", "[green]Yes[/green]" if turbo_exists else "[red]No[/red]"),
                ("API URL", svc.api_url or "[dim]not set[/dim]"),
            ],
        ),
    ]

    if svc.odoo_url or svc.odoo_db:
        sections.append(
            (
                "Odoo Settings",
                [
                    ("Odoo URL", svc.odoo_url or "[dim]not set[/dim]"),
                    ("Odoo DB", svc.odoo_db or "[dim]not set[/dim]"),
                ],
            )
        )

    all_services = get_all_services_in_profile(active)
    other = {k: v for k, v in all_services.items() if k != SERVICE_KEY and isinstance(v, dict)}
    if other:
        sections.append(
            (
                "Other Services in Profile",
                [(svc_name, v.get("url", v.get("project_root", "(no url)"))) for svc_name, v in other.items()],
            )
        )

    out.detail(
        "Current Profile",
        sections,
        data_for_json={
            "profile": active,
            "service": SERVICE_KEY,
            "source": source,
            "project_root": str(root),
            "monorepo_detected": turbo_exists,
            "api_url": svc.api_url,
        },
    )
