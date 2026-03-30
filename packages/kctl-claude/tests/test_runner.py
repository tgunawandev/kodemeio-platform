"""Tests for core/runner.py — script runner helper."""

from __future__ import annotations

from pathlib import Path

import pytest
from kctl_common.exceptions import CommandError

from kctl_claude.core.runner import run_script


class TestRunScript:
    def test_script_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(CommandError, match="Script not found"):
            run_script(tmp_path / "nonexistent.sh")

    def test_successful_script(self, tmp_path: Path) -> None:
        script = tmp_path / "test.sh"
        script.write_text("#!/bin/bash\necho hello")
        script.chmod(0o755)
        result = run_script(script)
        assert result.returncode == 0
        assert "hello" in result.stdout

    def test_failing_script(self, tmp_path: Path) -> None:
        script = tmp_path / "fail.sh"
        script.write_text("#!/bin/bash\nexit 42")
        script.chmod(0o755)
        with pytest.raises(CommandError) as exc_info:
            run_script(script)
        assert exc_info.value.returncode == 42

    def test_script_with_args(self, tmp_path: Path) -> None:
        script = tmp_path / "echo.sh"
        script.write_text('#!/bin/bash\necho "$@"')
        script.chmod(0o755)
        result = run_script(script, args=["arg1", "arg2"])
        assert "arg1 arg2" in result.stdout

    def test_timeout(self, tmp_path: Path) -> None:
        script = tmp_path / "slow.sh"
        script.write_text("#!/bin/bash\nsleep 10")
        script.chmod(0o755)
        with pytest.raises(CommandError, match="timed out"):
            run_script(script, timeout=1)

    def test_no_capture(self, tmp_path: Path) -> None:
        script = tmp_path / "test.sh"
        script.write_text("#!/bin/bash\necho hello")
        script.chmod(0o755)
        result = run_script(script, capture=False)
        assert result.returncode == 0
