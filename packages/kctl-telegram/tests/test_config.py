"""Tests for config management commands."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from kctl_lib.output import Output
from kctl_telegram.cli import app
from kctl_telegram.core.callbacks import AppContext
from kctl_telegram.core.client import TelegramClient


def make_context() -> AppContext:
    ctx = AppContext(quiet=True)
    ctx._output = Output(json_mode=False, quiet=True, format="pretty")
    return ctx


def make_json_context() -> AppContext:
    ctx = AppContext(json_mode=True, quiet=True)
    ctx._output = Output(json_mode=True, quiet=True, format="json")
    return ctx


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def mock_client() -> MagicMock:
    client = MagicMock(spec=TelegramClient)
    client.base_url = "https://telegram.kodeme.io"
    return client


@pytest.fixture
def isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect all config I/O to a temp directory."""
    config_file = tmp_path / "config.yaml"
    monkeypatch.setattr("kctl_telegram.core.config.CONFIG_DIR", tmp_path)
    monkeypatch.setattr("kctl_telegram.core.config.CONFIG_FILE", config_file)
    monkeypatch.setattr("kctl_lib.config.CONFIG_DIR", tmp_path)
    monkeypatch.setattr("kctl_lib.config.CONFIG_FILE", config_file)
    return config_file


class TestMaskKey:
    """Unit tests for the _mask_key helper (tested via config show output)."""

    def test_short_key_masked_as_stars(self) -> None:
        from kctl_telegram.commands.config_cmd import _mask_key

        assert _mask_key("short") == "****"

    def test_long_key_shows_first_and_last_four(self) -> None:
        from kctl_telegram.commands.config_cmd import _mask_key

        key = "abcd1234efgh5678"
        result = _mask_key(key)
        assert result.startswith("abcd")
        assert result.endswith("5678")
        assert "****" in result

    def test_empty_key_returns_not_set(self) -> None:
        from kctl_telegram.commands.config_cmd import _mask_key

        result = _mask_key("")
        assert "not set" in result

    def test_exactly_10_chars_masked_as_stars(self) -> None:
        from kctl_telegram.commands.config_cmd import _mask_key

        assert _mask_key("1234567890") == "****"

    def test_11_chars_shows_partial(self) -> None:
        from kctl_telegram.commands.config_cmd import _mask_key

        key = "12345678901"
        result = _mask_key(key)
        assert result.startswith("1234")
        assert result.endswith("8901")


class TestConfigShowCommand:
    def test_show_no_profiles(self, runner: CliRunner, isolated_config: Path) -> None:
        ctx = make_context()
        result = runner.invoke(app, ["config", "show"], obj=ctx)
        assert result.exit_code == 0

    def test_show_with_profiles(self, runner: CliRunner, isolated_config: Path) -> None:
        from kctl_telegram.core.config import ServiceConfig, set_service_config

        set_service_config("default", ServiceConfig(url="https://tg.example.com", api_key="abcd1234efgh5678"))
        ctx = make_context()
        result = runner.invoke(app, ["config", "show"], obj=ctx)
        assert result.exit_code == 0

    def test_show_json_masks_api_keys(self, runner: CliRunner, isolated_config: Path) -> None:
        from kctl_telegram.core.config import ServiceConfig, set_service_config

        set_service_config("prod", ServiceConfig(url="https://tg.prod.io", api_key="secretkey12345678"))
        ctx = make_json_context()
        result = runner.invoke(app, ["--json", "config", "show"], obj=ctx)
        assert result.exit_code == 0
        # Raw secret must not appear in output
        assert "secretkey12345678" not in result.output


class TestConfigUseCommand:
    def test_use_existing_profile(self, runner: CliRunner, isolated_config: Path) -> None:
        from kctl_telegram.core.config import ServiceConfig, set_service_config

        set_service_config("staging", ServiceConfig(url="", api_key=""))
        ctx = make_context()
        with patch("kctl_telegram.commands.config_cmd._test_connection", return_value=(False, "no url")):
            result = runner.invoke(app, ["config", "use", "staging"], obj=ctx)
        assert result.exit_code == 0

    def test_use_nonexistent_profile_exits_1(self, runner: CliRunner, isolated_config: Path) -> None:
        ctx = make_context()
        result = runner.invoke(app, ["config", "use", "nonexistent"], obj=ctx)
        assert result.exit_code == 1

    def test_use_profile_with_url_tests_connection(self, runner: CliRunner, isolated_config: Path) -> None:
        from kctl_telegram.core.config import ServiceConfig, set_service_config

        set_service_config("prod", ServiceConfig(url="https://tg.prod.io", api_key="key123"))
        ctx = make_context()
        with patch(
            "kctl_telegram.commands.config_cmd._test_connection",
            return_value=(True, "1.5.0"),
        ):
            result = runner.invoke(app, ["config", "use", "prod"], obj=ctx)
        assert result.exit_code == 0


