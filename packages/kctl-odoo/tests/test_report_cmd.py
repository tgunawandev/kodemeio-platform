"""Tests for the report template command group (report_cmd.py)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
import typer

from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.exceptions import RPCError


def _make_actx(client=None):
    actx = MagicMock(spec=AppContext)
    actx.json_mode = False
    actx.client = client or MagicMock()
    from kctl_lib import Output

    actx.output = Output(json_mode=False)
    return actx


def _make_ctx(actx):
    ctx = MagicMock(spec=typer.Context)
    ctx.obj = actx
    return ctx


class TestReportCmdImport:
    def test_module_imports(self):
        from kctl_odoo.commands.report_cmd import app

        assert app is not None

    def test_commands_exist(self):
        from kctl_odoo.commands.report_cmd import (
            clone_template,
            delete_template,
            export_template,
            import_template,
            library_install,
            library_list,
            list_templates,
            show_template,
        )

        assert callable(list_templates)
        assert callable(export_template)
        assert callable(import_template)
        assert callable(clone_template)
        assert callable(library_list)
        assert callable(library_install)
        assert callable(show_template)
        assert callable(delete_template)


class TestModelAvailabilityGuard:
    """Every command body short-circuits when report.template is missing."""

    def _client_without_report_template(self):
        c = MagicMock()
        c.search_count.side_effect = RPCError({"message": "model not found"})
        return c

    def test_list_missing_module_exits(self):
        from kctl_odoo.commands.report_cmd import list_templates

        actx = _make_actx(client=self._client_without_report_template())
        with pytest.raises(typer.Exit):
            list_templates(_make_ctx(actx))

    def test_export_missing_module_exits(self):
        from kctl_odoo.commands.report_cmd import export_template

        actx = _make_actx(client=self._client_without_report_template())
        with pytest.raises(typer.Exit):
            export_template(_make_ctx(actx), code="pnl_management", output=None)

    def test_library_missing_module_exits(self):
        from kctl_odoo.commands.report_cmd import library_list

        actx = _make_actx(client=self._client_without_report_template())
        with pytest.raises(typer.Exit):
            library_list(_make_ctx(actx))


class TestRecordIdHelper:
    def test_record_id_handles_int(self):
        from kctl_odoo.commands.report_cmd import _record_id

        assert _record_id(42) == 42

    def test_record_id_handles_list(self):
        from kctl_odoo.commands.report_cmd import _record_id

        assert _record_id([42]) == 42

    def test_record_id_handles_empty(self):
        from kctl_odoo.commands.report_cmd import _record_id

        assert _record_id([]) is None
        assert _record_id(None) is None


class TestListRendersTable:
    def test_list_shows_templates(self, capsys):
        from kctl_odoo.commands.report_cmd import list_templates

        c = MagicMock()
        c.search_count.return_value = 0  # model_available check passes
        c.search_read.return_value = [
            {
                "id": 1,
                "code": "pnl_management",
                "name": "Profit & Loss",
                "category": "financial",
                "report_type": "profit_loss",
                "company_id": [1, "Test Co"],
                "sequence": 10,
            }
        ]
        actx = _make_actx(client=c)
        list_templates(_make_ctx(actx), category=None, report_type=None)
        out = capsys.readouterr().out
        assert "pnl_management" in out


class TestImportValidatesFile:
    def test_import_missing_file_exits(self, tmp_path):
        from kctl_odoo.commands.report_cmd import import_template

        c = MagicMock()
        c.search_count.return_value = 0
        actx = _make_actx(client=c)
        missing = tmp_path / "nope.json"
        with pytest.raises(typer.Exit):
            import_template(_make_ctx(actx), file=missing, update=False)

    def test_import_invalid_json_exits(self, tmp_path):
        from kctl_odoo.commands.report_cmd import import_template

        c = MagicMock()
        c.search_count.return_value = 0
        actx = _make_actx(client=c)
        bad = tmp_path / "bad.json"
        bad.write_text("{not-json", encoding="utf-8")
        with pytest.raises(typer.Exit):
            import_template(_make_ctx(actx), file=bad, update=False)

    def test_import_missing_code_exits(self, tmp_path):
        from kctl_odoo.commands.report_cmd import import_template

        c = MagicMock()
        c.search_count.return_value = 0
        actx = _make_actx(client=c)
        f = tmp_path / "no_code.json"
        f.write_text('{"name": "No code here"}', encoding="utf-8")
        with pytest.raises(typer.Exit):
            import_template(_make_ctx(actx), file=f, update=False)


class TestExportCallsRPC:
    def test_export_calls_export_json(self, tmp_path):
        from kctl_odoo.commands.report_cmd import export_template

        c = MagicMock()
        c.search_count.return_value = 0
        c.search.return_value = [7]
        c.execute_kw.return_value = {
            "code": "pnl_management",
            "name": "P&L",
            "category": "financial",
            "report_type": "profit_loss",
            "sequence": 10,
            "lines": [],
            "subkpis": [],
            "schema_version": 1,
        }
        actx = _make_actx(client=c)
        out = tmp_path / "pnl.json"
        export_template(_make_ctx(actx), code="pnl_management", output=out)
        c.execute_kw.assert_called_once_with("report.template", "export_json", [[7]])
        assert out.exists()


class TestLibraryListCallsRPC:
    def test_library_list_uses_api_model_call(self):
        from kctl_odoo.commands.report_cmd import library_list

        c = MagicMock()
        c.search_count.return_value = 0
        c.execute_kw.return_value = []
        actx = _make_actx(client=c)
        library_list(_make_ctx(actx))
        # @api.model → args == [] (no recordset).
        c.execute_kw.assert_called_once_with("report.template", "library_list", [])
