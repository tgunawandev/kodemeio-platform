"""Tests for kctl_common.runner."""

from __future__ import annotations

import pytest

from kctl_common.exceptions import CommandError
from kctl_common.runner import get_git_branch, get_git_sha, run, run_quiet


class TestRun:
    def test_success(self) -> None:
        result = run(["echo", "hello"])
        assert result.returncode == 0
        assert "hello" in result.stdout

    def test_failure_raises(self) -> None:
        with pytest.raises(CommandError):
            run(["false"])

    def test_check_false_no_raise(self) -> None:
        result = run(["false"], check=False)
        assert result.returncode != 0

    def test_command_not_found(self) -> None:
        with pytest.raises(CommandError, match="Command not found"):
            run(["nonexistent_command_xyz"])

    def test_custom_env(self) -> None:
        result = run(["env"], env={"MY_TEST_VAR": "hello123"})
        assert "MY_TEST_VAR=hello123" in result.stdout


class TestRunQuiet:
    def test_no_raise_on_failure(self) -> None:
        result = run_quiet(["false"])
        assert result.returncode != 0


class TestGitHelpers:
    def test_get_git_sha(self) -> None:
        sha = get_git_sha()
        assert isinstance(sha, str)

    def test_get_git_branch(self) -> None:
        branch = get_git_branch()
        assert isinstance(branch, str)
