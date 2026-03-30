"""Tests for enhanced accounting/expense commands."""

from __future__ import annotations

from unittest.mock import MagicMock

import click
import typer

from kctl_odoo.core.callbacks import AppContext


def _exit_codes():
    """Return exception types that represent a CLI exit."""
    return (SystemExit, click.exceptions.Exit)


def _make_actx(client=None):
    actx = MagicMock(spec=AppContext)
    actx.json_mode = False
    actx.client = client or MagicMock()
    from kctl_common import Output

    actx.output = Output(json_mode=False)
    return actx


def _make_ctx(actx):
    ctx = MagicMock(spec=typer.Context)
    ctx.obj = actx
    return ctx


class TestRevalueCurrency:
    def test_import(self):
        from kctl_odoo.commands.accounting_cmd import revalue_currency

        assert callable(revalue_currency)

    def test_no_accounting_module(self):
        from kctl_odoo.commands.accounting_cmd import revalue_currency

        client = MagicMock()
        client.execute_kw.return_value = []  # fields_get returns nothing → model unavailable
        client.search_count.return_value = 0
        actx = _make_actx(client)
        ctx = _make_ctx(actx)

        # model_available returns False → early exit
        import kctl_odoo.commands.accounting_cmd as mod

        orig = mod.model_available
        mod.model_available = lambda _c, _m: False
        try:
            try:
                revalue_currency(ctx, date=None, dry_run=False)
            except (SystemExit, click.exceptions.Exit):
                pass
        finally:
            mod.model_available = orig


class TestBankStatus:
    def test_import(self):
        from kctl_odoo.commands.accounting_cmd import bank_status

        assert callable(bank_status)

    def test_no_journals(self):
        from kctl_odoo.commands.accounting_cmd import bank_status

        client = MagicMock()
        client.execute_kw.return_value = {"id": {"type": "integer", "string": "ID"}}
        client.search_read.return_value = []
        actx = _make_actx(client)
        ctx = _make_ctx(actx)

        import kctl_odoo.commands.accounting_cmd as mod

        orig = mod.model_available
        mod.model_available = lambda _c, _m: True
        try:
            bank_status(ctx)
        finally:
            mod.model_available = orig


class TestGlDetail:
    def test_import(self):
        from kctl_odoo.commands.accounting_cmd import gl_detail

        assert callable(gl_detail)

    def test_account_not_found(self):
        from kctl_odoo.commands.accounting_cmd import gl_detail

        client = MagicMock()
        client.execute_kw.return_value = {"id": {"type": "integer", "string": "ID"}}
        client.search_read.return_value = []
        actx = _make_actx(client)
        ctx = _make_ctx(actx)

        import kctl_odoo.commands.accounting_cmd as mod

        orig = mod.model_available
        mod.model_available = lambda _c, _m: True
        try:
            try:
                gl_detail(ctx, account_code="999999")
            except (SystemExit, click.exceptions.Exit):
                pass
        finally:
            mod.model_available = orig


class TestAuditTrail:
    def test_import(self):
        from kctl_odoo.commands.accounting_cmd import audit_trail

        assert callable(audit_trail)

    def test_no_entries(self):
        from kctl_odoo.commands.accounting_cmd import audit_trail

        client = MagicMock()
        client.execute_kw.return_value = {"id": {"type": "integer", "string": "ID"}}
        client.search_read.return_value = []
        actx = _make_actx(client)
        ctx = _make_ctx(actx)

        import kctl_odoo.commands.accounting_cmd as mod

        orig = mod.model_available
        mod.model_available = lambda _c, _m: True
        try:
            audit_trail(ctx, invoice=None, days=7, limit=50)
        finally:
            mod.model_available = orig


