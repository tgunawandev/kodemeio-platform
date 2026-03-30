"""Tests for dashboard commands."""

from __future__ import annotations

import json
from pathlib import Path
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


class TestDashboardList:
    def test_list_dashboards(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get.return_value = [
            {"uid": "abc123", "title": "Overview", "folderTitle": "General", "tags": ["prod"], "isStarred": False},
            {"uid": "def456", "title": "Node Exporter", "folderTitle": "Infra", "tags": [], "isStarred": True},
        ]

        with (
            patch(
                "kctl_grafana.core.callbacks.resolve_connection", return_value=("https://grafana.kodeme.io", "key", 1)
            ),
            patch("kctl_grafana.core.callbacks.GrafanaClient", return_value=mock_client),
        ):
            result = runner.invoke(app, ["--url", "https://grafana.kodeme.io", "--api-key", "key", "dashboard", "list"])

        assert result.exit_code == 0
        mock_client.get.assert_called_with("/search", params={"type": "dash-db", "limit": 5000})


class TestDashboardShow:
    def test_show_dashboard(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get.return_value = {
            "meta": {
                "created": "2024-01-01",
                "updated": "2024-06-01",
                "createdBy": "admin",
                "updatedBy": "admin",
                "folderTitle": "General",
                "url": "/d/abc123",
            },
            "dashboard": {
                "uid": "abc123",
                "title": "Overview",
                "version": 5,
                "panels": [{"title": "CPU", "type": "graph"}],
            },
        }

        with (
            patch(
                "kctl_grafana.core.callbacks.resolve_connection", return_value=("https://grafana.kodeme.io", "key", 1)
            ),
            patch("kctl_grafana.core.callbacks.GrafanaClient", return_value=mock_client),
        ):
            result = runner.invoke(
                app, ["--url", "https://grafana.kodeme.io", "--api-key", "key", "dashboard", "show", "abc123"]
            )

        assert result.exit_code == 0


class TestDashboardExport:
    def test_export_dashboard(self, runner: CliRunner, mock_client: MagicMock, tmp_path) -> None:
        mock_client.get.return_value = {
            "meta": {},
            "dashboard": {"uid": "abc123", "title": "Test Dashboard", "id": 42, "panels": []},
        }
        output_file = str(tmp_path / "test.json")

        with (
            patch(
                "kctl_grafana.core.callbacks.resolve_connection", return_value=("https://grafana.kodeme.io", "key", 1)
            ),
            patch("kctl_grafana.core.callbacks.GrafanaClient", return_value=mock_client),
        ):
            result = runner.invoke(
                app,
                [
                    "--url",
                    "https://grafana.kodeme.io",
                    "--api-key",
                    "key",
                    "dashboard",
                    "export",
                    "abc123",
                    "--output",
                    output_file,
                ],
            )

        assert result.exit_code == 0
        exported = json.loads(Path(output_file).read_text())
        assert "dashboard" in exported
        assert "id" not in exported["dashboard"]  # id removed for portability


class TestDashboardImport:
    def test_import_dashboard(self, runner: CliRunner, mock_client: MagicMock, tmp_path) -> None:
        dashboard_file = tmp_path / "dash.json"
        dashboard_file.write_text(
            json.dumps(
                {
                    "dashboard": {"uid": "new123", "title": "Imported", "panels": []},
                }
            )
        )

        mock_client.post.return_value = {"slug": "imported", "uid": "new123", "url": "/d/new123"}

        with (
            patch(
                "kctl_grafana.core.callbacks.resolve_connection", return_value=("https://grafana.kodeme.io", "key", 1)
            ),
            patch("kctl_grafana.core.callbacks.GrafanaClient", return_value=mock_client),
        ):
            result = runner.invoke(
                app,
                [
                    "--url",
                    "https://grafana.kodeme.io",
                    "--api-key",
                    "key",
                    "dashboard",
                    "import",
                    str(dashboard_file),
                ],
            )

        assert result.exit_code == 0
        mock_client.post.assert_called_once()


class TestDashboardSearch:
    def test_search_dashboards(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get.return_value = [
            {"uid": "abc123", "title": "CPU Overview", "folderTitle": "General", "tags": []},
        ]

        with (
            patch(
                "kctl_grafana.core.callbacks.resolve_connection", return_value=("https://grafana.kodeme.io", "key", 1)
            ),
            patch("kctl_grafana.core.callbacks.GrafanaClient", return_value=mock_client),
        ):
            result = runner.invoke(
                app, ["--url", "https://grafana.kodeme.io", "--api-key", "key", "dashboard", "search", "CPU"]
            )

        assert result.exit_code == 0
