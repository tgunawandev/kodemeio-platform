"""Test reactions commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from kctl_zulip.cli import app


def _patch_client(mock_client: MagicMock):
    return (
        patch("kctl_zulip.core.callbacks.resolve_connection", return_value=("https://z.test", "e@x.com", "key")),
        patch("kctl_zulip.core.callbacks.ZulipClient", return_value=mock_client),
    )


def test_reactions_add(runner: CliRunner, mock_client: MagicMock):
    mock_client.post.return_value = {}
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(app, ["reactions", "add", "42", "thumbs_up"])
    assert result.exit_code == 0
    mock_client.post.assert_called_once_with("messages/42/reactions", data={"emoji_name": "thumbs_up"})


def test_reactions_list(runner: CliRunner, mock_client: MagicMock):
    mock_client.get.return_value = {
        "messages": [
            {
                "id": 42,
                "reactions": [
                    {"emoji_name": "thumbs_up", "emoji_code": "1f44d", "user_id": 1, "reaction_type": "unicode_emoji"},
                ],
            }
        ]
    }
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(app, ["reactions", "list", "42"])
    assert result.exit_code == 0
    mock_client.get.assert_called_once()
