"""sitemaps command tests."""

from __future__ import annotations

from unittest.mock import MagicMock

from typer.testing import CliRunner

from kctl_gsc.cli import app


def _inject(monkeypatch, mc):
    from kctl_gsc.core import callbacks as cb

    monkeypatch.setattr(cb.AppContext, "client", property(lambda self: mc))
    monkeypatch.setattr(cb.AppContext, "property", property(lambda self: "sc-domain:kodeme.io"))


def test_sitemaps_list(monkeypatch) -> None:
    mc = MagicMock()
    mc.sitemaps.return_value.list.return_value.execute.return_value = {
        "sitemap": [
            {
                "path": "https://kodeme.io/sitemap.xml",
                "lastSubmitted": "2026-04-10T00:00:00Z",
                "isPending": False,
                "isSitemapsIndex": False,
            },
        ]
    }
    _inject(monkeypatch, mc)
    res = CliRunner().invoke(app, ["-p", "test", "sitemaps", "list"])
    assert res.exit_code == 0, res.stdout
    assert "sitemap.xml" in res.stdout


def test_sitemaps_submit_calls_api(monkeypatch) -> None:
    mc = MagicMock()
    mc.sitemaps.return_value.submit.return_value.execute.return_value = {}
    _inject(monkeypatch, mc)
    res = CliRunner().invoke(app, ["-p", "test", "sitemaps", "submit", "https://kodeme.io/sitemap.xml"])
    assert res.exit_code == 0, res.stdout
    args = mc.sitemaps.return_value.submit.call_args.kwargs
    assert args["feedpath"] == "https://kodeme.io/sitemap.xml"
    assert args["siteUrl"] == "sc-domain:kodeme.io"


def test_sitemaps_status(monkeypatch) -> None:
    mc = MagicMock()
    mc.sitemaps.return_value.get.return_value.execute.return_value = {
        "path": "https://kodeme.io/sitemap.xml",
        "lastSubmitted": "2026-04-10T00:00:00Z",
        "isPending": False,
        "isSitemapsIndex": False,
        "type": "sitemap",
    }
    _inject(monkeypatch, mc)
    res = CliRunner().invoke(app, ["-p", "test", "sitemaps", "status", "https://kodeme.io/sitemap.xml"])
    assert res.exit_code == 0, res.stdout
    args = mc.sitemaps.return_value.get.call_args.kwargs
    assert args["feedpath"] == "https://kodeme.io/sitemap.xml"


def test_sitemaps_delete_calls_api(monkeypatch) -> None:
    mc = MagicMock()
    mc.sitemaps.return_value.delete.return_value.execute.return_value = {}
    _inject(monkeypatch, mc)
    res = CliRunner().invoke(app, ["-p", "test", "sitemaps", "delete", "https://kodeme.io/sitemap.xml"])
    assert res.exit_code == 0, res.stdout
    args = mc.sitemaps.return_value.delete.call_args.kwargs
    assert args["feedpath"] == "https://kodeme.io/sitemap.xml"
