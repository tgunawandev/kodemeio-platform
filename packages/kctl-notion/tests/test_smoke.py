"""Smoke tests for CLI entry points."""

from typer.testing import CliRunner

from kctl_notion.cli import app

runner = CliRunner()


class TestCLISmoke:
    def test_help_exits_zero(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0

    def test_version_flag(self):
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "kctl-notion" in result.output

    def test_config_help(self):
        result = runner.invoke(app, ["config", "--help"])
        assert result.exit_code == 0

    def test_health_help(self):
        result = runner.invoke(app, ["health", "--help"])
        assert result.exit_code == 0

    def test_search_help(self):
        result = runner.invoke(app, ["search", "--help"])
        assert result.exit_code == 0

    def test_pages_help(self):
        result = runner.invoke(app, ["pages", "--help"])
        assert result.exit_code == 0

    def test_databases_help(self):
        result = runner.invoke(app, ["databases", "--help"])
        assert result.exit_code == 0

    def test_blocks_help(self):
        result = runner.invoke(app, ["blocks", "--help"])
        assert result.exit_code == 0

    def test_users_help(self):
        result = runner.invoke(app, ["users", "--help"])
        assert result.exit_code == 0
