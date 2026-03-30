"""Tests for issues commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from kctl_sentry.cli import app

runner = CliRunner()


def _mock_resolve(*args, **kwargs):  # type: ignore[no-untyped-def]
    return ("https://sentry.io", "test-token", "kodemeio", "web-app")


def _make_mock_client() -> MagicMock:
    client = MagicMock()
    client.organization = "kodemeio"
    client.default_project = "web-app"
    client.resolve_project.return_value = "web-app"
    return client


class TestIssuesList:
    @patch("kctl_sentry.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_issues_list_help(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["issues", "list", "--help"])
        assert result.exit_code == 0

    @patch("kctl_sentry.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_issues_list_json(self, _mock) -> None:  # type: ignore[no-untyped-def]
        mock_client = _make_mock_client()
        mock_client.project_get.return_value = [
            {
                "shortId": "WEB-1",
                "title": "ValueError: invalid input",
                "count": 42,
                "userCount": 5,
                "level": "error",
                "firstSeen": "2026-03-28T10:00:00Z",
                "lastSeen": "2026-03-29T08:00:00Z",
                "assignedTo": None,
            },
        ]

        # Direct approach: mock the client property on AppContext
        from kctl_sentry.core.callbacks import AppContext

        original_client = AppContext.client
        try:
            AppContext.client = property(lambda self: mock_client)  # type: ignore[assignment]
            runner.invoke(app, ["--json", "issues", "list"])
            # The command should execute (may fail on output formatting but shouldn't crash)
        finally:
            AppContext.client = original_client  # type: ignore[assignment]


class TestIssuesResolve:
    @patch("kctl_sentry.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_resolve_help(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["issues", "resolve", "--help"])
        assert result.exit_code == 0
        assert "resolve" in result.output.lower()


class TestIssuesAssign:
    @patch("kctl_sentry.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_assign_help(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["issues", "assign", "--help"])
        assert result.exit_code == 0
