"""Tests for health commands."""

from __future__ import annotations

from unittest.mock import patch

from typer.testing import CliRunner

from kctl_sentry.cli import app

runner = CliRunner()


def _mock_resolve(*args, **kwargs):  # type: ignore[no-untyped-def]
    return ("https://sentry.io", "test-token", "kodemeio", "web-app")


class TestHealthCheck:
    @patch("kctl_sentry.core.callbacks.resolve_connection", side_effect=_mock_resolve)
    def test_health_check_help(self, _mock) -> None:  # type: ignore[no-untyped-def]
        result = runner.invoke(app, ["health", "check", "--help"])
        assert result.exit_code == 0
        assert "check" in result.output.lower() or "connectivity" in result.output.lower()
