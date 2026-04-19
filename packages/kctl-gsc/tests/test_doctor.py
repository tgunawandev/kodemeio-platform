"""Tests for `kctl-gsc doctor` — 5 diagnostic checks."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

from typer.testing import CliRunner

from kctl_gsc.cli import app


def _inject(monkeypatch, mc, creds_path: Path):
    from kctl_gsc.core import callbacks as cb

    monkeypatch.setattr(cb.AppContext, "client", property(lambda self: mc))
    monkeypatch.setattr(cb.AppContext, "property", property(lambda self: "sc-domain:kodeme.io"))
    monkeypatch.setattr(
        "kctl_gsc.commands.doctor_cmd.resolve_connection",
        lambda **kw: (str(creds_path), "sc-domain:kodeme.io"),
    )


def test_doctor_all_green(monkeypatch, tmp_path: Path) -> None:
    sa = tmp_path / "sa.json"
    sa.write_text(json.dumps({"type": "service_account", "client_email": "sa@p.iam.gserviceaccount.com"}))

    mc = MagicMock()
    mc.service_account_email = "sa@p.iam.gserviceaccount.com"
    mc.sites.return_value.list.return_value.execute.return_value = {
        "siteEntry": [{"siteUrl": "sc-domain:kodeme.io", "permissionLevel": "siteOwner"}]
    }
    recent = (datetime.now(UTC) - timedelta(days=1)).isoformat().replace("+00:00", "Z")
    mc.sitemaps.return_value.list.return_value.execute.return_value = {
        "sitemap": [{"path": "https://kodeme.io/sitemap.xml", "lastSubmitted": recent, "isPending": False}]
    }
    _inject(monkeypatch, mc, sa)

    res = CliRunner().invoke(app, ["-p", "test", "doctor"])
    assert res.exit_code == 0, res.stdout
    for marker in ("credentials", "auth", "property", "sitemaps"):
        assert marker in res.stdout.lower()


def test_doctor_flags_stale_sitemap(monkeypatch, tmp_path: Path) -> None:
    sa = tmp_path / "sa.json"
    sa.write_text(json.dumps({"type": "service_account", "client_email": "sa@p.iam.gserviceaccount.com"}))
    mc = MagicMock()
    mc.service_account_email = "sa@p.iam.gserviceaccount.com"
    mc.sites.return_value.list.return_value.execute.return_value = {
        "siteEntry": [{"siteUrl": "sc-domain:kodeme.io", "permissionLevel": "siteOwner"}]
    }
    stale = (datetime.now(UTC) - timedelta(days=30)).isoformat().replace("+00:00", "Z")
    mc.sitemaps.return_value.list.return_value.execute.return_value = {
        "sitemap": [{"path": "https://kodeme.io/sitemap.xml", "lastSubmitted": stale, "isPending": False}]
    }
    _inject(monkeypatch, mc, sa)

    res = CliRunner().invoke(app, ["-p", "test", "doctor"])
    assert res.exit_code == 0
    assert "stale" in res.stdout.lower() or "warn" in res.stdout.lower()
