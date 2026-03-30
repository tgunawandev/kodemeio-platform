"""Tests for status command group."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from kctl_claw.cli import app

runner = CliRunner()


def test_status_overview(project_root):
    """overview shows agent/mcp/cron counts from config."""
    result = runner.invoke(app, ["--root", str(project_root), "status"])
    assert result.exit_code == 0
    # Should show counts derived from config files
    assert "5" in result.output or "Agents" in result.output
    assert "Cron" in result.output or "cron" in result.output.lower()


def test_status_overview_shows_gateway_status(project_root):
    """overview shows gateway status (may be unavailable in tests)."""
    result = runner.invoke(app, ["--root", str(project_root), "status"])
    assert result.exit_code == 0
    # Gateway will be unavailable in tests - should show gracefully
    assert "unavailable" in result.output or "unknown" in result.output or "healthy" in result.output


def test_status_overview_json(project_root):
    """overview outputs valid JSON in json mode."""
    result = runner.invoke(app, ["--root", str(project_root), "--json", "status"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "agents" in data
    assert "mcp_servers" in data
    assert "cron_jobs_enabled" in data
    assert "cron_jobs_total" in data
    assert data["agents"] == 5
    assert data["mcp_servers"] == 3


def test_status_overview_counts_match_config(project_root):
    """overview counts exactly match what's in the config files."""
    result = runner.invoke(app, ["--root", str(project_root), "--json", "status"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["agents"] == 5
    assert data["tool_profiles"] == 5
    # 3 cron jobs total, 2 enabled (weekly-content-plan is disabled)
    assert data["cron_jobs_total"] == 3
    assert data["cron_jobs_enabled"] == 2


def test_status_invoked_without_subcommand(project_root):
    """status with no subcommand shows overview (callback with invoke_without_command)."""
    result = runner.invoke(app, ["--root", str(project_root), "status"])
    assert result.exit_code == 0
    assert "OpenClaw" in result.output or "Agents" in result.output
