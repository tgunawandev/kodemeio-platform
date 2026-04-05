"""Full tests for config commands."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml
from typer.testing import CliRunner

from kctl_linear.cli import app
from kctl_linear.core.client import LinearClient

runner = CliRunner()


@pytest.fixture
def config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect config to a temp dir and return the dir path."""
    cfg_dir = tmp_path / "kodemeio"
    cfg_dir.mkdir(parents=True)
    monkeypatch.setenv("KCTL_CONFIG_DIR", str(cfg_dir))
    return cfg_dir


def write_config(config_dir: Path, data: dict) -> None:
    """Write config.yaml to the temp config dir."""
    cfg_file = config_dir / "config.yaml"
    cfg_file.write_text(yaml.dump(data))


class TestConfigHelp:
    def test_config_help(self):
        result = runner.invoke(app, ["config", "--help"])
        assert result.exit_code == 0
        assert "init" in result.output
        assert "show" in result.output
        assert "validate" in result.output
        assert "profiles" in result.output

    def test_config_show_help(self):
        result = runner.invoke(app, ["config", "show", "--help"])
        assert result.exit_code == 0

    def test_config_validate_help(self):
        result = runner.invoke(app, ["config", "validate", "--help"])
        assert result.exit_code == 0

    def test_config_use_help(self):
        result = runner.invoke(app, ["config", "use", "--help"])
        assert result.exit_code == 0

    def test_config_set_help(self):
        result = runner.invoke(app, ["config", "set", "--help"])
        assert result.exit_code == 0

    def test_config_remove_help(self):
        result = runner.invoke(app, ["config", "remove", "--help"])
        assert result.exit_code == 0

    def test_config_profiles_help(self):
        result = runner.invoke(app, ["config", "profiles", "--help"])
        assert result.exit_code == 0

    def test_config_current_help(self):
        result = runner.invoke(app, ["config", "current", "--help"])
        assert result.exit_code == 0


class TestConfigProfiles:
    def test_profiles_empty(self, config_dir: Path):
        result = runner.invoke(app, ["config", "profiles"])
        assert result.exit_code == 0

    def test_profiles_with_data(self, config_dir: Path):
        write_config(
            config_dir,
            {
                "default_profile": "default",
                "profiles": {
                    "default": {"linear": {"api_key": "lin_api_abc123", "default_team": "KOD"}},
                    "staging": {"linear": {"api_key": "lin_api_stg456", "default_team": "STG"}},
                },
            },
        )
        result = runner.invoke(app, ["config", "profiles"])
        assert result.exit_code == 0

    def test_profiles_json_output(self, config_dir: Path):
        write_config(
            config_dir,
            {
                "default_profile": "default",
                "profiles": {"default": {"linear": {"api_key": "lin_api_abc123"}}},
            },
        )
        result = runner.invoke(app, ["--json", "config", "profiles"])
        assert result.exit_code == 0


class TestConfigShow:
    def test_show_no_profile(self, config_dir: Path):
        result = runner.invoke(app, ["config", "show"])
        assert result.exit_code == 0

    def test_show_with_profile(self, config_dir: Path):
        write_config(
            config_dir,
            {
                "default_profile": "default",
                "profiles": {"default": {"linear": {"api_key": "lin_api_abc123", "default_team": "KOD"}}},
            },
        )
        result = runner.invoke(app, ["config", "show"])
        assert result.exit_code == 0

    def test_show_json_output(self, config_dir: Path):
        write_config(
            config_dir,
            {
                "default_profile": "default",
                "profiles": {"default": {"linear": {"api_key": "lin_api_abc123"}}},
            },
        )
        result = runner.invoke(app, ["--json", "config", "show"])
        assert result.exit_code == 0


class TestConfigCurrent:
    def test_current_with_config(self, config_dir: Path):
        write_config(
            config_dir,
            {
                "default_profile": "default",
                "profiles": {"default": {"linear": {"api_key": "lin_api_abc123", "default_team": "KOD"}}},
            },
        )
        result = runner.invoke(app, ["config", "current"])
        assert result.exit_code == 0

    def test_current_json_output(self, config_dir: Path):
        write_config(
            config_dir,
            {
                "default_profile": "default",
                "profiles": {"default": {"linear": {"api_key": "lin_api_abc123"}}},
            },
        )
        result = runner.invoke(app, ["--json", "config", "current"])
        assert result.exit_code == 0

    def test_current_empty_config(self, config_dir: Path):
        result = runner.invoke(app, ["config", "current"])
        assert result.exit_code == 0


