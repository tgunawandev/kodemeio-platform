"""Test muted commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from kctl_zulip.cli import app


def _patch_client(mock_client: MagicMock):
    return (
        patch("kctl_zulip.core.callbacks.resolve_connection", return_value=("https://z.test", "e@x.com", "key")),
        patch("kctl_zulip.core.callbacks.ZulipClient", return_value=mock_client),
    )


def test_muted_topics(runner: CliRunner, mock_client: MagicMock):
    mock_client.get.return_value = {
        "muted_topics": [
            ["general", "spam", 1700000000],
        ]
    }
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(app, ["muted", "topics"])
    assert result.exit_code == 0
    mock_client.get.assert_called_with("users/me/subscriptions")


def test_mute_topic(runner: CliRunner, mock_client: MagicMock):
    mock_client.patch.return_value = {}
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(app, ["muted", "mute-topic", "general", "spam"])
    assert result.exit_code == 0
    mock_client.patch.assert_called_once_with(
        "users/me/subscriptions/muted_topics",
        data={"stream": "general", "topic": "spam", "op": "add"},
    )
