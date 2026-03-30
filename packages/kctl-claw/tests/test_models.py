"""Tests for Pydantic data models."""

from __future__ import annotations

from kctl_claw.core.models import (
    AgentConfig,
    CronJob,
    HealthStatus,
    McpServer,
    McpTestResult,
    RetryConfig,
    ToolProfile,
)


def test_agent_config_defaults():
    agent = AgentConfig(name="test", model="claude-opus-4-6", profile="default")
    assert agent.thinking == "adaptive"
    assert agent.sandbox is True


def test_cron_job_with_retry():
    job = CronJob(
        id="test-job",
        name="Test Job",
        schedule="0 7 * * *",
        agent="kodemeiodev",
        prompt="Do something",
        retry=RetryConfig(max_attempts=3, backoff="exponential"),
    )
    assert job.enabled is True
    assert job.retry is not None
    assert job.retry.max_attempts == 3


def test_mcp_server():
    server = McpServer(command="node", args=["/opt/mcp-servers/test.mjs"])
    assert server.disabled is False
    assert server.env == {}


def test_tool_profile():
    profile = ToolProfile(name="default", servers=["odoo", "prometheus"])
    assert len(profile.servers) == 2
    assert profile.denied_tools == []


def test_health_status():
    status = HealthStatus(
        healthy=True,
        uptime_seconds=86400,
        version="2026.3.24",
        agents_active=3,
        mcp_servers_connected=22,
        memory_usage_mb=512.0,
    )
    assert status.healthy is True


def test_mcp_test_result_failure():
    result = McpTestResult(server="test", connected=False, tools_count=0, error="Connection refused")
    assert result.connected is False
    assert result.error == "Connection refused"
