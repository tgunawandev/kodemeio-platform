"""pages command tests."""

from __future__ import annotations

from unittest.mock import MagicMock

from typer.testing import CliRunner

from kctl_gsc.cli import app


def _inject(monkeypatch, mc):
    from kctl_gsc.core import callbacks as cb

    monkeypatch.setattr(cb.AppContext, "client", property(lambda self: mc))
    monkeypatch.setattr(cb.AppContext, "property", property(lambda self: "sc-domain:kodeme.io"))


def test_pages_top(monkeypatch) -> None:
    mc = MagicMock()
    mc.searchanalytics.return_value.query.return_value.execute.return_value = {
        "rows": [
            {
                "keys": ["https://kodeme.io/pricing"],
                "clicks": 80,
                "impressions": 2000,
                "ctr": 0.04,
                "position": 4.0,
            },
        ]
    }
    _inject(monkeypatch, mc)
    res = CliRunner().invoke(app, ["-p", "test", "pages", "top"])
    assert res.exit_code == 0, res.stdout
    assert "/pricing" in res.stdout


def test_pages_impressions(monkeypatch) -> None:
    mc = MagicMock()
    mc.searchanalytics.return_value.query.return_value.execute.return_value = {
        "rows": [
            {
                "keys": ["https://kodeme.io/a"],
                "clicks": 0,
                "impressions": 50,
                "ctr": 0.0,
                "position": 30.0,
            },
            {
                "keys": ["https://kodeme.io/b"],
                "clicks": 5,
                "impressions": 500,
                "ctr": 0.01,
                "position": 8.0,
            },
        ]
    }
    _inject(monkeypatch, mc)
    res = CliRunner().invoke(app, ["-p", "test", "pages", "impressions"])
    assert res.exit_code == 0, res.stdout
    # Both visible; /b should be listed first after impressions sort.
    assert "/b" in res.stdout
    assert "/a" in res.stdout
    assert res.stdout.index("/b") < res.stdout.index("/a")


def test_pages_orphans(monkeypatch) -> None:
    mc = MagicMock()
    mc.searchanalytics.return_value.query.return_value.execute.return_value = {
        "rows": [
            {
                "keys": ["https://kodeme.io/a"],
                "impressions": 500,
                "clicks": 0,
                "ctr": 0.0,
                "position": 25.0,
            },
            {
                "keys": ["https://kodeme.io/b"],
                "impressions": 100,
                "clicks": 5,
                "ctr": 0.05,
                "position": 4.0,
            },
        ]
    }
    _inject(monkeypatch, mc)
    res = CliRunner().invoke(app, ["-p", "test", "pages", "orphans"])
    assert res.exit_code == 0, res.stdout
    assert "/a" in res.stdout
    assert "/b" not in res.stdout
