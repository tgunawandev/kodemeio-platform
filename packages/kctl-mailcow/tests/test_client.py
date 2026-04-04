"""Test MailcowClient construction and auth header."""

import pytest
from kctl_lib.exceptions import ConfigError

from kctl_mailcow.core.client import MailcowClient


class TestClientConstruction:
    def test_requires_base_url(self) -> None:
        with pytest.raises(ConfigError, match="No API URL configured"):
            MailcowClient(base_url="", credential="test-key")

    def test_requires_credential(self) -> None:
        with pytest.raises(ConfigError, match="credential is required"):
            MailcowClient(base_url="https://mail.example.com", credential="")

    def test_auth_header_uses_x_api_key(self) -> None:
        client = MailcowClient(base_url="https://mail.example.com", credential="my-key")
        headers = client._build_auth_header()
        assert headers == {"X-API-Key": "my-key"}
        client.close()

    def test_api_prefix_appended(self) -> None:
        client = MailcowClient(base_url="https://mail.example.com", credential="my-key")
        assert client._base_url.endswith("/api/v1")
        client.close()

    def test_api_prefix_not_doubled(self) -> None:
        client = MailcowClient(base_url="https://mail.example.com/api/v1", credential="my-key")
        assert client._base_url.endswith("/api/v1")
        assert "/api/v1/api/v1" not in client._base_url
        client.close()

    def test_context_manager(self) -> None:
        with MailcowClient(base_url="https://mail.example.com", credential="key") as client:
            assert client._base_url.endswith("/api/v1")
