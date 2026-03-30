"""Tests for enhanced finance command groups."""

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


# ===================================================================
# assets_cmd tests
# ===================================================================


class TestAssetsImport:
    def test_import(self):
        from kctl_odoo.commands.assets_cmd import app

        assert app is not None


class TestAssetsSummary:
    def test_no_assets(self):
        c = MagicMock()
        c.search_count.return_value = 0
        actx = _make_actx(client=c)
        from kctl_odoo.commands.assets_cmd import summary

        ctx = _make_ctx(actx)
        summary(ctx)

    def test_with_model_unavailable(self):
        c = MagicMock()
        # model_available checks via execute_kw — raise to simulate not available
        c.execute_kw.side_effect = Exception("model not found")
        c.search_count.return_value = 0
        actx = _make_actx(client=c)
        from kctl_odoo.commands.assets_cmd import summary

        ctx = _make_ctx(actx)
        # Should warn and return gracefully
        summary(ctx)


class TestAssetsList:
    def test_no_results(self):
        c = MagicMock()
        c.execute_kw.return_value = {"display_name": {"type": "char"}}
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.assets_cmd import list_assets

        ctx = _make_ctx(actx)
        list_assets(ctx, state=None, limit=50)

    def test_with_results(self):
        c = MagicMock()
        c.execute_kw.return_value = {
            "display_name": {"type": "char"},
            "code": {"type": "char"},
            "state": {"type": "selection"},
            "purchase_value": {"type": "float"},
            "profile_id": {"type": "many2one"},
            "date_start": {"type": "date"},
            "company_id": {"type": "many2one"},
        }
        c.search_read.return_value = [
            {
                "id": 1,
                "display_name": "Office Building",
                "code": "FA-001",
                "state": "open",
                "purchase_value": 100000.0,
                "profile_id": [1, "Linear"],
                "date_start": "2024-01-01",
                "company_id": [1, "Company A"],
            }
        ]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.assets_cmd import list_assets

        ctx = _make_ctx(actx)
        list_assets(ctx, state="open", limit=10)


class TestAssetsDepreciationSchedule:
    def test_no_lines(self):
        c = MagicMock()
        c.execute_kw.return_value = {"display_name": {"type": "char"}}
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.assets_cmd import depreciation_schedule

        ctx = _make_ctx(actx)
        depreciation_schedule(ctx, asset_id=1)

    def test_with_lines(self):
        c = MagicMock()
        c.execute_kw.return_value = {
            "display_name": {"type": "char"},
            "line_date": {"type": "date"},
            "amount": {"type": "float"},
            "remaining_value": {"type": "float"},
            "type": {"type": "selection"},
            "move_id": {"type": "many2one"},
        }
        c.search_read.return_value = [
            {
                "id": 10,
                "line_date": "2025-01-31",
                "amount": 1000.0,
                "remaining_value": 9000.0,
                "type": "depreciate",
                "move_id": False,
            }
        ]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.assets_cmd import depreciation_schedule

        ctx = _make_ctx(actx)
        depreciation_schedule(ctx, asset_id=1)


# ===================================================================
# payment_gateways_cmd tests
# ===================================================================


class TestPaymentGatewaysImport:
    def test_import(self):
        from kctl_odoo.commands.payment_gateways_cmd import app

        assert app is not None


class TestPaymentGatewaysStatus:
    def test_no_providers(self):
        c = MagicMock()
        c.execute_kw.return_value = {"display_name": {"type": "char"}}
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.payment_gateways_cmd import status

        ctx = _make_ctx(actx)
        status(ctx)

    def test_with_providers(self):
        c = MagicMock()
        c.execute_kw.return_value = {
            "display_name": {"type": "char"},
            "state": {"type": "selection"},
            "module_id": {"type": "many2one"},
            "company_id": {"type": "many2one"},
            "is_published": {"type": "boolean"},
        }
        c.search_read.return_value = [
            {
                "id": 1,
                "display_name": "Midtrans",
                "state": "enabled",
                "module_id": [10, "payment_midtrans"],
                "company_id": [1, "Main Company"],
                "is_published": True,
            }
        ]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.payment_gateways_cmd import status

        ctx = _make_ctx(actx)
        status(ctx)

    def test_model_unavailable(self):
        c = MagicMock()
        c.execute_kw.side_effect = Exception("model not found")
        actx = _make_actx(client=c)
        from kctl_odoo.commands.payment_gateways_cmd import status

        ctx = _make_ctx(actx)
        status(ctx)


