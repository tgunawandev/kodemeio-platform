"""Test linkifiers commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from kctl_zulip.cli import app


def _patch_client(mock_client: MagicMock):
    return (
        patch("kctl_zulip.core.callbacks.resolve_connection", return_value=("https://z.test", "e@x.com", "key")),
        patch("kctl_zulip.core.callbacks.ZulipClient", return_value=mock_client),
    )


def test_linkifiers_list(runner: CliRunner, mock_client: MagicMock):
    mock_client.get.return_value = {
        "linkifiers": [
            {"id": 1, "pattern": "#(?P<id>[0-9]+)", "url_template": "https://github.com/org/repo/issues/{id}"},
        ]
    }
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(app, ["linkifiers", "list"])
    assert result.exit_code == 0
    mock_client.get.assert_called_with("realm/linkifiers")


def test_linkifiers_create(runner: CliRunner, mock_client: MagicMock):
    mock_client.post.return_value = {"id": 2}
    p1, p2 = _patch_client(mock_client)
    with p1, p2:
        result = runner.invoke(
            app,
            [
                "linkifiers",
                "create",
                "--pattern",
                "#(?P<id>[0-9]+)",
                "--url-template",
                "https://github.com/org/repo/issues/{id}",
            ],
        )
    assert result.exit_code == 0
    mock_client.post.assert_called_once()
    assert mock_client.post.call_args[0][0] == "realm/filters"
