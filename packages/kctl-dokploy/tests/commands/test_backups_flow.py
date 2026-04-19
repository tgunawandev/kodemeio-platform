"""Tests for backups_flow commands (dump-compose, download, restore-local, refresh)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from typer.testing import CliRunner

from kctl_dokploy.cli import app
from kctl_dokploy.commands import backups_flow as bf
from kctl_dokploy.core.callbacks import AppContext

runner = CliRunner()


SAMPLE_COMPOSE = {
    "composeId": "comp-xyz",
    "name": "tpp-infra-postgres",
    "appName": "compose-sample-app",
    "serverId": "srv-1",
    "env": "POSTGRES_USER=postgres\nPOSTGRES_PASSWORD=secret123\nPOSTGRES_DB=mydb\n",
}
SAMPLE_DEST = {
    "destinationId": "dest-1",
    "name": "hz-s3",
    "provider": "s3",
    "accessKey": "AK",
    "secretAccessKey": "SK",
    "bucket": "my-bucket",
    "region": "fsn1",
    "endpoint": "https://fsn1.your-objectstorage.com",
}
SAMPLE_SERVER = {"serverId": "srv-1", "name": "tpp-prod-01", "ipAddress": "10.0.0.1", "username": "root"}


@pytest.fixture(autouse=True)
def _patch_client(mock_client: MagicMock):
    with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
        yield


# ---------------------------------------------------------------------------
# Helper-level unit tests (no Typer invocation)
# ---------------------------------------------------------------------------


class TestParseEnvStr:
    def test_empty(self) -> None:
        assert bf._parse_env_str("") == {}

    def test_basic(self) -> None:
        env = "A=1\nB=2\n"
        assert bf._parse_env_str(env) == {"A": "1", "B": "2"}

    def test_strips_surrounding_quotes(self) -> None:
        env = "PW=\"secret\"\nUSER='bob'\n"
        assert bf._parse_env_str(env) == {"PW": "secret", "USER": "bob"}

    def test_ignores_comments(self) -> None:
        env = "# header\nA=1\n  # indented\nB=2"
        assert bf._parse_env_str(env) == {"A": "1", "B": "2"}

    def test_ignores_lines_without_equals(self) -> None:
        env = "A=1\nnoequals\nB=2"
        assert bf._parse_env_str(env) == {"A": "1", "B": "2"}


class TestLooksLikeCustomDump:
    def test_pgdmp_magic_detected(self, tmp_path: Path) -> None:
        f = tmp_path / "x.dump"
        f.write_bytes(b"PGDMP\x00\x01\x02")
        assert bf._looks_like_custom_dump(f) is True

    def test_plain_sql_rejected(self, tmp_path: Path) -> None:
        f = tmp_path / "x.sql"
        f.write_bytes(b"CREATE TABLE foo (id int);")
        assert bf._looks_like_custom_dump(f) is False

    def test_missing_file(self, tmp_path: Path) -> None:
        assert bf._looks_like_custom_dump(tmp_path / "missing") is False


# ---------------------------------------------------------------------------
# dump-compose
# ---------------------------------------------------------------------------


class TestDumpCompose:
    def test_dump_compose_builds_ssh_cmd_and_uploads(self, mock_client: MagicMock) -> None:
        mock_client.get.side_effect = _compose_one_then_dest_then_server

        fake_s3 = MagicMock()
        fake_s3.head_object.return_value = {"ContentLength": 12345}

        # Mock container discovery (subprocess.run)
        ps_result = MagicMock(returncode=0)
        ps_result.stdout = "compose-sample-app-postgres-1\tpostgres\nother-container\tredis\n"
        ps_result.stderr = ""

        # Mock pg_dump subprocess.Popen
        proc = MagicMock()
        proc.stdout = MagicMock()
        proc.stderr = MagicMock()
        proc.stderr.read.return_value = b""
        proc.wait.return_value = 0
        proc.poll.return_value = 0  # finished

        with (
            patch.object(bf, "_build_s3_client", return_value=fake_s3),
            patch("kctl_dokploy.commands.backups_flow.subprocess.run", return_value=ps_result),
            patch("kctl_dokploy.commands.backups_flow.subprocess.Popen", return_value=proc) as mock_popen,
        ):
            result = runner.invoke(
                app,
                [
                    "backups",
                    "dump-compose",
                    "--compose",
                    "comp-xyz",
                    "--destination",
                    "dest-1",
                    "--database",
                    "mydb",
                ],
            )
        assert result.exit_code == 0, result.output
        # Popen got an SSH command because serverId was set
        popen_args = mock_popen.call_args[0][0]
        assert popen_args[0] == "ssh"
        assert "root@10.0.0.1" in popen_args
        assert "pg_dump" in popen_args
        assert "-d" in popen_args and "mydb" in popen_args
        # S3 upload called
        fake_s3.upload_fileobj.assert_called_once()
        up_args = fake_s3.upload_fileobj.call_args[0]
        assert up_args[1] == "my-bucket"
        assert up_args[2].startswith("tpp-infra-postgres/mydb-")
        assert up_args[2].endswith(".dump")  # no .gz on custom format

    def test_dump_compose_local_with_no_ssh(self, mock_client: MagicMock) -> None:
        mock_client.get.side_effect = _compose_one_then_dest

        fake_s3 = MagicMock()
        fake_s3.head_object.return_value = {"ContentLength": 100}

        ps_result = MagicMock(returncode=0, stdout="compose-sample-app-postgres-1\tpostgres\n", stderr="")
        proc = MagicMock()
        proc.stdout = MagicMock()
        proc.stderr = MagicMock()
        proc.stderr.read.return_value = b""
        proc.wait.return_value = 0
        proc.poll.return_value = 0

        with (
            patch.object(bf, "_build_s3_client", return_value=fake_s3),
            patch("kctl_dokploy.commands.backups_flow.subprocess.run", return_value=ps_result),
            patch("kctl_dokploy.commands.backups_flow.subprocess.Popen", return_value=proc) as mock_popen,
        ):
            result = runner.invoke(
                app,
                [
                    "backups",
                    "dump-compose",
                    "--compose",
                    "comp-xyz",
                    "--destination",
                    "dest-1",
                    "--database",
                    "mydb",
                    "--no-ssh",
                ],
            )
        assert result.exit_code == 0, result.output
        # With --no-ssh, Popen gets docker directly (no ssh prefix)
        assert mock_popen.call_args[0][0][0] == "docker"

    def test_dump_compose_pg_dump_failure_exits_nonzero(self, mock_client: MagicMock) -> None:
        mock_client.get.side_effect = _compose_one_then_dest

        fake_s3 = MagicMock()
        ps_result = MagicMock(returncode=0, stdout="compose-sample-app-postgres-1\tpostgres\n", stderr="")
        proc = MagicMock()
        proc.stdout = MagicMock()
        proc.stderr = MagicMock()
        proc.stderr.read.return_value = b"pg_dump: connection refused"
        proc.wait.return_value = 2
        proc.poll.return_value = 2

        with (
            patch.object(bf, "_build_s3_client", return_value=fake_s3),
            patch("kctl_dokploy.commands.backups_flow.subprocess.run", return_value=ps_result),
            patch("kctl_dokploy.commands.backups_flow.subprocess.Popen", return_value=proc),
        ):
            result = runner.invoke(
                app,
                [
                    "backups",
                    "dump-compose",
                    "--compose",
                    "comp-xyz",
                    "--destination",
                    "dest-1",
                    "--database",
                    "mydb",
                    "--no-ssh",
                ],
            )
        assert result.exit_code != 0

    def test_missing_postgres_password_errors(self, mock_client: MagicMock) -> None:
        """Compose env without POSTGRES_PASSWORD should error clearly."""
        no_pw = {**SAMPLE_COMPOSE, "env": "POSTGRES_USER=postgres\nPOSTGRES_DB=x\n"}
        mock_client.get.return_value = no_pw
        result = runner.invoke(
            app,
            [
                "backups",
                "dump-compose",
                "--compose",
                "comp-xyz",
                "--destination",
                "dest-1",
                "--database",
                "mydb",
                "--no-ssh",
            ],
        )
        assert result.exit_code != 0
        assert "POSTGRES_PASSWORD" in result.output


# ---------------------------------------------------------------------------
# download
# ---------------------------------------------------------------------------


class TestDownload:
    def test_download_calls_s3_and_writes_file(self, mock_client: MagicMock, tmp_path: Path) -> None:
        mock_client.get.return_value = SAMPLE_DEST
        fake_s3 = MagicMock()

        # Simulate s3.download_file creating a file
        out = tmp_path / "dump.sql"

        def _fake_download(bucket: str, key: str, path: str) -> None:
            Path(path).write_bytes(b"fake dump contents")

        fake_s3.download_file.side_effect = _fake_download

        with patch.object(bf, "_build_s3_client", return_value=fake_s3):
            result = runner.invoke(
                app,
                [
                    "backups",
                    "download",
                    "path/to/file.dump",
                    "--destination",
                    "dest-1",
                    "--output",
                    str(out),
                ],
            )
        assert result.exit_code == 0, result.output
        fake_s3.download_file.assert_called_once_with("my-bucket", "path/to/file.dump", str(out))
        assert out.exists() and out.read_bytes() == b"fake dump contents"

    def test_download_errors_when_no_bucket(self, mock_client: MagicMock, tmp_path: Path) -> None:
        mock_client.get.return_value = {**SAMPLE_DEST, "bucket": ""}
        result = runner.invoke(
            app,
            [
                "backups",
                "download",
                "x.dump",
                "--destination",
                "dest-1",
                "--output",
                str(tmp_path / "x.dump"),
            ],
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# restore-local
# ---------------------------------------------------------------------------


class TestRestoreLocal:
    def test_restore_custom_format_uses_pg_restore(self, mock_client: MagicMock, tmp_path: Path) -> None:
        mock_client.get.return_value = SAMPLE_COMPOSE

        dump = tmp_path / "x.dump"
        dump.write_bytes(b"PGDMP\x01\x02\x03\x04")

        # Two subprocess.run calls expected: docker ps + pg_restore
        # We keep track of all subprocess.run calls via side_effect
        ps_result = MagicMock(returncode=0, stdout="compose-sample-app-postgres-1\tpostgres\n", stderr="")
        drop_result = MagicMock(returncode=0, stdout="", stderr="")
        create_result = MagicMock(returncode=0, stdout="", stderr="")
        restore_result = MagicMock(returncode=0, stdout=b"", stderr=b"")

        calls = []

        def run_side_effect(*args, **kwargs):
            calls.append(args[0])
            # First call: docker ps (list). Next two: psql DROP/CREATE. Last: pg_restore (has -i).
            argv = args[0]
            if argv[:2] == ["docker", "ps"]:
                return ps_result
            if "DROP DATABASE" in " ".join(argv):
                return drop_result
            if "CREATE DATABASE" in " ".join(argv):
                return create_result
            return restore_result

        with patch("kctl_dokploy.commands.backups_flow.subprocess.run", side_effect=run_side_effect):
            result = runner.invoke(
                app,
                [
                    "backups",
                    "restore-local",
                    str(dump),
                    "--compose",
                    "comp-xyz",
                    "--service",
                    "postgres",
                    "--force",
                ],
            )
        assert result.exit_code == 0, result.output
        # Final call should be pg_restore (custom format detected by magic bytes)
        final_cmd = calls[-1]
        assert "pg_restore" in final_cmd
        assert "--exit-on-error" in final_cmd

    def test_restore_plain_sql_uses_psql_with_on_error_stop(self, mock_client: MagicMock, tmp_path: Path) -> None:
        mock_client.get.return_value = SAMPLE_COMPOSE

        sql = tmp_path / "x.sql"
        sql.write_text("CREATE TABLE foo (id int);")

        ps_result = MagicMock(returncode=0, stdout="compose-sample-app-postgres-1\tpostgres\n", stderr="")
        ok = MagicMock(returncode=0, stdout=b"", stderr=b"")
        calls = []

        def run_side_effect(*args, **kwargs):
            calls.append(args[0])
            if args[0][:2] == ["docker", "ps"]:
                return ps_result
            return ok

        with patch("kctl_dokploy.commands.backups_flow.subprocess.run", side_effect=run_side_effect):
            result = runner.invoke(
                app,
                [
                    "backups",
                    "restore-local",
                    str(sql),
                    "--compose",
                    "comp-xyz",
                    "--force",
                ],
            )
        assert result.exit_code == 0, result.output
        final_cmd = calls[-1]
        assert "psql" in final_cmd
        assert "ON_ERROR_STOP=1" in final_cmd

    def test_restore_missing_file_errors(self, mock_client: MagicMock, tmp_path: Path) -> None:
        mock_client.get.return_value = SAMPLE_COMPOSE
        result = runner.invoke(
            app,
            [
                "backups",
                "restore-local",
                str(tmp_path / "does-not-exist.dump"),
                "--compose",
                "comp-xyz",
                "--force",
            ],
        )
        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_restore_failure_surfaces_error(self, mock_client: MagicMock, tmp_path: Path) -> None:
        mock_client.get.return_value = SAMPLE_COMPOSE

        dump = tmp_path / "x.dump"
        dump.write_bytes(b"PGDMP\x01\x02\x03\x04")

        ps_result = MagicMock(returncode=0, stdout="compose-sample-app-postgres-1\tpostgres\n", stderr="")
        ok = MagicMock(returncode=0, stdout="", stderr="")
        fail = MagicMock(returncode=1, stdout=b"", stderr=b"pg_restore: ERROR: schema exists")

        def run_side_effect(*args, **kwargs):
            argv = args[0]
            if argv[:2] == ["docker", "ps"]:
                return ps_result
            if "DROP DATABASE" in " ".join(argv) or "CREATE DATABASE" in " ".join(argv):
                return ok
            return fail

        with patch("kctl_dokploy.commands.backups_flow.subprocess.run", side_effect=run_side_effect):
            result = runner.invoke(
                app,
                [
                    "backups",
                    "restore-local",
                    str(dump),
                    "--compose",
                    "comp-xyz",
                    "--force",
                ],
            )
        assert result.exit_code != 0
        assert "Restore failed" in result.output or "schema exists" in result.output


# ---------------------------------------------------------------------------
# refresh --latest: skip dump, pick newest S3 key matching the database.
# ---------------------------------------------------------------------------


class TestRefreshLatest:
    def test_latest_picks_newest_matching_key_and_skips_dump(self, tmp_path: Path) -> None:
        """--latest should download the newest S3 file matching --database, not dump fresh."""
        # The command builds a DokployClient for --source-profile by reading the
        # shared kctl config. We monkeypatch the _build_source_client helper so
        # the test doesn't need a real profile, and so we can drive the
        # responses it returns.
        source_client = MagicMock()
        source_client.get.side_effect = lambda endpoint, params=None: {
            "/destination.one": SAMPLE_DEST,
        }.get(endpoint, {})

        fake_s3 = MagicMock()

        # We now list via boto3 paginator (list_objects_v2) instead of Dokploy's
        # buggy /backup.listBackupFiles. The paginator yields pages containing
        # Contents lists. _list_s3_keys sorts by LastModified — the test mocks
        # LastModified as an offset-aware datetime so the newest wins.
        from datetime import datetime, timezone

        def _paginate(**kwargs: object):  # matches boto3 signature
            yield {
                "Contents": [
                    {
                        "Key": "tpp-infra-postgres/tpp_odoo_erp-2026-04-17T02-00-00Z.dump",
                        "LastModified": datetime(2026, 4, 17, 2, 0, tzinfo=timezone.utc),
                    },
                    {
                        "Key": "tpp-infra-postgres/tpp_odoo_erp-2026-04-18T02-00-00Z.dump",  # newest
                        "LastModified": datetime(2026, 4, 18, 2, 0, tzinfo=timezone.utc),
                    },
                    {
                        "Key": "tpp-infra-postgres/other_db-2026-04-18T02-00-00Z.dump",  # different db
                        "LastModified": datetime(2026, 4, 18, 2, 0, tzinfo=timezone.utc),
                    },
                ],
            }

        fake_paginator = MagicMock()
        fake_paginator.paginate.side_effect = _paginate
        fake_s3.get_paginator.return_value = fake_paginator

        def _fake_download(bucket: str, key: str, path: str) -> None:
            # Write PGDMP magic so restore_local recognises as custom-format dump.
            Path(path).write_bytes(b"PGDMP\x00\x00\x00")

        fake_s3.download_file.side_effect = _fake_download

        # Fake the target-side Dokploy client that's resolved through ctx.obj
        target_client = MagicMock()
        target_client.get.side_effect = lambda endpoint, params=None: SAMPLE_COMPOSE

        # docker ps (local target) + drop/create/restore (all exit 0)
        ps_result = MagicMock(returncode=0, stdout="compose-sample-app-postgres-1\tpostgres\n", stderr="")
        ok = MagicMock(returncode=0, stdout=b"", stderr=b"")

        def run_side_effect(*args, **kwargs):
            argv = args[0]
            if argv[:2] == ["docker", "ps"]:
                return ps_result
            return ok

        # Route Popen so the fresh-dump path (if accidentally taken) would blow up.
        def no_dump(*args, **kwargs):  # pragma: no cover - guard for regressions
            raise AssertionError("fresh dump pg_dump should not be invoked under --latest")

        with (
            patch.object(AppContext, "client", new_callable=PropertyMock, return_value=target_client),
            patch.object(bf, "_build_source_client", return_value=source_client),
            patch.object(bf, "_build_s3_client", return_value=fake_s3),
            patch("kctl_dokploy.commands.backups_flow.subprocess.run", side_effect=run_side_effect),
            patch("kctl_dokploy.commands.backups_flow.subprocess.Popen", side_effect=no_dump),
        ):
            result = runner.invoke(
                app,
                [
                    "backups",
                    "refresh",
                    "--source-profile",
                    "idtpp",
                    "--source-compose",
                    "comp-xyz",
                    "--source-destination",
                    "dest-1",
                    "--target-compose",
                    "comp-xyz",
                    "--database",
                    "tpp_odoo_erp",
                    "--latest",
                    "--force",
                ],
            )

        assert result.exit_code == 0, result.output
        # The NEWEST matching file must have been downloaded (the 2026-04-18 one),
        # not the older 2026-04-17 file nor the unrelated other_db file.
        assert fake_s3.download_file.call_count == 1
        download_args = fake_s3.download_file.call_args[0]
        assert download_args[0] == SAMPLE_DEST["bucket"]
        assert download_args[1] == "tpp-infra-postgres/tpp_odoo_erp-2026-04-18T02-00-00Z.dump"

    def test_latest_errors_when_no_matching_key(self) -> None:
        """No matching key → clear error and exit 1, not a silent miss."""
        source_client = MagicMock()
        source_client.get.side_effect = lambda endpoint, params=None: {
            "/destination.one": SAMPLE_DEST,
        }.get(endpoint, {})

        # boto3 paginator returns an unrelated file; filter should reject it.
        from datetime import datetime, timezone

        fake_s3 = MagicMock()
        fake_pg = MagicMock()
        fake_pg.paginate.return_value = [
            {
                "Contents": [
                    {
                        "Key": "other_db/file-2026-04-18.dump",
                        "LastModified": datetime(2026, 4, 18, 2, 0, tzinfo=timezone.utc),
                    },
                ],
            },
        ]
        fake_s3.get_paginator.return_value = fake_pg

        with (
            patch.object(AppContext, "client", new_callable=PropertyMock, return_value=MagicMock()),
            patch.object(bf, "_build_source_client", return_value=source_client),
            patch.object(bf, "_build_s3_client", return_value=fake_s3),
        ):
            result = runner.invoke(
                app,
                [
                    "backups",
                    "refresh",
                    "--source-profile",
                    "idtpp",
                    "--source-compose",
                    "comp-xyz",
                    "--source-destination",
                    "dest-1",
                    "--target-compose",
                    "comp-xyz",
                    "--database",
                    "tpp_odoo_erp",
                    "--latest",
                    "--force",
                ],
            )
        assert result.exit_code != 0
        assert "No S3 files" in result.output or "tpp_odoo_erp" in result.output


# ---------------------------------------------------------------------------
# Shared helpers for the fixture side_effects
# ---------------------------------------------------------------------------


def _compose_one_then_dest_then_server(*args, **kwargs):
    """side_effect: /compose.one, /destination.one, /server.one — in dump_compose order."""
    endpoint = args[0] if args else kwargs.get("endpoint", "")
    if endpoint == "/compose.one":
        return SAMPLE_COMPOSE
    if endpoint == "/server.one":
        return SAMPLE_SERVER
    if endpoint == "/destination.one":
        return SAMPLE_DEST
    return {}


def _compose_one_then_dest(*args, **kwargs):
    """side_effect: /compose.one, /destination.one — for --no-ssh path."""
    endpoint = args[0] if args else kwargs.get("endpoint", "")
    if endpoint == "/compose.one":
        return SAMPLE_COMPOSE
    if endpoint == "/destination.one":
        return SAMPLE_DEST
    return {}
