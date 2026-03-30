"""Tests for projects commands."""

from __future__ import annotations

from unittest.mock import patch

from typer.testing import CliRunner

from kctl_sentry.cli import app

runner = CliRunner()


def _mock_resolve(*args, **kwargs):  # type: ignore[no-untyped-def]
    return ("https://sentry.io", "test-token", "kodemeio", "web-app")


class TestProjectsList:
    @patch("kctl_sentry.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_projects_list_help(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["projects", "list", "--help"])
        assert result.exit_code == 0

    @patch("kctl_sentry.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_projects_dsn_help(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["projects", "dsn", "--help"])
        assert result.exit_code == 0


class TestProjectsCreate:
    @patch("kctl_sentry.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_create_help(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["projects", "create", "--help"])
        assert result.exit_code == 0
