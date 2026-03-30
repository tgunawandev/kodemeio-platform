"""Tests for folder commands."""

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


class TestFolderList:
    def test_list_folders(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get.return_value = [
            {"uid": "infra", "title": "Infrastructure", "id": 1, "url": "/dashboards/f/infra"},
            {"uid": "apps", "title": "Applications", "id": 2, "url": "/dashboards/f/apps"},
        ]

        with (
            patch(
                "kctl_grafana.core.callbacks.resolve_connection", return_value=("https://grafana.kodeme.io", "key", 1)
            ),
            patch("kctl_grafana.core.callbacks.GrafanaClient", return_value=mock_client),
        ):
            result = runner.invoke(app, ["--url", "https://grafana.kodeme.io", "--api-key", "key", "folder", "list"])

        assert result.exit_code == 0


class TestFolderCreate:
    def test_create_folder(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {"uid": "new-folder", "title": "New Folder"}

        with (
            patch(
                "kctl_grafana.core.callbacks.resolve_connection", return_value=("https://grafana.kodeme.io", "key", 1)
            ),
            patch("kctl_grafana.core.callbacks.GrafanaClient", return_value=mock_client),
        ):
            result = runner.invoke(
                app, ["--url", "https://grafana.kodeme.io", "--api-key", "key", "folder", "create", "New Folder"]
            )

        assert result.exit_code == 0
        mock_client.post.assert_called_once()


class TestFolderDelete:
    def test_delete_folder_force(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.delete.return_value = {"message": "Folder deleted"}

        with (
            patch(
                "kctl_grafana.core.callbacks.resolve_connection", return_value=("https://grafana.kodeme.io", "key", 1)
            ),
            patch("kctl_grafana.core.callbacks.GrafanaClient", return_value=mock_client),
        ):
            result = runner.invoke(
                app,
                ["--url", "https://grafana.kodeme.io", "--api-key", "key", "folder", "delete", "infra", "--force"],
            )

        assert result.exit_code == 0
        mock_client.delete.assert_called_with("/folders/infra")
