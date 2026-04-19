"""Tests for kctl-glitchtip core modules.

Covers: SERVICE_KEY, ServiceConfig, exception re-exports, GlitchTipClient
initialization, AppContext lazy-init, and resolve_connection priority logic.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import httpx
import pytest

from kctl_glitchtip import __version__
from kctl_glitchtip.core.client import GlitchTipClient
from kctl_glitchtip.core.config import (
    ENV_PREFIX,
    SERVICE_KEY,
    ServiceConfig,
    resolve_connection,
)
from kctl_glitchtip.core.exceptions import (
    APIError,
    AuthenticationError,
    CommandError,
    ConfigError,
    ConnectionError,
    KctlError,
    NotFoundError,
)

# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------


class TestVersion:
    def test_version_is_string(self) -> None:
        assert isinstance(__version__, str)

    def test_version_not_empty(self) -> None:
        assert __version__ != ""

    def test_version_semver_format(self) -> None:
        parts = __version__.split(".")
        assert len(parts) == 3, f"Expected semver X.Y.Z, got {__version__!r}"
        for part in parts:
            assert part.isdigit(), f"Non-numeric version part: {part!r}"


# ---------------------------------------------------------------------------
# Config constants
# ---------------------------------------------------------------------------


class TestConfigConstants:
    def test_service_key_is_glitchtip(self) -> None:
        assert SERVICE_KEY == "glitchtip"

    def test_env_prefix_is_kctl_glitchtip(self) -> None:
        assert ENV_PREFIX == "KCTL_GLITCHTIP"

    def test_service_config_default_url_is_empty(self) -> None:
        svc = ServiceConfig()
        assert svc.url == ""

    def test_service_config_default_token_is_empty(self) -> None:
        svc = ServiceConfig()
        assert svc.token == ""

    def test_service_config_accepts_values(self) -> None:
        svc = ServiceConfig(url="https://glitchtip.example.com", token="abc123")
        assert svc.url == "https://glitchtip.example.com"
        assert svc.token == "abc123"


# ---------------------------------------------------------------------------
# Exception re-exports
# ---------------------------------------------------------------------------


class TestExceptionReExports:
    """All exceptions are re-exported and form the correct hierarchy."""

    def test_kctl_error_is_base(self) -> None:
        assert issubclass(ConfigError, KctlError)
        assert issubclass(AuthenticationError, KctlError)
        assert issubclass(APIError, KctlError)
        assert issubclass(NotFoundError, KctlError)
        assert issubclass(CommandError, KctlError)
        assert issubclass(ConnectionError, KctlError)

    def test_config_error_can_be_raised(self) -> None:
        with pytest.raises(ConfigError, match="missing"):
            raise ConfigError("missing url")

    def test_authentication_error_can_be_raised(self) -> None:
        with pytest.raises(AuthenticationError, match="invalid token"):
            raise AuthenticationError("invalid token")

    def test_api_error_can_be_raised(self) -> None:
        with pytest.raises(APIError):
            raise APIError("upstream error")

    def test_not_found_error_can_be_raised(self) -> None:
        with pytest.raises(NotFoundError):
            raise NotFoundError("project", "my-project")


# ---------------------------------------------------------------------------
# GlitchTipClient initialization
# ---------------------------------------------------------------------------


class TestGlitchTipClientInit:
    def test_missing_url_raises_config_error(self) -> None:
        with pytest.raises(ConfigError, match="No API URL configured"):
            GlitchTipClient(base_url="", token="some-token")

    def test_missing_token_raises_authentication_error(self) -> None:
        with pytest.raises(AuthenticationError, match="No API token configured"):
            GlitchTipClient(base_url="https://glitchtip.kodeme.io", token="")

    def test_valid_init_succeeds(self) -> None:
        client = GlitchTipClient(
            base_url="https://glitchtip.kodeme.io",
            token="test-token-123",
        )
        assert client is not None

    def test_original_base_url_stripped_of_trailing_slash(self) -> None:
        client = GlitchTipClient(
            base_url="https://glitchtip.kodeme.io/",
            token="test-token",
        )
        assert client._original_base_url == "https://glitchtip.kodeme.io"

    def test_original_base_url_without_trailing_slash(self) -> None:
        client = GlitchTipClient(
            base_url="https://glitchtip.kodeme.io",
            token="test-token",
        )
        assert client._original_base_url == "https://glitchtip.kodeme.io"

    def test_auth_header_constant(self) -> None:
        assert GlitchTipClient.AUTH_HEADER == "Authorization"

    def test_auth_prefix_constant(self) -> None:
        assert GlitchTipClient.AUTH_PREFIX == "Bearer"

    def test_api_prefix_constant(self) -> None:
        assert GlitchTipClient.API_PREFIX == "/api/0"


# ---------------------------------------------------------------------------
# GlitchTipClient.check_health
# ---------------------------------------------------------------------------


class TestGlitchTipClientHealth:
    @patch("kctl_glitchtip.core.client.httpx.get")
    def test_check_health_returns_200_on_success(self, mock_get: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        client = GlitchTipClient(base_url="https://glitchtip.kodeme.io", token="tok")
        status = client.check_health()

        assert status == 200
        mock_get.assert_called_once_with("https://glitchtip.kodeme.io/_health/", timeout=5)

    @patch("kctl_glitchtip.core.client.httpx.get")
    def test_check_health_returns_0_on_connection_error(self, mock_get: MagicMock) -> None:
        mock_get.side_effect = httpx.ConnectError("Connection refused")

        client = GlitchTipClient(base_url="https://glitchtip.kodeme.io", token="tok")
        status = client.check_health()

        assert status == 0

    @patch("kctl_glitchtip.core.client.httpx.get")
    def test_check_health_returns_0_on_timeout(self, mock_get: MagicMock) -> None:
        mock_get.side_effect = httpx.TimeoutException("timed out")

        client = GlitchTipClient(base_url="https://glitchtip.kodeme.io", token="tok")
        status = client.check_health()

        assert status == 0

    @patch("kctl_glitchtip.core.client.httpx.get")
    def test_check_health_returns_503_on_server_error(self, mock_get: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_get.return_value = mock_response

        client = GlitchTipClient(base_url="https://glitchtip.kodeme.io", token="tok")
        status = client.check_health()

        assert status == 503


# ---------------------------------------------------------------------------
# GlitchTipClient.get_list and get_all
# ---------------------------------------------------------------------------


class TestGlitchTipClientHelpers:
    def _make_client(self) -> GlitchTipClient:
        return GlitchTipClient(base_url="https://glitchtip.kodeme.io", token="tok")

    def test_get_list_returns_list_response_as_is(self) -> None:
        client = self._make_client()
        with patch.object(client, "get", return_value=[{"id": 1}, {"id": 2}]):
            result = client.get_list("/projects/")
        assert result == [{"id": 1}, {"id": 2}]

    def test_get_list_unwraps_paginated_dict(self) -> None:
        client = self._make_client()
        payload = {"results": [{"id": 1}], "count": 1}
        with patch.object(client, "get", return_value=payload):
            result = client.get_list("/projects/")
        assert result == [{"id": 1}]

    def test_get_list_returns_empty_list_on_unexpected_response(self) -> None:
        client = self._make_client()
        with patch.object(client, "get", return_value={"unexpected": "data"}):
            result = client.get_list("/projects/")
        assert result == []

    def test_get_all_returns_list_directly(self) -> None:
        client = self._make_client()
        with patch.object(client, "get", return_value=[{"id": 1}]):
            result = client.get_all("/issues/")
        assert result == [{"id": 1}]

    def test_get_all_unwraps_paginated_results(self) -> None:
        client = self._make_client()
        payload = {"results": [{"id": 1}, {"id": 2}], "count": 2}
        with patch.object(client, "get", return_value=payload):
            result = client.get_all("/issues/")
        assert result == [{"id": 1}, {"id": 2}]

    def test_get_all_returns_empty_list_on_unexpected_response(self) -> None:
        client = self._make_client()
        with patch.object(client, "get", return_value={}):
            result = client.get_all("/issues/")
        assert result == []


# ---------------------------------------------------------------------------
# resolve_connection priority logic
# ---------------------------------------------------------------------------


class TestResolveConnection:
    """Verify that the 4-level priority works correctly."""

    def test_cli_flags_take_highest_priority(self) -> None:
        with patch.dict(
            os.environ,
            {
                "KCTL_GLITCHTIP_PROFILE": "default",  # Stage B: explicit profile required
                "KCTL_GLITCHTIP_URL": "https://env.example.com",
                "KCTL_GLITCHTIP_TOKEN": "env-token",
            },
        ):
            url, token = resolve_connection(
                url_override="https://cli.example.com",
                token_override="cli-token",
            )
        assert url == "https://cli.example.com"
        assert token == "cli-token"

    def test_kctl_env_vars_override_glitchtip_env_vars(self) -> None:
        with patch.dict(
            os.environ,
            {
                "KCTL_GLITCHTIP_PROFILE": "default",  # Stage B: explicit profile required
                "GLITCHTIP_API_URL": "https://gt-env.example.com",
                "GLITCHTIP_API_TOKEN": "gt-env-token",
                "KCTL_GLITCHTIP_URL": "https://kctl-env.example.com",
                "KCTL_GLITCHTIP_TOKEN": "kctl-env-token",
            },
        ):
            url, token = resolve_connection()
        assert url == "https://kctl-env.example.com"
        assert token == "kctl-env-token"

    def test_glitchtip_env_vars_used_when_no_kctl_env(self) -> None:
        env = {
            "GLITCHTIP_API_URL": "https://gt-env.example.com",
            "GLITCHTIP_API_TOKEN": "gt-env-token",
        }
        # Ensure KCTL vars are not set
        clean = {k: v for k, v in os.environ.items() if not k.startswith("KCTL_GLITCHTIP")}
        clean.update(env)
        # Also strip KCTL URL/TOKEN vars explicitly but keep PROFILE for Stage B
        for key in ("KCTL_GLITCHTIP_URL", "KCTL_GLITCHTIP_TOKEN"):
            clean.pop(key, None)
        clean["KCTL_GLITCHTIP_PROFILE"] = "default"  # Stage B: explicit profile required

        with patch.dict(os.environ, clean, clear=True):
            url, token = resolve_connection()
        assert url == "https://gt-env.example.com"
        assert token == "gt-env-token"

    def test_returns_empty_strings_when_no_config(self) -> None:
        # Stage B: kctl-lib no longer silently falls back to default_profile.
        # When no profile is specified (no CLI flag, no KCTL_GLITCHTIP_PROFILE env var),
        # resolve_connection raises ValueError instead of returning empty strings.
        clean_env = {k: v for k, v in os.environ.items() if not k.startswith(("KCTL_GLITCHTIP", "GLITCHTIP"))}
        with patch.dict(os.environ, clean_env, clear=True):
            with pytest.raises(ValueError, match="No profile specified"):
                resolve_connection()

    def test_cli_override_takes_precedence_over_env_vars(self) -> None:
        with patch.dict(
            os.environ,
            {
                "KCTL_GLITCHTIP_PROFILE": "default",  # Stage B: explicit profile required
                "GLITCHTIP_API_URL": "https://env.example.com",
            },
        ):
            url, _token = resolve_connection(url_override="https://override.example.com")
        assert url == "https://override.example.com"


# ---------------------------------------------------------------------------
# AppContext lazy initialization
# ---------------------------------------------------------------------------


class TestAppContext:
    def test_app_context_default_values(self) -> None:
        from kctl_glitchtip.core.callbacks import AppContext

        ctx = AppContext()
        assert ctx.quiet is False
        assert ctx.json_mode is False
        assert ctx.profile is None
        assert ctx.url_override is None
        assert ctx.token_override is None
        assert ctx._client is None

    def test_app_context_with_overrides(self) -> None:
        from kctl_glitchtip.core.callbacks import AppContext

        ctx = AppContext(
            quiet=True,
            json_mode=True,
            url_override="https://glitchtip.example.com",
            token_override="secret",
        )
        assert ctx.quiet is True
        assert ctx.json_mode is True
        assert ctx.url_override == "https://glitchtip.example.com"
        assert ctx.token_override == "secret"

    def test_client_property_uses_injected_client(self) -> None:
        from unittest.mock import MagicMock

        from kctl_glitchtip.core.callbacks import AppContext

        ctx = AppContext(quiet=True)
        fake_client = MagicMock(spec=GlitchTipClient)
        ctx._client = fake_client

        # Accessing .client should return the injected mock, not re-init
        assert ctx.client is fake_client

    def test_output_property_lazy_init(self) -> None:
        from kctl_lib.output import Output

        from kctl_glitchtip.core.callbacks import AppContext

        ctx = AppContext(quiet=True)
        assert ctx._output is None
        output = ctx.output
        assert isinstance(output, Output)
        # Second access returns the same instance
        assert ctx.output is output
