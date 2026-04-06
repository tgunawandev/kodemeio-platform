"""Test profile fields commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from kctl_zulip.cli import app


def _patch_client(mock_client: MagicMock):
    return (
        patch("kctl_zulip.core.callbacks.resolve_connection", return_value=("https://z.test", "e@x.com", "key")),
        patch("kctl_zulip.core.callbacks.ZulipClient", return_value=mock_client),
    )


def test_profile_fields_list(runner: CliRunner, mock_client: MagicMock):
    mock_client.get.return_value = {
        "custom_fields": [
            {"id": 1, "name": "GitHub", "type": 5, "hint": "Your GitHub username", "order": 1},
        ]
    }
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(app, ["profile-fields", "list"])
    assert result.exit_code == 0
    mock_client.get.assert_called_with("realm/profile_fields")


def test_profile_fields_create(runner: CliRunner, mock_client: MagicMock):
    mock_client.post.return_value = {"id": 5}
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(app, ["profile-fields", "create", "--name", "GitHub", "--type", "5"])
    assert result.exit_code == 0
    mock_client.post.assert_called_once()
    assert mock_client.post.call_args[0][0] == "realm/profile_fields"
