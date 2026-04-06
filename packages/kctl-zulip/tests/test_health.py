"""Test health command."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from kctl_zulip.cli import app


def _patch_client(mock_client: MagicMock):
    return (
        patch("kctl_zulip.core.callbacks.resolve_connection", return_value=("https://z.test", "e@x.com", "key")),
        patch("kctl_zulip.core.callbacks.ZulipClient", return_value=mock_client),
    )


def test_health(runner: CliRunner, mock_client: MagicMock):
    mock_client.check_health.return_value = {
        "zulip_version": "9.0",
        "zulip_feature_level": 300,
        "realm_name": "Test",
        "push_notifications_enabled": True,
    }
    mock_client.get.return_value = {"user_id": 1, "email": "bot@test.io", "full_name": "Bot", "role": 200}
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(app, ["health"])
    assert result.exit_code == 0
    mock_client.check_health.assert_called_once()
