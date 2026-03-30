"""Tests for prs commands."""

from __future__ import annotations

MOCK_REPOS = [{"name": "kodemeio-next"}]


class TestPRsList:
    def test_list_help(self, runner, cli_app):
        result = runner.invoke(cli_app, ["prs", "list", "--help"])
        assert result.exit_code == 0

    def test_list_json(self, runner, cli_app, mock_context):
        mock_context.get_repos.return_value = MOCK_REPOS
        mock_context.get.return_value = [
            {
                "number": 1,
                "title": "Fix bug",
                "user": {"login": "dev1"},
                "created_at": "2026-03-27T00:00:00Z",
                "draft": False,
                "labels": [],
            },
        ]
        result = runner.invoke(cli_app, ["--json", "prs", "list"])
        assert result.exit_code == 0
        assert "Fix bug" in result.output


class TestPRsStale:
    def test_stale_help(self, runner, cli_app):
        result = runner.invoke(cli_app, ["prs", "stale", "--help"])
        assert result.exit_code == 0
