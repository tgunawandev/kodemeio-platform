"""queries command tests."""

from __future__ import annotations

from unittest.mock import MagicMock

from typer.testing import CliRunner

from kctl_gsc.cli import app


def _inject(monkeypatch, mc):
    from kctl_gsc.core import callbacks as cb

    monkeypatch.setattr(cb.AppContext, "client", property(lambda self: mc))
    monkeypatch.setattr(cb.AppContext, "property", property(lambda self: "sc-domain:kodeme.io"))


def test_queries_top(monkeypatch) -> None:
    mc = MagicMock()
    mc.searchanalytics.return_value.query.return_value.execute.return_value = {
        "rows": [
            {"keys": ["odoo erp indonesia"], "clicks": 42, "impressions": 1000, "ctr": 0.042, "position": 3.2},
            {"keys": ["payroll software"], "clicks": 10, "impressions": 500, "ctr": 0.020, "position": 5.1},
        ]
    }
    _inject(monkeypatch, mc)
    res = CliRunner().invoke(app, ["-p", "test", "queries", "top", "--days", "28", "--limit", "10"])
    assert res.exit_code == 0, res.stdout
    assert "odoo erp indonesia" in res.stdout

    body = mc.searchanalytics.return_value.query.call_args.kwargs["body"]
    assert body["dimensions"] == ["query"]
    assert body["rowLimit"] == 10


def test_queries_search_substring(monkeypatch) -> None:
    mc = MagicMock()
    mc.searchanalytics.return_value.query.return_value.execute.return_value = {
        "rows": [
            {"keys": ["payroll software"], "clicks": 10, "impressions": 500, "ctr": 0.02, "position": 5.1},
            {"keys": ["odoo erp"], "clicks": 2, "impressions": 40, "ctr": 0.05, "position": 8.0},
        ]
    }
    _inject(monkeypatch, mc)
    res = CliRunner().invoke(app, ["-p", "test", "queries", "search", "payroll"])
    assert res.exit_code == 0
    assert "payroll software" in res.stdout
    assert "odoo erp" not in res.stdout


def test_queries_trends_filter(monkeypatch) -> None:
    mc = MagicMock()
    mc.searchanalytics.return_value.query.return_value.execute.return_value = {
        "rows": [
            {"keys": ["2026-04-01"], "impressions": 100, "clicks": 5, "position": 4.1},
            {"keys": ["2026-04-02"], "impressions": 120, "clicks": 7, "position": 3.8},
        ]
    }
    _inject(monkeypatch, mc)
    res = CliRunner().invoke(app, ["-p", "test", "queries", "trends", "odoo erp", "--days", "7"])
    assert res.exit_code == 0, res.stdout
    assert "2026-04-01" in res.stdout

    body = mc.searchanalytics.return_value.query.call_args.kwargs["body"]
    assert body["dimensions"] == ["date"]
    assert body["dimensionFilterGroups"] == [
        {"filters": [{"dimension": "query", "operator": "equals", "expression": "odoo erp"}]}
    ]
