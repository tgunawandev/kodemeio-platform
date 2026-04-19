"""export command tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from typer.testing import CliRunner

from kctl_gsc.cli import app


def _inject(monkeypatch, mc):
    from kctl_gsc.core import callbacks as cb

    monkeypatch.setattr(cb.AppContext, "client", property(lambda self: mc))
    monkeypatch.setattr(cb.AppContext, "property", property(lambda self: "sc-domain:kodeme.io"))


def test_export_csv(monkeypatch, tmp_path: Path) -> None:
    mc = MagicMock()
    mc.searchanalytics.return_value.query.return_value.execute.return_value = {
        "rows": [{"keys": ["foo"], "clicks": 1, "impressions": 10, "ctr": 0.1, "position": 2.0}]
    }
    _inject(monkeypatch, mc)
    out = tmp_path / "export.csv"
    res = CliRunner().invoke(app, ["-p", "test", "export", "csv", "--dimensions", "query", "--out", str(out)])
    assert res.exit_code == 0, res.stdout
    data = out.read_text()
    assert "query" in data
    assert "foo" in data


def test_export_json(monkeypatch, tmp_path: Path) -> None:
    mc = MagicMock()
    mc.searchanalytics.return_value.query.return_value.execute.return_value = {
        "rows": [{"keys": ["foo"], "clicks": 1, "impressions": 10, "ctr": 0.1, "position": 2.0}]
    }
    _inject(monkeypatch, mc)
    out = tmp_path / "export.json"
    res = CliRunner().invoke(app, ["-p", "test", "export", "json", "--dimensions", "query", "--out", str(out)])
    assert res.exit_code == 0
    import json

    data = json.loads(out.read_text())
    assert data[0]["query"] == "foo"
