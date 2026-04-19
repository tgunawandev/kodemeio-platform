"""Tests for the `backups restore` Dokploy-native restore command."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from typer.testing import CliRunner


class TestBackupsRestore:
    def test_happy_path_streams_logs_exits_zero(self) -> None:
        """With --file + required compose metadata, the command invokes
        stream_subscription with the correct endpoint + URL-encoded input,
        prints each yielded line prefixed with [Dokploy], and exits 0 when
        it sees a success marker."""
        from kctl_dokploy.cli import app

        async def fake_stream(self: Any, endpoint: str, payload: dict) -> Any:
            assert endpoint == "/trpc/backup.restoreBackupWithLogs"
            # Dokploy requires all 6 base fields — verify they're all present.
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
                    "x.sql.gz",
                    "--service-name",
                    "postgres",
                    "--database-user",
                    "odoo",
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
    """Tests for the three new metadata flags: --service-name,
    --database-user, --database-password. These flags translate to
    payload.json.metadata.* fields that Dokploy's native restore requires
    for compose-embedded databases."""

    @staticmethod
    def _captured_payload() -> dict[str, Any]:
        """Shared container captured by fake_stream. Returns a fresh dict
        each call because the outer closure binds by reference."""
        return {}

    def _make_fake_stream(self, captured: dict[str, Any]):
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
                ],
            )
        assert result.exit_code == 0, result.output
        meta = captured["payload"]["json"]["metadata"]
        assert meta["mariadb"] == {
            "databaseUser": "root",
            "databasePassword": "hunter2",
        }

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
                ],
            )
        assert result.exit_code == 0, result.output
        meta = captured["payload"]["json"]["metadata"]
        assert meta["mysql"] == {"databaseRootPassword": "rootpw"}

    def test_no_metadata_flags_omits_metadata_key(self) -> None:
        """For database backups (not compose) with db-type=mysql and no
        metadata flags, payload.json must not contain a 'metadata' key —
        Dokploy tolerates omitted metadata for non-compose restores."""
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
                # Missing --service-name for backup-type=compose (default)
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
                # Missing --database-user for db-type=postgres (default)
            ],
        )
        assert result.exit_code != 0
        assert "--database-user" in result.output
