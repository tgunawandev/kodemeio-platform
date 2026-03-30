"""Tests for deploy command group."""

from __future__ import annotations

from unittest.mock import patch

from typer.testing import CliRunner

from kctl_claw.cli import app
from kctl_claw.core.exceptions import DockerError

runner = CliRunner()


def _docker_error():
    return DockerError(command="docker compose", returncode=1, stderr="docker daemon not running")


def test_deploy_up_docker_error(project_root):
    """up should fail gracefully when Docker is unavailable."""
    with patch("kctl_claw.core.docker_client.DockerClient.up", side_effect=_docker_error()):
        result = runner.invoke(app, ["--root", str(project_root), "deploy", "up"])
    assert result.exit_code == 1


def test_deploy_up_success(project_root):
    """up should report success when Docker succeeds."""
    with patch("kctl_claw.core.docker_client.DockerClient.up") as mock_up:
        result = runner.invoke(app, ["--root", str(project_root), "deploy", "up"])
    assert result.exit_code == 0
    assert "started" in result.output.lower()
    mock_up.assert_called_once()


def test_deploy_down_aborted(project_root):
    """down should abort when user doesn't type STOP."""
    result = runner.invoke(
        app,
        ["--root", str(project_root), "deploy", "down"],
        input="NO\n",
    )
    assert result.exit_code == 0
    assert "Aborted" in result.output


def test_deploy_down_confirmed(project_root):
    """down should call docker.down when user types STOP."""
    with patch("kctl_claw.core.docker_client.DockerClient.down") as mock_down:
        result = runner.invoke(
            app,
            ["--root", str(project_root), "deploy", "down"],
            input="STOP\n",
        )
    assert result.exit_code == 0
    assert "stopped" in result.output.lower()
    mock_down.assert_called_once()


def test_deploy_restart_success(project_root):
    """restart should call docker.restart successfully."""
    with patch("kctl_claw.core.docker_client.DockerClient.restart") as mock_restart:
        result = runner.invoke(app, ["--root", str(project_root), "deploy", "restart"])
    assert result.exit_code == 0
    assert "restarted" in result.output.lower()
    mock_restart.assert_called_once()


def test_deploy_restart_docker_error(project_root):
    """restart should fail gracefully when Docker is unavailable."""
    with patch("kctl_claw.core.docker_client.DockerClient.restart", side_effect=_docker_error()):
        result = runner.invoke(app, ["--root", str(project_root), "deploy", "restart"])
    assert result.exit_code == 1


def test_deploy_pull_success(project_root):
    """pull should call docker.pull successfully."""
    with patch("kctl_claw.core.docker_client.DockerClient.pull") as mock_pull:
        result = runner.invoke(app, ["--root", str(project_root), "deploy", "pull"])
    assert result.exit_code == 0
    assert "pulled" in result.output.lower()
    mock_pull.assert_called_once()


def test_deploy_status_success(project_root):
    """status should display docker ps output."""
    fake_output = "NAME  IMAGE  STATUS\nopenclaw  ghcr.io/kodemeio/openclaw  running"
    with patch("kctl_claw.core.docker_client.DockerClient.ps", return_value=fake_output):
        result = runner.invoke(app, ["--root", str(project_root), "deploy", "status"])
    assert result.exit_code == 0
    assert "openclaw" in result.output


def test_deploy_status_docker_error(project_root):
    """status should fail gracefully when Docker is unavailable."""
    with patch("kctl_claw.core.docker_client.DockerClient.ps", side_effect=_docker_error()):
        result = runner.invoke(app, ["--root", str(project_root), "deploy", "status"])
    assert result.exit_code == 1
