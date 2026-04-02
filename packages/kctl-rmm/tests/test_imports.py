"""Smoke tests — verify all modules import and CLI registers correctly."""

from __future__ import annotations


def test_version():
    from kctl_rmm import __version__

    assert __version__ == "0.2.0"


def test_cli_app_has_all_groups():
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
            "software",
            "tasks",
            "winupdates",
        ]
    )
    assert group_names == expected


def test_core_config_service_key():
    from kctl_rmm.core.config import SERVICE_KEY

    assert SERVICE_KEY == "rmm"


def test_rmm_client_requires_url():
    import pytest
    from kctl_lib import ConfigError

    from kctl_rmm.core.client import RMMClient

    with pytest.raises(ConfigError, match="No API URL configured"):
        RMMClient(base_url="", api_key="test")


def test_rmm_client_requires_api_key():
    import pytest
    from kctl_lib import ConfigError

    from kctl_rmm.core.client import RMMClient

    with pytest.raises(ConfigError, match="API credential is required"):
        RMMClient(base_url="https://example.com", api_key="")


def test_app_context_extends_base():
    from kctl_lib.callbacks import AppContextBase

    from kctl_rmm.core.callbacks import AppContext

    assert issubclass(AppContext, AppContextBase)
