"""Tests for kctl_common.completions."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from kctl_common.completions import get_completion_script, install_completions


def _make_result(stdout: str = "", returncode: int = 0) -> subprocess.CompletedProcess[str]:
    r: subprocess.CompletedProcess[str] = MagicMock(spec=subprocess.CompletedProcess)
    r.stdout = stdout
    r.returncode = returncode
    return r


class TestGetCompletionScript:
    def test_zsh_success(self) -> None:
        expected_script = "#compdef kctl-next\n_kctl_next() { ... }\n"
        with patch("kctl_common.completions.run_quiet", return_value=_make_result(expected_script)) as mock_rq:
            result = get_completion_script("kctl-next", shell="zsh")

        assert result == expected_script
        mock_rq.assert_called_once()
        call_kwargs = mock_rq.call_args
        assert call_kwargs[0][0] == ["kctl-next", "--help"]
        assert call_kwargs[1]["env"] == {"_KCTL_NEXT_COMPLETE": "complete_zsh"}

    def test_bash_success(self) -> None:
        expected_script = "# bash completion for kctl-next\n_kctl_next() { ... }\n"
        with patch("kctl_common.completions.run_quiet", return_value=_make_result(expected_script)) as mock_rq:
            result = get_completion_script("kctl-next", shell="bash")

        assert result == expected_script
        call_kwargs = mock_rq.call_args
        assert call_kwargs[1]["env"] == {"_KCTL_NEXT_COMPLETE": "complete_bash"}

    def test_failure_returns_empty(self) -> None:
        with patch("kctl_common.completions.run_quiet", return_value=_make_result("", returncode=1)):
            result = get_completion_script("kctl-next", shell="zsh")

        assert result == ""

    def test_env_var_name_replaces_dash(self) -> None:
        with patch("kctl_common.completions.run_quiet", return_value=_make_result("script")) as mock_rq:
            get_completion_script("my-cli-tool", shell="fish")

        env = mock_rq.call_args[1]["env"]
        assert "_MY_CLI_TOOL_COMPLETE" in env

    def test_default_shell_is_zsh(self) -> None:
        with patch("kctl_common.completions.run_quiet", return_value=_make_result("script")) as mock_rq:
            get_completion_script("kctl-api")

        env = mock_rq.call_args[1]["env"]
        assert env["_KCTL_API_COMPLETE"] == "complete_zsh"


class TestInstallCompletions:
    def test_zsh_writes_to_zfunc(self, tmp_path: Path) -> None:
        script = "#compdef kctl-next\n"
        home = tmp_path / "home"
        home.mkdir()

        with (
            patch("kctl_common.completions.run_quiet", return_value=_make_result(script)),
            patch("kctl_common.completions.Path.home", return_value=home),
        ):
            target = install_completions("kctl-next", shell="zsh")

        assert target is not None
        assert target.name == "_kctl-next"
        assert target.exists()
        assert target.read_text() == script

    def test_bash_writes_to_bash_completion(self, tmp_path: Path) -> None:
        script = "# bash completion\n"
        home = tmp_path / "home"
        home.mkdir()

        with (
            patch("kctl_common.completions.run_quiet", return_value=_make_result(script)),
            patch("kctl_common.completions.Path.home", return_value=home),
        ):
            target = install_completions("kctl-next", shell="bash")

        assert target is not None
        assert target.name == "kctl-next"
        assert target.exists()

    def test_fish_writes_to_fish_completions(self, tmp_path: Path) -> None:
        script = "# fish completion\n"
        home = tmp_path / "home"
        home.mkdir()

        with (
            patch("kctl_common.completions.run_quiet", return_value=_make_result(script)),
            patch("kctl_common.completions.Path.home", return_value=home),
        ):
            target = install_completions("kctl-next", shell="fish")

        assert target is not None
        assert target.name == "kctl-next.fish"

    def test_unknown_shell_returns_none(self) -> None:
        script = "some script\n"
        with patch("kctl_common.completions.run_quiet", return_value=_make_result(script)):
            result = install_completions("kctl-next", shell="tcsh")

        assert result is None

    def test_empty_script_returns_none(self) -> None:
        with patch("kctl_common.completions.run_quiet", return_value=_make_result("", returncode=1)):
            result = install_completions("kctl-next", shell="zsh")

        assert result is None