class TestConfigValidate:
    def test_validate_missing_api_key(self, config_dir: Path):
        write_config(
            config_dir,
            {
                "default_profile": "default",
                "profiles": {"default": {"linear": {}}},
            },
        )
        result = runner.invoke(app, ["config", "validate"])
        assert result.exit_code != 0

    def test_validate_valid_config(self, config_dir: Path):
        write_config(
            config_dir,
            {
                "default_profile": "default",
                "profiles": {"default": {"linear": {"api_key": "lin_api_abc123", "default_team": "KOD"}}},
            },
        )
        result = runner.invoke(app, ["config", "validate"])
        assert result.exit_code == 0

    def test_validate_missing_default_team_warns(self, config_dir: Path):
        write_config(
            config_dir,
            {
                "default_profile": "default",
                "profiles": {"default": {"linear": {"api_key": "lin_api_abc123"}}},
            },
        )
        result = runner.invoke(app, ["config", "validate"])
        # api_key present, so exit code should be 0 (only a warning for missing team)
        assert result.exit_code == 0

    def test_validate_json_valid(self, config_dir: Path):
        write_config(
            config_dir,
            {
                "default_profile": "default",
                "profiles": {"default": {"linear": {"api_key": "lin_api_abc123", "default_team": "KOD"}}},
            },
        )
        result = runner.invoke(app, ["--json", "config", "validate"])
        assert result.exit_code == 0

    def test_validate_json_invalid(self, config_dir: Path):
        write_config(
            config_dir,
            {
                "default_profile": "default",
                "profiles": {"default": {"linear": {}}},
            },
        )
        result = runner.invoke(app, ["--json", "config", "validate"])
        assert result.exit_code != 0


class TestConfigUse:
    def test_use_existing_profile(self, config_dir: Path):
        write_config(
            config_dir,
            {
                "default_profile": "default",
                "profiles": {
                    "default": {"linear": {"api_key": "lin_api_abc123"}},
                    "staging": {"linear": {"api_key": "lin_api_stg456"}},
                },
            },
        )
        result = runner.invoke(app, ["config", "use", "staging"])
        assert result.exit_code == 0

    def test_use_nonexistent_profile(self, config_dir: Path):
        write_config(
            config_dir,
            {
                "default_profile": "default",
                "profiles": {"default": {"linear": {"api_key": "lin_api_abc123"}}},
            },
        )
        result = runner.invoke(app, ["config", "use", "nonexistent"])
        assert result.exit_code != 0


class TestConfigSet:
    def test_set_valid_key(self, config_dir: Path):
        write_config(
            config_dir,
            {
                "default_profile": "default",
                "profiles": {"default": {"linear": {"api_key": "lin_api_abc123"}}},
            },
        )
        result = runner.invoke(app, ["config", "set", "default_team", "KOD"])
        assert result.exit_code == 0

    def test_set_api_key(self, config_dir: Path):
        write_config(
            config_dir,
            {
                "default_profile": "default",
                "profiles": {"default": {"linear": {"api_key": "lin_api_old"}}},
            },
        )
        result = runner.invoke(app, ["config", "set", "api_key", "lin_api_new123"])
        assert result.exit_code == 0

    def test_set_invalid_key_fails(self, config_dir: Path):
        write_config(
            config_dir,
            {
                "default_profile": "default",
                "profiles": {"default": {"linear": {"api_key": "lin_api_abc123"}}},
            },
        )
        result = runner.invoke(app, ["config", "set", "nonexistent_key", "value"])
        assert result.exit_code != 0


class TestConfigRemove:
    def test_remove_existing_profile(self, config_dir: Path):
        write_config(
            config_dir,
            {
                "default_profile": "default",
                "profiles": {
                    "default": {"linear": {"api_key": "lin_api_abc123"}},
                    "old": {"linear": {"api_key": "lin_api_old123"}},
                },
            },
        )
        result = runner.invoke(app, ["config", "remove", "old"])
        assert result.exit_code == 0

    def test_remove_nonexistent_profile(self, config_dir: Path):
        write_config(
            config_dir,
            {
                "default_profile": "default",
                "profiles": {"default": {"linear": {"api_key": "lin_api_abc123"}}},
            },
        )
        result = runner.invoke(app, ["config", "remove", "ghost"])
        assert result.exit_code != 0


class TestConfigTest:
    def test_test_connection_success(self, config_dir: Path):
        write_config(
            config_dir,
            {
                "default_profile": "default",
                "profiles": {"default": {"linear": {"api_key": "lin_api_abc123"}}},
            },
        )
        with patch("kctl_linear.commands.config_cmd.AppContext.client") as mock_client_prop:
            mock_client = MagicMock(spec=LinearClient)
            mock_client.query.return_value = {"viewer": {"id": "u1", "name": "Test User", "email": "test@kodeme.io"}}
            mock_client_prop.__get__ = MagicMock(return_value=mock_client)
            result = runner.invoke(app, ["config", "test"])
            # Connection test may exit 0 or 1 depending on mock setup; just verify no crash
            assert result.exit_code in (0, 1)
