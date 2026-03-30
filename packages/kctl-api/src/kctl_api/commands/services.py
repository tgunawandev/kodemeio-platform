"""Docker Compose service management commands for kctl-api.

List, start, stop, restart, and view logs for services.
"""

from __future__ import annotations

import subprocess
from typing import Annotated

import typer

from kctl_api.core.callbacks import AppContext
from kctl_api.core.utils import find_project_root

app = typer.Typer(name="services", help="Docker Compose services — list, status, restart, logs.", no_args_is_help=True)


def _compose_cmd(args: list[str]) -> list[str]:
    """Build a docker compose command rooted at the project."""
    root = find_project_root()
    return ["docker", "compose", "-f", str(root / "docker-compose.yml"), *args]


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------
@app.command(name="list")
def list_services(ctx: typer.Context) -> None:
    """List all docker compose services and their status."""
    actx: AppContext = ctx.obj
    out = actx.output

    result = subprocess.run(
        _compose_cmd(["ps", "--format", "json"]),
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        out.error(f"docker compose ps failed: {result.stderr.strip()}")
        raise typer.Exit(1)

    import json

    services: list[dict] = []
    for line in result.stdout.strip().splitlines():
        if line.strip():
            try:
                services.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    if actx.json_mode:
        out.raw_json(services)
        return

    rows: list[list[str]] = []
    for svc in services:
        name = svc.get("Name", svc.get("Service", ""))
        state = svc.get("State", svc.get("Status", ""))
        health = svc.get("Health", "")
        ports = svc.get("Publishers", svc.get("Ports", ""))
        if isinstance(ports, list):
            ports = ", ".join(
                f"{p.get('PublishedPort', '')}:{p.get('TargetPort', '')}" for p in ports if p.get("PublishedPort")
            )
        rows.append([name, str(state), str(health), str(ports)])

    out.table(
        title="Docker Compose Services",
        columns=[
            ("Name", "bold"),
            ("State", ""),
            ("Health", ""),
            ("Ports", "dim"),
        ],
        rows=rows,
        data_for_json=services,
    )


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------
@app.command()
def status(
    ctx: typer.Context,
    service: Annotated[str, typer.Argument(help="Service name.")],
) -> None:
    """Show status of a specific docker compose service."""
    actx: AppContext = ctx.obj
    result = subprocess.run(
        _compose_cmd(["ps", service]),
        capture_output=False,
    )
    if result.returncode != 0:
        actx.output.error(f"Service '{service}' not found or not running.")
        raise typer.Exit(result.returncode)


# ---------------------------------------------------------------------------
# restart
# ---------------------------------------------------------------------------
@app.command()
def restart(
    ctx: typer.Context,
    service: Annotated[str, typer.Argument(help="Service name to restart.")],
) -> None:
    """Restart a docker compose service."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info(f"Restarting {service} ...")
    result = subprocess.run(_compose_cmd(["restart", service]), capture_output=False)
    if result.returncode != 0:
        out.error(f"Failed to restart {service}.")
        raise typer.Exit(result.returncode)
    out.success(f"Service {service} restarted.")


# ---------------------------------------------------------------------------
# logs
# ---------------------------------------------------------------------------
@app.command()
def logs(
    ctx: typer.Context,
    service: Annotated[str, typer.Argument(help="Service name.")],
    follow: Annotated[bool, typer.Option("--follow", "-f", help="Follow log output.")] = False,
    tail: Annotated[int, typer.Option("--tail", "-n", help="Number of lines to show.")] = 100,
) -> None:
    """View logs for a docker compose service."""
    cmd = _compose_cmd(["logs", "--tail", str(tail)])
    if follow:
        cmd.append("--follow")
    cmd.append(service)
    subprocess.run(cmd, capture_output=False)


# ---------------------------------------------------------------------------
# up
# ---------------------------------------------------------------------------
@app.command()
def up(
    ctx: typer.Context,
    service: Annotated[str | None, typer.Argument(help="Service name (all if omitted).")] = None,
    build: Annotated[bool, typer.Option("--build", help="Rebuild images.")] = False,
    detach: Annotated[bool, typer.Option("--detach", "-d", help="Detached mode.")] = True,
) -> None:
    """Start docker compose services."""
    actx: AppContext = ctx.obj
    out = actx.output

    cmd = _compose_cmd(["up"])
    if build:
        cmd.append("--build")
    if detach:
        cmd.append("-d")
    if service:
        cmd.append(service)

    out.info("Starting services ...")
    result = subprocess.run(cmd, capture_output=False)
    if result.returncode != 0:
        out.error("Failed to start services.")
        raise typer.Exit(result.returncode)
    out.success("Services started.")


# ---------------------------------------------------------------------------
# down
# ---------------------------------------------------------------------------
@app.command()
def down(
    ctx: typer.Context,
    volumes: Annotated[bool, typer.Option("--volumes", "-v", help="Remove volumes too.")] = False,
) -> None:
    """Stop and remove docker compose services."""
    actx: AppContext = ctx.obj
    out = actx.output

    cmd = _compose_cmd(["down"])
    if volumes:
        cmd.append("--volumes")

    out.info("Stopping services ...")
    result = subprocess.run(cmd, capture_output=False)
    if result.returncode != 0:
        out.error("Failed to stop services.")
        raise typer.Exit(result.returncode)
    out.success("Services stopped.")
