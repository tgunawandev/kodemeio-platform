"""Tests for configuration management."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from kctl_lib.config import ConfigFile, expand_env, is_service_scoped

from kctl_hz.core.config import (
    ServiceConfig,
    get_service_config,
    load_config,
    resolve_active_profile_name,
    resolve_connection,
    save_raw_config,
)


class TestServiceConfig:
    """ServiceConfig pydantic model."""

    def test_defaults(self) -> None:
        cfg = ServiceConfig()
        assert cfg.token == ""
        assert cfg.dns_token == ""
        assert cfg.default_location == "fsn1"
        assert cfg.default_image == "ubuntu-24.04"
        assert cfg.default_server_type == "cx22"

    def test_custom_values(self) -> None:
        cfg = ServiceConfig(token="abc", dns_token="xyz", default_location="nbg1")
        assert cfg.token == "abc"
        assert cfg.dns_token == "xyz"
        assert cfg.default_location == "nbg1"


class TestConfigFile:
    """ConfigFile pydantic model."""

    def test_defaults(self) -> None:
        cfg = ConfigFile()
        assert cfg.default_profile == "default"
        assert cfg.profiles == {}


class TestExpandEnv:
    """Environment variable expansion."""

    def test_expand_env_var(self) -> None:
        with patch.dict(os.environ, {"MY_TOKEN": "secret123"}):
            assert expand_env("${MY_TOKEN}") == "secret123"

    def test_expand_missing_env_var(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            # kctl-lib's expand_env keeps the ${VAR} reference when missing
            result = expand_env("${MISSING_VAR}")
            assert result == "${MISSING_VAR}"

    def test_plain_token_unchanged(self) -> None:
        assert expand_env("my-plain-token") == "my-plain-token"


class TestIsServiceScoped:
    """Profile format detection."""

    def test_flat_profile(self) -> None:
        assert is_service_scoped({"token": "abc", "dns_token": "xyz"}) is False

    def test_scoped_profile(self) -> None:
        assert is_service_scoped({"hetzner": {"token": "abc"}}) is True


class TestResolveActiveProfileName:
    """Profile name resolution chain."""

    def test_explicit_profile(self) -> None:
        assert resolve_active_profile_name("staging") == "staging"

    def test_env_var_profile(self) -> None:
        with patch.dict(os.environ, {"KCTL_HZ_PROFILE": "production"}):
            assert resolve_active_profile_name(None) == "production"

    def test_default_profile(self) -> None:
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("kctl_lib.config.get_default_profile", return_value="my-default"),
        ):
            assert resolve_active_profile_name(None) == "my-default"


class TestResolveConnection:
    """Token resolution priority chain."""

    def test_env_override(self) -> None:
        with (
            patch.dict(os.environ, {"HCLOUD_TOKEN": "env-cloud", "HETZNER_DNS_TOKEN": "env-dns"}),
            patch("kctl_hz.core.config.get_service_config", return_value=ServiceConfig()),
        ):
            token, dns = resolve_connection()
            assert token == "env-cloud"
            assert dns == "env-dns"

    def test_cli_override_wins(self) -> None:
        with (
            patch.dict(os.environ, {"HCLOUD_TOKEN": "env-cloud"}),
            patch("kctl_hz.core.config.get_service_config", return_value=ServiceConfig()),
        ):
            token, dns = resolve_connection(token_override="cli-token", dns_token_override="cli-dns")
            assert token == "cli-token"
            assert dns == "cli-dns"

    def test_kctl_env_override(self) -> None:
        with (
            patch.dict(os.environ, {"KCTL_HZ_TOKEN": "kctl-cloud", "KCTL_HZ_DNS_TOKEN": "kctl-dns"}),
            patch("kctl_hz.core.config.get_service_config", return_value=ServiceConfig()),
        ):
            token, dns = resolve_connection()
            assert token == "kctl-cloud"
            assert dns == "kctl-dns"


class TestLoadSaveConfig:
    """Config file round-trip."""

    def test_save_and_load(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.yaml"
        data = {
            "default_profile": "test",
            "profiles": {"test": {"hetzner": {"token": "abc"}}},
        }
        with (
            patch("kctl_lib.config.CONFIG_FILE", config_file),
            patch("kctl_lib.config.CONFIG_DIR", tmp_path),
        ):
            save_raw_config(data)
            cfg = load_config()
            assert cfg.default_profile == "test"
            assert "test" in cfg.profiles

    def test_load_missing_file(self, tmp_path: Path) -> None:
        config_file = tmp_path / "nonexistent.yaml"
        with patch("kctl_lib.config.CONFIG_FILE", config_file):
            cfg = load_config()
            assert cfg.default_profile == "default"
            assert cfg.profiles == {}


class TestGetServiceConfig:
    """Service config extraction from profiles."""

    def test_scoped_profile(self) -> None:
        with patch(
            "kctl_lib.config.load_config",
            return_value=ConfigFile(
                default_profile="prod",
                profiles={"prod": {"hetzner": {"token": "hcloud-token", "dns_token": "dns-token"}}},
            ),
        ):
            svc = get_service_config("prod")
            assert svc.token == "hcloud-token"
            assert svc.dns_token == "dns-token"

    def test_flat_profile(self) -> None:
        with patch(
            "kctl_lib.config.load_config",
            return_value=ConfigFile(
                default_profile="prod",
                profiles={"prod": {"token": "hcloud-token"}},
            ),
        ):
            svc = get_service_config("prod")
            assert svc.token == "hcloud-token"

    def test_missing_profile(self) -> None:
        with patch(
            "kctl_lib.config.load_config",
            return_value=ConfigFile(),
        ):
            svc = get_service_config("nonexistent")
            assert svc.token == ""
