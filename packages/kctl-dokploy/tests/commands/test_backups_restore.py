"""Tests for the `backups restore` Dokploy-native restore command."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from typer.testing import CliRunner


class TestBackupsRestore:
    def test_happy_path_streams_logs_exits_zero(self) -> None:
        """With --file, the command invokes stream_subscription with the
        correct endpoint + URL-encoded input, prints each yielded line
        prefixed with [Dokploy], and exits 0 when it sees a success marker."""
        from kctl_dokploy.cli import app

        async def fake_stream(self: Any, endpoint: str, payload: dict) -> Any:
            assert endpoint == "/trpc/backup.restoreBackupWithLogs"
            # Dokploy requires all 6 fields — verify they're all present.
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
            ],
        )
        assert result.exit_code != 0
        assert "--file" in result.output or "--latest" in result.output
