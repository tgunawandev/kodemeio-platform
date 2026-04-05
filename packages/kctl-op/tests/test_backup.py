"""Tests for kctl-op backup commands."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from typer.testing import CliRunner

from kctl_op.cli import app
from kctl_op.core.callbacks import AppContext

runner = CliRunner()


@pytest.fixture(autouse=True)
def _patch_context(mock_context: AppContext):
    """Patch AppContext properties to return mocked instances."""
    with (
        patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_context._client),
        patch.object(AppContext, "output", new_callable=PropertyMock, return_value=mock_context._output),
        patch.object(
            AppContext,
            "service_config",
            new_callable=PropertyMock,
            return_value=MagicMock(
                vault="kodemeio-secrets",
                scan_roots=[],
                exclude_patterns=[],
                env_mappings={},
                custom_env_pattern="",
            ),
        ),
    ):
        yield


class TestBackupList:
    def test_list_no_backups_dir(self, tmp_path: Path) -> None:
        """When no backup dir exists, show info message."""
        with patch("kctl_op.commands.backup.BACKUP_DIR", tmp_path / "nonexistent"):
            result = runner.invoke(app, ["backup", "list"])
        assert result.exit_code == 0

    def test_list_empty_backup_dir(self, tmp_path: Path) -> None:
        """When backup dir exists but empty, show info."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        with patch("kctl_op.commands.backup.BACKUP_DIR", backup_dir):
            result = runner.invoke(app, ["backup", "list"])
        assert result.exit_code == 0

    def test_list_shows_backups(self, tmp_path: Path) -> None:
        """When backup files exist, list them."""
        backup_dir = tmp_path / "backups"
        project_dir = backup_dir / "myproject" / "production"
        project_dir.mkdir(parents=True)
        bak_file = project_dir / "20260101_120000.bak"
        bak_file.write_text("DB_HOST=localhost\n")

        with patch("kctl_op.commands.backup.BACKUP_DIR", backup_dir):
            result = runner.invoke(app, ["backup", "list"])
        assert result.exit_code == 0
        assert "myproject" in result.output

    def test_list_with_project_filter(self, tmp_path: Path) -> None:
        """Filter by project name."""
        backup_dir = tmp_path / "backups"
        for proj in ("alpha", "beta"):
            d = backup_dir / proj / "production"
            d.mkdir(parents=True)
            (d / "20260101_120000.bak").write_text("X=1\n")

        with patch("kctl_op.commands.backup.BACKUP_DIR", backup_dir):
            result = runner.invoke(app, ["backup", "list", "alpha"])
        assert result.exit_code == 0
        assert "alpha" in result.output
        assert "beta" not in result.output

    def test_list_help(self) -> None:
        result = runner.invoke(app, ["backup", "list", "--help"])
        assert result.exit_code == 0


class TestBackupRestore:
    def test_restore_no_backup_dir_exits_1(self, tmp_path: Path) -> None:
        """Restore fails if project backup dir doesn't exist."""
        with patch("kctl_op.commands.backup.BACKUP_DIR", tmp_path / "nonexistent"):
            result = runner.invoke(app, ["backup", "restore", "proj", "production", "--force"])
        assert result.exit_code == 1

    def test_restore_empty_backup_dir_exits_1(self, tmp_path: Path) -> None:
        """Restore fails if no .bak files in backup dir."""
        backup_dir = tmp_path / "backups"
        (backup_dir / "proj" / "production").mkdir(parents=True)
        with patch("kctl_op.commands.backup.BACKUP_DIR", backup_dir):
            result = runner.invoke(app, ["backup", "restore", "proj", "production", "--force"])
        assert result.exit_code == 1

    def test_restore_no_matching_timestamp(self, tmp_path: Path) -> None:
        """Restore fails if timestamp doesn't match any backup."""
        backup_dir = tmp_path / "backups"
        d = backup_dir / "proj" / "production"
        d.mkdir(parents=True)
        (d / "20260101_120000.bak").write_text("X=1\n")
        with patch("kctl_op.commands.backup.BACKUP_DIR", backup_dir):
            result = runner.invoke(app, ["backup", "restore", "proj", "production", "99999999", "--force"])
        assert result.exit_code == 1

    def test_restore_help(self) -> None:
        result = runner.invoke(app, ["backup", "restore", "--help"])
        assert result.exit_code == 0
        assert "--force" in result.output


class TestBackupClean:
    def test_clean_no_backups_dir(self, tmp_path: Path) -> None:
        """Clean when no backup dir returns info."""
        with patch("kctl_op.commands.backup.BACKUP_DIR", tmp_path / "nonexistent"):
            result = runner.invoke(app, ["backup", "clean", "--force"])
        assert result.exit_code == 0

    def test_clean_nothing_to_remove(self, tmp_path: Path) -> None:
        """Clean when fewer backups than keep limit returns info."""
        backup_dir = tmp_path / "backups"
        d = backup_dir / "proj" / "production"
        d.mkdir(parents=True)
        (d / "20260101_120000.bak").write_text("X=1\n")

        with patch("kctl_op.commands.backup.BACKUP_DIR", backup_dir):
            result = runner.invoke(app, ["backup", "clean", "--keep", "10", "--force"])
        assert result.exit_code == 0

    def test_clean_removes_old_backups(self, tmp_path: Path) -> None:
        """Clean removes backups beyond keep count."""
        backup_dir = tmp_path / "backups"
        d = backup_dir / "proj" / "production"
        d.mkdir(parents=True)
        for i in range(5):
            (d / f"2026010{i}_120000.bak").write_text(f"X={i}\n")

        with patch("kctl_op.commands.backup.BACKUP_DIR", backup_dir):
            result = runner.invoke(app, ["backup", "clean", "--keep", "2", "--force"])
        assert result.exit_code == 0
        remaining = list(d.glob("*.bak"))
        assert len(remaining) == 2

    def test_clean_help(self) -> None:
        result = runner.invoke(app, ["backup", "clean", "--help"])
        assert result.exit_code == 0
        assert "--keep" in result.output
