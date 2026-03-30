"""Tests for datasource commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from kctl_grafana.cli import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def mock_client() -> MagicMock:
    client = MagicMock()
    client.org_id = 1
    return client


class TestDatasourceList:
    def test_list_datasources(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get.return_value = [
            {
                "uid": "prom1",
                "name": "Prometheus",
                "type": "prometheus",
                "url": "http://prometheus:9090",
                "isDefault": True,
            },
            {"uid": "loki1", "name": "Loki", "type": "loki", "url": "http://loki:3100", "isDefault": False},
        ]

        with (
            patch(
                "kctl_grafana.core.callbacks.resolve_connection", return_value=("https://grafana.kodeme.io", "key", 1)
            ),
            patch("kctl_grafana.core.callbacks.GrafanaClient", return_value=mock_client),
        ):
            result = runner.invoke(
                app, ["--url", "https://grafana.kodeme.io", "--api-key", "key", "datasource", "list"]
            )

        assert result.exit_code == 0
        mock_client.get.assert_called_with("/datasources")


class TestDatasourceShow:
    def test_show_datasource(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get.return_value = {
            "uid": "prom1",
            "name": "Prometheus",
            "type": "prometheus",
            "url": "http://prometheus:9090",
            "database": "",
            "isDefault": True,
            "readOnly": False,
            "access": "proxy",
            "jsonData": {"httpMethod": "POST"},
        }

        with (
            patch(
                "kctl_grafana.core.callbacks.resolve_connection", return_value=("https://grafana.kodeme.io", "key", 1)
            ),
            patch("kctl_grafana.core.callbacks.GrafanaClient", return_value=mock_client),
        ):
            result = runner.invoke(
                app, ["--url", "https://grafana.kodeme.io", "--api-key", "key", "datasource", "show", "Prometheus"]
            )

        assert result.exit_code == 0


class TestDatasourceTest:
    def test_test_single_datasource_ok(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get.return_value = {"uid": "prom1", "name": "Prometheus"}
        mock_client.post.return_value = {"status": "OK", "message": ""}

        with (
            patch(
                "kctl_grafana.core.callbacks.resolve_connection", return_value=("https://grafana.kodeme.io", "key", 1)
            ),
            patch("kctl_grafana.core.callbacks.GrafanaClient", return_value=mock_client),
        ):
            result = runner.invoke(
                app, ["--url", "https://grafana.kodeme.io", "--api-key", "key", "datasource", "test", "Prometheus"]
            )

        assert result.exit_code == 0

    def test_test_all_datasources(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get.return_value = [
            {"uid": "prom1", "name": "Prometheus", "type": "prometheus"},
            {"uid": "loki1", "name": "Loki", "type": "loki"},
        ]
        mock_client.post.return_value = {"status": "OK", "message": ""}

        with (
            patch(
                "kctl_grafana.core.callbacks.resolve_connection", return_value=("https://grafana.kodeme.io", "key", 1)
            ),
            patch("kctl_grafana.core.callbacks.GrafanaClient", return_value=mock_client),
        ):
            result = runner.invoke(
                app, ["--url", "https://grafana.kodeme.io", "--api-key", "key", "datasource", "test"]
            )

        assert result.exit_code == 0
