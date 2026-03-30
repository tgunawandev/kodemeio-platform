"""Production monitoring commands for kctl-api.

Real-time metrics, alerts, and uptime monitoring.
"""

from __future__ import annotations

import time
from typing import Annotated

import typer

from kctl_api.core.callbacks import AppContext

app = typer.Typer(name="monitor", help="Production monitoring — live, metrics, uptime.", no_args_is_help=True)


# ---------------------------------------------------------------------------
# live
# ---------------------------------------------------------------------------
@app.command()
def live(
    ctx: typer.Context,
    interval: Annotated[int, typer.Option("--interval", "-i", help="Refresh interval in seconds.")] = 5,
) -> None:
    """Live dashboard — API health, DB, Redis, container status refreshed every N seconds."""
    actx: AppContext = ctx.obj
    out = actx.output

    import asyncio
    import contextlib
    import datetime
    import subprocess

    from kctl_api.core.utils import find_project_root

    root = find_project_root()

    def _get_container_status() -> list[dict]:
        result = subprocess.run(
            ["docker", "compose", "-f", str(root / "docker-compose.yml"), "ps", "--format", "json"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return []
        import json

        containers = []
        for line in result.stdout.strip().splitlines():
            if line.strip():
                with contextlib.suppress(json.JSONDecodeError):
                    containers.append(json.loads(line))
        return containers

    async def _check_services() -> dict:
        checks: dict[str, str] = {}

        # API
        try:
            healthy, _ = actx.client.health_check()
            checks["api-main"] = "[green]ok[/green]" if healthy else "[red]error[/red]"
        except Exception:
            checks["api-main"] = "[red]down[/red]"

        # DB
        try:
            from kctl_api.core.db import dispose_engine, execute_query

            db_url = actx.database_url
            if db_url:
                await execute_query(db_url, "SELECT 1")
                await dispose_engine()
                checks["postgresql"] = "[green]ok[/green]"
            else:
                checks["postgresql"] = "[yellow]no url[/yellow]"
        except Exception:
            checks["postgresql"] = "[red]error[/red]"

        # Redis
        try:
            from kctl_api.core.redis import close_redis, get_redis

            redis_url = actx.redis_url
            if redis_url:
                client = get_redis(redis_url)
                await client.ping()
                await close_redis()
                checks["redis"] = "[green]ok[/green]"
            else:
                checks["redis"] = "[yellow]no url[/yellow]"
        except Exception:
            checks["redis"] = "[red]error[/red]"

        return checks

    console = out.console  # type: ignore[attr-defined]

    try:
        while True:
            console.clear()
            now = datetime.datetime.now(tz=datetime.UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
            out.header(f"Live Monitor — {now} (refreshing every {interval}s)")

            # Service checks
            checks = asyncio.run(_check_services())
            out.text("")
            out.text("  [bold]Services:[/bold]")
            for svc, status in checks.items():
                out.text(f"    {svc:<20} {status}")

            # Container status
            containers = _get_container_status()
            if containers:
                out.text("")
                out.text("  [bold]Containers:[/bold]")
                for c in containers:
                    name = c.get("Name", c.get("Service", ""))
                    state = c.get("State", c.get("Status", ""))
                    health = c.get("Health", "")
                    indicator = "[green]up[/green]" if "running" in state.lower() else "[red]down[/red]"
                    health_str = f" ({health})" if health else ""
                    out.text(f"    {name:<30} {indicator}{health_str}")

            out.text("")
            out.text("  [dim]Press Ctrl+C to stop[/dim]")

            time.sleep(interval)
    except KeyboardInterrupt:
        out.info("Monitoring stopped.")


# ---------------------------------------------------------------------------
# metrics
# ---------------------------------------------------------------------------
@app.command()
def metrics(ctx: typer.Context) -> None:
    """Fetch metrics from the API (Prometheus endpoint if available)."""
    actx: AppContext = ctx.obj
    out = actx.output

    # Try /metrics endpoint (Prometheus format)
    metrics_endpoints = ["/metrics", "/api/v1/metrics", "/api/v1/health"]

    for endpoint in metrics_endpoints:
        try:
            response = actx.client.get_raw(endpoint)
            if response.status_code == 200:
                content_type = response.headers.get("content-type", "")
                if "text/plain" in content_type or "prometheus" in content_type:
                    out.header(f"Metrics: {endpoint}")
                    # Show first 50 lines
                    lines = response.text.splitlines()[:50]
                    for line in lines:
                        if not line.startswith("#"):
                            out.text(f"  {line}")
                    if len(response.text.splitlines()) > 50:
                        out.text(f"  ... ({len(response.text.splitlines())} total lines)")
                    return
                elif "json" in content_type:
                    import json

                    data = json.loads(response.text)
                    out.detail(
                        title=f"Metrics: {endpoint}",
                        sections=[("Data", [(k, str(v)) for k, v in data.items() if not isinstance(v, dict)])],
                        data_for_json=data,
                    )
                    return
        except Exception:
            continue

    out.warn("No metrics endpoint found. Consider adding prometheus-fastapi-instrumentator.")
    out.info("  uv add prometheus-fastapi-instrumentator")
    out.info("  Exposes: GET /metrics (Prometheus format)")


# ---------------------------------------------------------------------------
# uptime
# ---------------------------------------------------------------------------
@app.command()
def uptime(
    ctx: typer.Context,
    duration: Annotated[int, typer.Option("--duration", help="Monitor uptime for N seconds (0 = single check).")] = 0,
    interval: Annotated[int, typer.Option("--interval", "-i", help="Check interval in seconds.")] = 10,
) -> None:
    """Monitor API uptime — single check or continuous with SLA tracking."""
    actx: AppContext = ctx.obj
    out = actx.output

    def _check() -> tuple[bool, float]:
        start = time.monotonic()
        try:
            healthy, _ = actx.client.health_check()
            elapsed_ms = (time.monotonic() - start) * 1000
            return healthy, round(elapsed_ms, 1)
        except Exception:
            elapsed_ms = (time.monotonic() - start) * 1000
            return False, round(elapsed_ms, 1)

    if duration == 0:
        # Single check
        healthy, latency_ms = _check()
        status = "[green]UP[/green]" if healthy else "[red]DOWN[/red]"
        out.text(f"  Status:  {status}")
        out.text(f"  Latency: {latency_ms}ms")
        if actx.json_mode:
            out.raw_json({"healthy": healthy, "latency_ms": latency_ms})
        if not healthy:
            raise typer.Exit(1)
        return

    # Continuous monitoring
    out.info(f"Monitoring uptime for {duration}s (interval={interval}s) ...")
    checks: list[tuple[bool, float]] = []
    deadline = time.monotonic() + duration

    try:
        while time.monotonic() < deadline:
            healthy, latency_ms = _check()
            checks.append((healthy, latency_ms))
            status = "[green]UP[/green]" if healthy else "[red]DOWN[/red]"
            out.text(f"  [{len(checks)}] {status} ({latency_ms}ms)")
            if time.monotonic() < deadline:
                time.sleep(min(interval, deadline - time.monotonic()))
    except KeyboardInterrupt:
        out.info("Stopped.")

    if not checks:
        return

    total = len(checks)
    up_count = sum(1 for h, _ in checks if h)
    sla = round(up_count / total * 100, 2)
    avg_lat = round(sum(lat for _, lat in checks) / total, 1)

    out.text("")
    out.text(f"  Checks:     {total}")
    out.text(f"  Uptime:     [{'green' if sla >= 99 else 'yellow'}]{sla}%[/{'green' if sla >= 99 else 'yellow'}]")
    out.text(f"  Avg latency: {avg_lat}ms")

    if actx.json_mode:
        out.raw_json({"total": total, "up": up_count, "sla_pct": sla, "avg_latency_ms": avg_lat})
