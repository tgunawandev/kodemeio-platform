"""Tests for website command group."""

from __future__ import annotations

from unittest.mock import MagicMock

import typer

from kctl_odoo.core.callbacks import AppContext


def _make_actx(client: MagicMock | None = None) -> AppContext:
    actx = MagicMock(spec=AppContext)
    actx.json_mode = False
    actx.client = client or MagicMock()
    from kctl_common import Output

    actx.output = Output(json_mode=False)
    return actx


def _make_ctx(actx: AppContext) -> typer.Context:
    ctx = MagicMock(spec=typer.Context)
    ctx.obj = actx
    return ctx


class TestWebsiteImport:
    def test_import_app(self) -> None:
        from kctl_odoo.commands.website_cmd import app

        assert app is not None


class TestWebsiteSummary:
    def test_summary_no_website(self) -> None:
        """summary should handle website not installed."""
        c = MagicMock()
        c.search_count.return_value = 0
        actx = _make_actx(client=c)
        from kctl_odoo.commands.website_cmd import summary

        ctx = _make_ctx(actx)
        summary(ctx)

    def test_summary_with_website(self) -> None:
        """summary should display counts when website is installed."""
        c = MagicMock()
        c.search_count.return_value = 5
        actx = _make_actx(client=c)
        from kctl_odoo.commands.website_cmd import summary

        ctx = _make_ctx(actx)
        summary(ctx)


class TestWebsitePages:
    def test_pages_empty(self) -> None:
        c = MagicMock()
        c.search_read.return_value = []
        c.search_count.return_value = 0
        actx = _make_actx(client=c)
        from kctl_odoo.commands.website_cmd import pages

        ctx = _make_ctx(actx)
        pages(ctx, published=None, limit=50)

    def test_pages_with_results(self) -> None:
        c = MagicMock()
        c.search_count.return_value = 1
        c.search_read.return_value = [
            {
                "id": 1,
                "name": "Home",
                "url": "/",
                "website_published": True,
                "website_id": [1, "My Website"],
                "date_publish": "2024-01-01",
            }
        ]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.website_cmd import pages

        ctx = _make_ctx(actx)
        pages(ctx, published=True, limit=50)

    def test_pages_not_installed(self) -> None:
        """pages should warn when website model is not available."""
        from kctl_odoo.core.exceptions import RPCError

        c = MagicMock()
        c.search_count.side_effect = RPCError({"message": "website not installed"})
        actx = _make_actx(client=c)
        from kctl_odoo.commands.website_cmd import pages

        ctx = _make_ctx(actx)
        pages(ctx, published=None, limit=50)


class TestWebsiteProducts:
    def test_products_empty(self) -> None:
        c = MagicMock()
        c.search_count.return_value = 1
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.website_cmd import products

        ctx = _make_ctx(actx)
        products(ctx, published=None, limit=50)

    def test_products_with_results(self) -> None:
        c = MagicMock()
        c.search_count.return_value = 1
        c.search_read.return_value = [
            {
                "id": 1,
                "name": "Widget A",
                "list_price": 99.99,
                "website_published": True,
                "website_url": "/shop/widget-a",
            }
        ]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.website_cmd import products

        ctx = _make_ctx(actx)
        products(ctx, published=True, limit=50)


class TestWebsitePublish:
    def test_publish_records(self) -> None:
        c = MagicMock()
        c.search_count.return_value = 1
        c.execute_kw.return_value = True
        actx = _make_actx(client=c)
        from kctl_odoo.commands.website_cmd import publish

        ctx = _make_ctx(actx)
        publish(ctx, model="website.page", ids="1,2,3")

    def test_publish_invalid_ids(self) -> None:
        import pytest

        c = MagicMock()
        c.search_count.return_value = 1
        actx = _make_actx(client=c)
        from kctl_odoo.commands.website_cmd import publish

        ctx = _make_ctx(actx)
        with pytest.raises((SystemExit, typer.Exit)):
            publish(ctx, model="website.page", ids="abc,def")


