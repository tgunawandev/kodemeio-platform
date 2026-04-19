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
    def test_list_backups_json(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = {"backups": SAMPLE_BACKUPS}
        result = runner.invoke(app, ["--json", "backups", "list", "--compose", "comp-xyz-789"])
        assert result.exit_code == 0

    def test_list_empty_returns_empty(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = {"backups": []}
        result = runner.invoke(app, ["--json", "backups", "list", "--compose", "comp-xyz-789"])
        assert result.exit_code == 0

    def test_list_requires_compose(self, mock_client: MagicMock) -> None:
        result = runner.invoke(app, ["--json", "backups", "list"])
        assert result.exit_code == 1


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


class TestBackupsRun:
    def test_run_postgres_backup(self, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {}
        result = runner.invoke(app, ["backups", "run", "bkp-aaa-111", "--type", "postgres"])
        assert result.exit_code == 0

    def test_run_compose_backup(self, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {}
        result = runner.invoke(app, ["backups", "run", "bkp-aaa-111", "--type", "compose"])
        assert result.exit_code == 0

    def test_run_unknown_type_fails(self, mock_client: MagicMock) -> None:
        result = runner.invoke(app, ["backups", "run", "bkp-aaa-111", "--type", "unknown"])
        assert result.exit_code == 1


class TestBackupsGet:
    def test_get_backup(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = SAMPLE_BACKUPS[0]
        result = runner.invoke(app, ["--json", "backups", "get", "bkp-aaa-111"])
        assert result.exit_code == 0

    def test_get_backup_not_found(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = None
        result = runner.invoke(app, ["backups", "get", "bkp-nonexist"])
        assert result.exit_code == 1


class TestBackupsRemove:
    def test_remove_with_force(self, mock_client: MagicMock) -> None:
        mock_client.post.return_value = {}
        result = runner.invoke(app, ["backups", "remove", "bkp-aaa-111", "--force"])
        assert result.exit_code == 0


class TestBackupsRestore:
    def test_restore_missing_file_and_latest_exits_nonzero(self) -> None:
        """Omitting both --file and --latest should fail with a usage error."""
        result = runner.invoke(
            app,
            [
                "-p",
                "local",
                "backups",
                "restore",
                "--compose",
                "cmp-123",
                "--destination",
                "dst-001",
                "--database-name",
                "mydb",
            ],
        )
        assert result.exit_code != 0


class TestBackupsListFiles:
    def test_list_files(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = ["backup-2026-04-01.sql.gz", "backup-2026-04-02.sql.gz"]
        result = runner.invoke(app, ["--json", "backups", "list-files", "--destination", "dst-001"])
        assert result.exit_code == 0
