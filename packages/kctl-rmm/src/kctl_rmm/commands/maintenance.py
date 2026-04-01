"""Docker service maintenance commands for the RMM stack.

Note: These commands describe the expected docker compose services
and provide guidance. Actual docker commands must be run on the host
where the RMM stack is deployed.
"""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_rmm.core.callbacks import AppContext

app = typer.Typer(help="RMM stack maintenance (docker services).")

SERVICES = [
    "postgres", "mongodb", "redis", "nats",
    "tactical-init", "tactical-backend", "tactical-websocket",
    "tactical-frontend", "tactical-celery", "tactical-celerybeat",
    "meshcentral",
]


@app.command()
def status(ctx: typer.Context) -> None:
    """Show expected RMM service list and API health."""
    c: AppContext = ctx.obj

    # Check API health as proxy for stack health
    try:
        health_status, health_body = c.client.check_health()
        api_ok = health_status == 200 and health_body.get("status") == "ok"
    except Exception:
        api_ok = False

    rows: list[list[str]] = []
    for svc in SERVICES:
        if svc == "tactical-backend":
            status = "[green]reachable[/green]" if api_ok else "[red]unreachable[/red]"
        elif svc == "tactical-init":
            status = "[dim]one-shot (exits after init)[/dim]"
        else:
            status = "[dim]unknown (check via docker)[/dim]"
        rows.append([svc, status])

    c.output.table(
        "RMM Services",
        [("Service", "cyan"), ("Status", "")],
        rows,
        data_for_json=[{"service": s, "note": "check via docker compose ps"} for s in SERVICES],
    )
    c.output.info("For live container status, run on the host:")
    c.output.text("  docker compose -f docker-compose.prod.yml ps")


@app.command()
def restart(
    ctx: typer.Context,
    service: Annotated[str, typer.Argument(help=f"Service name: {', '.join(SERVICES)}")],
) -> None:
    """Show restart command for a service."""
    c: AppContext = ctx.obj

    if service not in SERVICES:
        c.output.error(f"Unknown service: {service}")
        c.output.info(f"Available: {', '.join(SERVICES)}")
        raise typer.Exit(1)

    c.output.info(f"To restart '{service}', run on the RMM host:")
    c.output.text(f"  docker compose -f docker-compose.prod.yml restart {service}")

    if service in ("tactical-celery", "tactical-celerybeat", "tactical-backend"):
        c.output.warn("Restarting this service may briefly interrupt agent communication")


@app.command()
def logs(
    ctx: typer.Context,
    service: Annotated[str, typer.Argument(help="Service name")],
    lines: Annotated[int, typer.Option("--lines", "-n", help="Number of lines to tail")] = 50,
) -> None:
    """Show log command for a service."""
    c: AppContext = ctx.obj

    if service not in SERVICES:
        c.output.error(f"Unknown service: {service}")
        c.output.info(f"Available: {', '.join(SERVICES)}")
        raise typer.Exit(1)

    c.output.info(f"To view logs for '{service}', run on the RMM host:")
    c.output.text(f"  docker compose -f docker-compose.prod.yml logs --tail {lines} -f {service}")
