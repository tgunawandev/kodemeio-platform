"""Smoke tests for all CLI commands."""

from typer.testing import CliRunner

from kctl_github.cli import app

runner = CliRunner()


class TestCLISmoke:
    def test_help_exits_zero(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0

    def test_version_flag(self):
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0

    def test_config_help(self):
        result = runner.invoke(app, ["config", "--help"])
        assert result.exit_code == 0

    def test_health_help(self):
        result = runner.invoke(app, ["health", "--help"])
        assert result.exit_code == 0

    def test_dashboard_help(self):
        result = runner.invoke(app, ["dashboard", "--help"])
        assert result.exit_code == 0

    def test_repos_help(self):
        result = runner.invoke(app, ["repos", "--help"])
        assert result.exit_code == 0

    def test_ci_help(self):
        result = runner.invoke(app, ["ci", "--help"])
        assert result.exit_code == 0

    def test_prs_help(self):
        result = runner.invoke(app, ["prs", "--help"])
        assert result.exit_code == 0

    def test_secrets_help(self):
        result = runner.invoke(app, ["secrets", "--help"])
        assert result.exit_code == 0

    def test_labels_help(self):
        result = runner.invoke(app, ["labels", "--help"])
        assert result.exit_code == 0

    def test_stats_help(self):
        result = runner.invoke(app, ["stats", "--help"])
        assert result.exit_code == 0

    def test_billing_help(self):
        result = runner.invoke(app, ["billing", "--help"])
        assert result.exit_code == 0
