"""Smoke tests for ``backups pull``, ``backups download``, ``backups run-wait``.

These tests mock ``DokployClient`` and the boto3 S3 client via monkeypatch
of ``_build_s3_client``. No network, no subprocess.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from typer.testing import CliRunner

from kctl_dokploy.cli import app
from kctl_dokploy.core.callbacks import AppContext

runner = CliRunner()


SAMPLE_BACKUP = {
    "backupId": "bkp-aaa",
    "destinationId": "dst-001",
    "database": "tpp_odoo_erp",
    "prefix": "compose-sample/postgres/tpp_odoo_erp/",
    "backupType": "compose",
    "databaseType": "postgres",
    "composeId": "cmp-xyz",
    "metadata": {"postgres": {"databaseUser": "odoo"}},
}

SAMPLE_DESTINATION = {
    "destinationId": "dst-001",
    "name": "hetzner-s3",
    "bucket": "kodemeio-backups",
    "endpoint": "https://s3.hetzner.com",
    "region": "eu-central-1",
    "accessKey": "AKIA-test",
    "secretAccessKey": "secret-test",
}


class FakePaginator:
    def __init__(self, pages: list[dict[str, Any]]):
        self._pages = pages

    def paginate(self, **_kwargs: Any) -> list[dict[str, Any]]:
        return self._pages


class FakeS3:
    def __init__(self, keys: list[tuple[str, datetime, int]]):
        self.keys = keys
        self.download_calls: list[tuple[str, str, str]] = []

    def get_paginator(self, _name: str) -> FakePaginator:
        contents = [{"Key": k, "LastModified": lm, "Size": size} for k, lm, size in self.keys]
        return FakePaginator([{"Contents": contents}])

    def download_file(self, bucket: str, key: str, dest: str) -> None:
        self.download_calls.append((bucket, key, dest))
        # Write a 1-byte placeholder so _detect_format + size checks don't explode.
        with open(dest, "wb") as f:
            f.write(b"PGDMP" + b"\x00" * 10)


@pytest.fixture(autouse=True)
def _patch_client(mock_client: MagicMock):
    with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
        yield


# ---------------------------------------------------------------------------
# backups download
# ---------------------------------------------------------------------------


class TestBackupsDownload:
    def test_download_calls_s3(self, mock_client: MagicMock, tmp_path: Any) -> None:
        mock_client.get.return_value = SAMPLE_DESTINATION

        fake_s3 = FakeS3([])
        out = tmp_path / "dump.sql.gz"
        with patch(
            "kctl_dokploy.commands.backups_pull._build_s3_client",
            return_value=fake_s3,
        ):
            result = runner.invoke(
                app,
                [
                    "--json",
                    "backups",
                    "download",
                    "some/key.sql.gz",
                    "--destination",
                    "dst-001",
                    "--output",
                    str(out),
                ],
            )
        assert result.exit_code == 0, result.output
        assert fake_s3.download_calls == [("kodemeio-backups", "some/key.sql.gz", str(out))]

    def test_download_missing_destination_errors(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = None
        result = runner.invoke(
            app,
            ["backups", "download", "x.sql.gz", "--destination", "missing"],
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# backups run-wait
# ---------------------------------------------------------------------------


class TestBackupsRunWait:
    def test_run_wait_triggers_and_polls(self, mock_client: MagicMock) -> None:
        # GET: /backup.one -> backup, /destination.one -> dest
        def get_side_effect(path: str, params: dict[str, Any] | None = None) -> Any:
            if path == "/backup.one":
                return SAMPLE_BACKUP
            if path == "/destination.one":
                return SAMPLE_DESTINATION
            return {}

        mock_client.get.side_effect = get_side_effect
        mock_client.post.return_value = {}

        # Provide a key dated AFTER trigger so the poll returns immediately.
        future = datetime.now(UTC).replace(year=2099)
        fake_s3 = FakeS3([("compose-sample/postgres/tpp_odoo_erp/new.sql.gz", future, 1024)])
        with patch(
            "kctl_dokploy.commands.backups_pull._build_s3_client",
            return_value=fake_s3,
        ):
            result = runner.invoke(
                app,
                [
                    "--json",
                    "backups",
                    "run-wait",
                    "bkp-aaa",
                    "--timeout",
                    "30",
                    "--poll-interval",
                    "1",
                ],
            )

        assert result.exit_code == 0, result.output
        # Post was called once (manual trigger) on /backup.manualBackupCompose.
        assert any("manualBackupCompose" in str(c) for c in mock_client.post.call_args_list)


# ---------------------------------------------------------------------------
# backups pull — we only smoke-test argument validation; the full restore
# flow shells out to subprocess, which we don't want to stub in this test.
# ---------------------------------------------------------------------------


class TestBackupsPull:
    def test_pull_requires_target(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = SAMPLE_BACKUP
        result = runner.invoke(
            app,
            [
                "backups",
                "pull",
                "bkp-aaa",
                "--target-db",
                "tpp_odoo_erp",
            ],
        )
        assert result.exit_code != 0

    def test_pull_rejects_both_targets(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = SAMPLE_BACKUP
        result = runner.invoke(
            app,
            [
                "backups",
                "pull",
                "bkp-aaa",
                "--target-db",
                "tpp_odoo_erp",
                "--target-host",
                "localhost",
                "--target-compose",
                "cmp-xyz",
            ],
        )
        assert result.exit_code != 0

    def test_pull_invalid_backup_id(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = None
        result = runner.invoke(
            app,
            [
                "backups",
                "pull",
                "does-not-exist",
                "--target-db",
                "x",
                "--target-host",
                "localhost",
                "--target-password",
                "p",
            ],
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# backups list-files — the fix
# ---------------------------------------------------------------------------


class TestBackupsListFilesFixed:
    def test_list_files_without_search_lists_all(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = SAMPLE_DESTINATION
        fake_s3 = FakeS3(
            [
                ("foo/a.sql.gz", datetime.now(UTC), 100),
                ("foo/b.sql.gz", datetime.now(UTC), 200),
            ]
        )
        with patch(
            "kctl_dokploy.commands.backups.backups_flow_mod"
            if False
            else "kctl_dokploy.commands.backups_flow._build_s3_client",
            return_value=fake_s3,
        ):
            result = runner.invoke(
                app,
                ["--json", "backups", "list-files", "--destination", "dst-001"],
            )
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        # JSON output is a list of {key,size,lastModified}
        assert isinstance(payload, list)
        assert {row["key"] for row in payload} == {"foo/a.sql.gz", "foo/b.sql.gz"}

    def test_list_files_with_search_filters(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = SAMPLE_DESTINATION
        fake_s3 = FakeS3(
            [
                ("foo/tpp_odoo_erp.sql.gz", datetime.now(UTC), 100),
                ("foo/mac_odoo_erp.sql.gz", datetime.now(UTC), 200),
            ]
        )
        with patch(
            "kctl_dokploy.commands.backups_flow._build_s3_client",
            return_value=fake_s3,
        ):
            result = runner.invoke(
                app,
                [
                    "--json",
                    "backups",
                    "list-files",
                    "--destination",
                    "dst-001",
                    "--search",
                    "tpp",
                ],
            )
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert [row["key"] for row in payload] == ["foo/tpp_odoo_erp.sql.gz"]
