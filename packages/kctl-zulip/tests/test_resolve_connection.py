"""Test resolve_connection logic."""

from __future__ import annotations

from unittest.mock import patch

from kctl_zulip.core.config import ServiceConfig, resolve_connection


def test_cli_flags_override_env_vars():
    """CLI flag overrides should take highest priority."""
    with (
        patch(
            "kctl_zulip.core.config.get_service_config",
            return_value=ServiceConfig(
                url="https://config.test",
                email="config@test.io",
                api_key="config-key",
            ),
        ),
        patch.dict(
            "os.environ",
            {
                "KCTL_ZULIP_URL": "https://env.test",
                "KCTL_ZULIP_EMAIL": "env@test.io",
                "KCTL_ZULIP_API_KEY": "env-key",
            },
        ),
    ):
        url, email, api_key = resolve_connection(
            profile_name="default",
            url_override="https://flag.test",
            email_override="flag@test.io",
            api_key_override="flag-key",
        )
    assert url == "https://flag.test"
    assert email == "flag@test.io"
    assert api_key == "flag-key"


def test_env_vars_override_config():
    """Env vars should override config file values."""
    with (
        patch(
            "kctl_zulip.core.config.get_service_config",
            return_value=ServiceConfig(
                url="https://config.test",
                email="config@test.io",
                api_key="config-key",
            ),
        ),
        patch.dict(
            "os.environ",
            {
                "KCTL_ZULIP_URL": "https://env.test",
                "KCTL_ZULIP_EMAIL": "env@test.io",
                "KCTL_ZULIP_API_KEY": "env-key",
            },
        ),
    ):
        url, email, api_key = resolve_connection(profile_name="default")
    assert url == "https://env.test"
    assert email == "env@test.io"
    assert api_key == "env-key"


def test_empty_config_returns_empty():
    """Empty config with no env vars should return empty strings."""
    with (
        patch("kctl_zulip.core.config.get_service_config", return_value=ServiceConfig()),
        patch.dict("os.environ", {}, clear=True),
    ):
        url, email, api_key = resolve_connection(profile_name="default")
    assert url == ""
    assert email == ""
    assert api_key == ""
