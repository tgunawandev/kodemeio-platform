"""Tests for config module."""

from __future__ import annotations

import os
from unittest.mock import patch

from kctl_sentry.core.config import ServiceConfig, resolve_connection


class TestServiceConfig:
    def test_defaults(self) -> None:
        cfg = ServiceConfig()
        assert cfg.url == "https://sentry.io"
        assert cfg.auth_token == ""
        assert cfg.organization == ""
        assert cfg.default_project == ""

    def test_custom_values(self) -> None:
        cfg = ServiceConfig(
            url="https://sentry.kodeme.io",
            auth_token="abc123",
            organization="kodemeio",
            default_project="web",
        )
        assert cfg.url == "https://sentry.kodeme.io"
        assert cfg.auth_token == "abc123"
        assert cfg.organization == "kodemeio"
        assert cfg.default_project == "web"


class TestResolveConnection:
    @patch("kctl_sentry.core.config.get_service_config")
    @patch("kctl_sentry.core.config.resolve_active_profile_name", return_value="default")
    def test_env_override_sentry_native(self, _mock_profile, mock_config) -> None:  # type: ignore[no-untyped-def]
        mock_config.return_value = ServiceConfig()
        with patch.dict(os.environ, {"SENTRY_AUTH_TOKEN": "env-token", "SENTRY_ORG": "env-org"}):
            url, token, org, proj = resolve_connection()
        assert token == "env-token"
        assert org == "env-org"

    @patch("kctl_sentry.core.config.get_service_config")
    @patch("kctl_sentry.core.config.resolve_active_profile_name", return_value="default")
    def test_kctl_env_overrides_native(self, _mock_profile, mock_config) -> None:  # type: ignore[no-untyped-def]
        mock_config.return_value = ServiceConfig()
        with patch.dict(
            os.environ,
            {
                "SENTRY_AUTH_TOKEN": "native",
                "KCTL_SENTRY_AUTH_TOKEN": "kctl-token",
                "KCTL_SENTRY_ORGANIZATION": "kctl-org",
            },
        ):
            url, token, org, proj = resolve_connection()
        assert token == "kctl-token"
        assert org == "kctl-org"

    @patch("kctl_sentry.core.config.get_service_config")
    @patch("kctl_sentry.core.config.resolve_active_profile_name", return_value="default")
    def test_cli_flag_overrides_all(self, _mock_profile, mock_config) -> None:  # type: ignore[no-untyped-def]
        mock_config.return_value = ServiceConfig(auth_token="profile-token")
        with patch.dict(os.environ, {"KCTL_SENTRY_AUTH_TOKEN": "env-token"}):
            url, token, org, proj = resolve_connection(auth_token_override="flag-token")
        assert token == "flag-token"
