"""Core unit tests for kctl-rmm.

Tests service key, config resolution, RMMClient validation, AppContext,
and agent logic — without making any real HTTP calls.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestVersion:
    def test_version_string_is_set(self) -> None:
        from kctl_rmm import __version__

        assert isinstance(__version__, str)
        assert len(__version__) > 0

    def test_version_semver_format(self) -> None:
        from kctl_rmm import __version__

        parts = __version__.split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)


class TestServiceKey:
    def test_service_key_value(self) -> None:
        from kctl_rmm.core.config import SERVICE_KEY

        assert SERVICE_KEY == "rmm"

    def test_env_prefix_value(self) -> None:
        from kctl_rmm.core.config import ENV_PREFIX

        assert ENV_PREFIX == "KCTL_RMM"


class TestServiceConfig:
    def test_default_config_is_empty_strings(self) -> None:
        from kctl_rmm.core.config import ServiceConfig

        cfg = ServiceConfig()
        assert cfg.url == ""
        assert cfg.api_key == ""
        assert cfg.mesh_url == ""
        assert cfg.rustdesk_url == ""

    def test_config_accepts_values(self) -> None:
        from kctl_rmm.core.config import ServiceConfig

        cfg = ServiceConfig(
            url="https://rmm.kodeme.io",
            api_key="abc123",
            mesh_url="https://mesh.kodeme.io",
            rustdesk_url="https://rustdesk.kodeme.io",
        )
        assert cfg.url == "https://rmm.kodeme.io"
        assert cfg.api_key == "abc123"


class TestResolveConnection:
    def test_url_override_takes_priority(self) -> None:
        from kctl_rmm.core.config import resolve_connection

        with (
            patch("kctl_rmm.core.config._resolve_active_profile_name", return_value="default"),
            patch("kctl_rmm.core.config._get_service_config", return_value={}),
        ):
            url, _ = resolve_connection(url_override="https://override.example.com")
            assert url == "https://override.example.com"

    def test_api_key_override_takes_priority(self) -> None:
        from kctl_rmm.core.config import resolve_connection

        with (
            patch("kctl_rmm.core.config._resolve_active_profile_name", return_value="default"),
            patch("kctl_rmm.core.config._get_service_config", return_value={}),
        ):
            _, api_key = resolve_connection(api_key_override="overridekey")
            assert api_key == "overridekey"

    def test_env_var_url_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from kctl_rmm.core.config import resolve_connection

        monkeypatch.setenv("KCTL_RMM_URL", "https://env-rmm.example.com")
        with (
            patch("kctl_rmm.core.config._resolve_active_profile_name", return_value="default"),
            patch("kctl_rmm.core.config._get_service_config", return_value={}),
        ):
            url, _ = resolve_connection()
            assert url == "https://env-rmm.example.com"

    def test_env_var_api_key_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from kctl_rmm.core.config import resolve_connection

        monkeypatch.setenv("KCTL_RMM_API_KEY", "envkey123")
        with (
            patch("kctl_rmm.core.config._resolve_active_profile_name", return_value="default"),
            patch("kctl_rmm.core.config._get_service_config", return_value={}),
        ):
            _, api_key = resolve_connection()
            assert api_key == "envkey123"

    def test_cli_flag_beats_env_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from kctl_rmm.core.config import resolve_connection

        monkeypatch.setenv("KCTL_RMM_URL", "https://env-rmm.example.com")
        with (
            patch("kctl_rmm.core.config._resolve_active_profile_name", return_value="default"),
            patch("kctl_rmm.core.config._get_service_config", return_value={}),
        ):
            url, _ = resolve_connection(url_override="https://cli-rmm.example.com")
            assert url == "https://cli-rmm.example.com"

    def test_returns_tuple_of_two_strings(self) -> None:
        from kctl_rmm.core.config import resolve_connection

        with (
            patch("kctl_rmm.core.config._resolve_active_profile_name", return_value="default"),
            patch("kctl_rmm.core.config._get_service_config", return_value={}),
        ):
            result = resolve_connection()
            assert isinstance(result, tuple)
            assert len(result) == 2
            assert all(isinstance(v, str) for v in result)


class TestResolveMeshUrl:
    def test_returns_mesh_url_from_config(self) -> None:
        from kctl_rmm.core.config import resolve_mesh_url

        with (
            patch("kctl_rmm.core.config._resolve_active_profile_name", return_value="default"),
            patch("kctl_rmm.core.config._get_service_config", return_value={"mesh_url": "https://mesh.example.com"}),
        ):
            url = resolve_mesh_url()
            assert url == "https://mesh.example.com"

    def test_returns_empty_string_when_not_configured(self) -> None:
        from kctl_rmm.core.config import resolve_mesh_url

        with (
            patch("kctl_rmm.core.config._resolve_active_profile_name", return_value="default"),
            patch("kctl_rmm.core.config._get_service_config", return_value={}),
        ):
            url = resolve_mesh_url()
            assert url == ""


class TestResolveRustdeskUrl:
    def test_returns_rustdesk_url_from_config(self) -> None:
        from kctl_rmm.core.config import resolve_rustdesk_url

        with (
            patch("kctl_rmm.core.config._resolve_active_profile_name", return_value="default"),
            patch("kctl_rmm.core.config._get_service_config", return_value={"rustdesk_url": "https://rd.example.com"}),
        ):
            url = resolve_rustdesk_url()
            assert url == "https://rd.example.com"

    def test_returns_empty_string_when_not_configured(self) -> None:
        from kctl_rmm.core.config import resolve_rustdesk_url

        with (
            patch("kctl_rmm.core.config._resolve_active_profile_name", return_value="default"),
            patch("kctl_rmm.core.config._get_service_config", return_value={}),
        ):
            url = resolve_rustdesk_url()
            assert url == ""


class TestRMMClient:
    def test_requires_base_url(self) -> None:
        from kctl_lib import ConfigError

        from kctl_rmm.core.client import RMMClient

        with pytest.raises(ConfigError, match="No API URL configured"):
            RMMClient(base_url="", api_key="somekey")

    def test_requires_api_key(self) -> None:
        from kctl_lib import ConfigError

        from kctl_rmm.core.client import RMMClient

        with pytest.raises(ConfigError):
            RMMClient(base_url="https://rmm.example.com", api_key="")

    def test_strips_trailing_slash_from_url(self) -> None:
        from kctl_rmm.core.client import RMMClient

        client = RMMClient(base_url="https://rmm.example.com/", api_key="testkey")
        assert not client._base_url.endswith("/")
        client.close()

    def test_auth_header_is_x_api_key(self) -> None:
        from kctl_rmm.core.client import RMMClient

        assert RMMClient.AUTH_HEADER == "X-API-KEY"

    def test_auth_prefix_is_empty(self) -> None:
        from kctl_rmm.core.client import RMMClient

        assert RMMClient.AUTH_PREFIX == ""

    def test_ensure_trailing_slash_adds_slash(self) -> None:
        from kctl_rmm.core.client import RMMClient

        client = RMMClient(base_url="https://rmm.example.com", api_key="testkey")
        assert client._ensure_trailing_slash("/agents") == "agents/"
        client.close()

    def test_ensure_trailing_slash_preserves_query(self) -> None:
        from kctl_rmm.core.client import RMMClient

        client = RMMClient(base_url="https://rmm.example.com", api_key="testkey")
        endpoint = client._ensure_trailing_slash("/agents?detail=false")
        assert "?" in endpoint
        assert not endpoint.endswith("/")
        client.close()

    def test_ensure_trailing_slash_idempotent(self) -> None:
        from kctl_rmm.core.client import RMMClient

        client = RMMClient(base_url="https://rmm.example.com", api_key="testkey")
        assert client._ensure_trailing_slash("/agents/") == "agents/"
        client.close()


class TestAppContext:
    def test_app_context_extends_base(self) -> None:
        from kctl_lib.callbacks import AppContextBase

        from kctl_rmm.core.callbacks import AppContext

        assert issubclass(AppContext, AppContextBase)

    def test_app_context_has_url_override_field(self) -> None:
        from kctl_rmm.core.callbacks import AppContext

        ctx = AppContext(quiet=True, url_override="https://rmm.example.com")
        assert ctx.url_override == "https://rmm.example.com"

    def test_app_context_has_api_key_override_field(self) -> None:
        from kctl_rmm.core.callbacks import AppContext

        ctx = AppContext(quiet=True, api_key_override="mykey")
        assert ctx.api_key_override == "mykey"

    def test_url_override_defaults_to_none(self) -> None:
        from kctl_rmm.core.callbacks import AppContext

        ctx = AppContext(quiet=True)
        assert ctx.url_override is None

    def test_client_is_lazy_loaded(self) -> None:
        from kctl_rmm.core.callbacks import AppContext
        from kctl_rmm.core.client import RMMClient

        ctx = AppContext(quiet=True)
        assert ctx._client is None

        with patch("kctl_rmm.core.callbacks.resolve_connection", return_value=("https://rmm.example.com", "key")):
            client = ctx.client
            assert isinstance(client, RMMClient)
            client.close()

    def test_close_clears_client(self) -> None:
        from kctl_rmm.core.callbacks import AppContext

        ctx = AppContext(quiet=True)
        mock_client = MagicMock()
        ctx._client = mock_client

        ctx.close()
        mock_client.close.assert_called_once()


class TestCLIRegistration:
    def test_all_command_groups_registered(self) -> None:
        from kctl_rmm.cli import app

        group_names = sorted(g.name for g in app.registered_groups)
        expected = sorted(
            [
                "agents",
                "alerts",
                "checks",
                "clients",
                "config",
                "dashboard",
                "drivers",
                "health",
                "linux",
                "maintenance",
                "patches",
                "remote",
                "rustdesk",
                "scripts",
                "services",
                "skill",
                "software",
                "tasks",
                "winupdates",
            ]
        )
        assert group_names == expected

    def test_app_name(self) -> None:
        from kctl_rmm.cli import app

        assert app.info.name == "kctl-rmm"


class TestAgentHelpers:
    """Unit tests for agent status helper functions."""

    def test_agent_status_online(self) -> None:
        from kctl_rmm.commands.agents import _agent_status

        assert _agent_status({"status": "online"}) == "online"

    def test_agent_status_offline_when_missing(self) -> None:
        from kctl_rmm.commands.agents import _agent_status

        assert _agent_status({}) == "offline"

    def test_agent_status_offline_for_other_values(self) -> None:
        from kctl_rmm.commands.agents import _agent_status

        assert _agent_status({"status": "overdue"}) == "offline"
        assert _agent_status({"status": "offline"}) == "offline"


class TestChecksHelpers:
    """Unit tests for checks command helpers."""

    def test_checks_has_expected_command_count(self) -> None:
        # checks has: list, create, delete, results, run = 5 commands
        from kctl_rmm.commands.checks import app as checks_app

        assert len(checks_app.registered_commands) == 5

    def test_checks_list_is_explicitly_named(self) -> None:
        # list is the one command with an explicit name= override ("list")
        from kctl_rmm.commands.checks import app as checks_app

        explicit_names = [c.name for c in checks_app.registered_commands if c.name is not None]
        assert "list" in explicit_names

    def test_checks_subcommands_via_callback_names(self) -> None:
        # Commands without explicit name= inherit the function name at invocation time.
        # Verify via the callback function names as the source of truth.
        from kctl_rmm.commands.checks import app as checks_app

        callback_names = {c.callback.__name__ for c in checks_app.registered_commands if c.callback}
        # list_ is the internal name for the "list" subcommand (avoids shadowing builtin)
        assert "list_" in callback_names
        assert "create" in callback_names
        assert "delete" in callback_names
        assert "run" in callback_names
        assert "results" in callback_names


class TestExceptions:
    def test_kctl_error_importable(self) -> None:
        from kctl_lib import ConfigError, KctlError

        assert issubclass(ConfigError, KctlError)

    def test_rmm_re_exports_kctl_error(self) -> None:
        from kctl_lib import KctlError

        from kctl_rmm.cli import KctlError as RmmKctlError

        assert RmmKctlError is KctlError
