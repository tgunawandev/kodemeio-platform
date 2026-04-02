"""Smoke tests for kctl-rustdesk CLI.

Verifies that every command group registers correctly and responds to --help.
No network or SSH connections are made.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from kctl_rustdesk import __version__
from kctl_rustdesk.cli import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class TestSmoke:
    """Basic CLI smoke tests — no executor/SSH required."""

    def test_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "rustdesk" in result.output.lower()

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
        # Typer with no_args_is_help=True may return 0 or 2 depending on version
        assert result.exit_code in (0, 2)
        assert "rustdesk" in result.output.lower()

    # --- Command group --help tests ---

    def test_config_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["config", "--help"])
        assert result.exit_code == 0

    def test_health_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["health", "--help"])
        assert result.exit_code == 0

    def test_dashboard_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["dashboard", "--help"])
        assert result.exit_code == 0

    def test_peers_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["peers", "--help"])
        assert result.exit_code == 0

    def test_users_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["users", "--help"])
        assert result.exit_code == 0

    def test_audit_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["audit", "--help"])
        assert result.exit_code == 0

    def test_backup_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["backup", "--help"])
        assert result.exit_code == 0

    def test_setup_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["setup", "--help"])
        assert result.exit_code == 0

    def test_maintenance_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["maintenance", "--help"])
        assert result.exit_code == 0

    # --- Subcommand --help tests ---

    def test_health_check_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["health", "check", "--help"])
        assert result.exit_code == 0

    def test_peers_list_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["peers", "list", "--help"])
        assert result.exit_code == 0

    def test_peers_get_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["peers", "get", "--help"])
        assert result.exit_code == 0

    def test_peers_count_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["peers", "count", "--help"])
        assert result.exit_code == 0

    def test_peers_search_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["peers", "search", "--help"])
        assert result.exit_code == 0

    def test_users_list_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["users", "list", "--help"])
        assert result.exit_code == 0

    def test_users_get_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["users", "get", "--help"])
        assert result.exit_code == 0

    def test_users_count_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["users", "count", "--help"])
        assert result.exit_code == 0

    def test_backup_list_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["backup", "list", "--help"])
        assert result.exit_code == 0

    def test_setup_get_key_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["setup", "get-key", "--help"])
        assert result.exit_code == 0

    def test_maintenance_db_optimize_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["maintenance", "db-optimize", "--help"])
        assert result.exit_code == 0

    def test_maintenance_db_stats_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["maintenance", "db-stats", "--help"])
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
