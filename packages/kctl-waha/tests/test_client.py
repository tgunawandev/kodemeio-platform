"""Tests for kctl-waha client module."""

import pytest
from kctl_common.exceptions import ConfigError, AuthenticationError
from kctl_waha.core.client import WahaClient, BridgeClient


class TestWahaClientConstruction:
    def test_requires_base_url(self):
        with pytest.raises(ConfigError):
            WahaClient(base_url="", api_key="test-key")

    def test_requires_api_key(self):
        with pytest.raises(AuthenticationError):
            WahaClient(base_url="https://waha.example.com", api_key="")

    def test_auth_header_uses_x_api_key(self):
        client = WahaClient(base_url="https://waha.example.com", api_key="test-key")
        headers = client._build_auth_header()
        assert "X-Api-Key" in headers
        assert headers["X-Api-Key"] == "test-key"
        client.close()

    def test_no_auth_prefix(self):
        """WahaClient should use empty AUTH_PREFIX (raw key, no 'Bearer')."""
        client = WahaClient(base_url="https://waha.example.com", api_key="mykey")
        headers = client._build_auth_header()
        assert headers["X-Api-Key"] == "mykey"  # no "Bearer " prefix
        client.close()

    def test_api_prefix(self):
        client = WahaClient(base_url="https://waha.example.com", api_key="k")
        assert "/api" in client._base_url
        client.close()


class TestBridgeClientConstruction:
    def test_creates_without_auth(self):
        client = BridgeClient(base_url="http://localhost:3050")
        assert client._base_url == "http://localhost:3050"
        client.close()

    def test_context_manager(self):
        with BridgeClient(base_url="http://localhost:3050") as client:
            assert client._base_url == "http://localhost:3050"
