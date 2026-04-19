"""inspect command tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from typer.testing import CliRunner

from kctl_gsc.cli import app


def _inject(monkeypatch, mc):
    from kctl_gsc.core import callbacks as cb

    monkeypatch.setattr(cb.AppContext, "client", property(lambda self: mc))
    monkeypatch.setattr(cb.AppContext, "property", property(lambda self: "sc-domain:kodeme.io"))


def test_inspect_url(monkeypatch) -> None:
    mc = MagicMock()
    mc.url_inspection.return_value.inspect.return_value.execute.return_value = {
        "inspectionResult": {
            "indexStatusResult": {
                "verdict": "PASS",
                "googleCanonical": "https://kodeme.io/",
                "lastCrawlTime": "2026-04-10T00:00:00Z",
            },
            "mobileUsabilityResult": {"verdict": "PASS"},
        }
    }
    _inject(monkeypatch, mc)
    res = CliRunner().invoke(app, ["-p", "test", "inspect", "url", "https://kodeme.io/"])
    assert res.exit_code == 0, res.stdout
    assert "PASS" in res.stdout


def test_inspect_bulk(monkeypatch, tmp_path: Path) -> None:
    urls = tmp_path / "urls.txt"
    urls.write_text("https://kodeme.io/a\nhttps://kodeme.io/b\n")

    mc = MagicMock()
    mc.url_inspection.return_value.inspect.return_value.execute.return_value = {
        "inspectionResult": {
            "indexStatusResult": {"verdict": "PASS", "googleCanonical": "x", "lastCrawlTime": "t"},
            "mobileUsabilityResult": {"verdict": "PASS"},
        }
    }
    _inject(monkeypatch, mc)
    monkeypatch.setattr("kctl_gsc.commands.inspect._sleep", lambda _: None)
    res = CliRunner().invoke(app, ["-p", "test", "inspect", "bulk", str(urls)])
    assert res.exit_code == 0, res.stdout
    assert mc.url_inspection.return_value.inspect.call_count == 2


def test_inspect_request_index(monkeypatch) -> None:
    mc = MagicMock()
    mc.url_inspection.return_value.inspect.return_value.execute.return_value = {
        "inspectionResult": {
            "indexStatusResult": {
                "verdict": "PASS",
                "googleCanonical": "https://kodeme.io/",
                "lastCrawlTime": "2026-04-10T00:00:00Z",
            },
            "mobileUsabilityResult": {"verdict": "PASS"},
        }
    }
    _inject(monkeypatch, mc)
    res = CliRunner().invoke(app, ["-p", "test", "inspect", "request-index", "https://kodeme.io/"])
    assert res.exit_code == 0, res.stdout
