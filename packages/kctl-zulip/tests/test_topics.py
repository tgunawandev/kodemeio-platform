"""Test topics commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from kctl_zulip.cli import app


def _patch_client(mock_client: MagicMock):
    return (
        patch("kctl_zulip.core.callbacks.resolve_connection", return_value=("https://z.test", "e@x.com", "key")),
        patch("kctl_zulip.core.callbacks.ZulipClient", return_value=mock_client),
    )


def test_topics_list_stream(runner: CliRunner, mock_client: MagicMock):
    # _resolve_stream_id will try int("5") first, succeeds, so stream_id=5
    mock_client.get.return_value = {
        "topics": [
            {"name": "greetings", "max_id": 100},
            {"name": "random", "max_id": 200},
        ]
    }
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(app, ["topics", "list", "--stream", "5"])
    assert result.exit_code == 0
    mock_client.get.assert_called_with("users/me/5/topics")
