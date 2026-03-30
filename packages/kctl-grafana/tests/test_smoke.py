"""Smoke tests for kctl-grafana CLI."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from kctl_grafana import __version__
from kctl_grafana.cli import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class TestSmoke:
    """Basic CLI smoke tests."""

    def test_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "kctl-grafana" in result.output.lower() or "grafana" in result.output.lower()

    def test_version(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert __version__ in result.output

    def test_no_args_shows_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, [])
        # Typer with no_args_is_help=True returns exit code 0 or 2 depending on version
        assert result.exit_code in (0, 2)
        assert "grafana" in result.output.lower()

    def test_config_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["config", "--help"])
        assert result.exit_code == 0
        assert "init" in result.output

    def test_dashboard_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["dashboard", "--help"])
        assert result.exit_code == 0

    def test_datasource_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["datasource", "--help"])
        assert result.exit_code == 0

    def test_alert_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["alert", "--help"])
        assert result.exit_code == 0

    def test_health_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["health", "--help"])
        assert result.exit_code == 0

    def test_folder_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["folder", "--help"])
        assert result.exit_code == 0

    def test_annotation_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["annotation", "--help"])
        assert result.exit_code == 0

    def test_user_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["user", "--help"])
        assert result.exit_code == 0

    def test_backup_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["backup", "--help"])
        assert result.exit_code == 0

    def test_status_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["status", "--help"])
        assert result.exit_code == 0

    def test_selftest_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["selftest", "--help"])
        assert result.exit_code == 0
