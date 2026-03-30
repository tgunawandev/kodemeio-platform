"""Tests for user commands."""

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


class TestUserList:
    def test_list_users(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get.return_value = [
            {"userId": 1, "login": "admin", "email": "admin@kodeme.io", "role": "Admin", "lastSeenAt": "2024-01-01"},
            {"userId": 2, "login": "viewer", "email": "viewer@kodeme.io", "role": "Viewer", "lastSeenAt": "2024-06-01"},
        ]

        with (
            patch(
                "kctl_grafana.core.callbacks.resolve_connection", return_value=("https://grafana.kodeme.io", "key", 1)
            ),
            patch("kctl_grafana.core.callbacks.GrafanaClient", return_value=mock_client),
        ):
            result = runner.invoke(app, ["--url", "https://grafana.kodeme.io", "--api-key", "key", "user", "list"])

        assert result.exit_code == 0


class TestUserAdd:
    def test_add_user(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {"message": "User added to organization"}

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
                    "user",
                    "add",
                    "newuser@kodeme.io",
                    "--role",
                    "Editor",
                ],
            )

        assert result.exit_code == 0
        mock_client.post.assert_called_once()

    def test_add_user_invalid_role(self, runner: CliRunner, mock_client: MagicMock) -> None:
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
                    "user",
                    "add",
                    "user@test.com",
                    "--role",
                    "SuperAdmin",
                ],
            )

        assert result.exit_code == 1