class TestConfigSetCommand:
    def test_set_url(self, runner: CliRunner, isolated_config: Path) -> None:
        from kctl_telegram.core.config import ServiceConfig, set_service_config

        set_service_config("default", ServiceConfig(url="https://old.io", api_key="key123"))
        ctx = make_context()
        result = runner.invoke(app, ["--profile", "default", "config", "set", "url", "https://new.io"], obj=ctx)
        assert result.exit_code == 0

    def test_set_default_profile(self, runner: CliRunner, isolated_config: Path) -> None:
        from kctl_telegram.core.config import ServiceConfig, set_service_config

        set_service_config("alpha", ServiceConfig(url="https://alpha.io", api_key="key"))
        set_service_config("beta", ServiceConfig(url="https://beta.io", api_key="key2"))
        ctx = make_context()
        result = runner.invoke(app, ["config", "set", "default_profile", "beta"], obj=ctx)
        assert result.exit_code == 0

    def test_set_invalid_key_exits_1(self, runner: CliRunner, isolated_config: Path) -> None:
        from kctl_telegram.core.config import ServiceConfig, set_service_config

        set_service_config("default", ServiceConfig(url="https://tg.io", api_key="key"))
        ctx = make_context()
        result = runner.invoke(app, ["config", "set", "invalid_field", "somevalue"], obj=ctx)
        assert result.exit_code == 1

    def test_set_api_key_masked_in_output(self, runner: CliRunner, isolated_config: Path) -> None:
        from kctl_telegram.core.config import ServiceConfig, set_service_config

        set_service_config("default", ServiceConfig(url="https://tg.io", api_key="oldkey123"))
        ctx = make_context()
        result = runner.invoke(
            app,
            ["--profile", "default", "config", "set", "api_key", "newkey_abcd_efgh_1234"],
            obj=ctx,
        )
        assert result.exit_code == 0
        assert "newkey_abcd_efgh_1234" not in result.output


class TestConfigProfilesCommand:
    def test_profiles_empty(self, runner: CliRunner, isolated_config: Path) -> None:
        ctx = make_context()
        result = runner.invoke(app, ["config", "profiles"], obj=ctx)
        assert result.exit_code == 0

    def test_profiles_lists_all(self, runner: CliRunner, isolated_config: Path) -> None:
        from kctl_telegram.core.config import ServiceConfig, set_service_config

        set_service_config("default", ServiceConfig(url="", api_key=""))
        set_service_config("prod", ServiceConfig(url="", api_key=""))
        ctx = make_context()
        with patch("kctl_telegram.commands.config_cmd._test_connection", return_value=(False, "no url")):
            result = runner.invoke(app, ["--profile", "default", "config", "profiles"], obj=ctx)
        assert result.exit_code == 0


class TestConfigRemoveCommand:
    def test_remove_nonexistent_exits_1(self, runner: CliRunner, isolated_config: Path) -> None:
        ctx = make_context()
        result = runner.invoke(app, ["config", "remove", "ghost"], obj=ctx)
        assert result.exit_code == 1

    def test_remove_with_force(self, runner: CliRunner, isolated_config: Path) -> None:
        from kctl_telegram.core.config import ServiceConfig, set_service_config

        set_service_config("temp", ServiceConfig(url="https://temp.io", api_key="k"))
        ctx = make_context()
        result = runner.invoke(app, ["config", "remove", "temp", "--force"], obj=ctx)
        assert result.exit_code == 0

    def test_remove_cancel_confirmation(self, runner: CliRunner, isolated_config: Path) -> None:
        from kctl_telegram.core.config import ServiceConfig, set_service_config

        set_service_config("keep", ServiceConfig(url="https://keep.io", api_key="k"))
        ctx = make_context()
        result = runner.invoke(app, ["config", "remove", "keep"], obj=ctx, input="n\n")
        assert result.exit_code == 0

    def test_remove_service_only_with_force(self, runner: CliRunner, isolated_config: Path) -> None:
        from kctl_telegram.core.config import ServiceConfig, set_service_config

        set_service_config("multi", ServiceConfig(url="https://multi.io", api_key="key"))
        ctx = make_context()
        result = runner.invoke(
            app,
            ["config", "remove", "multi", "--service-only", "--force"],
            obj=ctx,
        )
        assert result.exit_code == 0


class TestConfigMigrateCommand:
    def test_migrate_already_scoped(self, runner: CliRunner, isolated_config: Path) -> None:
        from kctl_telegram.core.config import ServiceConfig, set_service_config

        set_service_config("default", ServiceConfig(url="https://tg.io", api_key="key"))
        ctx = make_context()
        result = runner.invoke(app, ["config", "migrate"], obj=ctx)
        assert result.exit_code == 0

    def test_migrate_flat_format(self, runner: CliRunner, isolated_config: Path) -> None:
        """Migrate a flat-format profile to service-scoped format."""
        import yaml
        from kctl_lib.config import save_raw_config

        # Write a flat-format config manually
        flat_config = {
            "default_profile": "default",
            "profiles": {
                "default": {
                    "url": "https://tg.io",
                    "api_key": "flatkey123",
                }
            },
        }
        save_raw_config(flat_config)
        ctx = make_context()
        result = runner.invoke(app, ["config", "migrate"], obj=ctx)
        assert result.exit_code == 0
