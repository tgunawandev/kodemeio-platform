"""Smoke tests — verify CLI entry points and help text."""

from typer.testing import CliRunner

from kctl_sentry.cli import app

runner = CliRunner()


class TestCLISmoke:
    def test_help_exits_zero(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "kctl-sentry" in result.output.lower() or "sentry" in result.output.lower()

    def test_version_flag(self) -> None:
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_config_help(self) -> None:
        result = runner.invoke(app, ["config", "--help"])
        assert result.exit_code == 0

    def test_health_help(self) -> None:
        result = runner.invoke(app, ["health", "--help"])
        assert result.exit_code == 0

    def test_dashboard_help(self) -> None:
        result = runner.invoke(app, ["dashboard", "--help"])
        assert result.exit_code == 0

    def test_issues_help(self) -> None:
        result = runner.invoke(app, ["issues", "--help"])
        assert result.exit_code == 0

    def test_projects_help(self) -> None:
        result = runner.invoke(app, ["projects", "--help"])
        assert result.exit_code == 0

    def test_releases_help(self) -> None:
        result = runner.invoke(app, ["releases", "--help"])
        assert result.exit_code == 0

    def test_alerts_help(self) -> None:
        result = runner.invoke(app, ["alerts", "--help"])
        assert result.exit_code == 0

    def test_stats_help(self) -> None:
        result = runner.invoke(app, ["stats", "--help"])
        assert result.exit_code == 0

    def test_teams_help(self) -> None:
        result = runner.invoke(app, ["teams", "--help"])
        assert result.exit_code == 0

    def test_environments_help(self) -> None:
        result = runner.invoke(app, ["environments", "--help"])
        assert result.exit_code == 0
