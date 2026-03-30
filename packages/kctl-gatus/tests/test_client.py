"""Tests for kctl-gatus client module."""

import pytest
from kctl_common.exceptions import ConfigError
from kctl_gatus.core.client import GatusClient


class TestClientConstruction:
    def test_requires_base_url(self):
        with pytest.raises(ConfigError):
            GatusClient(base_url="")

    def test_no_auth_header_without_key(self):
        client = GatusClient(base_url="https://status.example.com")
        assert "Authorization" not in client._client.headers
        client.close()

    def test_auth_header_with_key(self):
        client = GatusClient(base_url="https://status.example.com", api_key="test-key")
        assert client._client.headers["Authorization"] == "Bearer test-key"
        client.close()

    def test_api_url_suffix(self):
        client = GatusClient(base_url="https://status.example.com")
        assert str(client._client.base_url).rstrip("/") == "https://status.example.com/api/v1"
        client.close()

    def test_base_url_property(self):
        client = GatusClient(base_url="https://status.example.com/")
        assert client.base_url == "https://status.example.com"
        client.close()

    def test_context_manager(self):
        with GatusClient(base_url="https://status.example.com") as client:
            assert client.base_url == "https://status.example.com"
