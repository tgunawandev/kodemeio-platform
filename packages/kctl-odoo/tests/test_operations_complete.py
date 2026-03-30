"""Tests for products, crm, delivery command groups."""

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


# ==========================================================================
# Products
# ==========================================================================


class TestProductsList:
    def test_import(self):
        from kctl_odoo.commands.products_cmd import app

        assert app is not None

    def test_list_empty(self):
        c = MagicMock()
        c.search_read.return_value = []
        c.execute_kw.return_value = {
            "display_name": {"type": "char"},
            "default_code": {"type": "char"},
            "list_price": {"type": "float"},
            "type": {"type": "selection"},
            "categ_id": {"type": "many2one"},
            "active": {"type": "boolean"},
        }
        actx = _make_actx(client=c)
        from kctl_odoo.commands.products_cmd import list_products

        ctx = _make_ctx(actx)
        list_products(ctx, category=None, product_type=None, limit=50)


class TestProductsSearch:
    def test_import(self):
        from kctl_odoo.commands.products_cmd import search

        assert callable(search)

    def test_search_empty(self):
        c = MagicMock()
        c.search_read.return_value = []
        c.execute_kw.return_value = {"display_name": {"type": "char"}}
        actx = _make_actx(client=c)
        from kctl_odoo.commands.products_cmd import search

        ctx = _make_ctx(actx)
        search(ctx, query="nonexistent", limit=20)


class TestProductsBarcode:
    def test_import(self):
        from kctl_odoo.commands.products_cmd import barcode_lookup

        assert callable(barcode_lookup)

    def test_barcode_empty(self):
        c = MagicMock()
        c.search_read.return_value = []
        c.execute_kw.return_value = {"display_name": {"type": "char"}}
        actx = _make_actx(client=c)
        from kctl_odoo.commands.products_cmd import barcode_lookup

        ctx = _make_ctx(actx)
        barcode_lookup(ctx, barcode="0000000000000")


class TestProductsCategories:
    def test_import(self):
        from kctl_odoo.commands.products_cmd import categories

        assert callable(categories)

    def test_categories_empty(self):
        c = MagicMock()
        c.search_read.return_value = []
        c.execute_kw.return_value = {"display_name": {"type": "char"}}
        actx = _make_actx(client=c)
        from kctl_odoo.commands.products_cmd import categories

        ctx = _make_ctx(actx)
        categories(ctx, limit=50)


class TestProductsByCategory:
    def test_import(self):
        from kctl_odoo.commands.products_cmd import by_category

        assert callable(by_category)

    def test_by_category_empty(self):
        c = MagicMock()
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.products_cmd import by_category

        ctx = _make_ctx(actx)
        by_category(ctx, limit=20)


class TestProductsLowMargin:
    def test_import(self):
        from kctl_odoo.commands.products_cmd import low_margin

        assert callable(low_margin)

    def test_low_margin_empty(self):
        c = MagicMock()
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.products_cmd import low_margin

        ctx = _make_ctx(actx)
        low_margin(ctx, threshold=10.0, limit=20)


# ==========================================================================
# CRM
# ==========================================================================


class TestCrmImport:
    def test_import(self):
        from kctl_odoo.commands.crm_cmd import app

        assert app is not None


class TestCrmPipeline:
    def test_no_crm(self):
        c = MagicMock()
        c.search_read.return_value = []
        # model_available check — raise RPCError to simulate not installed
        from kctl_odoo.core.exceptions import RPCError

        c.search_count.side_effect = RPCError({"message": "crm not installed", "code": 404, "data": {}})
        actx = _make_actx(client=c)
        from kctl_odoo.commands.crm_cmd import pipeline

        ctx = _make_ctx(actx)
        pipeline(ctx)

    def test_pipeline_empty(self):
        c = MagicMock()
        # model_available returns True
        c.search_count.return_value = 0
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.crm_cmd import pipeline

        ctx = _make_ctx(actx)
        pipeline(ctx)


class TestCrmCreateLead:
    def test_import(self):
        from kctl_odoo.commands.crm_cmd import create_lead

        assert callable(create_lead)


class TestCrmLeads:
    def test_import(self):
        from kctl_odoo.commands.crm_cmd import leads

        assert callable(leads)


class TestCrmOpportunities:
    def test_import(self):
        from kctl_odoo.commands.crm_cmd import opportunities

        assert callable(opportunities)


class TestCrmActivities:
    def test_import(self):
        from kctl_odoo.commands.crm_cmd import activities

        assert callable(activities)

    def test_activities_empty(self):
        c = MagicMock()
        c.search_read.return_value = []
        c.execute_kw.return_value = {"display_name": {"type": "char"}}
        actx = _make_actx(client=c)
        from kctl_odoo.commands.crm_cmd import activities

        ctx = _make_ctx(actx)
        activities(ctx, user=None, overdue=False, limit=50)


# ==========================================================================
# Delivery
# ==========================================================================


class TestDeliveryImport:
    def test_import(self):
        from kctl_odoo.commands.delivery_cmd import app

        assert app is not None


class TestDeliveryList:
    def test_list_empty(self):
        c = MagicMock()
        c.search_read.return_value = []
        c.execute_kw.return_value = {"display_name": {"type": "char"}}
        actx = _make_actx(client=c)
        from kctl_odoo.commands.delivery_cmd import list_deliveries

        ctx = _make_ctx(actx)
        list_deliveries(ctx, state=None, carrier=None, date_from=None, limit=50)


class TestDeliveryPerformance:
    def test_import(self):
        from kctl_odoo.commands.delivery_cmd import performance

        assert callable(performance)

    def test_performance_empty(self):
        c = MagicMock()
        c.search_read.return_value = []
        c.execute_kw.return_value = {"name": {"type": "char"}}
        actx = _make_actx(client=c)
        from kctl_odoo.commands.delivery_cmd import performance

        ctx = _make_ctx(actx)
        performance(ctx, days=30)


class TestDeliveryPending:
    def test_import(self):
        from kctl_odoo.commands.delivery_cmd import pending

        assert callable(pending)

    def test_pending_empty(self):
        c = MagicMock()
        c.search_read.return_value = []
        c.execute_kw.return_value = {"display_name": {"type": "char"}}
        actx = _make_actx(client=c)
        from kctl_odoo.commands.delivery_cmd import pending

        ctx = _make_ctx(actx)
        pending(ctx, days=3)


class TestDeliveryReturns:
    def test_import(self):
        from kctl_odoo.commands.delivery_cmd import returns

        assert callable(returns)

    def test_returns_empty(self):
        c = MagicMock()
        c.search_read.return_value = []
        c.execute_kw.return_value = {"display_name": {"type": "char"}}
        actx = _make_actx(client=c)
        from kctl_odoo.commands.delivery_cmd import returns

        ctx = _make_ctx(actx)
        returns(ctx, limit=50)


class TestDeliveryCarriers:
    def test_import(self):
        from kctl_odoo.commands.delivery_cmd import carriers

        assert callable(carriers)

    def test_carriers_not_installed(self):
        c = MagicMock()
        # model_available check raises RPCError to simulate module not installed
        from kctl_odoo.core.exceptions import RPCError

        c.search_count.side_effect = RPCError({"message": "delivery.carrier not found", "code": 404, "data": {}})
        actx = _make_actx(client=c)
        from kctl_odoo.commands.delivery_cmd import carriers

        ctx = _make_ctx(actx)
        carriers(ctx)
