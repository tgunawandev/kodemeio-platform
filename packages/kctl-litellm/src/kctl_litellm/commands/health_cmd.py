"""Health check commands for kctl-litellm.

Check LiteLLM proxy service health via HTTP.
"""

from __future__ import annotations

import time

import httpx
import typer
from rich import print as rprint
from rich.table import Table

from kctl_litellm.core.callbacks import AppContext
from kctl_litellm.core.client import LiteLLMClient
from kctl_litellm.core.exceptions import LiteLLMError

app = typer.Typer(help="Check LiteLLM proxy service health.")


def _get_client(actx: AppContext) -> LiteLLMClient:
    cfg = actx.config
    return LiteLLMClient(base_url=cfg.url, master_key=cfg.master_key)


@app.command()
def check(ctx: typer.Context) -> None:
    """Full health check via /health endpoint.

    Shows healthy and unhealthy models in a table.
    """
    actx: AppContext = ctx.obj
    out = actx.output

    try:
        client = _get_client(actx)
        result = client.health_check()
        client.close()
    except LiteLLMError as exc:
        out.error(str(exc))
        raise typer.Exit(1) from exc

    # Parse healthy/unhealthy models from the response
    healthy = result.get("healthy_endpoints", [])
    unhealthy = result.get("unhealthy_endpoints", [])

    table = Table(title="LiteLLM Health Check", show_header=True, header_style="bold cyan")
    table.add_column("Model", style="cyan")
    table.add_column("Status")
    table.add_column("Details")

    for endpoint in healthy:
        model = endpoint.get("model", "unknown") if isinstance(endpoint, dict) else str(endpoint)
        details = endpoint.get("api_base", "") if isinstance(endpoint, dict) else ""
        table.add_row(model, "[green]healthy[/green]", details)

    for endpoint in unhealthy:
        model = endpoint.get("model", "unknown") if isinstance(endpoint, dict) else str(endpoint)
        error = endpoint.get("error", "") if isinstance(endpoint, dict) else ""
        table.add_row(model, "[red]unhealthy[/red]", str(error)[:80])

    if not healthy and not unhealthy:
        # Simple status display if no model-level data
        status = result.get("status", "unknown")
        if status == "healthy":
            out.success("LiteLLM proxy is healthy")
        else:
            out.warn(f"LiteLLM proxy status: {status}")
        return

    rprint(table)
    out.info(f"Healthy: {len(healthy)}, Unhealthy: {len(unhealthy)}")


@app.command()
def ping(ctx: typer.Context) -> None:
    """Quick connectivity check (GET /, show status code and response time)."""
    actx: AppContext = ctx.obj
    out = actx.output

    cfg = actx.config
    if not cfg.url:
        out.error("No LiteLLM URL configured. Run: kctl-litellm config add <name> --url <url>")
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


@app.command()
def liveliness(ctx: typer.Context) -> None:
    """Quick liveness check via /health/liveliness (no auth required)."""
    actx: AppContext = ctx.obj
    out = actx.output

    cfg = actx.config
    if not cfg.url:
        out.error("No LiteLLM URL configured. Run: kctl-litellm config add <name> --url <url>")
        raise typer.Exit(1)

    base_url = cfg.url.rstrip("/")
    start = time.monotonic()
    try:
        response = httpx.get(f"{base_url}/health/liveliness", timeout=10.0)
        result = response.json()
        elapsed = (time.monotonic() - start) * 1000
    except httpx.ConnectError as exc:
        out.error(f"Connection failed: {exc}")
        raise typer.Exit(1) from exc
    except httpx.TimeoutException as exc:
        out.error(f"Timeout: {exc}")
        raise typer.Exit(1) from exc

    status = result.get("status", "unknown") if isinstance(result, dict) else str(result)
    out.kv("URL", cfg.url)
    out.kv("Status", status)
    out.kv("Response time", f"{elapsed:.1f}ms")

    if status == "alive":
        out.success("LiteLLM proxy is alive")
    else:
        out.warn(f"Unexpected status: {status}")
