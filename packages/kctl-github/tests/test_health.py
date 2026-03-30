"""Tests for health command."""

from __future__ import annotations


class TestHealth:
    def test_health_help(self, runner, cli_app):
        result = runner.invoke(cli_app, ["health", "--help"])
        assert result.exit_code == 0
        assert "rate limit" in result.output.lower() or "connectivity" in result.output.lower()

    def test_health_json(self, runner, cli_app, mock_context):
        mock_context.get.side_effect = [
            {"resources": {"core": {"remaining": 4999, "limit": 5000}, "search": {"remaining": 30, "limit": 30}}},
            {"login": "testuser", "name": "Test", "plan": {"name": "free"}},
        ]
        result = runner.invoke(cli_app, ["--json", "health"])
        assert result.exit_code == 0
        assert "healthy" in result.output
