"""Tests for SentryClient."""

from __future__ import annotations

import pytest
from kctl_common.exceptions import AuthenticationError

from kctl_sentry.core.client import SentryClient


class TestSentryClientInit:
    def test_missing_token_raises(self) -> None:
        with pytest.raises(AuthenticationError, match="No auth token"):
            SentryClient(auth_token="", organization="test-org")

    def test_valid_init(self) -> None:
        client = SentryClient(
            base_url="https://sentry.example.com",
            auth_token="sntrys_test_token_123",
            organization="kodemeio",
            default_project="web-app",
        )
        assert client.organization == "kodemeio"
        assert client.default_project == "web-app"
        client.close()

    def test_default_base_url(self) -> None:
        client = SentryClient(
            auth_token="sntrys_test_token_123",
            organization="kodemeio",
        )
        assert "sentry.io" in client._base_url
        client.close()

    def test_resolve_project_explicit(self) -> None:
        client = SentryClient(
            auth_token="sntrys_test_token_123",
            organization="kodemeio",
            default_project="fallback",
        )
        assert client.resolve_project("explicit") == "explicit"
        client.close()

    def test_resolve_project_default(self) -> None:
        client = SentryClient(
            auth_token="sntrys_test_token_123",
            organization="kodemeio",
            default_project="fallback",
        )
        assert client.resolve_project(None) == "fallback"
        client.close()

    def test_resolve_project_none_raises(self) -> None:
        client = SentryClient(
            auth_token="sntrys_test_token_123",
            organization="kodemeio",
            default_project="",
        )
        with pytest.raises(AuthenticationError, match="No project specified"):
            client.resolve_project(None)
        client.close()
