"""Tests for core/runner.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from kctl_react.core.exceptions import CommandError
from kctl_react.core.runner import run


class TestRun:
    def test_successful_command(self, tmp_path: Path) -> None:
        result = run(["echo", "hello"], cwd=tmp_path)
        assert result.returncode == 0
        assert "hello" in result.stdout

    def test_failed_command_raises(self, tmp_path: Path) -> None:
        with pytest.raises(CommandError) as exc_info:
            run(["false"], cwd=tmp_path)
        assert exc_info.value.returncode != 0

    def test_command_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(CommandError) as exc_info:
            run(["nonexistent_command_xyz"], cwd=tmp_path)
        assert "not found" in str(exc_info.value).lower()

    def test_timeout(self, tmp_path: Path) -> None:
        with pytest.raises(CommandError) as exc_info:
            run(["sleep", "10"], cwd=tmp_path, timeout=1)
        assert "timed out" in str(exc_info.value).lower()

    def test_capture_false_still_raises_on_failure(self, tmp_path: Path) -> None:
        with pytest.raises(CommandError):
            run(["false"], cwd=tmp_path, capture=False)

    def test_env_override(self, tmp_path: Path) -> None:
        result = run(["env"], cwd=tmp_path, env={"MY_TEST_VAR": "hello123"})
        assert "MY_TEST_VAR=hello123" in result.stdout
