"""Tests for name/ID resolution helpers."""

from __future__ import annotations

import json

import pytest

from kctl_claw.core.config_manager import ConfigManager
from kctl_claw.core.exceptions import NotFoundError
from kctl_claw.core.resolve import (
    get_all_agents,
    get_all_cron_jobs,
    get_all_mcp_servers,
    get_tool_profiles,
    resolve_agent,
    resolve_cron_job,
    resolve_mcp_server,
)


def _make_project(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "cron").mkdir()
    openclaw = {
        "agents": {
            "list": [
                {"name": "kodemeiodev", "model": "opus"},
                {"name": "kontenosdev", "model": "sonnet"},
            ]
        },
        "tools": {
            "profiles": {
                "default": {"servers": ["odoo", "prometheus"]},
            }
        },
    }
    (tmp_path / "config" / "openclaw.json").write_text(json.dumps(openclaw))
    mcp = {
        "mcpServers": {
            "kodemeio-mcp-odoo": {"command": "node", "args": ["/opt/odoo.mjs"]},
            "kodemeio-mcp-prometheus": {"command": "node", "args": ["/opt/prometheus.mjs"]},
        }
    }
    (tmp_path / "config" / "config.json").write_text(json.dumps(mcp))
    jobs = {
        "jobs": [
            {"id": "morning-briefing", "name": "Morning Briefing", "schedule": "0 7 * * *", "enabled": True},
            {"id": "health-check", "name": "Health Check", "schedule": "0 */6 * * *", "enabled": True},
        ]
    }
    (tmp_path / "config" / "cron" / "jobs.json").write_text(json.dumps(jobs))
    return ConfigManager(tmp_path)


def test_resolve_agent_found(tmp_path):
    mgr = _make_project(tmp_path)
    agent = resolve_agent(mgr, "kodemeiodev")
    assert agent["name"] == "kodemeiodev"


def test_resolve_agent_not_found(tmp_path):
    mgr = _make_project(tmp_path)
    with pytest.raises(NotFoundError) as exc_info:
        resolve_agent(mgr, "nonexistent")
    assert "kodemeiodev" in str(exc_info.value)


def test_resolve_cron_job_found(tmp_path):
    mgr = _make_project(tmp_path)
    job = resolve_cron_job(mgr, "morning-briefing")
    assert job["id"] == "morning-briefing"


def test_resolve_cron_job_not_found(tmp_path):
    mgr = _make_project(tmp_path)
    with pytest.raises(NotFoundError):
        resolve_cron_job(mgr, "nonexistent")


def test_resolve_mcp_server_found(tmp_path):
    mgr = _make_project(tmp_path)
    server = resolve_mcp_server(mgr, "kodemeio-mcp-odoo")
    assert server["command"] == "node"


def test_resolve_mcp_server_not_found(tmp_path):
    mgr = _make_project(tmp_path)
    with pytest.raises(NotFoundError):
        resolve_mcp_server(mgr, "nonexistent")


def test_get_all_agents(tmp_path):
    mgr = _make_project(tmp_path)
    agents = get_all_agents(mgr)
    assert len(agents) == 2
    assert agents[0]["name"] == "kodemeiodev"


def test_get_all_cron_jobs(tmp_path):
    mgr = _make_project(tmp_path)
    jobs = get_all_cron_jobs(mgr)
    assert len(jobs) == 2
    assert jobs[0]["id"] == "morning-briefing"


def test_get_all_mcp_servers(tmp_path):
    mgr = _make_project(tmp_path)
    servers = get_all_mcp_servers(mgr)
    assert "kodemeio-mcp-odoo" in servers
    assert "kodemeio-mcp-prometheus" in servers


def test_get_tool_profiles(tmp_path):
    mgr = _make_project(tmp_path)
    profiles = get_tool_profiles(mgr)
    assert "default" in profiles
    assert "odoo" in profiles["default"]["servers"]


# Tests using project_root fixture from conftest.py


def test_resolve_agent_from_fixture(config_mgr):
    agent = resolve_agent(config_mgr, "journaltxdev")
    assert agent["model"] == "claude-sonnet-4-20250514"


def test_resolve_mcp_server_from_fixture(config_mgr):
    server = resolve_mcp_server(config_mgr, "brave-search")
    assert server["command"] == "npx"


def test_resolve_cron_job_from_fixture(config_mgr):
    job = resolve_cron_job(config_mgr, "system-health-check")
    assert job["silent"] is True
