"""Tests for accountant workflow enhancements."""

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


class TestGlExport:
    def test_import(self):
        from kctl_odoo.commands.accounting_cmd import gl_export

        assert callable(gl_export)

    def test_invoices_has_date_filters(self):
        """invoices command should accept --date-from and --date-to."""
        import inspect

        from kctl_odoo.commands.accounting_cmd import invoices

        sig = inspect.signature(invoices)
        assert "date_from" in sig.parameters
        assert "date_to" in sig.parameters

    def test_journal_entries_has_ref_partner(self):
        """journal_entries command should accept --ref and --partner."""
        import inspect

        from kctl_odoo.commands.accounting_cmd import journal_entries

        sig = inspect.signature(journal_entries)
        assert "ref" in sig.parameters
        assert "partner" in sig.parameters


class TestCoretaxStatus:
    def test_import(self):
        from kctl_odoo.commands.tax_cmd import coretax_status

        assert callable(coretax_status)


class TestPph21Summary:
    def test_import(self):
        from kctl_odoo.commands.tax_cmd import pph21_summary

        assert callable(pph21_summary)

    def test_has_month_param(self):
        import inspect

        from kctl_odoo.commands.tax_cmd import pph21_summary

        sig = inspect.signature(pph21_summary)
        assert "month" in sig.parameters


class TestTaxInvoicesExport:
    def test_import(self):
        from kctl_odoo.commands.tax_cmd import tax_invoices_export

        assert callable(tax_invoices_export)

    def test_has_date_and_output_params(self):
        import inspect

        from kctl_odoo.commands.tax_cmd import tax_invoices_export

        sig = inspect.signature(tax_invoices_export)
        assert "date_from" in sig.parameters
        assert "date_to" in sig.parameters
        assert "output" in sig.parameters


class TestPartnerStatement:
    def test_import(self):
        from kctl_odoo.commands.statements_cmd import partner_statement

        assert callable(partner_statement)

    def test_has_date_from_and_output(self):
        import inspect

        from kctl_odoo.commands.statements_cmd import partner_statement

        sig = inspect.signature(partner_statement)
        assert "date_from" in sig.parameters
        assert "output" in sig.parameters


class TestBankImportStatement:
    def test_import(self):
        from kctl_odoo.commands.bank_cmd import import_statement

        assert callable(import_statement)

    def test_has_dry_run(self):
        import inspect

        from kctl_odoo.commands.bank_cmd import import_statement

        sig = inspect.signature(import_statement)
        assert "dry_run" in sig.parameters
        assert "journal" in sig.parameters
