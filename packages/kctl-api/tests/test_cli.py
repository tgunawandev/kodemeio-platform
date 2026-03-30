"""Tests for kctl-api CLI entry point and command registration."""

from __future__ import annotations

from typer.testing import CliRunner

from kctl_api.cli import app

runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "kctl-api" in result.output
    assert "0.1.0" in result.output


def test_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Kodemeio API CLI" in result.output


def test_all_command_groups_registered() -> None:
    """Verify all expected command groups are accessible."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0

    expected_groups = [
        "config",
        "auth",
        "health",
        "users",
        "files",
        "jobs",
        "workflows",
        "automation",
        "notifications",
        "webhooks",
        "marketplace",
        "saas",
        "stripe",
        "odoo",
        "realtime",
        "ai",
        "tenant-ai",
        "db",
        "redis",
        "streams",
        "services",
        "deploy",
        "apps",
        "dev",
        "test",
        "lint",
        "fmt",
        "build",
        "scaffold",
        "shell",
        "logs",
        "dashboard",
    ]

    for group in expected_groups:
        assert group in result.output, f"Command group '{group}' not found in --help output"


def test_apps_list() -> None:
    """Test apps list command works without API connection."""
    result = runner.invoke(app, ["apps", "list"])
    assert result.exit_code == 0
    assert "api-main" in result.output
    assert "ai-main" in result.output


def test_apps_list_json() -> None:
    """Test apps list JSON output."""
    result = runner.invoke(app, ["--json", "apps", "list"])
    assert result.exit_code == 0
    assert '"name": "api-main"' in result.output


def test_apps_info() -> None:
    """Test apps info command."""
    result = runner.invoke(app, ["apps", "info", "api-main"])
    assert result.exit_code == 0
    assert "api-main" in result.output
    assert "8000" in result.output


def test_apps_info_unknown() -> None:
    """Test apps info with unknown app."""
    result = runner.invoke(app, ["apps", "info", "nonexistent"])
    assert result.exit_code == 1


def test_config_profiles_empty() -> None:
    """Test config profiles with no config file."""
    result = runner.invoke(app, ["config", "profiles"])
    # Should not crash even without config
    assert result.exit_code == 0


def test_webhook_stubs() -> None:
    """Test webhook commands are proper stubs."""
    result = runner.invoke(app, ["webhooks", "recent"])
    assert result.exit_code == 0
    assert "not yet implemented" in result.output.lower()


def test_subcommand_help() -> None:
    """Test that subcommand help works for several groups."""
    for group in ["config", "auth", "health", "users", "db", "redis"]:
        result = runner.invoke(app, [group, "--help"])
        assert result.exit_code == 0, f"{group} --help failed"