class TestSubmitExpense:
    def test_import(self):
        from kctl_odoo.commands.hr_cmd import submit_expense

        assert callable(submit_expense)

    def test_sheet_not_found(self):
        from kctl_odoo.commands.hr_cmd import submit_expense

        client = MagicMock()
        client.execute_kw.return_value = {"id": {"type": "integer", "string": "ID"}}
        client.read.return_value = []
        actx = _make_actx(client)
        ctx = _make_ctx(actx)

        import kctl_odoo.commands.hr_cmd as mod

        orig = mod.model_available
        mod.model_available = lambda _c, _m: True
        try:
            try:
                submit_expense(ctx, sheet_id=999, force=False)
            except (SystemExit, click.exceptions.Exit):
                pass
        finally:
            mod.model_available = orig

    def test_wrong_state_without_force(self):
        from kctl_odoo.commands.hr_cmd import submit_expense

        client = MagicMock()
        client.execute_kw.return_value = {
            "id": {"type": "integer", "string": "ID"},
            "name": {"type": "char", "string": "Name"},
            "state": {"type": "selection", "string": "State"},
        }
        client.read.return_value = [{"id": 1, "name": "EXP/2026/001", "state": "approve", "employee_id": [5, "Alice"]}]
        actx = _make_actx(client)
        ctx = _make_ctx(actx)

        import kctl_odoo.commands.hr_cmd as mod

        orig = mod.model_available
        mod.model_available = lambda _c, _m: True
        try:
            try:
                submit_expense(ctx, sheet_id=1, force=False)
            except (SystemExit, click.exceptions.Exit):
                pass
        finally:
            mod.model_available = orig


class TestReimburseExpense:
    def test_import(self):
        from kctl_odoo.commands.hr_cmd import reimburse_expense

        assert callable(reimburse_expense)

    def test_sheet_not_found(self):
        from kctl_odoo.commands.hr_cmd import reimburse_expense

        client = MagicMock()
        client.execute_kw.return_value = {"id": {"type": "integer", "string": "ID"}}
        client.read.return_value = []
        actx = _make_actx(client)
        ctx = _make_ctx(actx)

        import kctl_odoo.commands.hr_cmd as mod

        orig = mod.model_available
        mod.model_available = lambda _c, _m: True
        try:
            try:
                reimburse_expense(ctx, sheet_id=999, journal=None, force=False)
            except (SystemExit, click.exceptions.Exit):
                pass
        finally:
            mod.model_available = orig


class TestExpenseSummary:
    def test_import(self):
        from kctl_odoo.commands.hr_cmd import expense_summary

        assert callable(expense_summary)

    def test_no_sheets(self):
        from kctl_odoo.commands.hr_cmd import expense_summary

        client = MagicMock()
        client.execute_kw.return_value = {"id": {"type": "integer", "string": "ID"}}
        client.search_read.return_value = []
        actx = _make_actx(client)
        ctx = _make_ctx(actx)

        import kctl_odoo.commands.hr_cmd as mod

        orig = mod.model_available
        mod.model_available = lambda _c, _m: True
        try:
            expense_summary(ctx, period="month")
        finally:
            mod.model_available = orig

    def test_quarter_period(self):
        from kctl_odoo.commands.hr_cmd import expense_summary

        client = MagicMock()
        client.execute_kw.return_value = {
            "id": {"type": "integer", "string": "ID"},
            "state": {"type": "selection", "string": "State"},
            "total_amount": {"type": "float", "string": "Total"},
        }
        client.search_read.return_value = [
            {"id": 1, "name": "EXP/2026/001", "state": "done", "total_amount": 500000.0, "employee_id": [1, "Bob"]},
            {"id": 2, "name": "EXP/2026/002", "state": "draft", "total_amount": 200000.0, "employee_id": [2, "Alice"]},
        ]
        actx = _make_actx(client)
        ctx = _make_ctx(actx)

        import kctl_odoo.commands.hr_cmd as mod

        orig = mod.model_available
        mod.model_available = lambda _c, _m: True
        try:
            expense_summary(ctx, period="quarter")
        finally:
            mod.model_available = orig
