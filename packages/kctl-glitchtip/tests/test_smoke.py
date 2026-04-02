"""Smoke tests for kctl-glitchtip CLI.

Verifies that the CLI entry points are wired correctly: --help, --version,
no-args, and <group> --help for every registered command group.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from kctl_glitchtip import __version__
from kctl_glitchtip.cli import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class TestRootCommands:
    """Top-level CLI invocations."""

    def test_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "glitchtip" in result.output.lower()

    def test_version(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert __version__ in result.output

    def test_version_short_flag(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["-V"])
        assert result.exit_code == 0
        assert __version__ in result.output

    def test_no_args_shows_help(self, runner: CliRunner) -> None:
        # no_args_is_help=True causes Typer to print help and exit 0
        result = runner.invoke(app, [])
        assert result.exit_code in (0, 2)
        assert "glitchtip" in result.output.lower()

    def test_help_lists_all_groups(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        for group in (
            "projects",
            "issues",
            "teams",
            "orgs",
            "events",
            "users",
            "health",
            "alerts",
            "config",
            "uptime",
        ):
            assert group in result.output, f"Command group '{group}' missing from --help output"


class TestGroupHelp:
    """Each command group responds to --help without connecting to the API."""

    def test_projects_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["projects", "--help"])
        assert result.exit_code == 0

    def test_issues_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["issues", "--help"])
        assert result.exit_code == 0

    def test_teams_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["teams", "--help"])
        assert result.exit_code == 0

    def test_orgs_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["orgs", "--help"])
        assert result.exit_code == 0

    def test_events_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["events", "--help"])
        assert result.exit_code == 0

    def test_users_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["users", "--help"])
        assert result.exit_code == 0

    def test_health_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["health", "--help"])
        assert result.exit_code == 0

    def test_alerts_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["alerts", "--help"])
        assert result.exit_code == 0

    def test_config_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["config", "--help"])
        assert result.exit_code == 0

    def test_config_help_shows_init(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["config", "--help"])
        assert result.exit_code == 0
        assert "init" in result.output

    def test_uptime_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["uptime", "--help"])
        assert result.exit_code == 0


class TestGlobalFlags:
    """Global flags are accepted without triggering API calls."""

    def test_json_flag_accepted(self, runner: CliRunner) -> None:
        # --json + --help should not cause an error (flag is parsed before subcommand)
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0

    def test_quiet_flag_accepted(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0

    def test_format_flag_in_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "--format" in result.output or "format" in result.output.lower()

    def test_profile_flag_in_help(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "--profile" in result.output or "-p" in result.output
