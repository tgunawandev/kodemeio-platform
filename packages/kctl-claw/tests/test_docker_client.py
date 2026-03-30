"""Tests for DockerClient — Docker compose/exec wrapper."""

from __future__ import annotations

import subprocess
from unittest.mock import patch

import pytest

from kctl_claw.core.docker_client import DockerClient
from kctl_claw.core.exceptions import DockerError


@pytest.fixture
def client(tmp_path):
    compose = tmp_path / "docker-compose.prod.yml"
    compose.write_text("version: '3'")
    env = tmp_path / ".env.prod"
    env.write_text("KEY=val")
    return DockerClient(compose_file=compose, env_file=env)


def test_compose_base_cmd(client):
    cmd = client._compose_cmd()
    assert cmd[0] == "docker"
    assert cmd[1] == "compose"
    assert "-f" in cmd
    assert "--env-file" in cmd


def test_is_running_true(client):
    mock_result = subprocess.CompletedProcess(args=[], returncode=0, stdout="openclaw-gateway  running")
    with patch("subprocess.run", return_value=mock_result):
        assert client.is_running() is True


def test_is_running_false(client):
    mock_result = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="no such service")
    with patch("subprocess.run", return_value=mock_result):
        assert client.is_running() is False


def test_exec_cmd_success(client):
    mock_result = subprocess.CompletedProcess(args=[], returncode=0, stdout="output here\n")
    with patch("subprocess.run", return_value=mock_result):
        result = client.exec_cmd(["echo", "hello"])
        assert "output" in result


def test_exec_cmd_failure(client):
    mock_result = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="error")
    with patch("subprocess.run", return_value=mock_result), pytest.raises(DockerError):
        client.exec_cmd(["bad-command"])


def test_ps_returns_stdout(client):
    mock_result = subprocess.CompletedProcess(args=[], returncode=0, stdout="NAME  STATUS\nopenclaw  running\n")
    with patch("subprocess.run", return_value=mock_result):
        output = client.ps()
    assert "openclaw" in output


def test_run_timeout(client):
    with (
        patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="docker", timeout=300)),
        pytest.raises(DockerError) as exc_info,
    ):
        client._run(["docker", "compose", "ps"])
    assert "timed out" in exc_info.value.stderr.lower()


def test_run_check_raises_on_nonzero(client):
    mock_result = subprocess.CompletedProcess(args=[], returncode=2, stdout="", stderr="fatal error")
    with patch("subprocess.run", return_value=mock_result), pytest.raises(DockerError) as exc_info:
        client._run(["docker", "compose", "up"])
    assert exc_info.value.returncode == 2


def test_logs_grep(client):
    mock_result = subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout="2026-03-28 ERROR something bad\n2026-03-28 INFO all good\n2026-03-28 ERROR another error\n",
    )
    with patch("subprocess.run", return_value=mock_result):
        result = client.logs_grep("error")
    assert "ERROR" in result
    assert "INFO all good" not in result
