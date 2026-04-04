"""Test config resolution logic."""

import pytest

from kctl_mailcow.core.config import SERVICE_KEY, resolve_active_profile_name, resolve_connection


class TestServiceKey:
    def test_service_key_is_mailcow(self) -> None:
        assert SERVICE_KEY == "mailcow"


class TestResolveActiveProfile:
    def test_explicit_profile_wins(self) -> None:
        assert resolve_active_profile_name("staging") == "staging"

    def test_env_var_used(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("KCTL_MAILCOW_PROFILE", "from-env")
        assert resolve_active_profile_name() == "from-env"


class TestResolveConnection:
    def test_cli_flags_override_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("KCTL_MAILCOW_URL", "https://env.example.com")
        monkeypatch.setenv("KCTL_MAILCOW_API_KEY", "env-key")
        url, key = resolve_connection(
            url_override="https://flag.example.com",
            api_key_override="flag-key",
        )
        assert url == "https://flag.example.com"
        assert key == "flag-key"

    def test_env_vars_used(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("KCTL_MAILCOW_URL", "https://env.example.com")
        monkeypatch.setenv("KCTL_MAILCOW_API_KEY", "env-key")
        url, key = resolve_connection()
        assert url == "https://env.example.com"
        assert key == "env-key"
