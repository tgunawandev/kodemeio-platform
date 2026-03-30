"""Tests for billing commands."""

from __future__ import annotations


class TestBillingActions:
    def test_actions_help(self, runner, cli_app):
        result = runner.invoke(cli_app, ["billing", "actions", "--help"])
        assert result.exit_code == 0

    def test_actions_json(self, runner, cli_app, mock_context):
        mock_context.get.return_value = {
            "total_minutes_used": 500,
            "included_minutes": 2000,
            "total_paid_minutes_used": 0,
            "minutes_used_breakdown": {"UBUNTU": 450, "MACOS": 50},
        }
        result = runner.invoke(cli_app, ["--json", "billing", "actions"])
        assert result.exit_code == 0


class TestBillingOverview:
    def test_overview_help(self, runner, cli_app):
        result = runner.invoke(cli_app, ["billing", "overview", "--help"])
        assert result.exit_code == 0
