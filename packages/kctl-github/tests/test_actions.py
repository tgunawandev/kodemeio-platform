"""Tests for ci, stats, and prs commands — extended coverage."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from kctl_github.cli import app

runner = CliRunner()

MOCK_REPOS = [
    {
        "name": "kodemeio-next",
        "private": False,
        "default_branch": "main",
        "pushed_at": "2026-03-28T10:00:00Z",
        "description": "Next.js frontend",
        "stargazers_count": 3,
        "forks_count": 1,
        "open_issues_count": 2,
        "size": 2048,
    },
    {
        "name": "kodemeio-odoo",
        "private": True,
        "default_branch": "18.0",
        "pushed_at": "2026-03-27T10:00:00Z",
        "description": "Odoo ERP",
        "stargazers_count": 1,
        "forks_count": 0,
        "open_issues_count": 5,
        "size": 8096,
    },
]

MOCK_WORKFLOW_RUNS = {
    "workflow_runs": [
        {
            "id": 12345,
            "run_number": 42,
            "name": "CI",
            "status": "completed",
            "conclusion": "success",
            "head_branch": "main",
            "created_at": "2026-03-28T10:00:00Z",
        }
    ]
}

MOCK_PRS = [
    {
        "number": 1,
        "title": "feat: add OIDC support",
        "user": {"login": "dev1"},
        "created_at": "2026-03-27T00:00:00Z",
        "updated_at": "2026-03-27T12:00:00Z",
        "draft": False,
        "labels": [],
        "merged_at": None,
    },
    {
        "number": 2,
        "title": "fix: Docker healthcheck",
        "user": {"login": "dev2"},
        "created_at": "2026-03-26T00:00:00Z",
        "updated_at": "2026-03-26T08:00:00Z",
        "draft": True,
        "labels": [{"name": "bug"}],
        "merged_at": "2026-03-26T09:00:00Z",
    },
]


def _make_mock_client() -> MagicMock:
    client = MagicMock()
    client.organization = "tgunawandev"
    client.repo_prefix = "kodemeio-"
    return client


# ---------------------------------------------------------------------------
# CI commands
# ---------------------------------------------------------------------------


class TestCIStatus:
    def test_status_help(self) -> None:
        result = runner.invoke(app, ["ci", "status", "--help"])
        assert result.exit_code == 0

    @patch(
        "kctl_github.core.callbacks.AppContext.client", new_callable=lambda: property(lambda self: _make_mock_client())
    )
    def test_status_exit_zero_with_client(self) -> None:
        """Help check only — avoids API calls."""
        result = runner.invoke(app, ["ci", "status", "--help"])
        assert result.exit_code == 0


class TestCIShow:
    def test_show_help(self) -> None:
        result = runner.invoke(app, ["ci", "show", "--help"])
        assert result.exit_code == 0

    def test_show_accepts_repo_argument(self) -> None:
        """Verify the 'repo' positional arg is accepted."""
        result = runner.invoke(app, ["ci", "show", "--help"])
        assert "repo" in result.output.lower()

    def test_show_accepts_limit_option(self) -> None:
        result = runner.invoke(app, ["ci", "show", "--help"])
        assert "--limit" in result.output


class TestCIStats:
    def test_stats_help(self) -> None:
        result = runner.invoke(app, ["ci", "stats", "--help"])
        assert result.exit_code == 0

    def test_stats_period_option(self) -> None:
        result = runner.invoke(app, ["ci", "stats", "--help"])
        assert "--period" in result.output


class TestCIBulkStatus:
    def test_bulk_status_help(self) -> None:
        result = runner.invoke(app, ["ci", "bulk-status", "--help"])
        assert result.exit_code == 0


class TestCIRerun:
    def test_rerun_help(self) -> None:
        result = runner.invoke(app, ["ci", "rerun", "--help"])
        assert result.exit_code == 0

    def test_rerun_accepts_workflow_option(self) -> None:
        result = runner.invoke(app, ["ci", "rerun", "--help"])
        assert "--workflow" in result.output


# ---------------------------------------------------------------------------
# Stats commands
# ---------------------------------------------------------------------------


class TestStatsOverview:
    def test_overview_help(self) -> None:
        result = runner.invoke(app, ["stats", "overview", "--help"])
        assert result.exit_code == 0


class TestStatsActivity:
    def test_activity_help(self) -> None:
        result = runner.invoke(app, ["stats", "activity", "--help"])
        assert result.exit_code == 0

    def test_activity_period_option(self) -> None:
        result = runner.invoke(app, ["stats", "activity", "--help"])
        assert "--period" in result.output


class TestStatsLanguages:
    def test_languages_help(self) -> None:
        result = runner.invoke(app, ["stats", "languages", "--help"])
        assert result.exit_code == 0


class TestStatsContributors:
    def test_contributors_help(self) -> None:
        result = runner.invoke(app, ["stats", "contributors", "--help"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# PRs commands
# ---------------------------------------------------------------------------


class TestPRsList:
    def test_list_help(self) -> None:
        result = runner.invoke(app, ["prs", "list", "--help"])
        assert result.exit_code == 0


class TestPRsStale:
    def test_stale_help(self) -> None:
        result = runner.invoke(app, ["prs", "stale", "--help"])
        assert result.exit_code == 0

    def test_stale_days_option(self) -> None:
        result = runner.invoke(app, ["prs", "stale", "--help"])
        assert "--days" in result.output


class TestPRsShow:
    def test_show_help(self) -> None:
        result = runner.invoke(app, ["prs", "show", "--help"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Direct command-level tests via AppContext injection
# ---------------------------------------------------------------------------


class TestCICommandDirect:
    """Direct invocation of command functions with mocked AppContext."""

    def _make_actx(self, json_mode: bool = True) -> MagicMock:
        from kctl_lib.output import Output

        actx = MagicMock()
        actx.output = Output(json_mode=json_mode, quiet=True, format="json" if json_mode else "pretty")
        actx.client = _make_mock_client()
        return actx

    def test_ci_show_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        """ci show returns list of workflow runs."""
        actx = self._make_actx(json_mode=True)
        actx.client.get.return_value = MOCK_WORKFLOW_RUNS

        ctx = MagicMock()
        ctx.obj = actx

        from kctl_github.commands.ci import show

        show(ctx, repo="kodemeio-next", limit=5)

        out = capsys.readouterr().out
        assert "CI" in out or "success" in out or out.startswith("[") or out.startswith("{")

    def test_ci_status_empty_repos(self, capsys: pytest.CaptureFixture[str]) -> None:
        """ci status with no repos returns empty table."""
        actx = self._make_actx(json_mode=True)
        actx.client.get_repos.return_value = []

        ctx = MagicMock()
        ctx.obj = actx

        from kctl_github.commands.ci import status

        status(ctx)
        out = capsys.readouterr().out
        assert out.strip() == "[]"

    def test_stats_overview_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        """stats overview sums up repo metadata."""
        actx = self._make_actx(json_mode=True)
        actx.client.get_repos.return_value = MOCK_REPOS

        ctx = MagicMock()
        ctx.obj = actx

        from kctl_github.commands.stats import overview

        overview(ctx)
        import json

        data = json.loads(capsys.readouterr().out)
        assert data["repos"] == 2
        assert data["stars"] == 4
        assert data["open_issues"] == 7

    def test_stats_languages_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        """stats languages aggregates across repos."""
        actx = self._make_actx(json_mode=True)
        actx.client.get_repos.return_value = [{"name": "kodemeio-next"}]
        actx.client.get.return_value = {"Python": 50000, "TypeScript": 30000}

        ctx = MagicMock()
        ctx.obj = actx

        from kctl_github.commands.stats import languages

        languages(ctx)
        import json

        data = json.loads(capsys.readouterr().out)
        assert "Python" in data
        assert "TypeScript" in data

    def test_stats_contributors_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        """stats contributors sums contributions across repos."""
        actx = self._make_actx(json_mode=True)
        actx.client.get_repos.return_value = [{"name": "kodemeio-next"}]
        actx.client.get.return_value = [
            {"login": "dev1", "contributions": 100},
            {"login": "dev2", "contributions": 50},
        ]

        ctx = MagicMock()
        ctx.obj = actx

        from kctl_github.commands.stats import contributors

        contributors(ctx)
        import json

        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)
        assert data[0]["login"] == "dev1"
        assert data[0]["total_contributions"] == 100

    def test_prs_list_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        """prs list collects open PRs from all repos."""
        actx = self._make_actx(json_mode=True)
        actx.client.get_repos.return_value = [{"name": "kodemeio-next"}]
        actx.client.get.return_value = MOCK_PRS[:1]  # Only open PR

        ctx = MagicMock()
        ctx.obj = actx

        from kctl_github.commands.prs import list_prs

        list_prs(ctx)
        import json

        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)
        assert data[0]["number"] == 1
        assert data[0]["repo"] == "kodemeio-next"

    def test_prs_stale_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        """prs stale finds PRs with no activity."""
        actx = self._make_actx(json_mode=True)
        actx.client.get_repos.return_value = [{"name": "kodemeio-next"}]
        # Return PRs with very old updated_at
        stale_pr = {
            "number": 5,
            "title": "Old PR",
            "user": {"login": "dev1"},
            "updated_at": "2020-01-01T00:00:00Z",
        }
        actx.client.get.return_value = [stale_pr]

        ctx = MagicMock()
        ctx.obj = actx

        from kctl_github.commands.prs import stale

        stale(ctx, days=7)
        import json

        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["number"] == 5

    def test_repos_list_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        """repos list shows all repos sorted by name."""
        actx = self._make_actx(json_mode=True)
        actx.client.get_repos.return_value = MOCK_REPOS

        ctx = MagicMock()
        ctx.obj = actx

        from kctl_github.commands.repos import list_repos

        list_repos(ctx)
        import json

        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)
        assert len(data) == 2
        names = [d["name"] for d in data]
        assert "kodemeio-next" in names
        assert "kodemeio-odoo" in names

    def test_repos_status_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        """repos status shows per-repo PR/CI/branch info."""
        actx = self._make_actx(json_mode=True)
        actx.client.get_repos.return_value = [{"name": "kodemeio-next"}]

        # First call: PRs, second: CI runs, third: branches
        def get_side(path: str, **kwargs: object) -> object:
            if "pulls" in path:
                return []
            if "actions/runs" in path:
                return {"workflow_runs": [{"conclusion": "success", "status": "completed"}]}
            if "branches" in path:
                return [{"name": "main"}, {"name": "feat/oidc"}]
            return []

        actx.client.get.side_effect = get_side

        ctx = MagicMock()
        ctx.obj = actx

        from kctl_github.commands.repos import status

        status(ctx)
        import json

        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)
        assert data[0]["repo"] == "kodemeio-next"
        assert data[0]["branches"] == 2
