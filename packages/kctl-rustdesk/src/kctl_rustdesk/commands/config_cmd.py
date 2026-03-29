"""Configuration management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_common.config import (
    CONFIG_FILE,
    get_default_profile,
    get_profile_names,
    set_default_profile,
)

from kctl_rustdesk.core.callbacks import AppContext
from kctl_rustdesk.core.config import (
    SERVICE_KEY,
    ServiceConfig,
    get_rustdesk_config,
    resolve_active_profile,
    set_rustdesk_config,
)

app = typer.Typer(help="Manage CLI configuration and profiles.")


@app.command()
def init(
    ctx: typer.Context,
    host: Annotated[str | None, typer.Option("--host", help="Server hostname")] = None,
    ssh_user: Annotated[str | None, typer.Option("--ssh-user", help="SSH username")] = None,
    compose_file: Annotated[str | None, typer.Option("--compose-file")] = None,
    env_file: Annotated[str | None, typer.Option("--env-file")] = None,
    project_name: Annotated[str | None, typer.Option("--project-name")] = None,
    domain: Annotated[str | None, typer.Option("--domain")] = None,
    name: Annotated[str | None, typer.Option("--name", "-n", help="Profile name")] = None,
) -> None:
    """Initialize CLI configuration with a new profile."""
    c: AppContext = ctx.obj
    out = c.output

    profile_name = name or typer.prompt("Profile name", default="production")
    h = host or typer.prompt("Server host", default="dokploy.kodeme.io")
    u = ssh_user or typer.prompt("SSH user", default="root")
    cf = compose_file or typer.prompt("Compose file path", default="/opt/kodemeio-rustdesk/docker-compose.prod.yml")
    ef = env_file or typer.prompt("Env file path", default="/opt/kodemeio-rustdesk/.env.prod")
    pn = project_name or typer.prompt("Compose project name", default="kodemeio-rustdesk")
    d = domain or typer.prompt("Domain", default="rustdesk.kodeme.io")

    svc = ServiceConfig(
        host=h,
        ssh_user=u,
        compose_file=cf,
        env_file=ef,
        project_name=pn,
        domain=d,
    )
    set_rustdesk_config(profile_name, svc)

    if len(get_profile_names()) <= 1:
        set_default_profile(profile_name)

    out.success(f"Profile '{profile_name}' saved to {CONFIG_FILE}")


@app.command()
def show(ctx: typer.Context) -> None:
    """Show current configuration."""
    c: AppContext = ctx.obj
    out = c.output
    default = get_default_profile()
    active = resolve_active_profile(c.profile)

    sections: list[tuple[str, list[tuple[str, str]]]] = [
        (
            "General",
            [
                ("Config file", str(CONFIG_FILE)),
                ("Default profile", default),
                ("Active profile", active),
                ("Service key", SERVICE_KEY),
            ],
        ),
    ]

    for pname in get_profile_names():
        marker = " (default)" if pname == default else ""
        svc = get_rustdesk_config(pname)
        sections.append(
            (
                f"Profile: {pname}{marker}",
                [
                    ("Host", svc.host),
                    ("SSH user", svc.ssh_user),
                    ("Compose file", svc.compose_file),
                    ("Env file", svc.env_file),
                    ("Project name", svc.project_name),
                    ("Domain", svc.domain),
                ],
            )
        )

    out.detail(
        "RustDesk Configuration",
        sections,
        data_for_json={
            "config_file": str(CONFIG_FILE),
            "default_profile": default,
            "active_profile": active,
            "profiles": {pname: get_rustdesk_config(pname).model_dump() for pname in get_profile_names()},
        },
    )


@app.command()
def profiles(ctx: typer.Context) -> None:
    """List all profiles."""
    c: AppContext = ctx.obj
    default = get_default_profile()
    rows: list[list[str]] = []
    for pname in get_profile_names():
        svc = get_rustdesk_config(pname)
        is_default = "yes" if pname == default else ""
        rows.append([pname, svc.host, svc.domain, is_default])

    c.output.table(
        "Profiles",
        [("Name", "cyan"), ("Host", ""), ("Domain", ""), ("Default", "green")],
        rows,
    )


@app.command()
def use(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name to set as default")],
) -> None:
    """Set the default profile."""
    c: AppContext = ctx.obj
    if name not in get_profile_names():
        c.output.error(f"Profile '{name}' not found")
        raise typer.Exit(1)
    set_default_profile(name)
    c.output.success(f"Default profile set to '{name}'")


@app.command()
def test(ctx: typer.Context) -> None:
    """Test connection to the RustDesk server."""
    c: AppContext = ctx.obj
    out = c.output
    ex = c.executor

    out.info(f"Testing connection to {ex.config.host}...")

    try:
        version = ex.get_compose_version()
        out.success(f"Docker Compose: {version}")
    except Exception as e:
        out.error(f"Cannot reach server: {e}")
        raise typer.Exit(1)

    hbbs_ok = ex.container_running("hbbs")
    hbbr_ok = ex.container_running("hbbr")
    out.success(f"hbbs container: {'running' if hbbs_ok else 'NOT running'}")
    out.success(f"hbbr container: {'running' if hbbr_ok else 'NOT running'}")

    try:
        count = ex.query_db_scalar("SELECT count(*) FROM peer;")
        out.success(f"Database accessible: {count} peers")
    except Exception as e:
        out.warn(f"Database check failed: {e}")
