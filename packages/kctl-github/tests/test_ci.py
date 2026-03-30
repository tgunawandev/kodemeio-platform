"""Tests for ci commands."""

from __future__ import annotations

MOCK_REPOS = [
    {"name": "kodemeio-next"},
    {"name": "kodemeio-odoo"},
]


class TestCIStatus:
    def test_status_help(self, runner, cli_app):
        result = runner.invoke(cli_app, ["ci", "status", "--help"])
        assert result.exit_code == 0

    def test_status_json(self, runner, cli_app, mock_context):
        mock_context.get_repos.return_value = MOCK_REPOS
        mock_context.get.return_value = {
            "workflow_runs": [
                {"name": "CI", "conclusion": "success", "status": "completed", "created_at": "2026-03-28T10:00:00Z"}
            ],
        }
        result = runner.invoke(cli_app, ["--json", "ci", "status"])
        assert result.exit_code == 0


class TestCIShow:
    def test_show_help(self, runner, cli_app):
        result = runner.invoke(cli_app, ["ci", "show", "--help"])
        assert result.exit_code == 0