class TestPaymentGatewaysPending:
    def test_no_pending(self):
        c = MagicMock()
        c.execute_kw.return_value = {"display_name": {"type": "char"}}
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.payment_gateways_cmd import pending

        ctx = _make_ctx(actx)
        pending(ctx, provider=None, limit=50)


class TestPaymentGatewaysReconcile:
    def test_no_stale(self):
        c = MagicMock()
        c.execute_kw.return_value = {"display_name": {"type": "char"}}
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.payment_gateways_cmd import reconcile

        ctx = _make_ctx(actx)
        reconcile(ctx, dry_run=True)


# ===================================================================
# bank_cmd tests
# ===================================================================


class TestBankImport:
    def test_import(self):
        from kctl_odoo.commands.bank_cmd import app

        assert app is not None


class TestBankStatus:
    def test_no_statements(self):
        c = MagicMock()
        c.search_count.return_value = 0
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.bank_cmd import status

        ctx = _make_ctx(actx)
        status(ctx)

    def test_model_unavailable(self):
        from kctl_odoo.core.exceptions import RPCError

        c = MagicMock()
        # model_available uses search_count — raise RPCError to signal model missing
        c.search_count.side_effect = RPCError({"message": "model not found", "code": 404})
        actx = _make_actx(client=c)
        from kctl_odoo.commands.bank_cmd import status

        ctx = _make_ctx(actx)
        status(ctx)

    def test_with_data(self):
        c = MagicMock()
        # model_available: search_count once (returns 0, model exists)
        # status calls: total, reconciled, unreconciled
        c.search_count.side_effect = [0, 100, 80, 20]
        c.search_read.return_value = [{"amount": -500.0}, {"amount": 200.0}]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.bank_cmd import status

        ctx = _make_ctx(actx)
        status(ctx)


class TestBankUnmatched:
    def test_no_unmatched(self):
        c = MagicMock()
        c.execute_kw.return_value = {"display_name": {"type": "char"}}
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.bank_cmd import unmatched

        ctx = _make_ctx(actx)
        unmatched(ctx, journal=None, limit=50)

    def test_with_results(self):
        c = MagicMock()
        c.execute_kw.return_value = {
            "display_name": {"type": "char"},
            "date": {"type": "date"},
            "amount": {"type": "float"},
            "partner_id": {"type": "many2one"},
            "journal_id": {"type": "many2one"},
            "is_reconciled": {"type": "boolean"},
        }
        c.search_read.return_value = [
            {
                "id": 5,
                "date": "2025-03-01",
                "amount": -1500.0,
                "partner_id": [2, "Supplier X"],
                "journal_id": [3, "Bank BCA"],
                "is_reconciled": False,
            }
        ]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.bank_cmd import unmatched

        ctx = _make_ctx(actx)
        unmatched(ctx, journal=None, limit=50)


class TestBankJournals:
    def test_no_journals(self):
        c = MagicMock()
        c.execute_kw.return_value = {"display_name": {"type": "char"}}
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.bank_cmd import journals

        ctx = _make_ctx(actx)
        journals(ctx)


class TestBankImportGuide:
    def test_shows_guide(self):
        c = MagicMock()
        actx = _make_actx(client=c)
        from kctl_odoo.commands.bank_cmd import import_guide

        ctx = _make_ctx(actx)
        import_guide(ctx)  # Should not raise
