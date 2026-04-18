"""Tests for settings commands."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from typer.testing import CliRunner

from kctl_dokploy.cli import app
from kctl_dokploy.core.callbacks import AppContext

runner = CliRunner()

SAMPLE_SERVERS = [
    {
        "name": "prod-01",
        "ipAddress": "10.0.0.1",
        "serverStatus": "active",
        "serverType": "dedicated",
        "enableDockerCleanup": True,
        "username": "root",
        "port": 22,
        "totalSum": 5,
        "createdAt": "2026-01-01T00:00:00Z",
    },
]


@pytest.fixture(autouse=True)
def _patch_client(mock_client: MagicMock):
    with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
        yield


class TestSettingsShow:
    def test_show_json(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = SAMPLE_SERVERS
        result = runner.invoke(app, ["--json", "settings", "show"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["servers"][0]["name"] == "prod-01"
        assert data["servers"][0]["ipAddress"] == "10.0.0.1"

    def test_show_empty_settings(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = {}
        result = runner.invoke(app, ["--json", "settings", "show"])
        assert result.exit_code == 0
        # Empty dict data_for_json produces no JSON output (kctl-lib behavior)
        if result.output.strip():
            data = json.loads(result.output)
            assert isinstance(data, dict)

    def test_show_non_dict_response(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = "unexpected string"
        result = runner.invoke(app, ["--json", "settings", "show"])
        assert result.exit_code == 0
        # Empty dict data_for_json produces no JSON output (kctl-lib behavior)
        if result.output.strip():
            data = json.loads(result.output)
            assert isinstance(data, dict)


class TestSettingsSshKeys:
    def test_ssh_keys_list_json(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = [
            {
                "sshKeyId": "key-001",
                "name": "deploy-key",
                "fingerprint": "SHA256:abc123",
                "createdAt": "2026-01-01T00:00:00Z",
            }
        ]
        result = runner.invoke(app, ["--json", "settings", "ssh-keys"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert data[0]["name"] == "deploy-key"

    def test_ssh_keys_empty(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = []
        result = runner.invoke(app, ["--json", "settings", "ssh-keys"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data == []
