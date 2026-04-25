"""Health check commands for kctl-supa.

Check Supabase service health via HTTP and SSH.
"""

from __future__ import annotations

import time
from typing import Annotated

import httpx
import typer
from rich import print as rprint
from rich.table import Table

from kctl_supa.core.callbacks import AppContext
from kctl_supa.core.client import SupabaseClient
from kctl_supa.core.docker import DockerOps
from kctl_supa.core.exceptions import DockerError, SupabaseError

app = typer.Typer(help="Check Supabase service health.")


def _get_client(actx: AppContext) -> SupabaseClient:
    cfg = actx.config
    return SupabaseClient(base_url=cfg.url, service_role_key=cfg.service_role_key, anon_key=cfg.anon_key)


def _get_docker(actx: AppContext) -> DockerOps:
    return DockerOps(actx.config)


@app.command()
def check(ctx: typer.Context) -> None:
    """Check all services via HTTP."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        client = _get_client(actx)
        results = client.health_check()
        client.close()
    except SupabaseError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc

    table = Table(title="Service Health", show_header=True, header_style="bold cyan")
    table.add_column("Service", style="cyan")
    table.add_column("Status")

    for service, status in results.items():
        if status == "ok":
            table.add_row(service, "[green]ok[/green]")
        else:
            table.add_row(service, f"[red]{status}[/red]")

    rprint(table)


@app.command()
def db(ctx: typer.Context) -> None:
    """Check DB health via SSH."""
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        docker = _get_docker(actx)
        result = docker.docker_exec("db", "/scripts/health.sh")
        docker.close()
    except DockerError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc

    typer.echo(result)


@app.command()
def ping(ctx: typer.Context) -> None:
    """Quick connectivity check."""
    actx: AppContext = ctx.obj
    out = actx.output

    cfg = actx.config
    if not cfg.url:
        out.error("No Supabase URL configured. Run: kctl-supa config add <name> --url <url>")
        raise typer.Exit(1)

    base_url = cfg.url.rstrip("/")
    start = time.monotonic()
    try:
        response = httpx.get(f"{base_url}/", timeout=10.0)
        elapsed = (time.monotonic() - start) * 1000
        out.kv("URL", base_url)
        out.kv("Status", str(response.status_code))
        out.kv("Response time", f"{elapsed:.1f}ms")
    except httpx.ConnectError as exc:
        out.error(f"Connection failed: {exc}")
        raise typer.Exit(1) from exc
    except httpx.TimeoutException as exc:
        out.error(f"Timeout: {exc}")
        raise typer.Exit(1) from exc
