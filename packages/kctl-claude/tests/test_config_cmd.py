"""Tests for commands/config_cmd.py."""

from __future__ import annotations

from unittest.mock import patch

from typer.testing import CliRunner

from kctl_claude.cli import app

runner = CliRunner()


class TestConfigCmd:
    def test_show_no_config(self) -> None:
        """Show should work even without config file."""
        with (
            patch("kctl_claude.commands.config_cmd.get_default_profile", return_value="default"),
            patch("kctl_claude.commands.config_cmd.get_profile_names", return_value=[]),
            patch("kctl_claude.commands.config_cmd.load_raw_config", return_value={}),
        ):
            result = runner.invoke(app, ["config", "show"])
        assert result.exit_code == 0

    def test_show_json(self) -> None:
        with (
            patch("kctl_claude.commands.config_cmd.get_default_profile", return_value="default"),
            patch("kctl_claude.commands.config_cmd.get_profile_names", return_value=["default"]),
            patch(
                "kctl_claude.commands.config_cmd.load_raw_config",
                return_value={"profiles": {"default": {"claude": {}}}},
            ),
        ):
            result = runner.invoke(app, ["--json", "config", "show"])
        assert result.exit_code == 0

    def test_profiles_empty(self) -> None:
        with patch("kctl_claude.commands.config_cmd.get_profile_names", return_value=[]):
            result = runner.invoke(app, ["config", "profiles"])
        assert result.exit_code == 0

    def test_profiles_with_data(self) -> None:
        with (
            patch("kctl_claude.commands.config_cmd.get_profile_names", return_value=["default", "work"]),
            patch("kctl_claude.commands.config_cmd.resolve_active_profile_name", return_value="default"),
            patch("kctl_claude.commands.config_cmd.get_default_profile", return_value="default"),
            patch("kctl_claude.commands.config_cmd.get_service_config", return_value={"config_dir": "~/.claude"}),
            patch("kctl_claude.commands.config_cmd.get_all_services_in_profile", return_value={"claude": {}}),
        ):
            result = runner.invoke(app, ["config", "profiles"])
        assert result.exit_code == 0

    def test_current(self) -> None:
        with (
            patch("kctl_claude.commands.config_cmd.resolve_active_profile_name", return_value="default"),
            patch("kctl_claude.commands.config_cmd.get_service_config", return_value={"config_dir": "~/.claude"}),
            patch("kctl_claude.commands.config_cmd.get_all_services_in_profile", return_value={"claude": {}}),
            patch("kctl_claude.commands.config_cmd.get_profile_names", return_value=["default"]),
        ):
            result = runner.invoke(app, ["config", "current"])
        assert result.exit_code == 0

    def test_validate_no_config(self) -> None:
        with patch("kctl_claude.commands.config_cmd.CONFIG_FILE") as mock_file:
            mock_file.exists.return_value = False
            result = runner.invoke(app, ["config", "validate"])
        assert result.exit_code == 1

    def test_set_unknown_key(self) -> None:
        with (
            patch("kctl_claude.commands.config_cmd.resolve_active_profile_name", return_value="default"),
            patch("kctl_claude.commands.config_cmd.get_service_config", return_value={}),
        ):
            result = runner.invoke(app, ["config", "set", "unknown_key", "value"])
        assert result.exit_code == 1

    def test_use_nonexistent_profile(self) -> None:
        with patch("kctl_claude.commands.config_cmd.get_profile_names", return_value=["default"]):
            result = runner.invoke(app, ["config", "use", "nonexistent"])
        assert result.exit_code == 1
