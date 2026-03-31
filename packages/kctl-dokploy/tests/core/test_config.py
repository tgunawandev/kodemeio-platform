"""Tests for profile configuration management."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from kctl_dokploy.core.config import (
    ServiceConfig,
    _expand_key,
    get_service_config,
    load_config,
    resolve_active_profile_name,
    resolve_connection,
    set_service_config,
)


@pytest.fixture
def tmp_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a temporary config file and point the module to it."""
    config_file = tmp_path / "config.yaml"
    # Patch at kctl_lib.config level since that's where the actual logic lives
    monkeypatch.setattr("kctl_lib.config.CONFIG_DIR", tmp_path)
    monkeypatch.setattr("kctl_lib.config.CONFIG_FILE", config_file)
    return config_file


class TestLoadConfig:
    def test_returns_default_when_no_file(self, tmp_config: Path) -> None:
        cfg = load_config()
        assert cfg.default_profile == "default"
        assert cfg.profiles == {}

    def test_loads_valid_config(self, tmp_config: Path) -> None:
        tmp_config.write_text(
            yaml.dump(
                {
                    "default_profile": "prod",
                    "profiles": {"prod": {"dokploy": {"url": "https://test.io", "api_key": "key123"}}},
                }
            )
        )
        cfg = load_config()
        assert cfg.default_profile == "prod"
        assert "prod" in cfg.profiles


class TestServiceConfig:
    def test_get_service_scoped(self, tmp_config: Path) -> None:
        tmp_config.write_text(
            yaml.dump({"profiles": {"prod": {"dokploy": {"url": "https://prod.io", "api_key": "pk"}}}})
        )
        svc = get_service_config("prod")
        assert svc.url == "https://prod.io"
        assert svc.api_key == "pk"

    def test_get_flat_format(self, tmp_config: Path) -> None:
        tmp_config.write_text(yaml.dump({"profiles": {"old": {"url": "https://old.io", "api_key": "ok"}}}))
        svc = get_service_config("old")
        assert svc.url == "https://old.io"

    def test_missing_profile_returns_empty(self, tmp_config: Path) -> None:
        tmp_config.write_text(yaml.dump({"profiles": {}}))
        svc = get_service_config("nonexistent")
        assert svc.url == ""


class TestSetServiceConfig:
    def test_creates_scoped_profile(self, tmp_config: Path) -> None:
        svc = ServiceConfig(url="https://new.io", api_key="newkey")
        set_service_config("test", svc)
        data = yaml.safe_load(tmp_config.read_text())
        assert data["profiles"]["test"]["dokploy"]["url"] == "https://new.io"


class TestExpandKey:
    def test_expands_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MY_KEY", "secret123")
        assert _expand_key("${MY_KEY}") == "secret123"

    def test_returns_literal_if_not_env_ref(self) -> None:
        assert _expand_key("plain-key") == "plain-key"

    def test_returns_original_for_missing_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("NONEXISTENT_VAR", raising=False)
        # kctl-lib's expand_env keeps the ${VAR} reference if not found
        result = _expand_key("${NONEXISTENT_VAR}")
        assert result in ("", "${NONEXISTENT_VAR}")


class TestResolveActiveProfileName:
    def test_cli_flag_wins(self) -> None:
        assert resolve_active_profile_name("cli-profile") == "cli-profile"

    def test_env_var_fallback(self, monkeypatch: pytest.MonkeyPatch, tmp_config: Path) -> None:
        monkeypatch.setenv("KCTL_DOKPLOY_PROFILE", "env-profile")
        assert resolve_active_profile_name(None) == "env-profile"


class TestResolveConnection:
    def test_cli_flags_override_all(self, tmp_config: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        tmp_config.write_text(
            yaml.dump({"profiles": {"default": {"dokploy": {"url": "https://config.io", "api_key": "cfg"}}}})
        )
        monkeypatch.setenv("KCTL_DOKPLOY_URL", "https://env.io")
        url, key = resolve_connection(url_override="https://cli.io", api_key_override="cli-key")
        assert url == "https://cli.io"
        assert key == "cli-key"

    def test_env_vars_override_config(self, tmp_config: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        tmp_config.write_text(
            yaml.dump({"profiles": {"default": {"dokploy": {"url": "https://config.io", "api_key": "cfg"}}}})
        )
        monkeypatch.setenv("KCTL_DOKPLOY_URL", "https://env.io")
        monkeypatch.setenv("KCTL_DOKPLOY_API_KEY", "env-key")
        url, key = resolve_connection()
        assert url == "https://env.io"
        assert key == "env-key"

    def test_legacy_env_vars(self, tmp_config: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DOKPLOY_API_URL", "https://legacy.io")
        monkeypatch.setenv("DOKPLOY_API_KEY", "legacy-key")
        # Clear KCTL vars
        monkeypatch.delenv("KCTL_DOKPLOY_URL", raising=False)
        monkeypatch.delenv("KCTL_DOKPLOY_API_KEY", raising=False)
        url, key = resolve_connection()
        assert url == "https://legacy.io"
        assert key == "legacy-key"
