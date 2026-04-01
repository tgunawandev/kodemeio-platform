"""Remote access commands -- Take Control via TRMM dashboard."""

from __future__ import annotations

import webbrowser
from typing import Annotated

import typer

from kctl_rmm.core.callbacks import AppContext
from kctl_rmm.core.config import resolve_mesh_url

app = typer.Typer(help="Remote access (Take Control, terminal, MeshCentral).")


def _frontend_url(ctx: AppContext) -> str:
    """Get TRMM frontend URL (rmm.xxx from api-rmm.xxx)."""
    api_url = ctx.client._base_url.rstrip("/")
    return api_url.replace("api-rmm.", "rmm.")


def _resolve_agent(ctx: AppContext, identifier: str) -> dict:
    """Resolve agent by ID or hostname."""
    # Try exact agent_id first
    try:
        agent = ctx.client.get(f"/agents/{identifier}/")
        if isinstance(agent, dict) and agent.get("agent_id"):
            return agent
    except Exception:
        pass

    # Search by hostname
    data = ctx.client.get("/agents/", params={"detail": "false"})
    agents = data if isinstance(data, list) else data.get("results", []) if isinstance(data, dict) else []
    for a in agents:
        if identifier.lower() in a.get("hostname", "").lower():
            # Get full details
            try:
                return ctx.client.get(f"/agents/{a['agent_id']}/")
            except Exception:
                return a
    return {}


@app.command()
def takecontrol(
    ctx: typer.Context,
    agent: Annotated[str, typer.Argument(help="Agent ID or hostname")],
) -> None:
    """Take Control of agent (opens TRMM remote desktop)."""
    c: AppContext = ctx.obj
    a = _resolve_agent(c, agent)

    if not a:
        c.output.error(f"Agent not found: {agent}")
        raise typer.Exit(1)

    agent_id = a.get("agent_id", "")
    hostname = a.get("hostname", agent)
    frontend = _frontend_url(c)

    # TRMM Take Control URL pattern
    url = f"{frontend}/takecontrol/{agent_id}"
    c.output.info(f"Taking control of {hostname}")
    c.output.success(f"Opening {url}")
    webbrowser.open(url)


@app.command()
def terminal(
    ctx: typer.Context,
    agent: Annotated[str, typer.Argument(help="Agent ID or hostname")],
) -> None:
    """Open terminal for agent via MeshCentral."""
    c: AppContext = ctx.obj
    a = _resolve_agent(c, agent)

    if not a:
        c.output.error(f"Agent not found: {agent}")
        raise typer.Exit(1)

    hostname = a.get("hostname", agent)
    mesh_node_id = a.get("mesh_node_id", "")

    mesh_url = resolve_mesh_url(c.profile)
    if mesh_url and mesh_node_id:
        url = f"{mesh_url.rstrip('/')}/#/devices/{mesh_node_id}"
    else:
        # Fallback to TRMM
        agent_id = a.get("agent_id", "")
        url = f"{_frontend_url(c)}/takecontrol/{agent_id}"

    c.output.info(f"Opening terminal for {hostname}")
    c.output.success(f"Opening {url}")
    webbrowser.open(url)


@app.command()
def mesh(ctx: typer.Context) -> None:
    """Open MeshCentral dashboard in browser."""
    c: AppContext = ctx.obj
    mesh_url = resolve_mesh_url(c.profile)
    if not mesh_url:
        c.output.error("MeshCentral URL not configured. Run: kctl-rmm config set mesh_url https://mesh.kodeme.io")
        raise typer.Exit(1)
    c.output.success(f"Opening {mesh_url}")
    webbrowser.open(mesh_url)


@app.command()
def rmm(ctx: typer.Context) -> None:
    """Open Tactical RMM dashboard in browser."""
    c: AppContext = ctx.obj
    url = _frontend_url(c)
    c.output.success(f"Opening {url}")
    webbrowser.open(url)
