"""Tests for dashboard command including --security."""

from __future__ import annotations

from typer.testing import CliRunner

from kctl_ak.cli import app

runner = CliRunner()


class TestDashboardHelp:
    def test_dashboard_help(self) -> None:
        result = runner.invoke(app, ["dashboard", "--help"])
        assert result.exit_code == 0
        assert "--watch" in result.output
        assert "--compact" in result.output
        assert "--security" in result.output

    def test_dashboard_security_flag_exists(self) -> None:
        """Verify --security is a valid option."""
        result = runner.invoke(app, ["dashboard", "--help"])
        assert "--security" in result.output
