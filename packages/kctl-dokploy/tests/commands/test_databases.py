"""Tests for databases commands."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from typer.testing import CliRunner

from kctl_dokploy.cli import app
from kctl_dokploy.core.callbacks import AppContext

runner = CliRunner()


@pytest.fixture(autouse=True)
def _patch_client(mock_client: MagicMock):
    with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
        yield


class TestDatabasesList:
    def test_list_empty_projects_returns_empty(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = []
        result = runner.invoke(app, ["--json", "databases", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data == []

    def test_list_with_postgres_db(self, mock_client: MagicMock) -> None:
        projects = [
            {
                "projectId": "proj-abc-123",
                "name": "main",
                "postgres": [
                    {
                        "postgresId": "pg-001",
                        "name": "main-db",
                        "postgresStatus": "running",
                        "databaseVersion": "16",
                    }
                ],
                "redis": [],
                "mysql": [],
                "mariadb": [],
                "mongo": [],
                "compose": [],
                "applications": [],
            }
        ]
        mock_client.get.return_value = projects
        result = runner.invoke(app, ["--json", "databases", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["name"] == "main-db"
        assert data[0]["type"] == "postgres"


class TestDatabasesGet:
    def test_get_postgres_json(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = {
            "postgresId": "pg-001",
            "name": "main-db",
            "postgresStatus": "running",
            "databaseVersion": "16",
            "externalPort": 5432,
            "createdAt": "2026-01-01T00:00:00Z",
        }
        result = runner.invoke(app, ["--json", "databases", "get", "pg-001", "--type", "postgres"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["name"] == "main-db"

    def test_get_not_found_exits_1(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = "not a dict"
        result = runner.invoke(app, ["databases", "get", "nonexistent", "--type", "postgres"])
        assert result.exit_code == 1

    def test_get_invalid_type_exits_1(self, mock_client: MagicMock) -> None:
        result = runner.invoke(app, ["databases", "get", "pg-001", "--type", "oracle"])
        assert result.exit_code == 1


class TestDatabasesCreatePostgres:
    def test_create_postgres_success(self, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {"postgresId": "pg-new-001"}
        result = runner.invoke(
            app,
            ["--json", "databases", "create-postgres", "--name", "mydb", "--project", "proj-abc-123"],
        )
        assert result.exit_code == 0
        assert "mydb" in result.output

    def test_create_postgres_with_version(self, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {"postgresId": "pg-new-002"}
        result = runner.invoke(
            app,
            [
                "databases",
                "create-postgres",
                "--name",
                "mydb",
                "--project",
                "proj-abc-123",
                "--version",
                "15",
            ],
        )
        assert result.exit_code == 0


class TestDatabasesRemove:
    def test_remove_with_force(self, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {}
        result = runner.invoke(app, ["databases", "remove", "pg-001", "--type", "postgres", "--force"])
        assert result.exit_code == 0

    def test_remove_invalid_type_exits_1(self, mock_client: MagicMock) -> None:
        result = runner.invoke(app, ["databases", "remove", "pg-001", "--type", "oracle", "--force"])
        assert result.exit_code == 1

    def test_remove_prompts_without_force(self, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {}
        result = runner.invoke(app, ["databases", "remove", "pg-001", "--type", "postgres"], input="y\n")
        assert result.exit_code == 0
