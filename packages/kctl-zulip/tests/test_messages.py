"""Test messages commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from kctl_zulip.cli import app


def _patch_client(mock_client: MagicMock):
    return (
        patch("kctl_zulip.core.callbacks.resolve_connection", return_value=("https://z.test", "e@x.com", "key")),
        patch("kctl_zulip.core.callbacks.ZulipClient", return_value=mock_client),
    )


def test_send_stream(runner: CliRunner, mock_client: MagicMock):
    mock_client.post.return_value = {"id": 42}
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(app, ["messages", "send", "Hello world", "--stream", "general", "--topic", "greetings"])
    assert result.exit_code == 0
    mock_client.post.assert_called_once()
    call_args = mock_client.post.call_args
    assert call_args[0][0] == "messages"
    assert call_args[1]["data"]["type"] == "stream"
    assert call_args[1]["data"]["to"] == "general"


def test_send_dm(runner: CliRunner, mock_client: MagicMock):
    mock_client.post.return_value = {"id": 43}
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(app, ["messages", "send", "Hi!", "--to", "alice@test.io"])
    assert result.exit_code == 0
    mock_client.post.assert_called_once()
    call_args = mock_client.post.call_args
    assert call_args[0][0] == "messages"
    assert call_args[1]["data"]["type"] == "direct"


def test_delete_force(runner: CliRunner, mock_client: MagicMock):
    mock_client.delete.return_value = {}
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(app, ["messages", "delete", "42", "--force"])
    assert result.exit_code == 0
    mock_client.delete.assert_called_with("messages/42")
