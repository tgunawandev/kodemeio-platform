"""Test scheduled messages commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from kctl_zulip.cli import app


def _patch_client(mock_client: MagicMock):
    return (
        patch("kctl_zulip.core.callbacks.resolve_connection", return_value=("https://z.test", "e@x.com", "key")),
        patch("kctl_zulip.core.callbacks.ZulipClient", return_value=mock_client),
    )


def test_scheduled_list(runner: CliRunner, mock_client: MagicMock):
    mock_client.get.return_value = {
        "scheduled_messages": [
            {
                "scheduled_message_id": 1,
                "type": "stream",
                "to": "general",
                "topic": "test",
                "content": "Hello later",
                "scheduled_delivery_timestamp": 1700000000,
            }
        ]
    }
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(app, ["scheduled", "list"])
    assert result.exit_code == 0
    mock_client.get.assert_called_with("scheduled_messages")


def test_scheduled_create(runner: CliRunner, mock_client: MagicMock):
    mock_client.post.return_value = {"scheduled_message_id": 5}
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(
            app,
            [
                "scheduled",
                "create",
                "--content",
                "Hello later",
                "--deliver-at",
                "1700000000",
                "--to",
                "general",
                "--topic",
                "test",
            ],
        )
    assert result.exit_code == 0
    mock_client.post.assert_called_once()
    assert mock_client.post.call_args[0][0] == "scheduled_messages"
