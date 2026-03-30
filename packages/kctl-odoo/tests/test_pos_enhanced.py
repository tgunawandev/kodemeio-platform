"""Tests for enhanced POS commands."""

from __future__ import annotations

from unittest.mock import MagicMock

import typer

from kctl_odoo.core.callbacks import AppContext


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


class TestCashControl:
    def test_import(self):
        from kctl_odoo.commands.pos_cmd import cash_control

        assert callable(cash_control)


class TestReconcile:
    def test_import(self):
        from kctl_odoo.commands.pos_cmd import reconcile

        assert callable(reconcile)


class TestOrderLines:
    def test_import(self):
        from kctl_odoo.commands.pos_cmd import order_lines

        assert callable(order_lines)


class TestTraceOrder:
    def test_import(self):
        from kctl_odoo.commands.pos_cmd import trace_order

        assert callable(trace_order)


class TestRefunds:
    def test_import(self):
        from kctl_odoo.commands.pos_cmd import refunds

        assert callable(refunds)

    def test_no_refunds(self):
        c = MagicMock()
        c.search_count.return_value = 0
        c.search_read.return_value = []
        # model_available check
        c.execute_kw.return_value = {"id": {"type": "integer", "string": "ID"}}
        actx = _make_actx(client=c)
        from kctl_odoo.commands.pos_cmd import refunds

        ctx = _make_ctx(actx)
        refunds(ctx, date_from=None, limit=50)


class TestCashierSummary:
    def test_import(self):
        from kctl_odoo.commands.pos_cmd import cashier_summary

        assert callable(cashier_summary)


class TestTopProducts:
    def test_import(self):
        from kctl_odoo.commands.pos_cmd import top_products

        assert callable(top_products)


class TestHourlySales:
    def test_import(self):
        from kctl_odoo.commands.pos_cmd import hourly_sales

        assert callable(hourly_sales)


class TestDebugSession:
    def test_import(self):
        from kctl_odoo.commands.pos_cmd import debug_session

        assert callable(debug_session)


class TestValidateClose:
    def test_import(self):
        from kctl_odoo.commands.pos_cmd import validate_close

        assert callable(validate_close)


class TestTaxSummary:
    def test_import(self):
        from kctl_odoo.commands.pos_cmd import tax_summary

        assert callable(tax_summary)


class TestPeriodReport:
    def test_import(self):
        from kctl_odoo.commands.pos_cmd import period_report

        assert callable(period_report)


class TestOrphanOrders:
    def test_import(self):
        from kctl_odoo.commands.pos_cmd import orphan_orders

        assert callable(orphan_orders)


class TestConfigDetail:
    def test_import(self):
        from kctl_odoo.commands.pos_cmd import config_detail

        assert callable(config_detail)
