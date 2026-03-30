"""Tests for health commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from kctl_grafana.cli import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class TestHealthCheck:
    """Test health check command."""

    def test_health_check_success(self, runner: CliRunner) -> None:
        mock_client = MagicMock()
        mock_client.check_health.return_value = {
            "commit": "abc123",
            "database": "ok",
            "version": "11.4.0",
        }
        mock_client.get_org.return_value = {
            "id": 1,
            "name": "Kodemeio",
        }

        with (
            patch(
                "kctl_grafana.core.callbacks.resolve_connection",
                return_value=("https://grafana.kodeme.io", "test-key", 1),
            ),
            patch("kctl_grafana.core.callbacks.GrafanaClient", return_value=mock_client),
        ):
            result = runner.invoke(
                app, ["--url", "https://grafana.kodeme.io", "--api-key", "test-key", "health", "check"]
            )

        # Should not error (exit 0)
        assert result.exit_code == 0

    def test_health_check_failure(self, runner: CliRunner) -> None:
        mock_client = MagicMock()
        mock_client.check_health.return_value = {
            "database": "error",
            "version": "unknown",
        }

        with (
            patch(
                "kctl_grafana.core.callbacks.resolve_connection",
                return_value=("https://grafana.kodeme.io", "test-key", 1),
            ),
            patch("kctl_grafana.core.callbacks.GrafanaClient", return_value=mock_client),
        ):
            result = runner.invoke(
                app, ["--url", "https://grafana.kodeme.io", "--api-key", "test-key", "health", "check"]
            )

        assert result.exit_code == 1


class TestStatusOverview:
    """Test status overview command."""

    def test_status_overview(self, runner: CliRunner) -> None:
        mock_client = MagicMock()
        mock_client.check_health.return_value = {
            "database": "ok",
            "version": "11.4.0",
        }
        mock_client.get.side_effect = lambda path, **kw: {
            "/search": [{"uid": "abc", "title": "Test"}],
            "/datasources": [{"name": "Prometheus", "type": "prometheus"}],
            "/v1/provisioning/alert-rules": [{"uid": "rule1"}],
            "/alertmanager/grafana/api/v2/alerts": [],
        }.get(path, [])

        with (
            patch(
                "kctl_grafana.core.callbacks.resolve_connection",
                return_value=("https://grafana.kodeme.io", "test-key", 1),
            ),
            patch("kctl_grafana.core.callbacks.GrafanaClient", return_value=mock_client),
        ):
            result = runner.invoke(
                app, ["--url", "https://grafana.kodeme.io", "--api-key", "test-key", "status", "overview"]
            )

        assert result.exit_code == 0
