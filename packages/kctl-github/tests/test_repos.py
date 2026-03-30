"""Tests for repos commands."""

from __future__ import annotations

MOCK_REPOS = [
    {
        "name": "kodemeio-next",
        "private": False,
        "default_branch": "main",
        "pushed_at": "2026-03-28T10:00:00Z",
        "description": "Next.js",
    },
    {
        "name": "kodemeio-odoo",
        "private": True,
        "default_branch": "main",
        "pushed_at": "2026-03-27T10:00:00Z",
        "description": "Odoo",
    },
]


class TestReposList:
    def test_list_help(self, runner, cli_app):
        result = runner.invoke(cli_app, ["repos", "list", "--help"])
        assert result.exit_code == 0

    def test_list_json(self, runner, cli_app, mock_context):
        mock_context.get_repos.return_value = MOCK_REPOS
        result = runner.invoke(cli_app, ["--json", "repos", "list"])
        assert result.exit_code == 0
        assert "kodemeio-next" in result.output


class TestReposShow:
    def test_show_help(self, runner, cli_app):
        result = runner.invoke(cli_app, ["repos", "show", "--help"])
        assert result.exit_code == 0

    def test_show_json(self, runner, cli_app, mock_context):
        mock_context.get_repo.return_value = {
            "name": "kodemeio-next",
            "description": "Next.js",
            "private": False,
            "default_branch": "main",
            "size": 1024,
            "open_issues_count": 3,
            "created_at": "2024-01-01T00:00:00Z",
            "pushed_at": "2026-03-28T00:00:00Z",
        }
        mock_context.get.side_effect = [
            {"Python": 50000, "TypeScript": 30000},
            [{"login": "user1", "contributions": 100}],
        ]
        result = runner.invoke(cli_app, ["--json", "repos", "show", "kodemeio-next"])
        assert result.exit_code == 0
        assert "kodemeio-next" in result.output
