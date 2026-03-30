"""Tests for backups commands."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from typer.testing import CliRunner

from kctl_dokploy.cli import app
from kctl_dokploy.core.callbacks import AppContext

runner = CliRunner()

SAMPLE_BACKUPS = [
    {
        "backupId": "bkp-aaa-111",
        "status": "done",
        "schedule": "0 2 * * *",
        "enabled": True,
        "destinationId": "dst-001",
    },
    {
        "backupId": "bkp-bbb-222",
        "status": "idle",
        "schedule": "0 3 * * 0",
        "enabled": False,
        "destinationId": "dst-002",
    },
]

SAMPLE_DESTINATIONS = [
    {
        "destinationId": "dst-001",
        "name": "hetzner-s3",
        "endpoint": "https://s3.hetzner.com",
        "bucket": "kodemeio-backups",
        "region": "eu-central-1",
    },
]


@pytest.fixture(autouse=True)
def _patch_client(mock_client: MagicMock):
    with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
        yield


class TestBackupsList:
    def test_list_all_backups_json(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = SAMPLE_BACKUPS
        result = runner.invoke(app, ["--json", "backups", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 2

    def test_list_empty_returns_empty(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = []
        result = runner.invoke(app, ["--json", "backups", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data == []

    def test_list_filter_by_compose(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = SAMPLE_BACKUPS[:1]
        result = runner.invoke(app, ["--json", "backups", "list", "--compose", "comp-xyz-789"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1


class TestBackupsDestinations:
    def test_destinations_json(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = SAMPLE_DESTINATIONS
        result = runner.invoke(app, ["--json", "backups", "destinations"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert data[0]["name"] == "hetzner-s3"

    def test_destinations_empty(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = []
        result = runner.invoke(app, ["--json", "backups", "destinations"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data == []


class TestBackupsTrigger:
    def test_trigger_with_explicit_destination(self, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {"backupId": "bkp-new"}
        result = runner.invoke(app, ["--json", "backups", "trigger", "comp-xyz-789", "--destination", "dst-001"])
        assert result.exit_code == 0

    def test_trigger_auto_selects_first_destination(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = SAMPLE_DESTINATIONS
        mock_client.post.return_value = {"backupId": "bkp-new"}
        result = runner.invoke(app, ["backups", "trigger", "comp-xyz-789"])
        assert result.exit_code == 0

    def test_trigger_fails_when_no_destination(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = []
        result = runner.invoke(app, ["backups", "trigger", "comp-xyz-789"])
        assert result.exit_code == 1


class TestBackupsRestore:
    def test_restore_with_force(self, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {}
        result = runner.invoke(app, ["backups", "restore", "bkp-aaa-111", "--force"])
        assert result.exit_code == 0
