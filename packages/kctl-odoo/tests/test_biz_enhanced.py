"""Tests for enhanced business operations."""

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


class TestSalesByProduct:
    def test_import(self):
        from kctl_odoo.commands.sales_cmd import by_product

        assert callable(by_product)


class TestSalesByCustomer:
    def test_import(self):
        from kctl_odoo.commands.sales_cmd import by_customer

        assert callable(by_customer)


class TestSalesTrend:
    def test_import(self):
        from kctl_odoo.commands.sales_cmd import trend

        assert callable(trend)


class TestSalesCancelOrder:
    def test_import(self):
        from kctl_odoo.commands.sales_cmd import cancel_order

        assert callable(cancel_order)


class TestSalesBySalesperson:
    def test_import(self):
        from kctl_odoo.commands.sales_cmd import by_salesperson

        assert callable(by_salesperson)


class TestSalesOrdersDateFilters:
    def test_import(self):
        from kctl_odoo.commands.sales_cmd import orders

        assert callable(orders)

    def test_has_date_params(self):
        import inspect

        from kctl_odoo.commands.sales_cmd import orders

        sig = inspect.signature(orders)
        assert "date_from" in sig.parameters
        assert "date_to" in sig.parameters


class TestPurchasingCancelOrder:
    def test_import(self):
        from kctl_odoo.commands.purchasing_cmd import cancel_order

        assert callable(cancel_order)


class TestPurchasingByVendor:
    def test_import(self):
        from kctl_odoo.commands.purchasing_cmd import by_vendor

        assert callable(by_vendor)


class TestPurchasingByProduct:
    def test_import(self):
        from kctl_odoo.commands.purchasing_cmd import by_product

        assert callable(by_product)


class TestPurchasingTrend:
    def test_import(self):
        from kctl_odoo.commands.purchasing_cmd import trend

        assert callable(trend)


class TestPurchasingOrdersDateFilters:
    def test_import(self):
        from kctl_odoo.commands.purchasing_cmd import orders

        assert callable(orders)

    def test_has_date_params(self):
        import inspect

        from kctl_odoo.commands.purchasing_cmd import orders

        sig = inspect.signature(orders)
        assert "date_from" in sig.parameters
        assert "date_to" in sig.parameters


class TestInventoryValuation:
    def test_import(self):
        from kctl_odoo.commands.inventory_cmd import valuation

        assert callable(valuation)


class TestInventoryStockMoves:
    def test_import(self):
        from kctl_odoo.commands.inventory_cmd import stock_moves

        assert callable(stock_moves)


class TestInventoryTurnover:
    def test_import(self):
        from kctl_odoo.commands.inventory_cmd import turnover

        assert callable(turnover)


class TestInventoryTransfersFilters:
    def test_import(self):
        from kctl_odoo.commands.inventory_cmd import transfers

        assert callable(transfers)

    def test_has_date_and_partner_params(self):
        import inspect

        from kctl_odoo.commands.inventory_cmd import transfers

        sig = inspect.signature(transfers)
        assert "date_from" in sig.parameters
        assert "partner" in sig.parameters
