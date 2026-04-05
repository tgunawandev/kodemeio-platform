"""Tests for kctl_lib.ssh module."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from kctl_lib.exceptions import ConnectionError as KctlConnectionError
from kctl_lib.ssh import SSHCommandError, SSHResult, _build_ssh_base, ssh_run


class TestSSHResult:
    def test_ok_on_zero(self):
        r = SSHResult(returncode=0, stdout="ok", stderr="")
        assert r.ok

    def test_not_ok_on_nonzero(self):
        r = SSHResult(returncode=1, stdout="", stderr="fail")
        assert not r.ok


class TestBuildSSHBase:
    def test_default_options(self):
        cmd = _build_ssh_base("1.2.3.4")
        assert "ssh" in cmd
        assert "root@1.2.3.4" in cmd
        assert "-p" in cmd
        assert "22" in cmd
        assert "BatchMode=yes" in cmd

    def test_custom_key(self):
        cmd = _build_ssh_base("1.2.3.4", ssh_key="~/.ssh/mykey")
        assert "-i" in cmd

    def test_custom_port(self):
        cmd = _build_ssh_base("1.2.3.4", port=2222)
        assert "2222" in cmd

    def test_custom_user(self):
        cmd = _build_ssh_base("1.2.3.4", user="deploy")
        assert "deploy@1.2.3.4" in cmd


class TestSSHRun:
    @patch("kctl_lib.ssh.subprocess.run")
    def test_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="output\n", stderr="")
        result = ssh_run("1.2.3.4", "echo hello")
        assert result.ok
        assert result.stdout == "output"

    @patch("kctl_lib.ssh.subprocess.run")
    def test_failure_no_check(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")
        result = ssh_run("1.2.3.4", "bad_cmd")
        assert not result.ok
        assert result.stderr == "error"

    @patch("kctl_lib.ssh.subprocess.run")
    def test_failure_with_check(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")
        with pytest.raises(SSHCommandError):
            ssh_run("1.2.3.4", "bad_cmd", check=True)

    @patch(
        "kctl_lib.ssh.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="ssh", timeout=30),
    )
    def test_timeout(self, mock_run):
        with pytest.raises(KctlConnectionError, match="timed out"):
            ssh_run("1.2.3.4", "slow_cmd")

    @patch("kctl_lib.ssh.subprocess.run")
    def test_capture_false(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout=None, stderr=None)
        result = ssh_run("1.2.3.4", "echo hello", capture=False)
        assert result.ok
        assert result.stdout == ""
        assert result.stderr == ""

    @patch("kctl_lib.ssh.subprocess.run")
    def test_custom_ssh_key(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="ok\n", stderr="")
        ssh_run("1.2.3.4", "ls", ssh_key="~/.ssh/id_ed25519")
        args = mock_run.call_args[0][0]
        assert "-i" in args
