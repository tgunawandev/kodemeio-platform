"""Tests for the `backups restore` Dokploy-native restore command.

Existing happy-path / metadata tests pass ``--skip-preflight --no-ensure-db
--skip-verify`` so the new robustness machinery (compose introspection,
remote command schedules, post-restore verification) doesn't reach out to
unmocked HTTP endpoints. Dedicated robustness tests are in
``TestBackupsRestoreRobustness`` and mock the helpers individually.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from typer.testing import CliRunner

# Common opt-out flags for tests that don't want to exercise the new
# pre-flight / ensure-db / verify code paths. Tests that DO exercise them
# patch the helper functions directly.
OPT_OUT_FLAGS = [
    "--skip-preflight",
    "--no-ensure-db",
    "--skip-verify",
]


class TestBackupsRestore:
    def test_happy_path_streams_logs_exits_zero(self) -> None:
        from kctl_dokploy.cli import app

        async def fake_stream(self: Any, endpoint: str, payload: dict) -> Any:
            assert endpoint == "/trpc/backup.restoreBackupWithLogs"
            p = payload["json"]
            assert p["backupType"] == "compose"
            assert p["databaseType"] == "postgres"
            assert p["databaseId"] == "cmp-123"
            assert p["destinationId"] == "dst-456"
            assert p["databaseName"] == "mydb"
            assert p["backupFile"] == "keypath/file.sql.gz"
            for line in [
                "Starting restore...",
                "Downloaded 10.1 MB",
                "Restore completed successfully",
            ]:
                yield line

        with patch(
            "kctl_dokploy.core.async_client.AsyncDokployClient.stream_subscription",
            new=fake_stream,
        ):
            result = CliRunner().invoke(
                app,
                [
                    "-p",
                    "local",
                    "backups",
                    "restore",
                    "--compose",
                    "cmp-123",
                    "--destination",
                    "dst-456",
                    "--database-name",
                    "mydb",
                    "--file",
                    "keypath/file.sql.gz",
                    "--service-name",
                    "postgres",
                    "--database-user",
                    "odoo",
                    *OPT_OUT_FLAGS,
                ],
            )

        assert result.exit_code == 0, result.output
        assert "[Dokploy] Starting restore..." in result.output
        assert "[Dokploy] Restore completed successfully" in result.output

    def test_error_line_exits_one(self) -> None:
        from kctl_dokploy.cli import app

        async def fake_stream(self: Any, endpoint: str, payload: dict) -> Any:
            yield "Downloading..."
            yield "Error: pg_restore crashed: exit 1"

        with (
            patch(
                "kctl_dokploy.core.async_client.AsyncDokployClient.stream_subscription",
                new=fake_stream,
            ),
            patch(
                "kctl_dokploy.commands.backups_restore._tail_postgres_logs",
                return_value="",
            ),
        ):
            result = CliRunner().invoke(
                app,
                [
                    "-p",
                    "local",
                    "backups",
                    "restore",
                    "--compose",
                    "cmp-123",
                    "--destination",
                    "dst-456",
                    "--database-name",
                    "mydb",
                    "--file",
                    "x.sql.gz",
                    "--service-name",
                    "postgres",
                    "--database-user",
                    "odoo",
                    *OPT_OUT_FLAGS,
                ],
            )
        assert result.exit_code == 1, result.output
        assert "Error: pg_restore crashed" in result.output

    def test_missing_file_and_latest_rejects(self) -> None:
        from kctl_dokploy.cli import app

        result = CliRunner().invoke(
            app,
            [
                "-p",
                "local",
                "backups",
                "restore",
                "--compose",
                "cmp-123",
                "--destination",
                "dst-456",
                "--database-name",
                "mydb",
                "--service-name",
                "postgres",
                "--database-user",
                "odoo",
            ],
        )
        assert result.exit_code != 0
        assert "--file" in result.output or "--latest" in result.output


class TestBackupsRestoreMetadata:
    @staticmethod
    def _make_fake_stream(captured: dict[str, Any]):
        async def fake_stream(self_: Any, endpoint: str, payload: dict) -> Any:
            captured["endpoint"] = endpoint
            captured["payload"] = payload
            yield "Restore completed successfully"

        return fake_stream

    def test_service_name_flag_goes_to_metadata(self) -> None:
        from kctl_dokploy.cli import app

        captured: dict[str, Any] = {}
        with patch(
            "kctl_dokploy.core.async_client.AsyncDokployClient.stream_subscription",
            new=self._make_fake_stream(captured),
        ):
            result = CliRunner().invoke(
                app,
                [
                    "-p",
                    "local",
                    "backups",
                    "restore",
                    "--compose",
                    "cmp-123",
                    "--destination",
                    "dst-456",
                    "--database-name",
                    "mydb",
                    "--file",
                    "k.sql.gz",
                    "--service-name",
                    "postgres",
                    "--database-user",
                    "odoo",
                    *OPT_OUT_FLAGS,
                ],
            )
        assert result.exit_code == 0, result.output
        meta = captured["payload"]["json"]["metadata"]
        assert meta["serviceName"] == "postgres"

    def test_database_user_with_postgres(self) -> None:
        from kctl_dokploy.cli import app

        captured: dict[str, Any] = {}
        with patch(
            "kctl_dokploy.core.async_client.AsyncDokployClient.stream_subscription",
            new=self._make_fake_stream(captured),
        ):
            result = CliRunner().invoke(
                app,
                [
                    "-p",
                    "local",
                    "backups",
                    "restore",
                    "--compose",
                    "cmp-123",
                    "--destination",
                    "dst-456",
                    "--database-name",
                    "mydb",
                    "--file",
                    "k.sql.gz",
                    "--db-type",
                    "postgres",
                    "--service-name",
                    "postgres",
                    "--database-user",
                    "odoo",
                    *OPT_OUT_FLAGS,
                ],
            )
        assert result.exit_code == 0, result.output
        meta = captured["payload"]["json"]["metadata"]
        assert meta["postgres"] == {"databaseUser": "odoo"}

    def test_database_user_and_password_with_mariadb(self) -> None:
        from kctl_dokploy.cli import app

        captured: dict[str, Any] = {}
        with patch(
            "kctl_dokploy.core.async_client.AsyncDokployClient.stream_subscription",
            new=self._make_fake_stream(captured),
        ):
            result = CliRunner().invoke(
                app,
                [
                    "-p",
                    "local",
                    "backups",
                    "restore",
                    "--compose",
                    "cmp-123",
                    "--destination",
                    "dst-456",
                    "--database-name",
                    "mydb",
                    "--file",
                    "k.sql.gz",
                    "--db-type",
                    "mariadb",
                    "--service-name",
                    "mariadb",
                    "--database-user",
                    "root",
                    "--database-password",
                    "hunter2",
                    *OPT_OUT_FLAGS,
                ],
            )
        assert result.exit_code == 0, result.output
        meta = captured["payload"]["json"]["metadata"]
        assert meta["mariadb"] == {"databaseUser": "root", "databasePassword": "hunter2"}

    def test_database_password_with_mysql_becomes_root_password(self) -> None:
        from kctl_dokploy.cli import app

        captured: dict[str, Any] = {}
        with patch(
            "kctl_dokploy.core.async_client.AsyncDokployClient.stream_subscription",
            new=self._make_fake_stream(captured),
        ):
            result = CliRunner().invoke(
                app,
                [
                    "-p",
                    "local",
                    "backups",
                    "restore",
                    "--compose",
                    "cmp-123",
                    "--destination",
                    "dst-456",
                    "--database-name",
                    "mydb",
                    "--file",
                    "k.sql.gz",
                    "--db-type",
                    "mysql",
                    "--service-name",
                    "mysql",
                    "--database-password",
                    "rootpw",
                    *OPT_OUT_FLAGS,
                ],
            )
        assert result.exit_code == 0, result.output
        meta = captured["payload"]["json"]["metadata"]
        assert meta["mysql"] == {"databaseRootPassword": "rootpw"}

    def test_no_metadata_flags_omits_metadata_key(self) -> None:
        from kctl_dokploy.cli import app

        captured: dict[str, Any] = {}
        with patch(
            "kctl_dokploy.core.async_client.AsyncDokployClient.stream_subscription",
            new=self._make_fake_stream(captured),
        ):
            result = CliRunner().invoke(
                app,
                [
                    "-p",
                    "local",
                    "backups",
                    "restore",
                    "--compose",
                    "cmp-123",
                    "--destination",
                    "dst-456",
                    "--database-name",
                    "mydb",
                    "--file",
                    "k.sql.gz",
                    "--backup-type",
                    "database",
                    "--db-type",
                    "mysql",
                    *OPT_OUT_FLAGS,
                ],
            )
        assert result.exit_code == 0, result.output
        assert "metadata" not in captured["payload"]["json"]

    def test_compose_without_service_name_fails_fast(self) -> None:
        from kctl_dokploy.cli import app

        result = CliRunner().invoke(
            app,
            [
                "-p",
                "local",
                "backups",
                "restore",
                "--compose",
                "cmp-123",
                "--destination",
                "dst-456",
                "--database-name",
                "mydb",
                "--file",
                "k.sql.gz",
            ],
        )
        assert result.exit_code != 0
        assert "--service-name" in result.output

    def test_postgres_without_database_user_fails_fast(self) -> None:
        from kctl_dokploy.cli import app

        result = CliRunner().invoke(
            app,
            [
                "-p",
                "local",
                "backups",
                "restore",
                "--compose",
                "cmp-123",
                "--destination",
                "dst-456",
                "--database-name",
                "mydb",
                "--file",
                "k.sql.gz",
                "--service-name",
                "postgres",
            ],
        )
        assert result.exit_code != 0
        assert "--database-user" in result.output


# ---------------------------------------------------------------------------
# Robustness tests — pre-flight, --ensure-db, --force, post-restore verify,
# and failure-diagnostic surfacing of postgres logs.
# ---------------------------------------------------------------------------


def _ok_stream():
    async def fake(self_: Any, endpoint: str, payload: dict) -> Any:
        yield "Restore completed successfully"

    return fake


def _err_stream():
    async def fake(self_: Any, endpoint: str, payload: dict) -> Any:
        yield "Error: Remote command failed with exit code 1"

    return fake


class TestBackupsRestoreRobustness:
    def test_preflight_validates_compose_service_and_s3(self) -> None:
        """When pre-flight is enabled (default), the command resolves the
        compose, checks the named service, and confirms the S3 key exists
        before kicking off the SSE stream."""
        from kctl_dokploy.cli import app

        with (
            patch(
                "kctl_dokploy.commands.backups_restore._get_compose_one",
                return_value={"composeStatus": "done"},
            ),
            patch(
                "kctl_dokploy.commands.backups_restore._list_compose_services",
                return_value=["postgres", "pgbouncer"],
            ),
            patch(
                "kctl_dokploy.commands.backups_restore._fetch_destination",
                return_value={
                    "bucket": "b",
                    "accessKey": "x",
                    "secretAccessKey": "y",
                    "endpoint": None,
                    "region": "us-east-1",
                },
            ),
            patch("kctl_dokploy.commands.backups_restore._build_s3_client", return_value=object()),
            patch(
                "kctl_dokploy.commands.backups_restore._check_s3_object_exists",
                return_value=(True, None),
            ),
            patch(
                "kctl_dokploy.commands.backups_restore._ensure_db_exists",
                return_value=(True, "already exists"),
            ),
            patch(
                "kctl_dokploy.commands.backups_restore._verify_restore_populated",
                return_value=True,
            ),
            patch(
                "kctl_dokploy.core.async_client.AsyncDokployClient.stream_subscription",
                new=_ok_stream(),
            ),
        ):
            result = CliRunner().invoke(
                app,
                [
                    "-p",
                    "local",
                    "backups",
                    "restore",
                    "--compose",
                    "cmp-123",
                    "--destination",
                    "dst-456",
                    "--database-name",
                    "mydb",
                    "--file",
                    "k.sql.gz",
                    "--service-name",
                    "postgres",
                    "--database-user",
                    "odoo",
                ],
            )
        assert result.exit_code == 0, result.output
        assert "Pre-flight passed" in result.output

    def test_preflight_rejects_unknown_service_name(self) -> None:
        """If the compose doesn't declare the given --service-name, fail
        before kicking off the restore."""
        from kctl_dokploy.cli import app

        with (
            patch(
                "kctl_dokploy.commands.backups_restore._get_compose_one",
                return_value={"composeStatus": "done"},
            ),
            patch(
                "kctl_dokploy.commands.backups_restore._list_compose_services",
                return_value=["redis", "pgbouncer"],
            ),
        ):
            result = CliRunner().invoke(
                app,
                [
                    "-p",
                    "local",
                    "backups",
                    "restore",
                    "--compose",
                    "cmp-123",
                    "--destination",
                    "dst-456",
                    "--database-name",
                    "mydb",
                    "--file",
                    "k.sql.gz",
                    "--service-name",
                    "postgres",
                    "--database-user",
                    "odoo",
                ],
            )
        assert result.exit_code != 0
        assert "service 'postgres' not in compose services" in result.output

    def test_preflight_fails_when_s3_key_missing(self) -> None:
        from kctl_dokploy.cli import app

        with (
            patch(
                "kctl_dokploy.commands.backups_restore._get_compose_one",
                return_value={"composeStatus": "done"},
            ),
            patch(
                "kctl_dokploy.commands.backups_restore._list_compose_services",
                return_value=["postgres"],
            ),
            patch(
                "kctl_dokploy.commands.backups_restore._fetch_destination",
                return_value={
                    "bucket": "b",
                    "accessKey": "x",
                    "secretAccessKey": "y",
                    "endpoint": None,
                    "region": "us-east-1",
                },
            ),
            patch("kctl_dokploy.commands.backups_restore._build_s3_client", return_value=object()),
            patch(
                "kctl_dokploy.commands.backups_restore._check_s3_object_exists",
                return_value=(False, "Not Found"),
            ),
        ):
            result = CliRunner().invoke(
                app,
                [
                    "-p",
                    "local",
                    "backups",
                    "restore",
                    "--compose",
                    "cmp-123",
                    "--destination",
                    "dst-456",
                    "--database-name",
                    "mydb",
                    "--file",
                    "missing.sql.gz",
                    "--service-name",
                    "postgres",
                    "--database-user",
                    "odoo",
                ],
            )
        assert result.exit_code != 0
        assert "S3 key not reachable" in result.output

    def test_ensure_db_runs_when_default(self) -> None:
        """--ensure-db (default) calls _ensure_db_exists before the SSE."""
        from kctl_dokploy.cli import app

        ensure = patch(
            "kctl_dokploy.commands.backups_restore._ensure_db_exists",
            return_value=(True, "created"),
        )
        with (
            ensure as ensure_mock,
            patch(
                "kctl_dokploy.commands.backups_restore._verify_restore_populated",
                return_value=True,
            ),
            patch(
                "kctl_dokploy.core.async_client.AsyncDokployClient.stream_subscription",
                new=_ok_stream(),
            ),
        ):
            result = CliRunner().invoke(
                app,
                [
                    "-p",
                    "local",
                    "backups",
                    "restore",
                    "--compose",
                    "cmp-123",
                    "--destination",
                    "dst-456",
                    "--database-name",
                    "mydb",
                    "--file",
                    "k.sql.gz",
                    "--service-name",
                    "postgres",
                    "--database-user",
                    "odoo",
                    "--skip-preflight",
                ],
            )
        assert result.exit_code == 0, result.output
        ensure_mock.assert_called_once()

    def test_force_drops_and_recreates(self) -> None:
        """--force calls _drop_and_recreate_db, NOT _ensure_db_exists."""
        from kctl_dokploy.cli import app

        with (
            patch(
                "kctl_dokploy.commands.backups_restore._drop_and_recreate_db",
                return_value=(True, "recreated (attempt 1)"),
            ) as drop_mock,
            patch(
                "kctl_dokploy.commands.backups_restore._ensure_db_exists",
                return_value=(True, "should-not-be-called"),
            ) as ensure_mock,
            patch(
                "kctl_dokploy.commands.backups_restore._verify_restore_populated",
                return_value=True,
            ),
            patch(
                "kctl_dokploy.core.async_client.AsyncDokployClient.stream_subscription",
                new=_ok_stream(),
            ),
        ):
            result = CliRunner().invoke(
                app,
                [
                    "-p",
                    "local",
                    "backups",
                    "restore",
                    "--compose",
                    "cmp-123",
                    "--destination",
                    "dst-456",
                    "--database-name",
                    "mydb",
                    "--file",
                    "k.sql.gz",
                    "--service-name",
                    "postgres",
                    "--database-user",
                    "odoo",
                    "--force",
                    "--skip-preflight",
                ],
            )
        assert result.exit_code == 0, result.output
        drop_mock.assert_called_once()
        ensure_mock.assert_not_called()
        assert "Database recreated" in result.output

    def test_force_fail_dies_with_actionable_message(self) -> None:
        from kctl_dokploy.cli import app

        with patch(
            "kctl_dokploy.commands.backups_restore._drop_and_recreate_db",
            return_value=(False, "dropdb failed after 3 attempts (active sessions persist?)"),
        ):
            result = CliRunner().invoke(
                app,
                [
                    "-p",
                    "local",
                    "backups",
                    "restore",
                    "--compose",
                    "cmp-123",
                    "--destination",
                    "dst-456",
                    "--database-name",
                    "mydb",
                    "--file",
                    "k.sql.gz",
                    "--service-name",
                    "postgres",
                    "--database-user",
                    "odoo",
                    "--force",
                    "--skip-preflight",
                ],
            )
        assert result.exit_code != 0
        assert "--force drop+recreate failed" in result.output

    def test_post_restore_verify_failure_flips_exit_code(self) -> None:
        """SSE says success, but verify shows the DB is empty -> exit 1."""
        from kctl_dokploy.cli import app

        with (
            patch(
                "kctl_dokploy.commands.backups_restore._verify_restore_populated",
                return_value=False,
            ),
            patch(
                "kctl_dokploy.core.async_client.AsyncDokployClient.stream_subscription",
                new=_ok_stream(),
            ),
        ):
            result = CliRunner().invoke(
                app,
                [
                    "-p",
                    "local",
                    "backups",
                    "restore",
                    "--compose",
                    "cmp-123",
                    "--destination",
                    "dst-456",
                    "--database-name",
                    "mydb",
                    "--file",
                    "k.sql.gz",
                    "--service-name",
                    "postgres",
                    "--database-user",
                    "odoo",
                    "--skip-preflight",
                    "--no-ensure-db",
                ],
            )
        assert result.exit_code == 1, result.output
        assert "Verification FAILED" in result.output

    def test_failure_surfaces_postgres_logs(self) -> None:
        """When SSE reports an error, the command fetches and prints the
        postgres container log tail to give the operator something to debug."""
        from kctl_dokploy.cli import app

        with (
            patch(
                "kctl_dokploy.commands.backups_restore._tail_postgres_logs",
                return_value="LOG: connection received\nERROR: out of disk",
            ) as tail_mock,
            patch(
                "kctl_dokploy.core.async_client.AsyncDokployClient.stream_subscription",
                new=_err_stream(),
            ),
        ):
            result = CliRunner().invoke(
                app,
                [
                    "-p",
                    "local",
                    "backups",
                    "restore",
                    "--compose",
                    "cmp-123",
                    "--destination",
                    "dst-456",
                    "--database-name",
                    "mydb",
                    "--file",
                    "k.sql.gz",
                    "--service-name",
                    "postgres",
                    "--database-user",
                    "odoo",
                    "--skip-preflight",
                    "--no-ensure-db",
                    "--skip-verify",
                ],
            )
        assert result.exit_code == 1
        tail_mock.assert_called_once()
        assert "ERROR: out of disk" in result.output
        assert "Re-run with --force" in result.output

    def test_stop_compose_pauses_consumer_during_force(self) -> None:
        """--stop-compose should call /compose.stop before destructive ops
        and /compose.start after."""
        from kctl_dokploy.cli import app

        post_calls: list[tuple[str, dict]] = []

        def fake_post(endpoint, json=None, **_kw):
            post_calls.append((endpoint, json or {}))
            return {}

        with (
            patch(
                "kctl_dokploy.commands.backups_restore._drop_and_recreate_db",
                return_value=(True, "recreated"),
            ),
            patch(
                "kctl_dokploy.commands.backups_restore._verify_restore_populated",
                return_value=True,
            ),
            patch(
                "kctl_dokploy.core.async_client.AsyncDokployClient.stream_subscription",
                new=_ok_stream(),
            ),
            patch("kctl_dokploy.core.client.DokployClient.post", side_effect=fake_post),
            patch("time.sleep"),  # speed up the 5s grace period in tests
        ):
            result = CliRunner().invoke(
                app,
                [
                    "-p",
                    "local",
                    "backups",
                    "restore",
                    "--compose",
                    "cmp-123",
                    "--destination",
                    "dst-456",
                    "--database-name",
                    "mydb",
                    "--file",
                    "k.sql.gz",
                    "--service-name",
                    "postgres",
                    "--database-user",
                    "odoo",
                    "--force",
                    "--stop-compose",
                    "downstream-app",
                    "--skip-preflight",
                ],
            )
        assert result.exit_code == 0, result.output
        endpoints = [e for e, _ in post_calls]
        assert "/compose.stop" in endpoints
        assert "/compose.start" in endpoints

    def test_force_warns_without_stop_compose(self) -> None:
        from kctl_dokploy.cli import app

        with (
            patch(
                "kctl_dokploy.commands.backups_restore._drop_and_recreate_db",
                return_value=(True, "recreated"),
            ),
            patch(
                "kctl_dokploy.commands.backups_restore._verify_restore_populated",
                return_value=True,
            ),
            patch(
                "kctl_dokploy.core.async_client.AsyncDokployClient.stream_subscription",
                new=_ok_stream(),
            ),
        ):
            result = CliRunner().invoke(
                app,
                [
                    "-p",
                    "local",
                    "backups",
                    "restore",
                    "--compose",
                    "cmp-123",
                    "--destination",
                    "dst-456",
                    "--database-name",
                    "mydb",
                    "--file",
                    "k.sql.gz",
                    "--service-name",
                    "postgres",
                    "--database-user",
                    "odoo",
                    "--force",
                    "--skip-preflight",
                ],
            )
        assert result.exit_code == 0, result.output
        assert "--force without --stop-compose" in result.output
