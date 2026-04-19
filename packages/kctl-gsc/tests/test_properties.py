"""properties command tests."""

from __future__ import annotations

from unittest.mock import MagicMock

from typer.testing import CliRunner

from kctl_gsc.cli import app


def _ctx_with_client(monkeypatch, mock_client):
    from kctl_gsc.core import callbacks as cb

    monkeypatch.setattr(cb.AppContext, "client", property(lambda self: mock_client))
    monkeypatch.setattr(cb.AppContext, "property", property(lambda self: "sc-domain:kodeme.io"))


def test_properties_list(monkeypatch) -> None:
    mc = MagicMock()
    mc.sites.return_value.list.return_value.execute.return_value = {
        "siteEntry": [
            {"siteUrl": "sc-domain:kodeme.io", "permissionLevel": "siteOwner"},
            {"siteUrl": "https://provetics.com/", "permissionLevel": "siteFullUser"},
        ]
    }
    _ctx_with_client(monkeypatch, mc)
    res = CliRunner().invoke(app, ["-p", "test", "properties", "list"])
    assert res.exit_code == 0, res.stdout
    assert "kodeme.io" in res.stdout
    assert "provetics.com" in res.stdout


def test_properties_show_not_found(monkeypatch) -> None:
    from googleapiclient.errors import HttpError

    class FakeResp:
        status = 404
        reason = "Not Found"

    mc = MagicMock()
    mc.sites.return_value.get.return_value.execute.side_effect = HttpError(FakeResp(), b"{}")
    _ctx_with_client(monkeypatch, mc)
    res = CliRunner().invoke(app, ["-p", "test", "properties", "show", "sc-domain:missing.io"])
    assert res.exit_code != 0
