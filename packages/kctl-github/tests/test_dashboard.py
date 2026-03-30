"""Tests for dashboard command."""

from __future__ import annotations


class TestDashboard:
    def test_dashboard_help(self, runner, cli_app):
        result = runner.invoke(cli_app, ["dashboard", "--help"])
        assert result.exit_code == 0
