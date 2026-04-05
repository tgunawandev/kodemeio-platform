"""Tests for config management commands."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from kctl_mailcow.cli import app
from kctl_mailcow.core.callbacks import AppContext
from kctl_mailcow.core.config import SERVICE_KEY


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def mock_ctx() -> AppContext:
    from kctl_lib.output import Output

    ctx = AppContext(quiet=True)
    ctx._output = Output(json_mode=False, quiet=True, format="pretty")
    return ctx


@pytest.fixture
def config_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect config to a temp file."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_file = config_dir / "config.yaml"
    monkeypatch.setattr("kctl_mailcow.core.config.CONFIG_DIR", config_dir)
    monkeypatch.setattr("kctl_mailcow.core.config.CONFIG_FILE", config_file)
    monkeypatch.setattr("kctl_mailcow.commands.config_cmd.CONFIG_FILE", config_file)
    return config_file


class TestMaskKey:
    """Test the _mask_key helper used for security."""

    def test_empty_key_returns_not_set(self) -> None:
        from kctl_mailcow.commands.config_cmd import _mask_key

        result = _mask_key("")
        assert "not set" in result

    def test_short_key_fully_masked(self) -> None:
        from kctl_mailcow.commands.config_cmd import _mask_key

        result = _mask_key("short")
        assert result == "****"

    def test_long_key_shows_first_and_last_4(self) -> None:
        from kctl_mailcow.commands.config_cmd import _mask_key

        key = "abcd1234efgh5678"
        result = _mask_key(key)
        assert result.startswith("abcd")
        assert result.endswith("5678")
        assert "****" in result

    def test_exactly_10_chars_masked(self) -> None:
        from kctl_mailcow.commands.config_cmd import _mask_key

        result = _mask_key("1234567890")
        assert result == "****"

    def test_11_chars_shows_first_last(self) -> None:
        from kctl_mailcow.commands.config_cmd import _mask_key

        result = _mask_key("abcd12345xyz")
        assert result.startswith("abcd")
        assert result.endswith("5xyz")


class TestConfigShow:
    def test_show_no_config(
        self, runner: CliRunner, mock_ctx: AppContext, config_file: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        with patch("kctl_mailcow.commands.config_cmd.get_profile_names", return_value=[]):
            with patch("kctl_mailcow.commands.config_cmd.get_default_profile", return_value="default"):
                result = runner.invoke(app, ["config", "show"], obj=mock_ctx)
                assert result.exit_code == 0

    def test_show_with_profiles(self, runner: CliRunner, mock_ctx: AppContext, config_file: Path) -> None:
        with patch("kctl_mailcow.commands.config_cmd.get_profile_names", return_value=["default", "staging"]):
            with patch("kctl_mailcow.commands.config_cmd.get_default_profile", return_value="default"):
                with patch(
                    "kctl_mailcow.commands.config_cmd.get_all_services_in_profile",
                    return_value={SERVICE_KEY: {"url": "https://mail.example.com", "api_key": "testkey123456"}},
                ):
                    result = runner.invoke(app, ["config", "show"], obj=mock_ctx)
                    assert result.exit_code == 0

    def test_show_masks_api_key(self, runner: CliRunner, mock_ctx: AppContext, config_file: Path) -> None:
        with patch("kctl_mailcow.commands.config_cmd.get_profile_names", return_value=["default"]):
            with patch("kctl_mailcow.commands.config_cmd.get_default_profile", return_value="default"):
                with patch(
                    "kctl_mailcow.commands.config_cmd.get_all_services_in_profile",
                    return_value={SERVICE_KEY: {"url": "https://mail.example.com", "api_key": "supersecretkey99"}},
                ):
                    result = runner.invoke(app, ["config", "show"], obj=mock_ctx)
                    assert result.exit_code == 0
                    assert "supersecretkey99" not in result.output

    def test_show_displays_config_file_path(self, runner: CliRunner, mock_ctx: AppContext, config_file: Path) -> None:
        with patch("kctl_mailcow.commands.config_cmd.get_profile_names", return_value=[]):
            with patch("kctl_mailcow.commands.config_cmd.get_default_profile", return_value="default"):
                result = runner.invoke(app, ["config", "show"], obj=mock_ctx)
                assert result.exit_code == 0


class TestConfigSet:
    def test_set_url(self, runner: CliRunner, mock_ctx: AppContext, config_file: Path) -> None:
        from kctl_mailcow.core.config import ServiceConfig

        with patch("kctl_mailcow.commands.config_cmd.resolve_active_profile_name", return_value="default"):
            with patch(
                "kctl_mailcow.commands.config_cmd.get_service_config",
                return_value=ServiceConfig(url="", api_key=""),
            ):
                with patch("kctl_mailcow.commands.config_cmd.set_service_config") as mock_set:
                    result = runner.invoke(app, ["config", "set", "url", "https://new.example.com"], obj=mock_ctx)
                    assert result.exit_code == 0
                    mock_set.assert_called_once()

    def test_set_api_key(self, runner: CliRunner, mock_ctx: AppContext, config_file: Path) -> None:
        from kctl_mailcow.core.config import ServiceConfig

        with patch("kctl_mailcow.commands.config_cmd.resolve_active_profile_name", return_value="default"):
            with patch(
                "kctl_mailcow.commands.config_cmd.get_service_config",
                return_value=ServiceConfig(url="https://mail.example.com", api_key="oldkey"),
            ):
                with patch("kctl_mailcow.commands.config_cmd.set_service_config") as mock_set:
                    result = runner.invoke(app, ["config", "set", "api_key", "newkey12345678"], obj=mock_ctx)
                    assert result.exit_code == 0
                    mock_set.assert_called_once()

    def test_set_api_key_output_masked(self, runner: CliRunner, mock_ctx: AppContext, config_file: Path) -> None:
        from kctl_mailcow.core.config import ServiceConfig

        with patch("kctl_mailcow.commands.config_cmd.resolve_active_profile_name", return_value="default"):
            with patch(
                "kctl_mailcow.commands.config_cmd.get_service_config",
                return_value=ServiceConfig(url="https://mail.example.com", api_key="oldkey"),
            ):
                with patch("kctl_mailcow.commands.config_cmd.set_service_config"):
                    result = runner.invoke(app, ["config", "set", "api_key", "supersecret9999"], obj=mock_ctx)
                    assert result.exit_code == 0
                    assert "supersecret9999" not in result.output

    def test_set_default_profile(self, runner: CliRunner, mock_ctx: AppContext, config_file: Path) -> None:
        with patch("kctl_mailcow.commands.config_cmd.set_default_profile") as mock_set_default:
            result = runner.invoke(app, ["config", "set", "default_profile", "staging"], obj=mock_ctx)
            assert result.exit_code == 0
            mock_set_default.assert_called_once_with("staging")

    def test_set_unknown_key_exits_error(self, runner: CliRunner, mock_ctx: AppContext, config_file: Path) -> None:
        with patch("kctl_mailcow.commands.config_cmd.resolve_active_profile_name", return_value="default"):
            with patch(
                "kctl_mailcow.commands.config_cmd.get_service_config",
                return_value=MagicMock(),
            ):
                result = runner.invoke(app, ["config", "set", "invalid_key", "somevalue"], obj=mock_ctx)
                assert result.exit_code == 1


class TestConfigUse:
    def test_use_existing_profile(self, runner: CliRunner, mock_ctx: AppContext, config_file: Path) -> None:
        from kctl_mailcow.core.config import ServiceConfig

        with patch("kctl_mailcow.commands.config_cmd.get_profile_names", return_value=["default", "staging"]):
            with patch("kctl_mailcow.commands.config_cmd.get_default_profile", return_value="default"):
                with patch("kctl_mailcow.commands.config_cmd.set_default_profile") as mock_set:
                    with patch(
                        "kctl_mailcow.commands.config_cmd.get_service_config",
                        return_value=ServiceConfig(url="", api_key=""),
                    ):
                        result = runner.invoke(app, ["config", "use", "staging"], obj=mock_ctx)
                        assert result.exit_code == 0
                        mock_set.assert_called_once_with("staging")

    def test_use_nonexistent_profile_fails(self, runner: CliRunner, mock_ctx: AppContext, config_file: Path) -> None:
        with patch("kctl_mailcow.commands.config_cmd.get_profile_names", return_value=["default"]):
            result = runner.invoke(app, ["config", "use", "nonexistent"], obj=mock_ctx)
            assert result.exit_code == 1

    def test_use_profile_with_url_tests_connection(
        self, runner: CliRunner, mock_ctx: AppContext, config_file: Path
    ) -> None:
        from kctl_mailcow.core.config import ServiceConfig

        with patch("kctl_mailcow.commands.config_cmd.get_profile_names", return_value=["default", "prod"]):
            with patch("kctl_mailcow.commands.config_cmd.get_default_profile", return_value="default"):
                with patch("kctl_mailcow.commands.config_cmd.set_default_profile"):
                    with patch(
                        "kctl_mailcow.commands.config_cmd.get_service_config",
                        return_value=ServiceConfig(url="https://mail.example.com", api_key="testkey12345678"),
                    ):
                        with patch(
                            "kctl_mailcow.commands.config_cmd._test_connection",
                            return_value=(True, "Mailcow 1.0"),
                        ):
                            result = runner.invoke(app, ["config", "use", "prod"], obj=mock_ctx)
                            assert result.exit_code == 0


class TestConfigRemove:
    def test_remove_nonexistent_profile_fails(self, runner: CliRunner, mock_ctx: AppContext, config_file: Path) -> None:
        with patch("kctl_mailcow.commands.config_cmd.get_profile_names", return_value=["default"]):
            result = runner.invoke(app, ["config", "remove", "ghost"], obj=mock_ctx)
            assert result.exit_code == 1

    def test_remove_with_force(self, runner: CliRunner, mock_ctx: AppContext, config_file: Path) -> None:
        with patch("kctl_mailcow.commands.config_cmd.get_profile_names", return_value=["default", "old"]):
            with patch("kctl_mailcow.commands.config_cmd.remove_profile") as mock_remove:
                with patch("kctl_mailcow.commands.config_cmd.get_default_profile", return_value="default"):
                    result = runner.invoke(app, ["config", "remove", "old", "--force"], obj=mock_ctx)
                    assert result.exit_code == 0
                    mock_remove.assert_called_once_with("old")

    def test_remove_service_only_with_force(self, runner: CliRunner, mock_ctx: AppContext, config_file: Path) -> None:
        raw_config = {
            "profiles": {
                "default": {
                    SERVICE_KEY: {"url": "https://mail.example.com", "api_key": "key"},
                    "grafana": {"url": "https://grafana.example.com"},
                }
            }
        }
        with patch("kctl_mailcow.commands.config_cmd.get_profile_names", return_value=["default"]):
            with patch("kctl_mailcow.commands.config_cmd.load_raw_config", return_value=raw_config):
                with patch("kctl_mailcow.commands.config_cmd.save_raw_config") as mock_save:
                    result = runner.invoke(
                        app, ["config", "remove", "default", "--force", "--service-only"], obj=mock_ctx
                    )
                    assert result.exit_code == 0
                    mock_save.assert_called_once()
                    saved = mock_save.call_args[0][0]
                    assert SERVICE_KEY not in saved["profiles"]["default"]

    def test_remove_without_force_aborts(self, runner: CliRunner, mock_ctx: AppContext, config_file: Path) -> None:
        with patch("kctl_mailcow.commands.config_cmd.get_profile_names", return_value=["default", "old"]):
            with patch(
                "kctl_mailcow.commands.config_cmd.get_all_services_in_profile",
                return_value={SERVICE_KEY: {"url": "x"}},
            ):
                with patch("kctl_mailcow.commands.config_cmd.remove_profile") as mock_remove:
                    result = runner.invoke(app, ["config", "remove", "old"], input="n\n", obj=mock_ctx)
                    assert result.exit_code == 0
                    mock_remove.assert_not_called()


class TestConfigProfiles:
    def test_profiles_empty(self, runner: CliRunner, mock_ctx: AppContext, config_file: Path) -> None:
        with patch("kctl_mailcow.commands.config_cmd.get_profile_names", return_value=[]):
            result = runner.invoke(app, ["config", "profiles"], obj=mock_ctx)
            assert result.exit_code == 0

    def test_profiles_lists_all(self, runner: CliRunner, mock_ctx: AppContext, config_file: Path) -> None:
        from kctl_mailcow.core.config import ServiceConfig

        with patch("kctl_mailcow.commands.config_cmd.get_profile_names", return_value=["default", "staging"]):
            with patch("kctl_mailcow.commands.config_cmd.resolve_active_profile_name", return_value="default"):
                with patch("kctl_mailcow.commands.config_cmd.get_default_profile", return_value="default"):
                    with patch(
                        "kctl_mailcow.commands.config_cmd.get_service_config",
                        return_value=ServiceConfig(url="", api_key=""),
                    ):
                        with patch(
                            "kctl_mailcow.commands.config_cmd.get_all_services_in_profile",
                            return_value={},
                        ):
                            with patch(
                                "kctl_mailcow.commands.config_cmd._test_connection",
                                return_value=(False, "not configured"),
                            ):
                                result = runner.invoke(app, ["config", "profiles"], obj=mock_ctx)
                                assert result.exit_code == 0
                                assert "default" in result.output
                                assert "staging" in result.output


class TestConfigCurrent:
    def test_current_shows_active_profile(self, runner: CliRunner, mock_ctx: AppContext, config_file: Path) -> None:
        with patch("kctl_mailcow.commands.config_cmd.resolve_active_profile_name", return_value="default"):
            with patch(
                "kctl_mailcow.commands.config_cmd.resolve_connection",
                return_value=("https://mail.example.com", "testkey"),
            ):
                with patch(
                    "kctl_mailcow.commands.config_cmd._test_connection",
                    return_value=(True, "Mailcow 1.0"),
                ):
                    with patch(
                        "kctl_mailcow.commands.config_cmd.get_all_services_in_profile",
                        return_value={SERVICE_KEY: {"url": "https://mail.example.com"}},
                    ):
                        with patch("kctl_mailcow.commands.config_cmd.get_profile_names", return_value=["default"]):
                            with patch(
                                "kctl_mailcow.commands.config_cmd.get_service_config",
                                return_value=MagicMock(url=""),
                            ):
                                result = runner.invoke(app, ["config", "current"], obj=mock_ctx)
                                assert result.exit_code == 0
                                assert "default" in result.output

    def test_current_shows_url(self, runner: CliRunner, mock_ctx: AppContext, config_file: Path) -> None:
        with patch("kctl_mailcow.commands.config_cmd.resolve_active_profile_name", return_value="default"):
            with patch(
                "kctl_mailcow.commands.config_cmd.resolve_connection",
                return_value=("https://mail.example.com", "testkey"),
            ):
                with patch(
                    "kctl_mailcow.commands.config_cmd._test_connection",
                    return_value=(True, "ok"),
                ):
                    with patch(
                        "kctl_mailcow.commands.config_cmd.get_all_services_in_profile",
                        return_value={},
                    ):
                        with patch("kctl_mailcow.commands.config_cmd.get_profile_names", return_value=["default"]):
                            with patch(
                                "kctl_mailcow.commands.config_cmd.get_service_config",
                                return_value=MagicMock(url=""),
                            ):
                                result = runner.invoke(app, ["config", "current"], obj=mock_ctx)
                                assert result.exit_code == 0
                                assert "mail.example.com" in result.output

    def test_current_not_configured(self, runner: CliRunner, mock_ctx: AppContext, config_file: Path) -> None:
        with patch("kctl_mailcow.commands.config_cmd.resolve_active_profile_name", return_value="default"):
            with patch(
                "kctl_mailcow.commands.config_cmd.resolve_connection",
                return_value=("", ""),
            ):
                with patch(
                    "kctl_mailcow.commands.config_cmd.get_all_services_in_profile",
                    return_value={},
                ):
                    with patch("kctl_mailcow.commands.config_cmd.get_profile_names", return_value=["default"]):
                        with patch(
                            "kctl_mailcow.commands.config_cmd.get_service_config",
                            return_value=MagicMock(url=""),
                        ):
                            result = runner.invoke(app, ["config", "current"], obj=mock_ctx)
                            assert result.exit_code == 0


class TestConfigTest:
    def test_test_connection_success(self, runner: CliRunner, mock_ctx: AppContext, mock_client: MagicMock) -> None:
        mock_client.mc_get.return_value = {"postfix": "running"}
        result = runner.invoke(app, ["config", "test"], obj=mock_ctx)
        assert result.exit_code == 0
        mock_client.mc_get.assert_called_once_with("status/containers")

    def test_test_connection_failure(self, runner: CliRunner, mock_ctx: AppContext, mock_client: MagicMock) -> None:
        from kctl_mailcow.core.exceptions import KctlError

        mock_client.mc_get.side_effect = KctlError("Connection refused")
        result = runner.invoke(app, ["config", "test"], obj=mock_ctx)
        assert result.exit_code == 1

    def test_test_shows_connected(self, runner: CliRunner, mock_ctx: AppContext, mock_client: MagicMock) -> None:
        mock_client.mc_get.return_value = {}
        with patch("kctl_mailcow.commands.config_cmd.resolve_active_profile_name", return_value="myprod"):
            result = runner.invoke(app, ["config", "test"], obj=mock_ctx)
            assert result.exit_code == 0


@pytest.fixture
def mock_client() -> MagicMock:
    from kctl_mailcow.core.client import MailcowClient

    client = MagicMock(spec=MailcowClient)
    client.base_url = "https://mail.kodeme.io"
    return client


@pytest.fixture
def mock_ctx_with_client(mock_client: MagicMock) -> AppContext:
    from kctl_lib.output import Output

    ctx = AppContext(quiet=True)
    ctx._client = mock_client
    ctx._output = Output(json_mode=False, quiet=True, format="pretty")
    return ctx


class TestConfigMigrate:
    def test_migrate_flat_config(self, runner: CliRunner, mock_ctx: AppContext, config_file: Path) -> None:
        flat_config = {
            "profiles": {
                "default": {
                    "url": "https://mail.example.com",
                    "api_key": "oldkey",
                }
            }
        }
        with patch("kctl_mailcow.commands.config_cmd.load_raw_config", return_value=flat_config):
            with patch("kctl_mailcow.commands.config_cmd.save_raw_config") as mock_save:
                result = runner.invoke(app, ["config", "migrate"], obj=mock_ctx)
                assert result.exit_code == 0
                mock_save.assert_called_once()
                saved = mock_save.call_args[0][0]
                assert SERVICE_KEY in saved["profiles"]["default"]

    def test_migrate_already_scoped(self, runner: CliRunner, mock_ctx: AppContext, config_file: Path) -> None:
        scoped_config = {
            "profiles": {
                "default": {
                    SERVICE_KEY: {"url": "https://mail.example.com", "api_key": "key"},
                }
            }
        }
        with patch("kctl_mailcow.commands.config_cmd.load_raw_config", return_value=scoped_config):
            with patch("kctl_mailcow.commands.config_cmd.save_raw_config") as mock_save:
                result = runner.invoke(app, ["config", "migrate"], obj=mock_ctx)
                assert result.exit_code == 0
                mock_save.assert_not_called()
