"""Tests for stats commands."""

from __future__ import annotations

MOCK_REPOS = [
    {"name": "kodemeio-next", "stargazers_count": 5, "forks_count": 2, "open_issues_count": 3, "size": 1024},
]


class TestStatsOverview:
    def test_overview_help(self, runner, cli_app):
        result = runner.invoke(cli_app, ["stats", "overview", "--help"])
        assert result.exit_code == 0

    def test_overview_json(self, runner, cli_app, mock_context):
        mock_context.get_repos.return_value = MOCK_REPOS
        result = runner.invoke(cli_app, ["--json", "stats", "overview"])
        assert result.exit_code == 0
        assert '"repos": 1' in result.output


class TestStatsLanguages:
    def test_languages_help(self, runner, cli_app):
        result = runner.invoke(cli_app, ["stats", "languages", "--help"])
        assert result.exit_code == 0
