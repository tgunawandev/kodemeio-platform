"""Tests for core/config.py — ServiceConfig and config loading."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from kctl_claude.core.config import SERVICE_KEY, ServiceConfig, load_claude_config


class TestServiceConfig:
    def test_defaults(self) -> None:
        cfg = ServiceConfig()
        assert cfg.config_dir == ""
        assert cfg.backup_dir == ""

    def test_custom_values(self) -> None:
        cfg = ServiceConfig(config_dir="/custom/dir", backup_dir="/custom/backup")
        assert cfg.config_dir == "/custom/dir"
        assert cfg.backup_dir == "/custom/backup"

    def test_model_dump(self) -> None:
        cfg = ServiceConfig(config_dir="~/.claude")
        data = cfg.model_dump()
        assert data["config_dir"] == "~/.claude"
        assert data["backup_dir"] == ""

    def test_service_key_is_claude(self) -> None:
        assert SERVICE_KEY == "claude"


class TestLoadClaudeConfig:
    def test_load_with_default_profile(self) -> None:
        mock_cfg = MagicMock()
        mock_cfg.default_profile = "default"
        with (
            patch("kctl_claude.core.config.load_config", return_value=mock_cfg),
            patch(
                "kctl_claude.core.config.get_service_config",
                return_value={"config_dir": "/test", "backup_dir": "/backup"},
            ),
        ):
            result = load_claude_config()
        assert result.config_dir == "/test"
        assert result.backup_dir == "/backup"

    def test_load_with_explicit_profile(self) -> None:
        mock_cfg = MagicMock()
        mock_cfg.default_profile = "default"
        with (
            patch("kctl_claude.core.config.load_config", return_value=mock_cfg),
            patch(
                "kctl_claude.core.config.get_service_config",
                return_value={"config_dir": "/work", "backup_dir": ""},
            ) as mock_get,
        ):
            result = load_claude_config(profile="work")
        mock_get.assert_called_once_with("work", SERVICE_KEY)
        assert result.config_dir == "/work"

    def test_load_empty_service_data(self) -> None:
        mock_cfg = MagicMock()
        mock_cfg.default_profile = "default"
        with (
            patch("kctl_claude.core.config.load_config", return_value=mock_cfg),
            patch("kctl_claude.core.config.get_service_config", return_value={}),
        ):
            result = load_claude_config()
        assert result.config_dir == ""
        assert result.backup_dir == ""
