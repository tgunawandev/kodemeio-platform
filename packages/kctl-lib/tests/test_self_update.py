"""Tests for kctl_lib.self_update."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

from kctl_lib.self_update import check_update, update


def _make_result(stdout: str = "", returncode: int = 0) -> subprocess.CompletedProcess[str]:
    r: subprocess.CompletedProcess[str] = MagicMock(spec=subprocess.CompletedProcess)
    r.stdout = stdout
    r.returncode = returncode
    return r


class TestCheckUpdate:
    def test_newer_version_returns_version(self) -> None:
        # The function parses the first non-'(' line as the latest version token
        pip_output = "kctl-lib 0.3.0\n"
        with patch("kctl_lib.self_update.run_quiet", return_value=_make_result(pip_output)):
            result = check_update("kctl-lib", "0.2.0")

        assert result == "0.3.0"

    def test_same_version_returns_none(self) -> None:
        pip_output = "kctl-lib 0.2.0\n"
        with patch("kctl_lib.self_update.run_quiet", return_value=_make_result(pip_output)):
            result = check_update("kctl-lib", "0.2.0")

        assert result is None

    def test_older_version_returns_none(self) -> None:
        pip_output = "kctl-lib 0.1.0\n"
        with patch("kctl_lib.self_update.run_quiet", return_value=_make_result(pip_output)):
            result = check_update("kctl-lib", "0.2.0")

        assert result is None

    def test_command_failure_returns_none(self) -> None:
        with patch("kctl_lib.self_update.run_quiet", return_value=_make_result("", returncode=1)):
            result = check_update("kctl-lib", "0.1.0")

        assert result is None

    def test_empty_output_returns_none(self) -> None:
        with patch("kctl_lib.self_update.run_quiet", return_value=_make_result("")):
            result = check_update("kctl-lib", "0.1.0")

        assert result is None

    def test_version_with_parenthesis_line_skipped(self) -> None:
        # Lines starting with '(' are skipped; first real line gives the version
        pip_output = "(from cached)\nkctl-lib 0.5.0\n"
        with patch("kctl_lib.self_update.run_quiet", return_value=_make_result(pip_output)):
            result = check_update("kctl-lib", "0.3.0")

        assert result == "0.5.0"

    def test_invalid_version_format_returns_none(self) -> None:
        pip_output = "kctl-lib v0.3.0-beta\n"
        with patch("kctl_lib.self_update.run_quiet", return_value=_make_result(pip_output)):
            result = check_update("kctl-lib", "0.2.0")

        assert result is None

    def test_minor_version_bump_detected(self) -> None:
        pip_output = "kctl-lib 0.2.1\n"
        with patch("kctl_lib.self_update.run_quiet", return_value=_make_result(pip_output)):
            result = check_update("kctl-lib", "0.2.0")

        assert result == "0.2.1"


class TestUpdate:
    def test_calls_uv_tool_upgrade(self) -> None:
        mock_run = MagicMock(return_value=_make_result(""))
        with patch("kctl_lib.self_update.run", mock_run):
            update("kctl-lib")

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd == ["uv", "tool", "upgrade", "kctl-lib"]
