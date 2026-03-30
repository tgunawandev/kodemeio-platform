"""Tests for backup command group."""

from __future__ import annotations

from unittest.mock import patch

from typer.testing import CliRunner

from kctl_claw.cli import app
from kctl_claw.core.exceptions import DockerError

runner = CliRunner()


def _docker_error():
    return DockerError(command="docker run", returncode=1, stderr="volume not found")


def test_backup_list_empty(project_root):
    """list should show info message when no backups exist."""
    result = runner.invoke(app, ["--root", str(project_root), "backup", "list"])
    assert result.exit_code == 0
    assert "No backups" in result.output


def test_backup_list_with_entries(project_root):
    """list should show backup entries when they exist."""
    backups_dir = project_root / "backups" / "20260328-120000"
    backups_dir.mkdir(parents=True)
    # Create a fake tar.gz
    (backups_dir / "openclaw-data.tar.gz").write_bytes(b"x" * 1024)

    result = runner.invoke(app, ["--root", str(project_root), "backup", "list"])
    assert result.exit_code == 0
    assert "20260328-120000" in result.output


def test_backup_create_docker_error(project_root):
    """create should fail gracefully when Docker is unavailable."""
    with patch("kctl_claw.core.docker_client.DockerClient.backup_volumes", side_effect=_docker_error()):
        result = runner.invoke(app, ["--root", str(project_root), "backup", "create"])
    assert result.exit_code == 1


def test_backup_create_success(project_root, tmp_path):
    """create should report success when Docker backup completes."""
    fake_backup = project_root / "backups" / "20260328-120000"
    fake_backup.mkdir(parents=True)

    with patch("kctl_claw.core.docker_client.DockerClient.backup_volumes", return_value=fake_backup):
        result = runner.invoke(app, ["--root", str(project_root), "backup", "create"])
    assert result.exit_code == 0
    assert "Backup created" in result.output


def test_backup_restore_aborted(project_root):
    """restore should abort when user doesn't type RESTORE."""
    backups_dir = project_root / "backups" / "20260328-120000"
    backups_dir.mkdir(parents=True)

    result = runner.invoke(
        app,
        ["--root", str(project_root), "backup", "restore", "20260328-120000"],
        input="NO\n",
    )
    assert result.exit_code == 0
    assert "Aborted" in result.output


def test_backup_restore_not_found(project_root):
    """restore should fail when backup path doesn't exist."""
    result = runner.invoke(
        app,
        ["--root", str(project_root), "backup", "restore", "nonexistent-backup"],
        input="RESTORE\n",
    )
    assert result.exit_code == 1
    assert "not found" in result.output.lower()


def test_backup_restore_success(project_root):
    """restore should call restore_volumes when confirmed."""
    backups_dir = project_root / "backups" / "20260328-120000"
    backups_dir.mkdir(parents=True)

    with patch("kctl_claw.core.docker_client.DockerClient.restore_volumes") as mock_restore:
        result = runner.invoke(
            app,
            ["--root", str(project_root), "backup", "restore", "20260328-120000"],
            input="RESTORE\n",
        )
    assert result.exit_code == 0
    assert "restored" in result.output.lower()
    mock_restore.assert_called_once()
