"""Dashboard commands for kctl-supa.

Supabase overview dashboard.
"""

from __future__ import annotations

import typer
from rich import print as rprint
from rich.panel import Panel
from rich.table import Table

from kctl_supa.core.callbacks import AppContext
from kctl_supa.core.client import SupabaseClient
from kctl_supa.core.docker import DockerOps
from kctl_supa.core.exceptions import DockerError, SupabaseError

app = typer.Typer(help="Supabase overview dashboard.")


def _get_client(actx: AppContext) -> SupabaseClient:
    cfg = actx.config
    return SupabaseClient(base_url=cfg.url, service_role_key=cfg.service_role_key, anon_key=cfg.anon_key)


def _get_docker(actx: AppContext) -> DockerOps:
    return DockerOps(actx.config)


@app.command()
def show(ctx: typer.Context) -> None:
    """Show Supabase overview dashboard."""
    actx: AppContext = ctx.obj

    cfg = actx.config

    # Collect all metrics
    service_count = "N/A"
    db_size = "N/A"
    auth_users = "N/A"
    bucket_count = "N/A"

    # Docker-based metrics
    docker = _get_docker(actx)
    try:
        containers = docker.container_status()
        running = sum(1 for c in containers if c.get("State") == "running")
        service_count = f"{running}/{len(containers)}"
    except DockerError:
        pass

    try:
        raw = docker.psql("SELECT pg_size_pretty(pg_database_size(current_database()))")
        # grab the first line that looks like a size (e.g. "8192 bytes" or "16 MB")
        for line in raw.splitlines():
            stripped = line.strip()
            if (
                stripped
                and not stripped.startswith("-")
                and not stripped.startswith("pg_size")
                and not stripped.startswith("(")
            ):
                db_size = stripped
                break
    except DockerError:
        pass

    try:
        raw = docker.psql("SELECT count(*) FROM auth.users")
        for line in raw.splitlines():
            stripped = line.strip()
            if stripped.isdigit():
                auth_users = stripped
                break
    except DockerError:
        pass

    docker.close()

    # HTTP-based metrics
    if cfg.url and cfg.service_role_key:
        try:
            client = _get_client(actx)
            blist = client.storage_list_buckets()
            client.close()
            if isinstance(blist, list):
                bucket_count = str(len(blist))
        except SupabaseError:
            pass

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Metric", style="bold cyan")
    table.add_column("Value", style="white")

    table.add_row("URL", cfg.url or "[dim]not configured[/dim]")
    table.add_row("Services running", service_count)
    table.add_row("Database size", db_size)
    table.add_row("Auth users", auth_users)
    table.add_row("Storage buckets", bucket_count)

    rprint(Panel(table, title="[bold]Supabase Dashboard[/bold]", border_style="cyan"))
