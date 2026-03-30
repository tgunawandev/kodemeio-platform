"""Tests for health command group."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from kctl_claw.cli import app

runner = CliRunner()


def test_health_check_config_files_ok(project_root):
    """check validates all config files successfully."""
    result = runner.invoke(app, ["--root", str(project_root), "health", "check"])
    # Config files exist, so no FAIL. Gateway/docker may be WARN.
    assert result.exit_code == 0
    assert "openclaw.json" in result.output
    assert "config.json" in result.output
    assert "cron/jobs.json" in result.output


def test_health_check_json(project_root):
    """check outputs valid JSON (may have warn lines mixed in)."""
    result = runner.invoke(app, ["--root", str(project_root), "--json", "health", "check"])
    assert result.exit_code == 0
    # Extract JSON array from output (warn messages may precede it)
    output = result.output
    start = output.index("[")
    data = json.loads(output[start:])
    assert isinstance(data, list)
    assert any(item["check"] == "openclaw.json" for item in data)
    assert any(item["status"] == "OK" for item in data)


def test_health_check_broken_config(project_root, tmp_path):
    """check exits 1 when config file is invalid JSON."""
    # Corrupt the openclaw.json
    (project_root / "config" / "openclaw.json").write_text("{ invalid json }")
    result = runner.invoke(app, ["--root", str(project_root), "health", "check"])
    assert result.exit_code == 1


def test_health_check_gateway_unavailable(project_root):
    """check handles gateway unavailability as warning, not failure."""
    result = runner.invoke(app, ["--root", str(project_root), "health", "check"])
    # Gateway is unavailable in tests, should be WARN not FAIL
    assert result.exit_code == 0
    # Check that gateway row shows WARN
    assert "gateway" in result.output
    assert "WARN" in result.output


def test_health_gateway_unavailable(project_root):
    """gateway subcommand shows warning when gateway is down."""
    result = runner.invoke(app, ["--root", str(project_root), "health", "gateway"])
    assert result.exit_code == 0
    # Should show warn message, not crash
    assert "unavailable" in result.output or "Gateway" in result.output
