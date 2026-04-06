"""Test streams commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from kctl_zulip.cli import app


def _patch_client(mock_client: MagicMock):
    return (
        patch("kctl_zulip.core.callbacks.resolve_connection", return_value=("https://z.test", "e@x.com", "key")),
        patch("kctl_zulip.core.callbacks.ZulipClient", return_value=mock_client),
    )


def test_streams_list(runner: CliRunner, mock_client: MagicMock):
    mock_client.get.return_value = {
        "streams": [
            {
                "stream_id": 1,
                "name": "general",
                "description": "General chat",
                "invite_only": False,
                "stream_weekly_traffic": 50,
            },
        ]
    }
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(app, ["streams", "list"])
    assert result.exit_code == 0
    mock_client.get.assert_called_once()


def test_streams_get(runner: CliRunner, mock_client: MagicMock):
    mock_client.get.side_effect = [
        {"stream": {"stream_id": 1, "name": "general", "description": "General chat"}},
        {"subscribers": [1, 2, 3]},
    ]
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(app, ["streams", "get", "1"])
    assert result.exit_code == 0


def test_streams_create(runner: CliRunner, mock_client: MagicMock):
    mock_client.post.return_value = {"subscribed": {"bot@test.io": ["new-stream"]}}
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(app, ["streams", "create", "new-stream"])
    assert result.exit_code == 0
    mock_client.post.assert_called_once()


def test_streams_delete_force(runner: CliRunner, mock_client: MagicMock):
    mock_client.get.return_value = {"stream_id": 5}
    mock_client.delete.return_value = {}
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(app, ["streams", "delete", "5", "--force"])
    assert result.exit_code == 0
    mock_client.delete.assert_called_with("streams/5")


def test_streams_subscribe(runner: CliRunner, mock_client: MagicMock):
    mock_client.post.return_value = {"subscribed": {"bot@test.io": ["general"]}, "already_subscribed": {}}
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(app, ["streams", "subscribe", "general"])
    assert result.exit_code == 0
    mock_client.post.assert_called_once()
