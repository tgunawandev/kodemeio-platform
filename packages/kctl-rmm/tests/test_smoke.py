"""Smoke tests for kctl-rmm CLI.

Verifies that every command group registers correctly and responds to --help.
No network connections are made.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from kctl_rmm import __version__
from kctl_rmm.cli import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class TestSmoke:
    """Basic CLI smoke tests — no HTTP client required."""

    def test_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "rmm" in result.output.lower()

    def test_version(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert __version__ in result.output

    def test_version_short_flag(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["-V"])
        assert result.exit_code == 0
        assert __version__ in result.output

    def test_no_args_shows_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, [])
        assert result.exit_code in (0, 2)
        assert "rmm" in result.output.lower()

    # --- Command group --help tests ---

    def test_agents_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["agents", "--help"])
        assert result.exit_code == 0

    def test_alerts_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["alerts", "--help"])
        assert result.exit_code == 0

    def test_checks_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["checks", "--help"])
        assert result.exit_code == 0

    def test_clients_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["clients", "--help"])
        assert result.exit_code == 0

    def test_config_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["config", "--help"])
        assert result.exit_code == 0

    def test_dashboard_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["dashboard", "--help"])
        assert result.exit_code == 0

    def test_drivers_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["drivers", "--help"])
        assert result.exit_code == 0

    def test_health_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["health", "--help"])
        assert result.exit_code == 0

    def test_linux_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["linux", "--help"])
        assert result.exit_code == 0

    def test_maintenance_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["maintenance", "--help"])
        assert result.exit_code == 0

    def test_patches_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["patches", "--help"])
        assert result.exit_code == 0

    def test_remote_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["remote", "--help"])
        assert result.exit_code == 0

    def test_rustdesk_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["rustdesk", "--help"])
        assert result.exit_code == 0

    def test_scripts_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["scripts", "--help"])
        assert result.exit_code == 0

    def test_services_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["services", "--help"])
        assert result.exit_code == 0

    def test_software_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["software", "--help"])
        assert result.exit_code == 0

    def test_tasks_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["tasks", "--help"])
        assert result.exit_code == 0

    def test_winupdates_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["winupdates", "--help"])
        assert result.exit_code == 0

    # --- Key subcommand --help tests ---

    def test_agents_list_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["agents", "list", "--help"])
        assert result.exit_code == 0

    def test_agents_get_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["agents", "get", "--help"])
        assert result.exit_code == 0

    def test_agents_ping_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["agents", "ping", "--help"])
        assert result.exit_code == 0

    def test_agents_offline_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["agents", "offline", "--help"])
        assert result.exit_code == 0

    def test_checks_list_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["checks", "list", "--help"])
        assert result.exit_code == 0

    def test_checks_create_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["checks", "create", "--help"])
        assert result.exit_code == 0

    def test_checks_delete_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["checks", "delete", "--help"])
        assert result.exit_code == 0

    def test_scripts_list_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["scripts", "list", "--help"])
        assert result.exit_code == 0

    def test_rustdesk_list_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["rustdesk", "list", "--help"])
        assert result.exit_code == 0

    # --- Global option pass-through ---

    def test_json_flag_is_accepted(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["--json", "--help"])
        assert result.exit_code == 0

    def test_quiet_flag_is_accepted(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["-q", "--help"])
        assert result.exit_code == 0

    def test_format_flag_is_accepted(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["--format", "json", "--help"])
        assert result.exit_code == 0

    def test_profile_flag_is_accepted(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["--profile", "test", "--help"])
        assert result.exit_code == 0

    def test_url_flag_is_accepted(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["--url", "https://rmm.example.com", "--help"])
        assert result.exit_code == 0

    def test_api_key_flag_is_accepted(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["--api-key", "testkey123", "--help"])
        assert result.exit_code == 0
