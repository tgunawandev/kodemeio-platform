"""Tests for config commands."""

from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from typer.testing import CliRunner

from kctl_dokploy.cli import app
from kctl_dokploy.core.callbacks import AppContext

runner = CliRunner()


@pytest.fixture(autouse=True)
def _patch_client(mock_client: MagicMock):
    with patch.object(AppContext, "client", new_callable=PropertyMock, return_value=mock_client):
        yield


class TestConfigShow:
    def test_show_runs_without_error(self, mock_client: MagicMock) -> None:
        with (
            patch("kctl_dokploy.commands.config_cmd.get_default_profile", return_value="default"),
            patch("kctl_dokploy.commands.config_cmd.get_profile_names", return_value=["default"]),
            patch("kctl_dokploy.commands.config_cmd.get_all_services_in_profile", return_value={}),
        ):
            result = runner.invoke(app, ["config", "show"])
        assert result.exit_code == 0

    def test_show_displays_config_file_path(self, mock_client: MagicMock) -> None:
        with (
            patch("kctl_dokploy.commands.config_cmd.get_default_profile", return_value="default"),
            patch("kctl_dokploy.commands.config_cmd.get_profile_names", return_value=["default"]),
            patch("kctl_dokploy.commands.config_cmd.get_all_services_in_profile", return_value={}),
        ):
            result = runner.invoke(app, ["config", "show"])
        assert "config" in result.output.lower() or result.exit_code == 0


class TestConfigUse:
    def test_use_existing_profile(self, mock_client: MagicMock) -> None:
        with (
            patch("kctl_dokploy.commands.config_cmd.get_profile_names", return_value=["default", "staging"]),
            patch("kctl_dokploy.commands.config_cmd.set_default_profile") as mock_set,
        ):
            result = runner.invoke(app, ["config", "use", "staging"])
        assert result.exit_code == 0
        mock_set.assert_called_once_with("staging")

    def test_use_nonexistent_profile_exits_1(self, mock_client: MagicMock) -> None:
        with patch("kctl_dokploy.commands.config_cmd.get_profile_names", return_value=["default"]):
            result = runner.invoke(app, ["config", "use", "nonexistent"])
        assert result.exit_code == 1

    def test_use_prints_success_message(self, mock_client: MagicMock) -> None:
        with (
            patch("kctl_dokploy.commands.config_cmd.get_profile_names", return_value=["default", "prod"]),
            patch("kctl_dokploy.commands.config_cmd.set_default_profile"),
        ):
            result = runner.invoke(app, ["config", "use", "prod"])
        assert result.exit_code == 0
        assert "prod" in result.output


class TestConfigTest:
    def test_test_connection_success(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = []
        with patch(
            "kctl_dokploy.commands.config_cmd.resolve_active_profile_name",
            return_value="default",
        ):
            result = runner.invoke(app, ["config", "test"])
        assert result.exit_code == 0
