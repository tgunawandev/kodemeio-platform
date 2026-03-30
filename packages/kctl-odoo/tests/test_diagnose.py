"""Tests for the diagnose command."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC
from unittest.mock import MagicMock

import pytest

from kctl_odoo.commands.diagnose import (
    WEIGHTS,
    DiagnosticReport,
    Finding,
    SectionResult,
    _check_configuration,
    _check_data_integrity,
    _check_dr,
    _check_financial_health,
    _check_inventory_health,
    _check_kpis,
    _check_mail,
    _check_security,
    _check_server_health,
    _check_storage,
    diagnose,
)
from kctl_odoo.core.exceptions import RPCError
from kctl_odoo.core.output import Output

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_actx(*, json_mode: bool = False, client: MagicMock | None = None) -> MagicMock:
    actx = MagicMock()
    actx.json_mode = json_mode
    actx.output = Output(json_mode=json_mode)
    actx.client = client or MagicMock()
    actx.profile = "test"
    actx.url_override = None
    actx.api_key_override = None
    actx.database_override = None
    actx.username_override = None
    return actx


def _make_ctx(actx: MagicMock) -> MagicMock:
    ctx = MagicMock()
    ctx.obj = actx
    return ctx


def _healthy_client() -> MagicMock:
    """Client that returns sane defaults for all checks."""
    c = MagicMock()
    c.database = "test_db"
    c.base_url = "https://odoo.example.com"
    c.authenticate.return_value = 2
    c.version_info.return_value = {"server_version": "18.0"}
    c.search_count.return_value = 0
    c.search_read.return_value = []
    return c


# ---------------------------------------------------------------------------
# Data-class unit tests
# ---------------------------------------------------------------------------


class TestFinding:
    def test_creation(self) -> None:
        f = Finding("critical", "server", "Down", "Cannot connect")
        assert f.severity == "critical"
        assert f.fix_command is None

    def test_with_fix(self) -> None:
        f = Finding("high", "mail", "Failed", "50 failed", fix_command="kctl-odoo mail retry-failed")
        assert f.fix_command == "kctl-odoo mail retry-failed"


class TestSectionResult:
    def test_defaults(self) -> None:
        sr = SectionResult("test", 85)
        assert sr.findings == []
        assert sr.duration_ms == 0


class TestDiagnosticReport:
    def _make_report(self) -> DiagnosticReport:
        from datetime import datetime

        return DiagnosticReport(
            profile="test",
            url="https://odoo.example.com",
            version="18.0",
            database="test_db",
            timestamp=datetime(2026, 3, 27, tzinfo=UTC),
            sections=[
                SectionResult("server_health", 100, [Finding("info", "server", "Version", "18.0")]),
                SectionResult("security", 70, [Finding("high", "security", "Too many admins", "6 admins")]),
            ],
            overall_score=85,
            duration_seconds=2.3,
        )

    def test_to_json(self) -> None:
        report = self._make_report()
        data = json.loads(report.to_json())
        assert data["overall_score"] == 85
        assert data["database"] == "test_db"
        assert len(data["sections"]) == 2

    def test_to_markdown(self) -> None:
        report = self._make_report()
        md = report.to_markdown()
        assert "# Diagnostic Report" in md
        assert "server_health" in md
        assert "Too many admins" in md

    def test_to_html(self) -> None:
        report = self._make_report()
        html = report.to_html()
        assert "<!DOCTYPE html>" in html
        assert "85/100" in html
        assert "Too many admins" in html

    def test_to_dict(self) -> None:
        report = self._make_report()
        d = report.to_dict()
        assert d["profile"] == "test"
        assert isinstance(d["timestamp"], str)


# ---------------------------------------------------------------------------
# Section check tests
# ---------------------------------------------------------------------------


class TestCheckServerHealth:
    def test_healthy(self, mock_client: MagicMock) -> None:
        result = _check_server_health(mock_client, quick=True)
        assert result.name == "server_health"
        assert result.score == 100

    def test_exception(self) -> None:
        c = MagicMock()
        c.version_info.side_effect = Exception("connection refused")
        result = _check_server_health(c)
        assert result.score == 0
        assert result.findings[0].severity == "critical"


class TestCheckConfiguration:
    def test_healthy(self) -> None:
        c = _healthy_client()
        c.search_read.return_value = [{"value": "https://odoo.example.com"}]
        result = _check_configuration(c)
        assert result.name == "configuration"
        assert result.score > 0

    def test_exception(self) -> None:
        c = MagicMock()
        c.search_read.side_effect = Exception("boom")
        result = _check_configuration(c)
        assert result.score == 0


class TestCheckSecurity:
    def test_healthy(self) -> None:
        c = _healthy_client()
        # search_read is called multiple times; first for admin groups, then config params
        c.search_read.side_effect = [
            [{"users": [1, 2]}],  # admin groups
            [{"value": "https://odoo.example.com"}],  # web.base.url
            [{"value": "b2b"}],  # signup scope
        ]
        result = _check_security(c)
        assert result.name == "security"
        assert result.score > 0

    def test_exception(self) -> None:
        c = MagicMock()
        c.search_read.side_effect = Exception("boom")
        result = _check_security(c)
        assert result.score == 0


class TestCheckDataIntegrity:
    def test_clean(self) -> None:
        c = _healthy_client()
        result = _check_data_integrity(c)
        assert result.name == "data_integrity"
        assert result.score == 100

    def test_negative_stock(self) -> None:
        c = _healthy_client()

        def _count(model: str, domain: list) -> int:
            if model == "stock.quant":
                return 3
            return 0

        c.search_count.side_effect = _count
        result = _check_data_integrity(c)
        assert result.score < 100
        assert any("Negative stock" in f.title for f in result.findings)


class TestCheckFinancialHealth:
    def test_clean(self) -> None:
        c = _healthy_client()
        result = _check_financial_health(c, quick=True)
        assert result.name == "financial_health"
        assert result.score == 100

    def test_exception(self) -> None:
        c = MagicMock()
        c.search_count.side_effect = Exception("boom")
        c.search_read.side_effect = Exception("boom")
        result = _check_financial_health(c)
        assert result.score == 0


class TestCheckInventoryHealth:
    def test_stock_not_installed(self) -> None:
        c = _healthy_client()
        c.search_count.side_effect = RPCError({"message": "Model not found"})
        result = _check_inventory_health(c)
        # stock.quant returns None => module not installed => score 100
        assert result.score == 100

    def test_clean(self) -> None:
        c = _healthy_client()
        result = _check_inventory_health(c, quick=True)
        assert result.score == 100


class TestCheckKpis:
    def test_no_modules(self) -> None:
        c = _healthy_client()
        c.search_count.side_effect = RPCError({"message": "not found"})
        result = _check_kpis(c)
        assert result.score == 100  # no data => no failures

    def test_exception(self) -> None:
        c = MagicMock()
        c.search_count.side_effect = Exception("total failure")
        result = _check_kpis(c)
        assert result.score == 0


class TestCheckMail:
    def test_healthy(self) -> None:
        c = _healthy_client()

        def _count(model: str, domain: list) -> int:
            if model == "ir.mail_server":
                return 1
            return 0

        c.search_count.side_effect = _count
        result = _check_mail(c)
        assert result.score == 100

    def test_no_smtp(self) -> None:
        c = _healthy_client()
        result = _check_mail(c)
        assert result.score < 100
        assert any("No SMTP" in f.title for f in result.findings)


class TestCheckStorage:
    def test_clean(self) -> None:
        c = _healthy_client()
        result = _check_storage(c)
        assert result.name == "storage"
        assert result.score == 100


class TestCheckDR:
    def test_no_backup(self) -> None:
        c = _healthy_client()
        result = _check_dr(c)
        assert result.score < 100


# ---------------------------------------------------------------------------
# Weights
# ---------------------------------------------------------------------------


class TestWeights:
    def test_all_sections_have_weights(self) -> None:
        from kctl_odoo.commands.diagnose import SECTION_CHECKS

        for name, _ in SECTION_CHECKS:
            assert name in WEIGHTS, f"Missing weight for section: {name}"

    def test_weights_sum_to_100(self) -> None:
        assert sum(WEIGHTS.values()) == 100


# ---------------------------------------------------------------------------
# Integration: diagnose command
# ---------------------------------------------------------------------------


class TestDiagnoseCommand:
    def test_json_output(self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        mock_client.base_url = "https://odoo.example.com"
        actx = _make_actx(json_mode=True, client=mock_client)
        ctx = _make_ctx(actx)

        diagnose(ctx, output=None, quick=True, section_filter="server_health,mail")

        captured = capsys.readouterr().out
        data = json.loads(captured)
        assert "overall_score" in data
        assert "sections" in data

    def test_file_output_json(self, mock_client: MagicMock) -> None:
        mock_client.base_url = "https://odoo.example.com"
        actx = _make_actx(client=mock_client)
        ctx = _make_ctx(actx)

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name

        try:
            diagnose(ctx, output=path, quick=True, section_filter="server_health")
            with open(path) as fh:
                data = json.loads(fh.read())
            assert data["overall_score"] >= 0
        finally:
            os.unlink(path)

    def test_file_output_md(self, mock_client: MagicMock) -> None:
        mock_client.base_url = "https://odoo.example.com"
        actx = _make_actx(client=mock_client)
        ctx = _make_ctx(actx)

        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
            path = f.name

        try:
            diagnose(ctx, output=path, quick=True, section_filter="server_health")
            with open(path) as fh:
                content = fh.read()
            assert "# Diagnostic Report" in content
        finally:
            os.unlink(path)

    def test_file_output_html(self, mock_client: MagicMock) -> None:
        mock_client.base_url = "https://odoo.example.com"
        actx = _make_actx(client=mock_client)
        ctx = _make_ctx(actx)

        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name

        try:
            diagnose(ctx, output=path, quick=True, section_filter="server_health")
            with open(path) as fh:
                content = fh.read()
            assert "<!DOCTYPE html>" in content
        finally:
            os.unlink(path)

    def test_section_filter(self, mock_client: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        mock_client.base_url = "https://odoo.example.com"
        actx = _make_actx(json_mode=True, client=mock_client)
        ctx = _make_ctx(actx)

        diagnose(ctx, output=None, quick=False, section_filter="mail,storage")

        data = json.loads(capsys.readouterr().out)
        section_names = [s["name"] for s in data["sections"]]
        assert set(section_names) == {"mail", "storage"}

    def test_pretty_output(self, mock_client: MagicMock) -> None:
        """Ensure pretty mode doesn't crash."""
        mock_client.base_url = "https://odoo.example.com"
        actx = _make_actx(client=mock_client)
        ctx = _make_ctx(actx)

        # Should not raise
        diagnose(ctx, output=None, quick=True, section_filter="server_health")
