"""Project settings management commands for kctl-supa."""

from __future__ import annotations

import typer
from rich import print as rprint
from rich.table import Table

from kctl_supa.core.callbacks import AppContext
from kctl_supa.core.docker import DockerOps
from kctl_supa.core.exceptions import DockerError

app = typer.Typer(help="Project settings management.")


def _get_docker(actx: AppContext) -> DockerOps:
    return DockerOps(actx.config)


def _mask(value: str) -> str:
    if not value or len(value) < 16:
        return "****" if value else "(not set)"
    return f"{value[:4]}****{value[-4:]}"


@app.command()
def show(ctx: typer.Context) -> None:
    """Show current Supabase project settings."""
    actx: AppContext = ctx.obj
    cfg = actx.config

    table = Table(title="Project Settings", show_header=True, header_style="bold cyan")
    table.add_column("Setting", style="cyan")
    table.add_column("Value")

    table.add_row("URL", cfg.url)
    table.add_row("SSH Host", cfg.ssh_host)
    table.add_row("SSH User", cfg.ssh_user)
    table.add_row("Container Prefix", cfg.container_prefix)
    table.add_row("Service Role Key", _mask(cfg.service_role_key))
    table.add_row("Anon Key", _mask(cfg.anon_key))
    table.add_row("DB Password", _mask(cfg.db_password))

    rprint(table)


@app.command("auth-config")
def auth_config(ctx: typer.Context) -> None:
    """Show GoTrue auth service configuration."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        docker = _get_docker(actx)
        result = docker.docker_exec(
            "auth",
            "env | grep -E '^GOTRUE_' | sort",
        )
        docker.close()
    except DockerError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc

    for line in result.splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            if any(s in key.upper() for s in ("KEY", "SECRET", "PASSWORD", "TOKEN")):
                value = value[:4] + "****" if len(value) > 4 else "****"
            typer.echo(f"{key}={value}")


@app.command("storage-config")
def storage_config(ctx: typer.Context) -> None:
    """Show storage service configuration."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        docker = _get_docker(actx)
        result = docker.docker_exec(
            "storage",
            "env | sort",
        )
        docker.close()
    except DockerError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc

    for line in result.splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            if any(s in key.upper() for s in ("KEY", "SECRET", "PASSWORD", "TOKEN")):
                value = value[:4] + "****" if len(value) > 4 else "****"
            typer.echo(f"{key}={value}")


@app.command("log-drains")
def log_drains(ctx: typer.Context) -> None:
    """Show log drain configuration (Vector pipeline)."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        docker = _get_docker(actx)
        result = docker.docker_exec(
            "vector",
            "cat /etc/vector/vector.yml 2>/dev/null || echo 'config not found'",
        )
        docker.close()
    except DockerError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc

    typer.echo(result)
