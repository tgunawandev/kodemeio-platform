"""Tests for core/runner.py — thin subprocess wrapper with structured errors."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from kctl_odoo.core.exceptions import CommandError
from kctl_odoo.core.runner import get_git_branch, get_git_sha, run, run_quiet

# ---------------------------------------------------------------------------
# run()
# ---------------------------------------------------------------------------


class TestRun:
    def test_successful_command_returns_result(self) -> None:
        """run() returns a CompletedProcess on success."""
        mock_result = MagicMock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 0
        mock_result.stdout = "hello\n"
        mock_result.stderr = ""

        with patch("kctl_lib.runner.subprocess.run", return_value=mock_result):
            result = run(["echo", "hello"])

        assert result.returncode == 0
        assert result.stdout == "hello\n"

    def test_nonzero_exit_raises_command_error(self) -> None:
        """run() with check=True raises CommandError on non-zero exit code."""
        mock_result = MagicMock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "something went wrong"

        with (
            patch("kctl_lib.runner.subprocess.run", return_value=mock_result),
            pytest.raises(CommandError) as exc_info,
        ):
            run(["failing", "command"])

        assert exc_info.value.returncode == 1
        assert "something went wrong" in exc_info.value.stderr

    def test_nonzero_exit_no_raise_when_check_false(self) -> None:
        """run() with check=False returns the result even on failure."""
        mock_result = MagicMock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 2
        mock_result.stdout = ""
        mock_result.stderr = "error"

        with patch("kctl_lib.runner.subprocess.run", return_value=mock_result):
            result = run(["cmd"], check=False)

        assert result.returncode == 2

    def test_timeout_raises_command_error(self) -> None:
        """run() raises CommandError with -1 returncode on timeout."""
        with (
            patch(
                "kctl_lib.runner.subprocess.run",
                side_effect=subprocess.TimeoutExpired(["sleep", "100"], 5),
            ),
            pytest.raises(CommandError) as exc_info,
        ):
            run(["sleep", "100"], timeout=5)

        assert exc_info.value.returncode == -1
        assert "timed out" in exc_info.value.stderr

    def test_command_not_found_raises_command_error(self) -> None:
        """run() raises CommandError when the executable does not exist."""
        with (
            patch(
                "kctl_lib.runner.subprocess.run",
                side_effect=FileNotFoundError("No such file"),
            ),
            pytest.raises(CommandError) as exc_info,
        ):
            run(["nonexistent_binary"])

        assert exc_info.value.returncode == -1
        assert "Command not found" in exc_info.value.stderr

    def test_cwd_passed_to_subprocess(self, tmp_path: Path) -> None:
        """run() forwards the cwd argument to subprocess.run."""
        mock_result = MagicMock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""

        with patch("kctl_lib.runner.subprocess.run", return_value=mock_result) as mock_sp:
            run(["ls"], cwd=tmp_path)

        _, call_kwargs = mock_sp.call_args
        assert call_kwargs["cwd"] == tmp_path

    def test_capture_false_does_not_set_capture_output(self) -> None:
        """run() passes capture_output=False to subprocess when capture=False."""
        mock_result = MagicMock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 0
        mock_result.stdout = None
        mock_result.stderr = None

        with patch("kctl_lib.runner.subprocess.run", return_value=mock_result) as mock_sp:
            run(["cmd"], capture=False)

        _, call_kwargs = mock_sp.call_args
        assert call_kwargs["capture_output"] is False


# ---------------------------------------------------------------------------
# run_quiet()
# ---------------------------------------------------------------------------


class TestRunQuiet:
    def test_does_not_raise_on_failure(self) -> None:
        """run_quiet() returns the result without raising on non-zero exit."""
        mock_result = MagicMock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "error"

        with patch("kctl_lib.runner.subprocess.run", return_value=mock_result):
            result = run_quiet(["cmd_that_fails"])

        assert result.returncode == 1


# ---------------------------------------------------------------------------
# git helpers
# ---------------------------------------------------------------------------


class TestGetGitSha:
    def test_returns_sha_on_success(self) -> None:
        """get_git_sha() returns the trimmed SHA string."""
        mock_result = MagicMock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 0
        mock_result.stdout = "abc1234\n"

        with patch("kctl_lib.runner.subprocess.run", return_value=mock_result):
            sha = get_git_sha()

        assert sha == "abc1234"

    def test_returns_empty_string_on_failure(self) -> None:
        """get_git_sha() returns '' when the git command fails."""
        mock_result = MagicMock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 128
        mock_result.stdout = ""

        with patch("kctl_lib.runner.subprocess.run", return_value=mock_result):
            sha = get_git_sha()

        assert sha == ""

    def test_calls_rev_parse_head(self) -> None:
        """get_git_sha() invokes git rev-parse HEAD."""
        mock_result = MagicMock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 0
        mock_result.stdout = "deadbeef\n"

        with patch("kctl_lib.runner.subprocess.run", return_value=mock_result) as mock_sp:
            get_git_sha()

        cmd_called = mock_sp.call_args[0][0]
        assert cmd_called == ["git", "rev-parse", "HEAD"]


class TestGetGitBranch:
    def test_returns_branch_name(self) -> None:
        """get_git_branch() returns the current branch name."""
        mock_result = MagicMock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 0
        mock_result.stdout = "18.0\n"

        with patch("kctl_lib.runner.subprocess.run", return_value=mock_result):
            branch = get_git_branch()

        assert branch == "18.0"

    def test_returns_empty_on_detached_head(self) -> None:
        """get_git_branch() returns '' when git fails (e.g. detached HEAD in some configs)."""
        mock_result = MagicMock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 128
        mock_result.stdout = ""

        with patch("kctl_lib.runner.subprocess.run", return_value=mock_result):
            branch = get_git_branch()

        assert branch == ""


# ---------------------------------------------------------------------------
# CommandError data class
# ---------------------------------------------------------------------------


class TestCommandError:
    def test_attributes_preserved(self) -> None:
        """CommandError stores command, returncode, and stderr."""
        err = CommandError("git push", 128, "Permission denied")
        assert err.command == "git push"
        assert err.returncode == 128
        assert err.stderr == "Permission denied"
        assert "git push" in str(err)
        assert "128" in str(err)
