"""Tests for commands/status_cmd.py."""

from __future__ import annotations

from unittest.mock import patch

from typer.testing import CliRunner

from kctl_claude.cli import app

runner = CliRunner()

MOCK_STATUS = {
    "timestamp": "2025-01-01T00:00:00",
    "claude": {"installed": True, "version": "1.0.5"},
    "auth": {"credentials": True, "oauth": False},
    "config": {
        "local": {"agents": 3, "skills": 10, "commands": 2, "rules": 5},
        "repo": {},
        "sync_status": "synced",
        "sync_details": [],
    },
    "settings": {"exists": True, "hooks": True, "plugins": True, "thinking": False, "mcp": 2},
    "tools": {
        "ruff": True,
        "prettier": True,
        "pnpm": True,
        "uv": True,
        "gh": True,
        "docker": True,
        "terraform": False,
        "tmux": True,
        "kctl_installed": 5,
        "kctl_total": 14,
        "kctl_config": True,
    },
    "server": {
        "container_running": False,
        "container_healthy": False,
        "sdk_api_up": False,
        "sdk_in_flight": None,
        "sdk_max_concurrent": None,
    },
    "git": {"branch": "main", "clean": True},
    "updates": {"current": "1.0.5", "latest_npm": "1.0.5", "up_to_date": True},
}


class TestStatusCommand:
    def test_status_help(self) -> None:
        result = runner.invoke(app, ["status", "--help"])
        assert result.exit_code == 0

    def test_health_json(self) -> None:
        with patch("kctl_claude.commands.status_cmd.collect_status", return_value=MOCK_STATUS):
            result = runner.invoke(app, ["--json", "status", "health"])
        assert result.exit_code == 0
        assert "installed" in result.output

    def test_health_pretty(self) -> None:
        with patch("kctl_claude.commands.status_cmd.collect_status", return_value=MOCK_STATUS):
            result = runner.invoke(app, ["status", "health"])
        assert result.exit_code == 0

    def test_health_with_issues(self) -> None:
        data = {**MOCK_STATUS}
        data["claude"] = {"installed": False, "version": ""}
        with patch("kctl_claude.commands.status_cmd.collect_status", return_value=data):
            result = runner.invoke(app, ["status", "health"])
        assert result.exit_code == 1

    def test_updates_command(self) -> None:
        with patch("kctl_claude.commands.status_cmd.collect_status", return_value=MOCK_STATUS):
            result = runner.invoke(app, ["status", "updates"])
        assert result.exit_code == 0

    def test_updates_json(self) -> None:
        with patch("kctl_claude.commands.status_cmd.collect_status", return_value=MOCK_STATUS):
            result = runner.invoke(app, ["--json", "status", "updates"])
        assert result.exit_code == 0

    def test_dashboard_json(self) -> None:
        with patch("kctl_claude.commands.status_cmd.collect_status", return_value=MOCK_STATUS):
            result = runner.invoke(app, ["--json", "status"])
        assert result.exit_code == 0
