"""Tests for commands/doctor_cmd.py."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from kctl_claude.commands.doctor_cmd import (
    AuthCheck,
    ClaudeCodeCheck,
    GhCliCheck,
    KctlConfigCheck,
    NodeCheck,
    SdkApiCheck,
    SettingsCheck,
)


class TestClaudeCodeCheck:
    def test_installed(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "1.0.5"
        with patch("kctl_claude.commands.doctor_cmd.run_quiet", return_value=mock_result):
            result = ClaudeCodeCheck().run()
        assert result.status == "ok"

    def test_not_installed(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        with patch("kctl_claude.commands.doctor_cmd.run_quiet", return_value=mock_result):
            result = ClaudeCodeCheck().run()
        assert result.status == "fail"
        assert result.fix_command is not None


class TestAuthCheck:
    def test_has_credentials(self, tmp_path: Path) -> None:
        with patch("kctl_claude.commands.doctor_cmd.Path.home", return_value=tmp_path):
            (tmp_path / ".claude").mkdir()
            (tmp_path / ".claude" / ".credentials.json").write_text("{}")
            result = AuthCheck().run()
        assert result.status == "ok"

    def test_no_credentials(self, tmp_path: Path) -> None:
        with patch("kctl_claude.commands.doctor_cmd.Path.home", return_value=tmp_path):
            (tmp_path / ".claude").mkdir()
            result = AuthCheck().run()
        assert result.status == "warn"


class TestSettingsCheck:
    def test_settings_ok(self, tmp_path: Path) -> None:
        with patch("kctl_claude.commands.doctor_cmd.Path.home", return_value=tmp_path):
            (tmp_path / ".claude").mkdir()
            sf = tmp_path / ".claude" / "settings.json"
            sf.write_text('{"PreToolUse": [], "enabledPlugins": ["test"]}')
            result = SettingsCheck().run()
        assert result.status == "ok"

    def test_settings_missing(self, tmp_path: Path) -> None:
        with patch("kctl_claude.commands.doctor_cmd.Path.home", return_value=tmp_path):
            (tmp_path / ".claude").mkdir()
            result = SettingsCheck().run()
        assert result.status == "fail"

    def test_settings_incomplete(self, tmp_path: Path) -> None:
        with patch("kctl_claude.commands.doctor_cmd.Path.home", return_value=tmp_path):
            (tmp_path / ".claude").mkdir()
            sf = tmp_path / ".claude" / "settings.json"
            sf.write_text('{"some": "config"}')
            result = SettingsCheck().run()
        assert result.status == "warn"


class TestNodeCheck:
    def test_installed(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "v22.0.0"
        with patch("kctl_claude.commands.doctor_cmd.run_quiet", return_value=mock_result):
            result = NodeCheck().run()
        assert result.status == "ok"

    def test_not_installed(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        with patch("kctl_claude.commands.doctor_cmd.run_quiet", return_value=mock_result):
            result = NodeCheck().run()
        assert result.status == "fail"


class TestKctlConfigCheck:
    def test_config_exists(self, tmp_path: Path) -> None:
        with patch("kctl_claude.commands.doctor_cmd.Path.home", return_value=tmp_path):
            (tmp_path / ".config" / "kodemeio").mkdir(parents=True)
            (tmp_path / ".config" / "kodemeio" / "config.yaml").write_text("profiles: {}")
            result = KctlConfigCheck().run()
        assert result.status == "ok"

    def test_config_missing(self, tmp_path: Path) -> None:
        with patch("kctl_claude.commands.doctor_cmd.Path.home", return_value=tmp_path):
            result = KctlConfigCheck().run()
        assert result.status == "warn"


class TestSdkApiCheck:
    def test_not_running(self) -> None:
        import httpx

        with patch.object(
            httpx,
            "get",
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            result = SdkApiCheck().run()
        assert result.status == "warn"


class TestGhCliCheck:
    def test_installed(self) -> None:
        with patch("kctl_claude.commands.doctor_cmd.shutil.which", return_value="/usr/bin/gh"):
            result = GhCliCheck().run()
        assert result.status == "ok"

    def test_not_installed(self) -> None:
        with patch("kctl_claude.commands.doctor_cmd.shutil.which", return_value=None):
            result = GhCliCheck().run()
        assert result.status == "warn"
