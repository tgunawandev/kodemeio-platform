"""Test announce commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from kctl_zulip.cli import app


def _patch_client(mock_client: MagicMock):
    return (
        patch("kctl_zulip.core.callbacks.resolve_connection", return_value=("https://z.test", "e@x.com", "key")),
        patch("kctl_zulip.core.callbacks.ZulipClient", return_value=mock_client),
    )


def test_announce_send(runner: CliRunner, mock_client: MagicMock):
    mock_client.post.return_value = {"id": 100}
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(
            app,
            [
                "announce",
                "send",
                "System maintenance tonight",
                "--stream",
                "general",
                "--topic",
                "Ops",
            ],
        )
    assert result.exit_code == 0
    mock_client.post.assert_called_once_with(
        "messages",
        data={
            "type": "stream",
            "to": "general",
            "topic": "Ops",
            "content": "System maintenance tonight",
        },
    )
