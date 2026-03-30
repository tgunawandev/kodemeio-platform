"""Tests for servers commands."""

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


class TestServersList:
    def test_list_json(self, mock_client: MagicMock, sample_servers: list[dict]) -> None:
        mock_client.get.return_value = sample_servers
        result = runner.invoke(app, ["--json", "servers", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["name"] == "hetzner-main"

    def test_list_empty(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = []
        result = runner.invoke(app, ["--json", "servers", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data == []


class TestServersGet:
    def test_get_server_json(self, mock_client: MagicMock, sample_servers: list[dict]) -> None:
        mock_client.get.return_value = sample_servers[0]
        result = runner.invoke(app, ["--json", "servers", "get", "srv-001"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["name"] == "hetzner-main"
        assert data["serverId"] == "srv-001"

    def test_get_not_found_exits_1(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = "not a dict"
        result = runner.invoke(app, ["servers", "get", "nonexistent"])
        assert result.exit_code == 1


class TestServersCreate:
    def test_create_server_success(self, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {"serverId": "srv-new-001"}
        result = runner.invoke(
            app,
            ["--json", "servers", "create", "--name", "new-server", "--ip", "10.0.0.3"],
        )
        assert result.exit_code == 0
        assert "new-server" in result.output

    def test_create_server_with_ssh_key(self, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {"serverId": "srv-new-002"}
        result = runner.invoke(
            app,
            [
                "servers",
                "create",
                "--name",
                "worker",
                "--ip",
                "10.0.0.4",
                "--ssh-key",
                "key-001",
                "--port",
                "22",
                "--username",
                "deploy",
            ],
        )
        assert result.exit_code == 0


class TestServersRemove:
    def test_remove_with_force(self, mock_client: MagicMock) -> None:
        mock_client.delete.return_value = {}
        result = runner.invoke(app, ["servers", "remove", "srv-001", "--force"])
        assert result.exit_code == 0

    def test_remove_prompts_without_force(self, mock_client: MagicMock) -> None:
        mock_client.delete.return_value = {}
        result = runner.invoke(app, ["servers", "remove", "srv-001"], input="y\n")
        assert result.exit_code == 0
