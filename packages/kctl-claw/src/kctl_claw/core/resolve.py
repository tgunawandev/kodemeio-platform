"""Name/ID resolution helpers for agents, cron jobs, and MCP servers."""

from __future__ import annotations

from typing import Any, cast

from kctl_claw.core.config_manager import ConfigFile, ConfigManager
from kctl_claw.core.exceptions import NotFoundError


def resolve_agent(mgr: ConfigManager, name: str) -> dict[str, Any]:
    """Resolve agent by name from openclaw.json."""
    data = mgr.read(ConfigFile.OPENCLAW)
    agents: list[dict[str, Any]] = cast(list[dict[str, Any]], data.get("agents", {}).get("list", []))
    valid_names = [a["name"] for a in agents]
    for agent in agents:
        if agent["name"] == name:
            return agent
    raise NotFoundError("agent", name, valid_names=valid_names)


def resolve_cron_job(mgr: ConfigManager, job_id: str) -> dict[str, Any]:
    """Resolve cron job by id from jobs.json."""
    data = mgr.read(ConfigFile.CRON_JOBS)
    jobs: list[dict[str, Any]] = cast(list[dict[str, Any]], data.get("jobs", []))
    valid_ids = [j["id"] for j in jobs]
    for job in jobs:
        if job["id"] == job_id:
            return job
    raise NotFoundError("cron job", job_id, valid_names=valid_ids)


def resolve_mcp_server(mgr: ConfigManager, server_name: str) -> dict[str, Any]:
    """Resolve MCP server by name from config.json."""
    data = mgr.read(ConfigFile.MCP_REGISTRY)
    servers: dict[str, dict[str, Any]] = cast(dict[str, dict[str, Any]], data.get("mcpServers", {}))
    if server_name in servers:
        return servers[server_name]
    raise NotFoundError("MCP server", server_name, valid_names=list(servers.keys()))


def get_all_agents(mgr: ConfigManager) -> list[dict[str, Any]]:
    """Get all agents from openclaw.json."""
    data = mgr.read(ConfigFile.OPENCLAW)
    return cast(list[dict[str, Any]], data.get("agents", {}).get("list", []))


def get_all_cron_jobs(mgr: ConfigManager) -> list[dict[str, Any]]:
    """Get all cron jobs from jobs.json."""
    data = mgr.read(ConfigFile.CRON_JOBS)
    return cast(list[dict[str, Any]], data.get("jobs", []))


def get_all_mcp_servers(mgr: ConfigManager) -> dict[str, dict[str, Any]]:
    """Get all MCP servers from config.json."""
    data = mgr.read(ConfigFile.MCP_REGISTRY)
    return cast(dict[str, dict[str, Any]], data.get("mcpServers", {}))


def get_tool_profiles(mgr: ConfigManager) -> dict[str, Any]:
    """Get tool profiles from openclaw.json."""
    data = mgr.read(ConfigFile.OPENCLAW)
    return cast(dict[str, Any], data.get("tools", {}).get("profiles", {}))
