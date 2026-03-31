"""Tests for kctl_lib.config."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from kctl_lib.config import (
    ConfigFile,
    expand_env,
    get_default_profile,
    get_profile_names,
    get_service_config,
    is_service_scoped,
    load_raw_config,
    remove_profile,
    resolve_active_profile_name,
    save_raw_config,
    set_default_profile,
    set_service_config,
)


class TestExpandEnv:
    def test_expands_env_var(self, monkeypatch: Any) -> None:
        monkeypatch.setenv("MY_SECRET", "s3cr3t")
        assert expand_env("key=${MY_SECRET}") == "key=s3cr3t"

    def test_missing_env_var_kept(self) -> None:
        assert expand_env("${NONEXISTENT_VAR_12345}") == "${NONEXISTENT_VAR_12345}"

    def test_no_vars(self) -> None:
        assert expand_env("plain") == "plain"


class TestIsServiceScoped:
    def test_flat_profile(self) -> None:
        assert is_service_scoped({"url": "https://example.com"}) is False

    def test_scoped_profile(self) -> None:
        assert is_service_scoped({"next": {"project_root": "/path"}}) is True


class TestConfigFile:
    def test_defaults(self) -> None:
        cfg = ConfigFile()
        assert cfg.default_profile == "default"
        assert cfg.profiles == {}


class TestLoadSave:
    def test_roundtrip(self, tmp_path: Path, monkeypatch: Any) -> None:
        config_file = tmp_path / "config.yaml"
        monkeypatch.setattr("kctl_lib.config.CONFIG_FILE", config_file)
        monkeypatch.setattr("kctl_lib.config.CONFIG_DIR", tmp_path)
        data = {"default_profile": "prod", "profiles": {"prod": {"next": {"project_root": "/p"}}}}
        save_raw_config(data)
        loaded = load_raw_config()
        assert loaded["default_profile"] == "prod"

    def test_load_missing_file(self, tmp_path: Path, monkeypatch: Any) -> None:
        config_file = tmp_path / "nonexistent.yaml"
        monkeypatch.setattr("kctl_lib.config.CONFIG_FILE", config_file)
        assert load_raw_config() == {}


class TestServiceConfig:
    def test_get_scoped(self, tmp_path: Path, monkeypatch: Any) -> None:
        config_file = tmp_path / "config.yaml"
        monkeypatch.setattr("kctl_lib.config.CONFIG_FILE", config_file)
        monkeypatch.setattr("kctl_lib.config.CONFIG_DIR", tmp_path)
        data = {"default_profile": "default", "profiles": {"default": {"next": {"project_root": "/my/path"}}}}
        save_raw_config(data)
        result = get_service_config("default", "next", ["project_root"])
        assert result["project_root"] == "/my/path"

    def test_get_flat_fallback(self, tmp_path: Path, monkeypatch: Any) -> None:
        config_file = tmp_path / "config.yaml"
        monkeypatch.setattr("kctl_lib.config.CONFIG_FILE", config_file)
        monkeypatch.setattr("kctl_lib.config.CONFIG_DIR", tmp_path)
        data = {"default_profile": "default", "profiles": {"default": {"project_root": "/flat/path"}}}
        save_raw_config(data)
        result = get_service_config("default", "next", ["project_root"])
        assert result["project_root"] == "/flat/path"

    def test_get_empty_profile(self, tmp_path: Path, monkeypatch: Any) -> None:
        config_file = tmp_path / "config.yaml"
        monkeypatch.setattr("kctl_lib.config.CONFIG_FILE", config_file)
        monkeypatch.setattr("kctl_lib.config.CONFIG_DIR", tmp_path)
        data = {"default_profile": "default", "profiles": {}}
        save_raw_config(data)
        result = get_service_config("nonexistent", "next")
        assert result == {}


class TestSetServiceConfig:
    def test_set_creates_scoped(self, tmp_path: Path, monkeypatch: Any) -> None:
        config_file = tmp_path / "config.yaml"
        monkeypatch.setattr("kctl_lib.config.CONFIG_FILE", config_file)
        monkeypatch.setattr("kctl_lib.config.CONFIG_DIR", tmp_path)
        set_service_config("default", "next", {"project_root": "/new/path"})
        result = get_service_config("default", "next", ["project_root"])
        assert result["project_root"] == "/new/path"

    def test_set_migrates_flat_to_scoped(self, tmp_path: Path, monkeypatch: Any) -> None:
        config_file = tmp_path / "config.yaml"
        monkeypatch.setattr("kctl_lib.config.CONFIG_FILE", config_file)
        monkeypatch.setattr("kctl_lib.config.CONFIG_DIR", tmp_path)
        data = {"default_profile": "default", "profiles": {"default": {"project_root": "/old"}}}
        save_raw_config(data)
        set_service_config("default", "next", {"project_root": "/new"})
        raw = load_raw_config()
        assert isinstance(raw["profiles"]["default"]["next"], dict)


class TestResolveProfile:
    def test_explicit_wins(self) -> None:
        assert resolve_active_profile_name("staging", "KCTL_TEST") == "staging"

    def test_env_var(self, monkeypatch: Any) -> None:
        monkeypatch.setenv("KCTL_TEST_PROFILE", "prod")
        assert resolve_active_profile_name(None, "KCTL_TEST") == "prod"


class TestProfileCRUD:
    def test_get_profile_names(self, tmp_path: Path, monkeypatch: Any) -> None:
        config_file = tmp_path / "config.yaml"
        monkeypatch.setattr("kctl_lib.config.CONFIG_FILE", config_file)
        monkeypatch.setattr("kctl_lib.config.CONFIG_DIR", tmp_path)
        data = {"default_profile": "a", "profiles": {"a": {}, "b": {}}}
        save_raw_config(data)
        assert set(get_profile_names()) == {"a", "b"}

    def test_remove_profile(self, tmp_path: Path, monkeypatch: Any) -> None:
        config_file = tmp_path / "config.yaml"
        monkeypatch.setattr("kctl_lib.config.CONFIG_FILE", config_file)
        monkeypatch.setattr("kctl_lib.config.CONFIG_DIR", tmp_path)
        data = {"default_profile": "a", "profiles": {"a": {}, "b": {}}}
        save_raw_config(data)
        remove_profile("a")
        assert "a" not in get_profile_names()

    def test_set_default_profile(self, tmp_path: Path, monkeypatch: Any) -> None:
        config_file = tmp_path / "config.yaml"
        monkeypatch.setattr("kctl_lib.config.CONFIG_FILE", config_file)
        monkeypatch.setattr("kctl_lib.config.CONFIG_DIR", tmp_path)
        data = {"default_profile": "a", "profiles": {"a": {}, "b": {}}}
        save_raw_config(data)
        set_default_profile("b")
        assert get_default_profile() == "b"
