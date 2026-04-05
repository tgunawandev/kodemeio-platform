"""Tests for kctl-api config commands."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from kctl_api.cli import app
from kctl_api.core.config import ServiceConfig

runner = CliRunner()


# ---------------------------------------------------------------------------
# config --help checks
# ---------------------------------------------------------------------------
class TestConfigHelp:
    def test_config_help(self) -> None:
        result = runner.invoke(app, ["config", "--help"])
        assert result.exit_code == 0

    def test_config_add_help(self) -> None:
        result = runner.invoke(app, ["config", "add", "--help"])
        assert result.exit_code == 0
        assert "--url" in result.output

    def test_config_use_help(self) -> None:
        result = runner.invoke(app, ["config", "use", "--help"])
        assert result.exit_code == 0

    def test_config_show_help(self) -> None:
        result = runner.invoke(app, ["config", "show", "--help"])
        assert result.exit_code == 0

    def test_config_profiles_help(self) -> None:
        result = runner.invoke(app, ["config", "profiles", "--help"])
        assert result.exit_code == 0

    def test_config_set_help(self) -> None:
        result = runner.invoke(app, ["config", "set", "--help"])
        assert result.exit_code == 0

    def test_config_remove_help(self) -> None:
        result = runner.invoke(app, ["config", "remove", "--help"])
        assert result.exit_code == 0

    def test_config_current_help(self) -> None:
        result = runner.invoke(app, ["config", "current", "--help"])
        assert result.exit_code == 0

    def test_config_migrate_help(self) -> None:
        result = runner.invoke(app, ["config", "migrate", "--help"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# config profiles
# ---------------------------------------------------------------------------
class TestConfigProfiles:
    def test_profiles_no_config(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.yaml"
        with (
            patch("kctl_api.core.config.CONFIG_FILE", config_file),
            patch("kctl_api.core.config.CONFIG_DIR", tmp_path),
        ):
            result = runner.invoke(app, ["config", "profiles"])
        assert result.exit_code == 0

    def test_profiles_with_one_profile(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.yaml"
        config_file.write_text("default_profile: dev\nprofiles:\n  dev:\n    api:\n      url: http://localhost:8000\n")
        with (
            patch("kctl_api.core.config.CONFIG_FILE", config_file),
            patch("kctl_api.core.config.CONFIG_DIR", tmp_path),
            patch("kctl_lib.config.CONFIG_FILE", config_file),
            patch("kctl_lib.config.CONFIG_DIR", tmp_path),
        ):
            result = runner.invoke(app, ["config", "profiles"])
        assert result.exit_code == 0

    def test_profiles_json_empty(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.yaml"
        with (
            patch("kctl_api.core.config.CONFIG_FILE", config_file),
            patch("kctl_api.core.config.CONFIG_DIR", tmp_path),
        ):
            result = runner.invoke(app, ["--json", "config", "profiles"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# config add
# ---------------------------------------------------------------------------
class TestConfigAdd:
    def test_add_profile(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.yaml"
        with (
            patch("kctl_api.core.config.CONFIG_FILE", config_file),
            patch("kctl_api.core.config.CONFIG_DIR", tmp_path),
            patch("kctl_lib.config.CONFIG_FILE", config_file),
            patch("kctl_lib.config.CONFIG_DIR", tmp_path),
        ):
            result = runner.invoke(
                app,
                ["config", "add", "staging", "--url", "http://stg.example.com", "--api-key", "tok123"],
            )
        assert result.exit_code == 0
        assert "staging" in result.output

    def test_add_profile_with_default(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.yaml"
        with (
            patch("kctl_api.core.config.CONFIG_FILE", config_file),
            patch("kctl_api.core.config.CONFIG_DIR", tmp_path),
            patch("kctl_lib.config.CONFIG_FILE", config_file),
            patch("kctl_lib.config.CONFIG_DIR", tmp_path),
        ):
            result = runner.invoke(
                app,
                ["config", "add", "prod", "--url", "https://api.kodeme.io", "--default"],
            )
        assert result.exit_code == 0
        assert "prod" in result.output

    def test_add_profile_json(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.yaml"
        with (
            patch("kctl_api.core.config.CONFIG_FILE", config_file),
            patch("kctl_api.core.config.CONFIG_DIR", tmp_path),
            patch("kctl_lib.config.CONFIG_FILE", config_file),
            patch("kctl_lib.config.CONFIG_DIR", tmp_path),
        ):
            result = runner.invoke(
                app,
                ["--json", "config", "add", "test", "--url", "http://test.com"],
            )
        assert result.exit_code == 0
        assert '"profile": "test"' in result.output

    def test_add_duplicate_warns(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            "default_profile: default\nprofiles:\n  myprofile:\n    api:\n      url: http://old.com\n"
        )
        with (
            patch("kctl_api.core.config.CONFIG_FILE", config_file),
            patch("kctl_api.core.config.CONFIG_DIR", tmp_path),
            patch("kctl_lib.config.CONFIG_FILE", config_file),
            patch("kctl_lib.config.CONFIG_DIR", tmp_path),
        ):
            result = runner.invoke(app, ["config", "add", "myprofile", "--url", "http://new.com"])
        assert result.exit_code == 0
        # Should warn about overwrite
        assert "already exists" in result.output or "myprofile" in result.output


# ---------------------------------------------------------------------------
# config use
# ---------------------------------------------------------------------------
class TestConfigUse:
    def test_use_existing_profile(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            "default_profile: dev\nprofiles:\n  dev:\n    api:\n      url: http://dev.com\n  prod:\n    api:\n      url: http://prod.com\n"
        )
        with (
            patch("kctl_api.core.config.CONFIG_FILE", config_file),
            patch("kctl_api.core.config.CONFIG_DIR", tmp_path),
            patch("kctl_lib.config.CONFIG_FILE", config_file),
            patch("kctl_lib.config.CONFIG_DIR", tmp_path),
        ):
            result = runner.invoke(app, ["config", "use", "prod"])
        assert result.exit_code == 0
        assert "prod" in result.output

    def test_use_nonexistent_profile_exits_1(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.yaml"
        with (
            patch("kctl_api.core.config.CONFIG_FILE", config_file),
            patch("kctl_api.core.config.CONFIG_DIR", tmp_path),
            patch("kctl_lib.config.CONFIG_FILE", config_file),
            patch("kctl_lib.config.CONFIG_DIR", tmp_path),
        ):
            result = runner.invoke(app, ["config", "use", "nonexistent"])
        assert result.exit_code == 1

    def test_use_json_mode(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.yaml"
        config_file.write_text("default_profile: dev\nprofiles:\n  dev:\n    api: {}\n  staging:\n    api: {}\n")
        with (
            patch("kctl_api.core.config.CONFIG_FILE", config_file),
            patch("kctl_api.core.config.CONFIG_DIR", tmp_path),
            patch("kctl_lib.config.CONFIG_FILE", config_file),
            patch("kctl_lib.config.CONFIG_DIR", tmp_path),
        ):
            result = runner.invoke(app, ["--json", "config", "use", "staging"])
        assert result.exit_code == 0
        assert '"default_profile": "staging"' in result.output


# ---------------------------------------------------------------------------
# config set
# ---------------------------------------------------------------------------
class TestConfigSet:
    def test_set_url(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.yaml"
        config_file.write_text("default_profile: default\nprofiles:\n  default:\n    api: {}\n")
        with (
            patch("kctl_api.core.config.CONFIG_FILE", config_file),
            patch("kctl_api.core.config.CONFIG_DIR", tmp_path),
            patch("kctl_lib.config.CONFIG_FILE", config_file),
            patch("kctl_lib.config.CONFIG_DIR", tmp_path),
        ):
            result = runner.invoke(app, ["config", "set", "url", "http://new-api.com"])
        assert result.exit_code == 0
        assert "url" in result.output

    def test_set_api_key_masked(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.yaml"
        config_file.write_text("default_profile: default\nprofiles:\n  default:\n    api: {}\n")
        with (
            patch("kctl_api.core.config.CONFIG_FILE", config_file),
            patch("kctl_api.core.config.CONFIG_DIR", tmp_path),
            patch("kctl_lib.config.CONFIG_FILE", config_file),
            patch("kctl_lib.config.CONFIG_DIR", tmp_path),
        ):
            result = runner.invoke(app, ["config", "set", "api_key", "super-secret-token-here"])
        assert result.exit_code == 0
        # Secret should be masked in output
        assert "super-secret-token-here" not in result.output

    def test_set_invalid_key_exits_1(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.yaml"
        config_file.write_text("default_profile: default\nprofiles:\n  default:\n    api: {}\n")
        with (
            patch("kctl_api.core.config.CONFIG_FILE", config_file),
            patch("kctl_api.core.config.CONFIG_DIR", tmp_path),
            patch("kctl_lib.config.CONFIG_FILE", config_file),
            patch("kctl_lib.config.CONFIG_DIR", tmp_path),
        ):
            result = runner.invoke(app, ["config", "set", "invalid_key", "value"])
        assert result.exit_code == 1
        assert "Invalid key" in result.output

    def test_set_json_output(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.yaml"
        config_file.write_text("default_profile: default\nprofiles:\n  default:\n    api: {}\n")
        with (
            patch("kctl_api.core.config.CONFIG_FILE", config_file),
            patch("kctl_api.core.config.CONFIG_DIR", tmp_path),
            patch("kctl_lib.config.CONFIG_FILE", config_file),
            patch("kctl_lib.config.CONFIG_DIR", tmp_path),
        ):
            result = runner.invoke(app, ["--json", "config", "set", "url", "http://example.com"])
        assert result.exit_code == 0
        assert '"key": "url"' in result.output


# ---------------------------------------------------------------------------
# config remove
# ---------------------------------------------------------------------------
class TestConfigRemove:
    def test_remove_nonexistent_exits_1(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.yaml"
        with (
            patch("kctl_api.core.config.CONFIG_FILE", config_file),
            patch("kctl_api.core.config.CONFIG_DIR", tmp_path),
            patch("kctl_lib.config.CONFIG_FILE", config_file),
            patch("kctl_lib.config.CONFIG_DIR", tmp_path),
        ):
            result = runner.invoke(app, ["config", "remove", "ghost"])
        assert result.exit_code == 1
        assert "does not exist" in result.output

    def test_remove_with_force(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.yaml"
        config_file.write_text("default_profile: default\nprofiles:\n  tobedeleted:\n    api: {}\n")
        with (
            patch("kctl_api.core.config.CONFIG_FILE", config_file),
            patch("kctl_api.core.config.CONFIG_DIR", tmp_path),
            patch("kctl_lib.config.CONFIG_FILE", config_file),
            patch("kctl_lib.config.CONFIG_DIR", tmp_path),
        ):
            result = runner.invoke(app, ["config", "remove", "tobedeleted", "--force"])
        assert result.exit_code == 0
        assert "tobedeleted" in result.output

    def test_remove_json_output(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.yaml"
        config_file.write_text("default_profile: default\nprofiles:\n  old:\n    api: {}\n")
        with (
            patch("kctl_api.core.config.CONFIG_FILE", config_file),
            patch("kctl_api.core.config.CONFIG_DIR", tmp_path),
            patch("kctl_lib.config.CONFIG_FILE", config_file),
            patch("kctl_lib.config.CONFIG_DIR", tmp_path),
        ):
            result = runner.invoke(app, ["--json", "config", "remove", "old", "--force"])
        assert result.exit_code == 0
        assert '"removed": "old"' in result.output


# ---------------------------------------------------------------------------
# config show
# ---------------------------------------------------------------------------
class TestConfigShow:
    def test_show_empty_config(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.yaml"
        with (
            patch("kctl_api.core.config.CONFIG_FILE", config_file),
            patch("kctl_api.core.config.CONFIG_DIR", tmp_path),
            patch("kctl_lib.config.CONFIG_FILE", config_file),
            patch("kctl_lib.config.CONFIG_DIR", tmp_path),
        ):
            result = runner.invoke(app, ["config", "show"])
        assert result.exit_code == 0

    def test_show_masks_api_key(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            "default_profile: default\nprofiles:\n  default:\n    api:\n      url: http://localhost\n      api_key: my-secret-token-here\n"
        )
        with (
            patch("kctl_api.core.config.CONFIG_FILE", config_file),
            patch("kctl_api.core.config.CONFIG_DIR", tmp_path),
            patch("kctl_lib.config.CONFIG_FILE", config_file),
            patch("kctl_lib.config.CONFIG_DIR", tmp_path),
        ):
            result = runner.invoke(app, ["config", "show"])
        assert result.exit_code == 0
        assert "my-secret-token-here" not in result.output


# ---------------------------------------------------------------------------
# config migrate
# ---------------------------------------------------------------------------
class TestConfigMigrate:
    def test_migrate_no_profiles(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.yaml"
        with (
            patch("kctl_api.core.config.CONFIG_FILE", config_file),
            patch("kctl_api.core.config.CONFIG_DIR", tmp_path),
            patch("kctl_lib.config.CONFIG_FILE", config_file),
            patch("kctl_lib.config.CONFIG_DIR", tmp_path),
        ):
            result = runner.invoke(app, ["config", "migrate"])
        assert result.exit_code == 0
        assert "Nothing to migrate" in result.output or "No profiles" in result.output

    def test_migrate_already_scoped(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            "default_profile: default\nprofiles:\n  default:\n    api:\n      url: http://localhost\n"
        )
        with (
            patch("kctl_api.core.config.CONFIG_FILE", config_file),
            patch("kctl_api.core.config.CONFIG_DIR", tmp_path),
            patch("kctl_lib.config.CONFIG_FILE", config_file),
            patch("kctl_lib.config.CONFIG_DIR", tmp_path),
        ):
            result = runner.invoke(app, ["config", "migrate"])
        assert result.exit_code == 0
        assert "already" in result.output.lower()

    def test_migrate_flat_format(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            "default_profile: default\nprofiles:\n  default:\n    url: http://localhost\n    api_key: old-key\n"
        )
        with (
            patch("kctl_api.core.config.CONFIG_FILE", config_file),
            patch("kctl_api.core.config.CONFIG_DIR", tmp_path),
            patch("kctl_lib.config.CONFIG_FILE", config_file),
            patch("kctl_lib.config.CONFIG_DIR", tmp_path),
        ):
            result = runner.invoke(app, ["config", "migrate"])
        assert result.exit_code == 0
        assert "Migrated" in result.output or "migrated" in result.output
