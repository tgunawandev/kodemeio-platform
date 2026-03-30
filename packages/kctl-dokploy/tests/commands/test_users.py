"""Tests for users commands."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from typer.testing import CliRunner

from kctl_dokploy.cli import app
from kctl_dokploy.core.callbacks import AppContext

runner = CliRunner()

SAMPLE_USERS = [
    {
        "userId": "usr-aaa-111",
        "email": "admin@kodeme.io",
        "rol": "admin",
        "status": "active",
        "createdAt": "2026-01-01T00:00:00Z",
    },
    {
        "userId": "usr-bbb-222",
        "email": "dev@kodeme.io",
        "rol": "user",
        "status": "active",
        "createdAt": "2026-02-01T00:00:00Z",
    },
]


@pytest.fixture(autouse=True)
def _patch_client(mock_client: MagicMock):
    with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
        yield


class TestUsersList:
    def test_list_json(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = SAMPLE_USERS
        result = runner.invoke(app, ["--json", "users", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["email"] == "admin@kodeme.io"

    def test_list_empty(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = []
        result = runner.invoke(app, ["--json", "users", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data == []


class TestUsersGet:
    def test_get_user_json(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = SAMPLE_USERS[0]
        result = runner.invoke(app, ["--json", "users", "get", "usr-aaa-111"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["email"] == "admin@kodeme.io"
        assert data["rol"] == "admin"

    def test_get_not_found_exits_1(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = "not a dict"
        result = runner.invoke(app, ["users", "get", "nonexistent"])
        assert result.exit_code == 1


class TestUsersCreate:
    def test_create_user_success(self, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {"userId": "usr-new-001"}
        result = runner.invoke(
            app,
            ["--json", "users", "create", "--email", "new@kodeme.io", "--password", "secret123"],
        )
        assert result.exit_code == 0
        assert "new@kodeme.io" in result.output

    def test_create_user_with_role(self, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {"userId": "usr-new-002"}
        result = runner.invoke(
            app,
            [
                "users",
                "create",
                "--email",
                "admin2@kodeme.io",
                "--password",
                "secret456",
                "--role",
                "admin",
            ],
        )
        assert result.exit_code == 0


class TestUsersRemove:
    def test_remove_with_force(self, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {}
        result = runner.invoke(app, ["users", "remove", "usr-bbb-222", "--force"])
        assert result.exit_code == 0

    def test_remove_prompts_without_force(self, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {}
        result = runner.invoke(app, ["users", "remove", "usr-bbb-222"], input="y\n")
        assert result.exit_code == 0
