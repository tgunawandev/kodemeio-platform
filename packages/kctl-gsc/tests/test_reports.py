"""reports command tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from typer.testing import CliRunner

from kctl_gsc.cli import app


def _inject(monkeypatch, mc):
    from kctl_gsc.core import callbacks as cb

    monkeypatch.setattr(cb.AppContext, "client", property(lambda self: mc))
    monkeypatch.setattr(cb.AppContext, "property", property(lambda self: "sc-domain:kodeme.io"))


def test_reports_overview(monkeypatch) -> None:
    mc = MagicMock()
    mc.searchanalytics.return_value.query.return_value.execute.return_value = {
        "rows": [{"keys": ["2026-04-01"], "clicks": 50, "impressions": 900, "ctr": 0.055, "position": 10.0}]
    }
    _inject(monkeypatch, mc)
    res = CliRunner().invoke(app, ["-p", "test", "reports", "overview"])
    assert res.exit_code == 0
    assert "50" in res.stdout


def test_reports_product(monkeypatch, tmp_path: Path) -> None:
    yaml_path = tmp_path / "clusters.yaml"
    yaml_path.write_text(
        """
products:
  bas:
    property: sc-domain:kodeme.io
    clusters:
      - name: payroll
        patterns: [payroll]
      - name: erp
        patterns: [odoo]
"""
    )
    mc = MagicMock()
    mc.searchanalytics.return_value.query.return_value.execute.return_value = {
        "rows": [
            {"keys": ["odoo erp"], "clicks": 10, "impressions": 200, "ctr": 0.05, "position": 4.5},
            {"keys": ["aplikasi payroll"], "clicks": 3, "impressions": 80, "ctr": 0.037, "position": 7.0},
        ]
    }
    _inject(monkeypatch, mc)
    res = CliRunner().invoke(app, ["-p", "test", "reports", "product", "bas", "--clusters", str(yaml_path)])
    assert res.exit_code == 0, res.stdout
    assert "payroll" in res.stdout
    assert "erp" in res.stdout


def test_reports_opportunities(monkeypatch) -> None:
    mc = MagicMock()
    mc.searchanalytics.return_value.query.return_value.execute.return_value = {
        "rows": [
            {"keys": ["low hanging"], "impressions": 2000, "clicks": 10, "ctr": 0.005, "position": 7.5},
            {"keys": ["too high"], "impressions": 500, "clicks": 80, "ctr": 0.16, "position": 2.0},
            {"keys": ["too deep"], "impressions": 300, "clicks": 0, "ctr": 0.0, "position": 50.0},
        ]
    }
    _inject(monkeypatch, mc)
    res = CliRunner().invoke(app, ["-p", "test", "reports", "opportunities"])
    assert res.exit_code == 0
    assert "low hanging" in res.stdout
    assert "too high" not in res.stdout
    assert "too deep" not in res.stdout


def test_reports_drift(monkeypatch) -> None:
    mc = MagicMock()
    exec_mock = mc.searchanalytics.return_value.query.return_value.execute
    # Current period: q1 now ranks 6.0 (worse). Prior: q1 ranked 2.0.
    # delta = current - prior = 6.0 - 2.0 = +4 ≥ threshold(3) → flagged.
    exec_mock.side_effect = [
        {"rows": [{"keys": ["q1"], "impressions": 1000, "clicks": 5, "position": 6.0, "ctr": 0.005}]},
        {"rows": [{"keys": ["q1"], "impressions": 900, "clicks": 45, "position": 2.0, "ctr": 0.05}]},
    ]
    _inject(monkeypatch, mc)
    res = CliRunner().invoke(app, ["-p", "test", "reports", "drift", "--days", "7", "--threshold", "3"])
    assert res.exit_code == 0
    assert "q1" in res.stdout
