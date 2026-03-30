"""Tests for logs command group."""

from __future__ import annotations

from unittest.mock import patch

from typer.testing import CliRunner

from kctl_claw.cli import app
from kctl_claw.core.exceptions import DockerError

runner = CliRunner()


def _docker_error():
    return DockerError(command="docker compose logs", returncode=1, stderr="not running")


def test_logs_tail_no_docker(project_root):
    """tail should fail gracefully when Docker is unavailable."""
    with patch("kctl_claw.core.docker_client.DockerClient.logs", side_effect=_docker_error()):
        result = runner.invoke(app, ["--root", str(project_root), "logs", "tail"])
    assert result.exit_code == 1


def test_logs_search_no_docker(project_root):
    """search should fail gracefully when Docker is unavailable."""
    with patch("kctl_claw.core.docker_client.DockerClient.logs_grep", side_effect=_docker_error()):
        result = runner.invoke(app, ["--root", str(project_root), "logs", "search", "ERROR"])
    assert result.exit_code == 1


def test_logs_errors_no_docker(project_root):
    """errors should fail gracefully when Docker is unavailable."""
    with patch("kctl_claw.core.docker_client.DockerClient.logs_grep", side_effect=_docker_error()):
        result = runner.invoke(app, ["--root", str(project_root), "logs", "errors"])
    assert result.exit_code == 1


def test_logs_search_with_results(project_root):
    """search should display results when Docker returns matching lines."""
    mock_result = "2026-03-28 ERROR something went wrong\n2026-03-28 ERROR another error"
    with patch("kctl_claw.core.docker_client.DockerClient.logs_grep", return_value=mock_result):
        result = runner.invoke(app, ["--root", str(project_root), "logs", "search", "ERROR"])
    assert result.exit_code == 0
    assert "ERROR" in result.output


def test_logs_search_no_results(project_root):
    """search should show info message when no lines match."""
    with patch("kctl_claw.core.docker_client.DockerClient.logs_grep", return_value=""):
        result = runner.invoke(app, ["--root", str(project_root), "logs", "search", "NOTFOUND"])
    assert result.exit_code == 0
    assert "No log lines" in result.output


def test_logs_errors_with_results(project_root):
    """errors should display error lines when found."""
    mock_result = "2026-03-28 ERROR something went wrong"
    with patch("kctl_claw.core.docker_client.DockerClient.logs_grep", return_value=mock_result):
        result = runner.invoke(app, ["--root", str(project_root), "logs", "errors"])
    assert result.exit_code == 0
    assert "ERROR" in result.output
