"""Test users commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from kctl_zulip.cli import app


def _patch_client(mock_client: MagicMock):
    return (
        patch("kctl_zulip.core.callbacks.resolve_connection", return_value=("https://z.test", "e@x.com", "key")),
        patch("kctl_zulip.core.callbacks.ZulipClient", return_value=mock_client),
    )


def test_users_list(runner: CliRunner, mock_client: MagicMock):
    mock_client.get.return_value = {
        "members": [
            {
                "user_id": 1,
                "email": "alice@test.io",
                "full_name": "Alice",
                "role": 200,
                "is_active": True,
                "is_bot": False,
            },
            {"user_id": 2, "email": "bob@test.io", "full_name": "Bob", "role": 400, "is_active": True, "is_bot": False},
        ]
    }
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(app, ["users", "list"])
    assert result.exit_code == 0
    mock_client.get.assert_called_once()


def test_users_get(runner: CliRunner, mock_client: MagicMock):
    mock_client.get.return_value = {
        "user": {"user_id": 1, "email": "alice@test.io", "full_name": "Alice", "role": 200, "is_active": True}
    }
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(app, ["users", "get", "1"])
    assert result.exit_code == 0
    mock_client.get.assert_called_with("users/1")


def test_users_create(runner: CliRunner, mock_client: MagicMock):
    mock_client.post.return_value = {"user_id": 10}
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(app, ["users", "create", "new@test.io", "--name", "New User", "--password", "secret123"])
    assert result.exit_code == 0
    mock_client.post.assert_called_once()


def test_users_deactivate_force(runner: CliRunner, mock_client: MagicMock):
    mock_client.delete.return_value = {}
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(app, ["users", "deactivate", "1", "--force"])
    assert result.exit_code == 0
    mock_client.delete.assert_called_with("users/1")


def test_users_reactivate(runner: CliRunner, mock_client: MagicMock):
    mock_client.post.return_value = {}
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(app, ["users", "reactivate", "1"])
    assert result.exit_code == 0
    mock_client.post.assert_called_with("users/1/reactivate")
