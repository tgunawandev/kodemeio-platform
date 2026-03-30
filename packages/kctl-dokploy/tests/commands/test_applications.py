"""Tests for applications commands."""

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


class TestApplicationsList:
    def test_list_json_returns_all_apps(self, mock_client: MagicMock, sample_projects: list[dict]) -> None:
        mock_client.get.return_value = sample_projects
        result = runner.invoke(app, ["--json", "applications", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 1  # only 1 app in sample_projects
        assert data[0]["name"] == "frontend"

    def test_list_empty_when_no_apps(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = [{"projectId": "p-1", "name": "empty", "compose": [], "applications": []}]
        result = runner.invoke(app, ["--json", "applications", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data == []

    def test_list_filter_by_project(self, mock_client: MagicMock, sample_projects: list[dict]) -> None:
        mock_client.get.return_value = sample_projects
        result = runner.invoke(app, ["--json", "applications", "list", "--project", "kodemeio"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1
        assert data[0]["project"] == "kodemeio"

    def test_list_filter_by_wrong_project_returns_empty(
        self, mock_client: MagicMock, sample_projects: list[dict]
    ) -> None:
        mock_client.get.return_value = sample_projects
        result = runner.invoke(app, ["--json", "applications", "list", "--project", "nonexistent"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data == []


class TestApplicationsGet:
    def test_get_application_json(self, mock_client: MagicMock) -> None:
        app_data = {
            "applicationId": "app-111-222",
            "name": "frontend",
            "applicationStatus": "done",
            "applicationType": "docker",
            "updatedAt": "2026-03-20T14:30:00Z",
            "domains": [],
        }
        mock_client.get.return_value = app_data
        result = runner.invoke(app, ["--json", "applications", "get", "app-111-222"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["name"] == "frontend"
        assert data["applicationStatus"] == "done"

    def test_get_not_found_exits_1(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = "not a dict"
        result = runner.invoke(app, ["applications", "get", "nonexistent"])
        assert result.exit_code == 1


class TestApplicationsCreate:
    def test_create_success(self, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {"applicationId": "new-app-id"}
        result = runner.invoke(app, ["--json", "applications", "create", "--name", "my-app", "--project", "proj-123"])
        assert result.exit_code == 0
        assert "my-app" in result.output

    def test_create_with_optional_fields(self, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {"applicationId": "new-app-id"}
        result = runner.invoke(
            app,
            [
                "--json",
                "applications",
                "create",
                "--name",
                "my-app",
                "--project",
                "proj-123",
                "--description",
                "test",
                "--server",
                "srv-001",
            ],
        )
        assert result.exit_code == 0


class TestApplicationsDelete:
    def test_delete_with_force(self, mock_client: MagicMock) -> None:
        mock_client.delete.return_value = {}
        result = runner.invoke(app, ["applications", "delete", "app-111-222", "--force"])
        assert result.exit_code == 0

    def test_delete_prompts_without_force(self, mock_client: MagicMock) -> None:
        mock_client.delete.return_value = {}
        result = runner.invoke(app, ["applications", "delete", "app-111-222"], input="y\n")
        assert result.exit_code == 0


class TestApplicationsDeploy:
    def test_deploy_triggers_successfully(self, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {}
        result = runner.invoke(app, ["applications", "deploy", "app-111-222"])
        assert result.exit_code == 0

    def test_stop_with_force(self, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {}
        result = runner.invoke(app, ["applications", "stop", "app-111-222", "--force"])
        assert result.exit_code == 0
