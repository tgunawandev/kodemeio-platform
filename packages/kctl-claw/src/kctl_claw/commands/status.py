"""Status dashboard commands."""

from __future__ import annotations

import typer

from kctl_claw.core.callbacks import AppContext
from kctl_claw.core.config_manager import ConfigFile
from kctl_claw.core.exceptions import GatewayError

app = typer.Typer(help="Quick status dashboard.")


@app.callback(invoke_without_command=True)
def overview(ctx: typer.Context) -> None:
    """Show one-screen status overview: agents, cron, MCP, gateway."""
    if ctx.invoked_subcommand is not None:
        return

    actx: AppContext = ctx.obj
    out = actx.output
    mgr = actx.config_mgr

    # Config-based counts (always available)
    openclaw = mgr.read(ConfigFile.OPENCLAW)
    agents = openclaw.get("agents", {}).get("list", [])
    profiles = openclaw.get("tools", {}).get("profiles", {})

    mcp_data = mgr.read(ConfigFile.MCP_REGISTRY)
    mcp_servers = mcp_data.get("mcpServers", {})

    cron_data = mgr.read(ConfigFile.CRON_JOBS)
    jobs = cron_data.get("jobs", [])
    enabled_jobs = [j for j in jobs if j.get("enabled", True)]

    # Gateway status (optional)
    gw_status = "unknown"
    try:
        actx.gateway.health()
        gw_status = "healthy"
    except GatewayError:
        gw_status = "unavailable"
    except Exception:
        gw_status = "unavailable"

    # Docker status (optional)
    docker_status = "unknown"
    try:
        actx.docker.ps()
        docker_status = "running"
    except Exception:
        docker_status = "unavailable"

    sections = [
        (
            "Overview",
            [
                ("Agents", f"{len(agents)} configured"),
                ("MCP Servers", f"{len(mcp_servers)} registered"),
                ("Tool Profiles", f"{len(profiles)} profiles"),
                ("Cron Jobs", f"{len(enabled_jobs)}/{len(jobs)} enabled"),
                ("Gateway", gw_status),
                ("Docker", docker_status),
            ],
        ),
    ]

    json_data = {
        "agents": len(agents),
        "mcp_servers": len(mcp_servers),
        "tool_profiles": len(profiles),
        "cron_jobs_enabled": len(enabled_jobs),
        "cron_jobs_total": len(jobs),
        "gateway": gw_status,
        "docker": docker_status,
    }

    out.detail("OpenClaw Status", sections, data_for_json=json_data)
