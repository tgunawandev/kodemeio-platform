"""Test emoji commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from kctl_zulip.cli import app


def _patch_client(mock_client: MagicMock):
    return (
        patch("kctl_zulip.core.callbacks.resolve_connection", return_value=("https://z.test", "e@x.com", "key")),
        patch("kctl_zulip.core.callbacks.ZulipClient", return_value=mock_client),
    )


def test_emoji_list(runner: CliRunner, mock_client: MagicMock):
    mock_client.get.return_value = {
        "emoji": {
            "1": {"name": "wave", "author_id": 1, "deactivated": False},
            "2": {"name": "heart", "author_id": 2, "deactivated": False},
        }
    }
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(app, ["emoji", "list"])
    assert result.exit_code == 0
    mock_client.get.assert_called_with("realm/emoji")


def test_emoji_delete_force(runner: CliRunner, mock_client: MagicMock):
    # First call for lookup, second for the delete
    mock_client.get.return_value = {
        "emoji": {
            "42": {"name": "wave", "author_id": 1, "deactivated": False},
        }
    }
    mock_client.delete.return_value = {}
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(app, ["emoji", "delete", "wave", "--force"])
    assert result.exit_code == 0
    mock_client.delete.assert_called_with("realm/emoji/42")
