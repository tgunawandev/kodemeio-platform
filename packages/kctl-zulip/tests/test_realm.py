"""Test realm commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from kctl_zulip.cli import app


def _patch_client(mock_client: MagicMock):
    return (
        patch("kctl_zulip.core.callbacks.resolve_connection", return_value=("https://z.test", "e@x.com", "key")),
        patch("kctl_zulip.core.callbacks.ZulipClient", return_value=mock_client),
    )


def test_realm_settings_json(runner: CliRunner, mock_client: MagicMock):
    mock_client.get.return_value = {
        "zulip_version": "9.0",
        "zulip_feature_level": 300,
        "zulip_merge_base": "9.0",
        "push_notifications_enabled": True,
        "realm_name": "Test Realm",
        "realm_description": "A test realm",
        "realm_icon": "",
        "realm_uri": "https://zulip.test.io",
        "realm_web_public_access_enabled": False,
        "authentication_methods": {"password": True, "ldap": False},
        "require_email_format_usernames": True,
    }
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(app, ["--json", "realm", "settings"])
    assert result.exit_code == 0
    mock_client.get.assert_called_with("server_settings")