class TestWebsiteUnpublish:
    def test_unpublish_records(self) -> None:
        c = MagicMock()
        c.search_count.return_value = 1
        c.execute_kw.return_value = True
        actx = _make_actx(client=c)
        from kctl_odoo.commands.website_cmd import unpublish

        ctx = _make_ctx(actx)
        unpublish(ctx, model="product.template", ids="42")


class TestWebsiteOrders:
    def test_orders_empty(self) -> None:
        c = MagicMock()
        c.search_count.return_value = 1
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.website_cmd import orders

        ctx = _make_ctx(actx)
        orders(ctx, state=None, limit=50)

    def test_orders_with_results(self) -> None:
        c = MagicMock()
        c.search_count.return_value = 1
        c.search_read.return_value = [
            {
                "id": 1,
                "name": "S00001",
                "partner_id": [5, "John Doe"],
                "date_order": "2024-01-15 10:00:00",
                "amount_total": 150.0,
                "state": "sale",
            }
        ]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.website_cmd import orders

        ctx = _make_ctx(actx)
        orders(ctx, state="sale", limit=50)


class TestWebsiteVisitors:
    def test_visitors_no_model(self) -> None:
        """visitors should warn when website.visitor model is missing."""
        from kctl_odoo.core.exceptions import RPCError

        c = MagicMock()

        def search_count_side_effect(model: str, domain: list) -> int:
            if model == "website.visitor":
                raise RPCError({"message": "not found"})
            return 1

        c.search_count.side_effect = search_count_side_effect
        actx = _make_actx(client=c)
        from kctl_odoo.commands.website_cmd import visitors

        ctx = _make_ctx(actx)
        visitors(ctx, days=7)

    def test_visitors_with_data(self) -> None:
        c = MagicMock()
        c.search_count.return_value = 42
        actx = _make_actx(client=c)
        from kctl_odoo.commands.website_cmd import visitors

        ctx = _make_ctx(actx)
        visitors(ctx, days=30)


class TestWebsiteMenus:
    def test_menus_empty(self) -> None:
        c = MagicMock()
        c.search_count.return_value = 1
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.website_cmd import menus

        ctx = _make_ctx(actx)
        menus(ctx)

    def test_menus_nested(self) -> None:
        c = MagicMock()
        c.search_count.return_value = 1
        c.search_read.return_value = [
            {"id": 1, "name": "Home", "url": "/", "parent_id": False, "sequence": 10},
            {"id": 2, "name": "Shop", "url": "/shop", "parent_id": False, "sequence": 20},
            {
                "id": 3,
                "name": "Category A",
                "url": "/shop/cat-a",
                "parent_id": [2, "Shop"],
                "sequence": 10,
            },
        ]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.website_cmd import menus

        ctx = _make_ctx(actx)
        menus(ctx)


class TestWebsiteRedirects:
    def test_redirects_no_model(self) -> None:
        """redirects should warn when neither redirect model is available."""
        from kctl_odoo.core.exceptions import RPCError

        c = MagicMock()

        def search_count_side_effect(model: str, domain: list) -> int:
            if model in ("website.rewrite", "website.redirect"):
                raise RPCError({"message": "not found"})
            return 1

        c.search_count.side_effect = search_count_side_effect
        actx = _make_actx(client=c)
        from kctl_odoo.commands.website_cmd import redirects

        ctx = _make_ctx(actx)
        redirects(ctx, limit=50)

    def test_redirects_with_results(self) -> None:

        c = MagicMock()

        def search_count_side_effect(model: str, domain: list) -> int:
            # First call: website model check, second: website.rewrite check
            return 1

        c.search_count.side_effect = search_count_side_effect
        c.search_read.return_value = [
            {
                "id": 1,
                "name": "Old page redirect",
                "url_from": "/old-page",
                "url_to": "/new-page",
                "redirect_type": "301",
            }
        ]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.website_cmd import redirects

        ctx = _make_ctx(actx)
        redirects(ctx, limit=50)
