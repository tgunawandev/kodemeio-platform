"""Windows service management on remote agents."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_rmm.core.callbacks import AppContext

app = typer.Typer(help="Manage Windows services on remote agents.")


@app.command("list")
def list_(
    ctx: typer.Context,
    agent_id: Annotated[str, typer.Argument(help="Agent ID")],
) -> None:
    """List Windows services on an agent."""
    c: AppContext = ctx.obj
    data = c.client.get(f"/services/{agent_id}/")

    services = data if isinstance(data, list) else data.get("results", []) if isinstance(data, dict) else []

    rows: list[list[str]] = []
    for s in services:
        status = s.get("status", "")
        status_display = "[green]running[/green]" if status.lower() == "running" else f"[dim]{status}[/dim]"
        rows.append(
            [
                s.get("name", ""),
                s.get("display_name", ""),
                status_display,
                s.get("start_type", ""),
            ]
        )

    c.output.table(
        f"Services ({len(services)})",
        [("Name", "cyan"), ("Display Name", ""), ("Status", ""), ("Start Type", "dim")],
        rows,
        data_for_json=services,
    )


@app.command()
def start(
    ctx: typer.Context,
    agent_id: Annotated[str, typer.Argument(help="Agent ID")],
    service_name: Annotated[str, typer.Argument(help="Service name")],
) -> None:
    """Start a Windows service."""
    c: AppContext = ctx.obj
    c.client.post(f"/services/{agent_id}/{service_name}/start/")
    c.output.success(f"Service '{service_name}' start command sent to {agent_id}")


@app.command()
def stop(
    ctx: typer.Context,
    agent_id: Annotated[str, typer.Argument(help="Agent ID")],
    service_name: Annotated[str, typer.Argument(help="Service name")],
) -> None:
    """Stop a Windows service."""
    c: AppContext = ctx.obj
    c.client.post(f"/services/{agent_id}/{service_name}/stop/")
    c.output.success(f"Service '{service_name}' stop command sent to {agent_id}")


@app.command()
def restart(
    ctx: typer.Context,
    agent_id: Annotated[str, typer.Argument(help="Agent ID")],
    service_name: Annotated[str, typer.Argument(help="Service name")],
) -> None:
    """Restart a Windows service."""
    c: AppContext = ctx.obj
    c.client.post(f"/services/{agent_id}/{service_name}/restart/")
    c.output.success(f"Service '{service_name}' restart command sent to {agent_id}")
