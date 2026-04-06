"""Test invitations commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from kctl_zulip.cli import app


def _patch_client(mock_client: MagicMock):
    return (
        patch("kctl_zulip.core.callbacks.resolve_connection", return_value=("https://z.test", "e@x.com", "key")),
        patch("kctl_zulip.core.callbacks.ZulipClient", return_value=mock_client),
    )


def test_invitations_list(runner: CliRunner, mock_client: MagicMock):
    mock_client.get.return_value = {
        "invites": [
            {
                "id": 1,
                "email": "new@test.io",
                "invited_by": {"email": "admin@test.io"},
                "is_multiuse": False,
                "invited_at": "2026-01-01",
            },
        ]
    }
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(app, ["invitations", "list"])
    assert result.exit_code == 0
    mock_client.get.assert_called_with("invites")


def test_invitations_create(runner: CliRunner, mock_client: MagicMock):
    mock_client.post.return_value = {}
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(app, ["invitations", "create", "new@test.io,other@test.io"])
    assert result.exit_code == 0
    mock_client.post.assert_called_once()
    assert mock_client.post.call_args[0][0] == "invites"
