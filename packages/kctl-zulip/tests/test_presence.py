"""Test presence commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from kctl_zulip.cli import app


def _patch_client(mock_client: MagicMock):
    return (
        patch("kctl_zulip.core.callbacks.resolve_connection", return_value=("https://z.test", "e@x.com", "key")),
        patch("kctl_zulip.core.callbacks.ZulipClient", return_value=mock_client),
    )


def test_presence_list(runner: CliRunner, mock_client: MagicMock):
    mock_client.get.return_value = {
        "presences": {
            "alice@test.io": {"aggregated": {"status": "active", "timestamp": 1700000000}},
            "bob@test.io": {"aggregated": {"status": "idle", "timestamp": 1699999000}},
        }
    }
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(app, ["presence", "list"])
    assert result.exit_code == 0
    mock_client.get.assert_called_with("realm/presence")


def test_presence_get(runner: CliRunner, mock_client: MagicMock):
    mock_client.get.return_value = {
        "presence": {
            "aggregated": {"status": "active", "timestamp": 1700000000, "client": "website"},
            "website": {"status": "active", "timestamp": 1700000000},
        }
    }
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(app, ["presence", "get", "alice@test.io"])
    assert result.exit_code == 0
    mock_client.get.assert_called_with("users/alice@test.io/presence")
