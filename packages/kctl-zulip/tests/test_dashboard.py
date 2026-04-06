"""Test dashboard command."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from kctl_zulip.cli import app


def _patch_client(mock_client: MagicMock):
    return (
        patch("kctl_zulip.core.callbacks.resolve_connection", return_value=("https://z.test", "e@x.com", "key")),
        patch("kctl_zulip.core.callbacks.ZulipClient", return_value=mock_client),
    )


def test_dashboard_json(runner: CliRunner, mock_client: MagicMock):
    mock_client.get.side_effect = [
        # server_settings
        {"zulip_version": "9.0", "realm_name": "Test"},
        # users/me
        {"user_id": 1, "email": "bot@test.io", "full_name": "Bot"},
        # users
        {
            "members": [
                {"user_id": 1, "is_active": True, "is_bot": False},
                {"user_id": 2, "is_active": True, "is_bot": True},
            ]
        },
        # streams
        {"streams": [{"stream_id": 1, "name": "general"}]},
        # user_groups
        {"user_groups": [{"id": 1, "name": "eng"}]},
        # realm/emoji
        {"emoji": {"1": {"name": "wave"}}},
    ]
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(app, ["--json", "dashboard"])
    assert result.exit_code == 0
