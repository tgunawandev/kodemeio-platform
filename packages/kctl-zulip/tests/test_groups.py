"""Test groups commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from kctl_zulip.cli import app


def _patch_client(mock_client: MagicMock):
    return (
        patch("kctl_zulip.core.callbacks.resolve_connection", return_value=("https://z.test", "e@x.com", "key")),
        patch("kctl_zulip.core.callbacks.ZulipClient", return_value=mock_client),
    )


def test_groups_list(runner: CliRunner, mock_client: MagicMock):
    mock_client.get.return_value = {
        "user_groups": [
            {"id": 1, "name": "engineering", "description": "Eng team", "members": [1, 2], "is_system_group": False},
        ]
    }
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(app, ["groups", "list"])
    assert result.exit_code == 0
    mock_client.get.assert_called_with("user_groups")


def test_groups_create(runner: CliRunner, mock_client: MagicMock):
    mock_client.post.return_value = {}
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(app, ["groups", "create", "new-group"])
    assert result.exit_code == 0
    mock_client.post.assert_called_once()
    assert mock_client.post.call_args[0][0] == "user_groups/create"


def test_groups_delete_force(runner: CliRunner, mock_client: MagicMock):
    mock_client.delete.return_value = {}
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(app, ["groups", "delete", "1", "--force"])
    assert result.exit_code == 0
    mock_client.delete.assert_called_with("user_groups/1")
