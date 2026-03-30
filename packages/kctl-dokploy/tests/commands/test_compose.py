"""Tests for compose commands using Typer's CliRunner."""

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
    """Patch AppContext.client to return our mock."""
    with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
        yield


class TestComposeList:
    def test_list_json(self, mock_client: MagicMock, sample_projects: list[dict]) -> None:
        mock_client.get.return_value = sample_projects
        result = runner.invoke(app, ["--json", "compose", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["name"] == "web-app"

    def test_list_empty(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = []
        result = runner.invoke(app, ["--json", "compose", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data == []


class TestComposeGet:
    def test_get_details(self, mock_client: MagicMock, sample_compose: dict) -> None:
        mock_client.get.return_value = sample_compose
        result = runner.invoke(app, ["--json", "compose", "get", "comp-xyz-789"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["name"] == "web-app"

    def test_get_not_found(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = "not a dict"
        result = runner.invoke(app, ["compose", "get", "nonexistent"])
        assert result.exit_code == 1


class TestComposeCreate:
    def test_create_success(self, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {"composeId": "new-id"}
        result = runner.invoke(app, ["--json", "compose", "create", "proj-123", "--name", "new-svc"])
        assert result.exit_code == 0
        assert "new-svc" in result.output


class TestComposeDelete:
    def test_delete_with_force(self, mock_client: MagicMock) -> None:
        mock_client.delete.return_value = {}
        result = runner.invoke(app, ["compose", "delete", "comp-123", "--force"])
        assert result.exit_code == 0

    def test_delete_prompts_without_force(self, mock_client: MagicMock) -> None:
        mock_client.delete.return_value = {}
        result = runner.invoke(app, ["compose", "delete", "comp-123"], input="y\n")
        assert result.exit_code == 0


class TestComposeStop:
    def test_stop_with_force(self, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {}
        result = runner.invoke(app, ["compose", "stop", "comp-123", "--force"])
        assert result.exit_code == 0


class TestComposeStart:
    def test_start(self, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {}
        result = runner.invoke(app, ["compose", "start", "comp-123"])
        assert result.exit_code == 0


class TestComposeLogs:
    def test_logs_json(self, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {"logs": "line1\nline2"}
        result = runner.invoke(app, ["--json", "compose", "logs", "comp-123"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "logs" in data
