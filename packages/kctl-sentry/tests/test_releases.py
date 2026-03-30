"""Tests for releases commands."""

from __future__ import annotations

from unittest.mock import patch

from typer.testing import CliRunner

from kctl_sentry.cli import app

runner = CliRunner()


def _mock_resolve(*args, **kwargs):  # type: ignore[no-untyped-def]
    return ("https://sentry.io", "test-token", "kodemeio", "web-app")


class TestReleasesList:
    @patch("kctl_sentry.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_releases_list_help(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["releases", "list", "--help"])
        assert result.exit_code == 0


class TestReleasesCreate:
    @patch("kctl_sentry.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_create_help(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["releases", "create", "--help"])
        assert result.exit_code == 0


class TestReleasesAssociate:
    @patch("kctl_sentry.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_associate_help(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["releases", "associate", "--help"])
        assert result.exit_code == 0
