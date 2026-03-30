"""Tests for currency command group."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
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


class TestCurrencyImport:
    def test_import(self):
        from kctl_odoo.commands.currency_cmd import app

        assert app is not None

    def test_commands_exist(self):
        from kctl_odoo.commands.currency_cmd import add, check_stale, rates, update

        assert callable(rates)
        assert callable(update)
        assert callable(add)
        assert callable(check_stale)


class TestCurrencyRates:
    def test_rates_empty(self):
        c = MagicMock()
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.currency_cmd import rates

        ctx = _make_ctx(actx)
        rates(ctx, code=None, days=30, limit=50)

    def test_rates_with_data(self):
        c = MagicMock()
        c.search_read.return_value = [
            {
                "id": 1,
                "currency_id": [1, "IDR"],
                "name": "2026-03-28",
                "rate": 15800.0,
                "company_id": [1, "My Company"],
            }
        ]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.currency_cmd import rates

        ctx = _make_ctx(actx)
        rates(ctx, code=None, days=30, limit=50)

    def test_rates_with_code_filter(self):
        c = MagicMock()
        # First call: search currency by code
        c.search_read.side_effect = [
            [{"id": 2, "name": "EUR"}],  # currency lookup
            [{"id": 1, "currency_id": [2, "EUR"], "name": "2026-03-28", "rate": 1.08, "company_id": [1, "Test"]}],
        ]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.currency_cmd import rates

        ctx = _make_ctx(actx)
        rates(ctx, code="EUR", days=30, limit=50)

    def test_rates_with_unknown_code_exits(self):
        c = MagicMock()
        c.search_read.return_value = []  # currency not found
        actx = _make_actx(client=c)
        from kctl_odoo.commands.currency_cmd import rates

        ctx = _make_ctx(actx)
        with pytest.raises(typer.Exit):
            rates(ctx, code="XYZ", days=30, limit=50)


class TestCurrencyUpdate:
    def test_update_no_cron(self):
        c = MagicMock()
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.currency_cmd import update

        ctx = _make_ctx(actx)
        with pytest.raises(typer.Exit):
            update(ctx, force=False)

    def test_update_triggers_cron(self):
        c = MagicMock()
        c.search_read.return_value = [{"id": 5, "name": "Update Currency Rates", "active": True, "lastcall": None}]
        c.execute_kw.return_value = True
        actx = _make_actx(client=c)
        from kctl_odoo.commands.currency_cmd import update

        ctx = _make_ctx(actx)
        update(ctx, force=False)
        c.execute_kw.assert_called_once_with("ir.cron", "method_direct_trigger", [[5]])

    def test_update_inactive_without_force_exits(self):
        c = MagicMock()
        c.search_read.return_value = [{"id": 5, "name": "Currency Rates", "active": False, "lastcall": None}]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.currency_cmd import update

        ctx = _make_ctx(actx)
        with pytest.raises(typer.Exit):
            update(ctx, force=False)


class TestCurrencyAdd:
    def test_add_currency(self):
        c = MagicMock()
        c.search_read.return_value = [{"id": 1, "name": "EUR", "active": False}]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.currency_cmd import add

        ctx = _make_ctx(actx)
        add(ctx, code="EUR")
        c.execute_kw.assert_called_once()

    def test_add_already_active(self):
        c = MagicMock()
        c.search_read.return_value = [{"id": 1, "name": "EUR", "active": True}]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.currency_cmd import add

        ctx = _make_ctx(actx)
        add(ctx, code="EUR")
        # Should not call execute_kw since it's already active
        c.execute_kw.assert_not_called()

    def test_add_not_found_exits(self):
        c = MagicMock()
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.currency_cmd import add

        ctx = _make_ctx(actx)
        with pytest.raises(typer.Exit):
            add(ctx, code="XYZ")


class TestCurrencyCheckStale:
    def test_check_stale_no_currencies(self):
        c = MagicMock()
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.currency_cmd import check_stale

        ctx = _make_ctx(actx)
        check_stale(ctx, days=7)

    def test_check_stale_all_fresh(self):
        c = MagicMock()
        c.search_read.return_value = [{"id": 1, "name": "IDR"}, {"id": 2, "name": "USD"}]
        c.search_count.return_value = 3  # each currency has recent rates
        actx = _make_actx(client=c)
        from kctl_odoo.commands.currency_cmd import check_stale

        ctx = _make_ctx(actx)
        check_stale(ctx, days=7)

    def test_check_stale_has_stale(self):
        c = MagicMock()
        c.search_read.return_value = [{"id": 1, "name": "IDR"}, {"id": 2, "name": "EUR"}]
        c.search_count.side_effect = [0, 2]  # IDR stale, EUR fresh
        actx = _make_actx(client=c)
        from kctl_odoo.commands.currency_cmd import check_stale

        ctx = _make_ctx(actx)
        check_stale(ctx, days=7)
