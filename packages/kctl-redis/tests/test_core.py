"""Tests for kctl-redis core modules."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from kctl_redis.core.config import SERVICE_KEY, ServiceConfig, resolve_connection
from kctl_redis.core.client import RedisClient
from kctl_redis.core.exceptions import KctlConnectionError


class TestServiceConfig:
    def test_defaults(self):
        cfg = ServiceConfig()
        assert cfg.host == ""
        assert cfg.port == 6379
        assert cfg.password == ""
        assert cfg.username == "default"
        assert cfg.db == 0
        assert cfg.ssh_host == ""
        assert cfg.ssh_port == 22
        assert cfg.ssh_user == "root"
        assert cfg.ssh_key == "~/.ssh/id_ed25519"

    def test_custom_values(self):
        cfg = ServiceConfig(host="10.0.0.5", port=6380, password="secret", username="app", db=2)
        assert cfg.host == "10.0.0.5"
        assert cfg.port == 6380
        assert cfg.password == "secret"
        assert cfg.username == "app"
        assert cfg.db == 2

    def test_service_key(self):
        assert SERVICE_KEY == "redis"


class TestResolveConnection:
    @patch("kctl_redis.core.config.resolve_active_profile_name", return_value="default")
    @patch("kctl_redis.core.config.get_service_config")
    def test_cli_overrides_take_priority(self, mock_get_svc, mock_profile):
        mock_get_svc.return_value = ServiceConfig(host="10.0.0.1", port=6379, ssh_host="jump.example.com")
        cfg = resolve_connection(
            profile_name="default",
            host_override="10.0.0.99",
            port_override=6380,
        )
        assert cfg.host == "10.0.0.99"
        assert cfg.port == 6380

    @patch.dict("os.environ", {"KCTL_REDIS_HOST": "10.0.0.50"})
    @patch("kctl_redis.core.config.resolve_active_profile_name", return_value="default")
    @patch("kctl_redis.core.config.get_service_config")
    def test_env_vars_override_profile(self, mock_get_svc, mock_profile):
        mock_get_svc.return_value = ServiceConfig(host="10.0.0.1", ssh_host="jump.example.com")
        cfg = resolve_connection(profile_name="default")
        assert cfg.host == "10.0.0.50"


class TestRedisClient:
    def test_requires_host(self):
        cfg = ServiceConfig(ssh_host="jump.example.com")
        with pytest.raises(KctlConnectionError):
            RedisClient(config=cfg)

    def test_requires_ssh_host(self):
        cfg = ServiceConfig(host="10.0.0.5")
        with pytest.raises(KctlConnectionError):
            RedisClient(config=cfg)

    def test_valid_config_creates_client(self):
        cfg = ServiceConfig(host="10.0.0.5", ssh_host="jump.example.com", password="secret")
        client = RedisClient(config=cfg)
        assert client._config == cfg
        assert client._tunnel is None
        assert client._redis is None
