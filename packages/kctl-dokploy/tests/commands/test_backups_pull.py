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
    "prefix": "tpp-infra-postgres/tpp_odoo_erp",
    "serviceName": "postgres",
    "backupType": "compose",
    "databaseType": "postgres",
    "composeId": "cmp-xyz",
    "metadata": {"postgres": {"databaseUser": "odoo"}},
}

SAMPLE_COMPOSE = {
    "composeId": "cmp-xyz",
    "appName": "compose-foo-qsokry",
    "name": "compose-foo",
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
    """Paginator that honors the ``Prefix`` filter passed by the helper."""

    def __init__(self, all_keys: list[tuple[str, datetime, int]]):
        self._all_keys = all_keys

    def paginate(self, **kwargs: Any) -> list[dict[str, Any]]:
        prefix: str = kwargs.get("Prefix", "") or ""
        matched = [
            {"Key": k, "LastModified": lm, "Size": size} for k, lm, size in self._all_keys if k.startswith(prefix)
        ]
        return [{"Contents": matched}] if matched else [{"Contents": []}]


class FakeS3:
    def __init__(self, keys: list[tuple[str, datetime, int]]):
        self.keys = keys
        self.download_calls: list[tuple[str, str, str]] = []

    def get_paginator(self, _name: str) -> FakePaginator:
        return FakePaginator(self.keys)

    def download_file(self, bucket: str, key: str, dest: str) -> None:
        self.download_calls.append((bucket, key, dest))
        # Write a PGDMP magic header so _detect_format returns 'custom'.
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
        # GET: /backup.one -> backup, /destination.one -> dest, /compose.one -> compose
        def get_side_effect(path: str, params: dict[str, Any] | None = None) -> Any:
            if path == "/backup.one":
                return SAMPLE_BACKUP
            if path == "/destination.one":
                return SAMPLE_DESTINATION
            if path == "/compose.one":
                return SAMPLE_COMPOSE
            return {}

        mock_client.get.side_effect = get_side_effect
        mock_client.post.return_value = {}

        # Provide a key dated AFTER trigger under the NEW hierarchical prefix
        # <appName>/<backup.prefix>/<timestamp>.sql.gz so the poll returns immediately.
        future = datetime.now(UTC).replace(year=2099)
        new_key = "compose-foo-qsokry_postgres/tpp-infra-postgres/tpp_odoo_erp/2099-01-01T00-00-00Z.sql.gz"
        fake_s3 = FakeS3([(new_key, future, 1024)])
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
# Multi-prefix discovery — the Dokploy path-convention fix
# ---------------------------------------------------------------------------


class TestMultiPrefixDiscovery:
    """Dokploy changed the S3 layout from flat to hierarchical. The helpers
    must scan BOTH candidate prefixes and pick the newest object globally.
    """

    def _run_pull(
        self,
        mock_client: MagicMock,
        fake_s3: FakeS3,
        backup: dict[str, Any],
        compose: dict[str, Any] | None = None,
    ) -> Any:
        def get_side_effect(path: str, params: dict[str, Any] | None = None) -> Any:
            if path == "/backup.one":
                return backup
            if path == "/destination.one":
                return SAMPLE_DESTINATION
            if path == "/compose.one":
                return compose or {}
            return {}

        mock_client.get.side_effect = get_side_effect

        # Side-step gzip decompression (the FakeS3 writes a PGDMP header,
        # not valid gzip), and also the subprocess-backed restore pipeline.
        def passthrough_decompress(_c: Any, src: Any) -> Any:
            return src

        with (
            patch(
                "kctl_dokploy.commands.backups_pull._build_s3_client",
                return_value=fake_s3,
            ),
            patch(
                "kctl_dokploy.commands.backups_pull._maybe_decompress",
                side_effect=passthrough_decompress,
            ),
            patch("kctl_dokploy.commands.backups_pull._terminate_and_recreate_db") as _drop,
            patch("kctl_dokploy.commands.backups_pull._restore_to_raw_host") as _restore,
            patch("kctl_dokploy.commands.backups_pull._smoke_test_row_count") as _smoke,
        ):
            _drop.return_value = None
            _restore.return_value = None
            _smoke.return_value = None
            return runner.invoke(
                app,
                [
                    "backups",
                    "pull",
                    backup["backupId"],
                    "--target-db",
                    "tpp_odoo_erp",
                    "--target-host",
                    "localhost",
                    "--target-port",
                    "5434",
                    "--target-user",
                    "odoo",
                    "--target-password",
                    "pw",
                    "--force",
                    "--no-smoke-test",
                ],
            )

    @pytest.mark.parametrize(
        "newest_under_new_prefix,expected_key",
        [
            (
                True,
                "compose-foo-qsokry_postgres/tpp-infra-postgres/tpp_odoo_erp/2026-04-19T11-24-29Z.sql.gz",
            ),
            (
                False,
                "tpp-infra-postgres/tpp_odoo_erp-2026-04-19T11-24-29Z.dump",
            ),
        ],
    )
    def test_pull_picks_globally_newest_across_prefixes(
        self,
        mock_client: MagicMock,
        newest_under_new_prefix: bool,
        expected_key: str,
    ) -> None:
        old_time = datetime(2026, 4, 18, 4, 9, 13, tzinfo=UTC)
        new_time = datetime(2026, 4, 19, 11, 24, 29, tzinfo=UTC)

        # NEW-format key (hierarchical) lives under <appName>/<prefix>/
        new_format_key = "compose-foo-qsokry_postgres/tpp-infra-postgres/tpp_odoo_erp/2026-04-19T11-24-29Z.sql.gz"
        # OLD-format key (flat) lives directly under <prefix> — note the
        # db-name-prefixed filename convention.
        old_format_key = "tpp-infra-postgres/tpp_odoo_erp-2026-04-19T11-24-29Z.dump"

        if newest_under_new_prefix:
            # Old-format file is stale (2026-04-18), new-format file is fresh.
            keys = [
                ("tpp-infra-postgres/tpp_odoo_erp-2026-04-18T04-09-13Z.dump", old_time, 100),
                (new_format_key, new_time, 200),
            ]
        else:
            # Opposite: new-format file is stale, old-format file is fresh.
            keys = [
                (
                    "compose-foo-qsokry_postgres/tpp-infra-postgres/tpp_odoo_erp/2026-04-18T04-09-13Z.sql.gz",
                    old_time,
                    100,
                ),
                (old_format_key, new_time, 200),
            ]

        fake_s3 = FakeS3(keys)
        result = self._run_pull(
            mock_client,
            fake_s3,
            SAMPLE_BACKUP,
            compose=SAMPLE_COMPOSE,
        )
        assert result.exit_code == 0, result.output
        assert fake_s3.download_calls, "no download was attempted"
        chosen_key = fake_s3.download_calls[0][1]
        assert chosen_key == expected_key, f"expected globally-newest key {expected_key!r}, got {chosen_key!r}"

    def test_pull_filters_by_database_name(self, mock_client: MagicMock) -> None:
        """Defense-in-depth: objects whose name doesn't contain the DB are skipped."""
        now = datetime.now(UTC)
        # The newest object is for a DIFFERENT database — should be ignored.
        keys = [
            (
                "compose-foo-qsokry_postgres/tpp-infra-postgres/tpp_odoo_erp/2026-04-18T04-09-13Z.sql.gz",
                now.replace(year=now.year - 1),
                100,
            ),
            (
                "compose-foo-qsokry_postgres/tpp-infra-postgres/some_other_db/2099-01-01T00-00-00Z.sql.gz",
                now.replace(year=2099),
                200,
            ),
        ]
        fake_s3 = FakeS3(keys)
        result = self._run_pull(
            mock_client,
            fake_s3,
            SAMPLE_BACKUP,
            compose=SAMPLE_COMPOSE,
        )
        assert result.exit_code == 0, result.output
        chosen_key = fake_s3.download_calls[0][1]
        assert "tpp_odoo_erp" in chosen_key
        assert "some_other_db" not in chosen_key

    def test_pull_non_compose_backup_uses_single_prefix(self, mock_client: MagicMock) -> None:
        """When composeId is None (postgres/mysql/mariadb/mongo native backups),
        no new-format expansion — only the stored prefix is searched.
        """
        native_backup = {
            "backupId": "bkp-native",
            "destinationId": "dst-001",
            "database": "tpp_odoo_erp",
            "prefix": "tpp-infra-postgres/tpp_odoo_erp",
            "backupType": "database",
            "databaseType": "postgres",
            "composeId": None,
        }
        now = datetime.now(UTC)
        # Place a lone object under the flat prefix.
        keys = [
            (
                "tpp-infra-postgres/tpp_odoo_erp-2026-04-19T11-24-29Z.dump",
                now,
                100,
            ),
        ]
        fake_s3 = FakeS3(keys)
        result = self._run_pull(
            mock_client,
            fake_s3,
            native_backup,
            compose=None,
        )
        assert result.exit_code == 0, result.output

        # /compose.one must NOT have been called — it's not a compose backup.
        called_paths = [call.args[0] for call in mock_client.get.call_args_list if call.args]
        assert "/compose.one" not in called_paths, (
            f"non-compose backup should not fetch compose.one (got calls: {called_paths})"
        )

    def test_pull_missing_prefix_silently_skipped(self, mock_client: MagicMock) -> None:
        """If one of the candidate prefixes has no objects, don't fail — scan the other."""
        now = datetime.now(UTC)
        # Only an OLD-format object exists; the NEW prefix is empty in this bucket.
        keys = [
            (
                "tpp-infra-postgres/tpp_odoo_erp-2026-04-19T11-24-29Z.dump",
                now,
                100,
            ),
        ]
        fake_s3 = FakeS3(keys)
        result = self._run_pull(
            mock_client,
            fake_s3,
            SAMPLE_BACKUP,
            compose=SAMPLE_COMPOSE,
        )
        assert result.exit_code == 0, result.output
        assert fake_s3.download_calls[0][1] == ("tpp-infra-postgres/tpp_odoo_erp-2026-04-19T11-24-29Z.dump")


# ---------------------------------------------------------------------------
# _get_search_prefixes — direct unit tests
# ---------------------------------------------------------------------------


class TestGetSearchPrefixes:
    """Direct unit tests for the prefix-expansion helper."""

    def _ctx(self, mock_client: MagicMock, compose: dict[str, Any] | None = None) -> AppContext:
        def get_side_effect(path: str, params: dict[str, Any] | None = None) -> Any:
            if path == "/compose.one":
                return compose or {}
            return {}

        mock_client.get.side_effect = get_side_effect
        ctx = AppContext(json_mode=True)
        ctx._client = mock_client  # type: ignore[attr-defined]
        return ctx

    def test_compose_with_service_name(self, mock_client: MagicMock) -> None:
        from kctl_dokploy.commands.backups_pull import _get_search_prefixes

        ctx = self._ctx(mock_client, compose=SAMPLE_COMPOSE)
        prefixes = _get_search_prefixes(ctx, SAMPLE_BACKUP)
        # Preferred: <appName>_<serviceName>/<rawPrefix>/
        # Fallback:  <appName>/<rawPrefix>/
        # Legacy:    <rawPrefix>
        assert prefixes == [
            "compose-foo-qsokry_postgres/tpp-infra-postgres/tpp_odoo_erp/",
            "compose-foo-qsokry/tpp-infra-postgres/tpp_odoo_erp/",
            "tpp-infra-postgres/tpp_odoo_erp",
        ]

    def test_compose_without_service_name(self, mock_client: MagicMock) -> None:
        from kctl_dokploy.commands.backups_pull import _get_search_prefixes

        backup = dict(SAMPLE_BACKUP)
        backup.pop("serviceName", None)
        ctx = self._ctx(mock_client, compose=SAMPLE_COMPOSE)
        prefixes = _get_search_prefixes(ctx, backup)
        assert prefixes == [
            "compose-foo-qsokry/tpp-infra-postgres/tpp_odoo_erp/",
            "tpp-infra-postgres/tpp_odoo_erp",
        ]

    def test_non_compose_backup_no_expansion(self, mock_client: MagicMock) -> None:
        from kctl_dokploy.commands.backups_pull import _get_search_prefixes

        backup = {
            "backupId": "bkp-native",
            "database": "tpp_odoo_erp",
            "prefix": "tpp-infra-postgres/tpp_odoo_erp",
            "backupType": "database",
            "databaseType": "postgres",
            "composeId": None,
        }
        ctx = self._ctx(mock_client, compose=None)
        prefixes = _get_search_prefixes(ctx, backup)
        # Only the raw prefix; no /compose.one call.
        assert prefixes == ["tpp-infra-postgres/tpp_odoo_erp"]
        called_paths = [call.args[0] for call in mock_client.get.call_args_list if call.args]
        assert "/compose.one" not in called_paths


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
