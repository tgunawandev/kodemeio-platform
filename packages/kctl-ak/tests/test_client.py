"""Tests for kctl-ak client module."""

import pytest
from kctl_lib.exceptions import ConfigError
from kctl_ak.core.client import AuthentikClient


class TestClientConstruction:
    def test_requires_base_url(self):
        with pytest.raises(ConfigError):
            AuthentikClient(base_url="", credential="test-key")

    def test_requires_credential(self):
        with pytest.raises(ConfigError):
            AuthentikClient(base_url="https://example.com", credential="")

    def test_auth_header(self):
        client = AuthentikClient(base_url="https://example.com", credential="test-key")
        headers = client._build_auth_header()
        assert headers["Authorization"] == "Bearer test-key"
        client.close()

    def test_api_prefix(self):
        client = AuthentikClient(base_url="https://example.com", credential="test-key")
        assert "/api/v3" in client._base_url
        client.close()

    def test_trailing_slash_added(self):
        client = AuthentikClient(base_url="https://example.com", credential="k")
        assert client._ensure_trailing_slash("users") == "users/"
        assert client._ensure_trailing_slash("/users") == "users/"
        assert client._ensure_trailing_slash("users?page=1") == "users?page=1"
        client.close()


class TestPatchMultipart:
    def test_method_exists(self) -> None:
        """patch_multipart is available on AuthentikClient."""
        assert hasattr(AuthentikClient, "patch_multipart")
