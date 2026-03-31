"""Tests for data-quality command group."""

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


class TestDataQualityImport:
    def test_import(self):
        from kctl_odoo.commands.data_quality_cmd import app

        assert app is not None

    def test_commands_exist(self):
        from kctl_odoo.commands.data_quality_cmd import (
            completeness,
            duplicates,
            orphans,
            report,
            validate,
        )

        assert callable(duplicates)
        assert callable(completeness)
        assert callable(orphans)
        assert callable(validate)
        assert callable(report)


class TestDataQualityDuplicates:
    def test_duplicates_no_dups(self):
        c = MagicMock()
        c.execute_kw.return_value = [{"name": "Acme", "name_count": 1}]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.data_quality_cmd import duplicates

        ctx = _make_ctx(actx)
        duplicates(ctx, model="res.partner", field="name", limit=50)

    def test_duplicates_found(self):
        c = MagicMock()
        c.execute_kw.return_value = [
            {"name": "Acme Corp", "name_count": 3},
            {"name": "John Doe", "name_count": 2},
        ]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.data_quality_cmd import duplicates

        ctx = _make_ctx(actx)
        duplicates(ctx, model="res.partner", field="name", limit=50)

    def test_duplicates_rpc_error(self):
        c = MagicMock()
        c.execute_kw.side_effect = RPCError({"message": "model not found"})
        actx = _make_actx(client=c)
        from kctl_odoo.commands.data_quality_cmd import duplicates

        ctx = _make_ctx(actx)
        with pytest.raises(typer.Exit):
            duplicates(ctx, model="nonexistent.model", field="name", limit=50)

    def test_duplicates_m2o_value(self):
        """Test that many2one values are handled correctly."""
        c = MagicMock()
        c.execute_kw.return_value = [
            {"categ_id": [1, "All / Saleable"], "categ_id_count": 5},
        ]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.data_quality_cmd import duplicates

        ctx = _make_ctx(actx)
        duplicates(ctx, model="product.template", field="categ_id", limit=50)


class TestDataQualityCompleteness:
    def test_completeness_no_records(self):
        c = MagicMock()
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.data_quality_cmd import completeness

        ctx = _make_ctx(actx)
        completeness(ctx, model="res.partner", fields=None, limit=100)

    def test_completeness_with_data(self):
        c = MagicMock()
        c.search_read.return_value = [
            {"id": 1, "name": "Acme", "email": "acme@test.com", "phone": False, "city": "Jakarta"},
            {"id": 2, "name": "Beta", "email": False, "phone": "0812345", "city": "Surabaya"},
            {"id": 3, "name": "Gamma", "email": "gamma@test.com", "phone": False, "city": False},
        ]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.data_quality_cmd import completeness

        ctx = _make_ctx(actx)
        completeness(ctx, model="res.partner", fields="name,email,phone,city", limit=100)

    def test_completeness_custom_fields(self):
        c = MagicMock()
        c.search_read.return_value = [
            {"id": 1, "ref": "REF001"},
            {"id": 2, "ref": False},
        ]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.data_quality_cmd import completeness

        ctx = _make_ctx(actx)
        completeness(ctx, model="res.partner", fields="ref", limit=50)

    def test_completeness_rpc_error(self):
        c = MagicMock()
        c.search_read.side_effect = RPCError({"message": "model not found"})
        actx = _make_actx(client=c)
        from kctl_odoo.commands.data_quality_cmd import completeness

        ctx = _make_ctx(actx)
        with pytest.raises(typer.Exit):
            completeness(ctx, model="nonexistent.model", fields=None, limit=100)


class TestDataQualityOrphans:
    def test_orphans_partner(self):
        c = MagicMock()
        c.search_count.return_value = 0
        actx = _make_actx(client=c)
        from kctl_odoo.commands.data_quality_cmd import orphans

        ctx = _make_ctx(actx)
        orphans(ctx, model="res.partner")
        # Should have called search_count multiple times for different checks
        assert c.search_count.call_count >= 1

    def test_orphans_with_counts(self):
        c = MagicMock()
        c.search_count.side_effect = [150, 200, 50, 10]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.data_quality_cmd import orphans

        ctx = _make_ctx(actx)
        orphans(ctx, model="res.partner")

    def test_orphans_employee(self):
        c = MagicMock()
        c.search_count.return_value = 5
        actx = _make_actx(client=c)
        from kctl_odoo.commands.data_quality_cmd import orphans

        ctx = _make_ctx(actx)
        orphans(ctx, model="hr.employee")

    def test_orphans_generic_model(self):
        c = MagicMock()
        c.search_count.return_value = 0
        actx = _make_actx(client=c)
        from kctl_odoo.commands.data_quality_cmd import orphans

        ctx = _make_ctx(actx)
        orphans(ctx, model="crm.lead")


class TestDataQualityValidate:
    def test_validate_partner(self):
        c = MagicMock()
        c.search_count.return_value = 0
        actx = _make_actx(client=c)
        from kctl_odoo.commands.data_quality_cmd import validate

        ctx = _make_ctx(actx)
        validate(ctx, model="res.partner", rules=None)

    def test_validate_with_violations(self):
        c = MagicMock()
        c.search_count.side_effect = [5, 3, 120]  # required violations, email violations, phone count
        actx = _make_actx(client=c)
        from kctl_odoo.commands.data_quality_cmd import validate

        ctx = _make_ctx(actx)
        validate(ctx, model="res.partner", rules=None)

    def test_validate_only_required_rule(self):
        c = MagicMock()
        c.search_count.return_value = 0
        actx = _make_actx(client=c)
        from kctl_odoo.commands.data_quality_cmd import validate

        ctx = _make_ctx(actx)
        validate(ctx, model="res.partner", rules="required")
        assert c.search_count.call_count == 1

    def test_validate_no_applicable_rules(self):
        c = MagicMock()
        actx = _make_actx(client=c)
        from kctl_odoo.commands.data_quality_cmd import validate

        ctx = _make_ctx(actx)
        # Rules that don't match anything for this model config
        validate(ctx, model="res.partner", rules="nonexistent_rule")


class TestDataQualityReport:
    def test_report_all(self):
        c = MagicMock()
        c.execute_kw.return_value = [{"name": "Acme", "name_count": 1}]
        c.search_count.return_value = 10
        actx = _make_actx(client=c)
        from kctl_odoo.commands.data_quality_cmd import report

        ctx = _make_ctx(actx)
        report(ctx, category="all")

    def test_report_master(self):
        c = MagicMock()
        c.execute_kw.return_value = []
        c.search_count.return_value = 0
        actx = _make_actx(client=c)
        from kctl_odoo.commands.data_quality_cmd import report

        ctx = _make_ctx(actx)
        report(ctx, category="master")

    def test_report_operations(self):
        c = MagicMock()
        c.execute_kw.return_value = [
            {"name": "SO/001", "name_count": 1},
            {"name": "INV/001", "name_count": 2},
        ]
        c.search_count.return_value = 0
        actx = _make_actx(client=c)
        from kctl_odoo.commands.data_quality_cmd import report

        ctx = _make_ctx(actx)
        report(ctx, category="operations")

    def test_report_handles_rpc_error(self):
        c = MagicMock()
        # Some checks fail with RPCError (model not installed)
        c.execute_kw.side_effect = RPCError({"message": "model not found"})
        c.search_count.side_effect = RPCError({"message": "model not found"})
        actx = _make_actx(client=c)
        from kctl_odoo.commands.data_quality_cmd import report

        ctx = _make_ctx(actx)
        # Should not raise — errors are caught and shown as N/A
        report(ctx, category="master")
