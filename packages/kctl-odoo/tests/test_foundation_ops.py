"""Tests for foundation ops command groups."""

from __future__ import annotations

from unittest.mock import MagicMock

import typer

from kctl_odoo.core.callbacks import AppContext


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


# ===================================================================
# Import tests for all 10 groups
# ===================================================================


class TestFoundationImports:
    def test_audit(self):
        from kctl_odoo.commands.audit_cmd import app

        assert app is not None

    def test_forms(self):
        from kctl_odoo.commands.forms_cmd import app

        assert app is not None

    def test_compliance(self):
        from kctl_odoo.commands.compliance_cmd import app

        assert app is not None

    def test_dunning(self):
        from kctl_odoo.commands.dunning_cmd import app

        assert app is not None

    def test_budget(self):
        from kctl_odoo.commands.budget_cmd import app

        assert app is not None

    def test_quality(self):
        from kctl_odoo.commands.quality_cmd import app

        assert app is not None

    def test_support(self):
        from kctl_odoo.commands.support_cmd import app

        assert app is not None

    def test_kpi(self):
        from kctl_odoo.commands.kpi_cmd import app

        assert app is not None

    def test_periods(self):
        from kctl_odoo.commands.periods_cmd import app

        assert app is not None

    def test_statements(self):
        from kctl_odoo.commands.statements_cmd import app

        assert app is not None


# ===================================================================
# Audit tests
# ===================================================================


class TestAuditList:
    def test_no_auditlog_model(self):
        """When auditlog.log is unavailable, warn and return."""
        from kctl_odoo.commands.audit_cmd import list_logs
        from kctl_odoo.core.exceptions import RPCError

        c = MagicMock()
        c.search_count.side_effect = RPCError({"message": "model not found"})
        actx = _make_actx(client=c)
        ctx = _make_ctx(actx)
        list_logs(ctx, model=None, user=None, days=30, limit=50)

    def test_empty_results(self):
        """When model is available but no records, info message shown."""
        from kctl_odoo.commands.audit_cmd import list_logs

        c = MagicMock()
        # model_available returns True (search_count doesn't raise)
        c.search_count.return_value = 0
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        ctx = _make_ctx(actx)
        list_logs(ctx, model=None, user=None, days=30, limit=50)

    def test_audit_rules_empty(self):
        """Audit rules command with no rules configured."""
        from kctl_odoo.commands.audit_cmd import rules

        c = MagicMock()
        c.search_count.return_value = 0
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        ctx = _make_ctx(actx)
        rules(ctx)


# ===================================================================
# Forms tests
# ===================================================================


class TestFormsPending:
    def test_no_form_model(self):
        """When form.type unavailable, warn and return."""
        from kctl_odoo.commands.forms_cmd import pending
        from kctl_odoo.core.exceptions import RPCError

        c = MagicMock()
        c.search_count.side_effect = RPCError({"message": "model not found"})
        actx = _make_actx(client=c)
        ctx = _make_ctx(actx)
        pending(ctx, form_type=None, limit=50)

    def test_no_pending_forms(self):
        """When model is available but no pending requests."""
        from kctl_odoo.commands.forms_cmd import pending

        c = MagicMock()
        c.search_count.return_value = 0
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        ctx = _make_ctx(actx)
        pending(ctx, form_type=None, limit=50)

    def test_form_types_empty(self):
        """Form types command returns empty list."""
        from kctl_odoo.commands.forms_cmd import types

        c = MagicMock()
        c.search_count.return_value = 0
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        ctx = _make_ctx(actx)
        types(ctx)


# ===================================================================
# Compliance tests
# ===================================================================


class TestComplianceLicenses:
    def test_no_compliance_model(self):
        """When compliance model unavailable, warn and return."""
        from kctl_odoo.commands.compliance_cmd import licenses
        from kctl_odoo.core.exceptions import RPCError

        c = MagicMock()
        c.search_count.side_effect = RPCError({"message": "model not found"})
        actx = _make_actx(client=c)
        ctx = _make_ctx(actx)
        licenses(ctx, expiring_days=30, limit=50)

    def test_no_licenses(self):
        """When no licenses found."""
        from kctl_odoo.commands.compliance_cmd import licenses

        c = MagicMock()
        c.search_count.return_value = 0
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        ctx = _make_ctx(actx)
        licenses(ctx, expiring_days=30, limit=50)


# ===================================================================
# Dunning tests
# ===================================================================


class TestDunningCases:
    def test_no_dunning_model(self):
        """When dunning.case unavailable, warn and return."""
        from kctl_odoo.commands.dunning_cmd import cases
        from kctl_odoo.core.exceptions import RPCError

        c = MagicMock()
        c.search_count.side_effect = RPCError({"message": "model not found"})
        actx = _make_actx(client=c)
        ctx = _make_ctx(actx)
        cases(ctx, level=None, limit=50)

    def test_no_cases(self):
        """When dunning model available but no cases."""
        from kctl_odoo.commands.dunning_cmd import cases

        c = MagicMock()
        c.search_count.return_value = 0
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        ctx = _make_ctx(actx)
        cases(ctx, level=None, limit=50)

    def test_dunning_levels_empty(self):
        """Dunning levels command returns empty list."""
        from kctl_odoo.commands.dunning_cmd import levels

        c = MagicMock()
        c.search_count.return_value = 0
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        ctx = _make_ctx(actx)
        levels(ctx)


# ===================================================================
# Budget tests
# ===================================================================


class TestBudgetList:
    def test_no_budget_model(self):
        """When budget.budget unavailable, warn and return."""
        from kctl_odoo.commands.budget_cmd import list_budgets
        from kctl_odoo.core.exceptions import RPCError

        c = MagicMock()
        c.search_count.side_effect = RPCError({"message": "model not found"})
        actx = _make_actx(client=c)
        ctx = _make_ctx(actx)
        list_budgets(ctx, state=None, limit=50)

    def test_no_budgets(self):
        """When budget model available but no records."""
        from kctl_odoo.commands.budget_cmd import list_budgets

        c = MagicMock()
        c.search_count.return_value = 0
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        ctx = _make_ctx(actx)
        list_budgets(ctx, state=None, limit=50)


# ===================================================================
# Quality tests
# ===================================================================


class TestQualityChecks:
    def test_no_quality_model(self):
        """When neither quality model is available, warn and return."""
        from kctl_odoo.commands.quality_cmd import checks
        from kctl_odoo.core.exceptions import RPCError

        c = MagicMock()
        c.search_count.side_effect = RPCError({"message": "model not found"})
        actx = _make_actx(client=c)
        ctx = _make_ctx(actx)
        checks(ctx, state=None, limit=50)

    def test_quality_check_empty(self):
        """When quality.check exists but no records."""
        from kctl_odoo.commands.quality_cmd import checks

        c = MagicMock()
        c.search_count.return_value = 0
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        ctx = _make_ctx(actx)
        checks(ctx, state=None, limit=50)


# ===================================================================
# Support tests
# ===================================================================


class TestSupportTickets:
    def test_no_support_model(self):
        """When support.ticket unavailable, warn and return."""
        from kctl_odoo.commands.support_cmd import tickets
        from kctl_odoo.core.exceptions import RPCError

        c = MagicMock()
        c.search_count.side_effect = RPCError({"message": "model not found"})
        actx = _make_actx(client=c)
        ctx = _make_ctx(actx)
        tickets(ctx, status=None, limit=50)

    def test_no_tickets(self):
        """When support model available but no tickets."""
        from kctl_odoo.commands.support_cmd import tickets

        c = MagicMock()
        c.search_count.return_value = 0
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        ctx = _make_ctx(actx)
        tickets(ctx, status=None, limit=50)


# ===================================================================
# KPI tests
# ===================================================================


class TestKpiList:
    def test_no_mis_model(self):
        """When mis.report unavailable, warn and return."""
        from kctl_odoo.commands.kpi_cmd import list_reports
        from kctl_odoo.core.exceptions import RPCError

        c = MagicMock()
        c.search_count.side_effect = RPCError({"message": "model not found"})
        actx = _make_actx(client=c)
        ctx = _make_ctx(actx)
        list_reports(ctx)

    def test_no_reports(self):
        """When mis.report available but no reports configured."""
        from kctl_odoo.commands.kpi_cmd import list_reports

        c = MagicMock()
        c.search_count.return_value = 0
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        ctx = _make_ctx(actx)
        list_reports(ctx)


# ===================================================================
# Periods tests
# ===================================================================


class TestPeriodsList:
    def test_no_date_range_model(self):
        """When date.range unavailable, warn and return."""
        from kctl_odoo.commands.periods_cmd import list_periods
        from kctl_odoo.core.exceptions import RPCError

        c = MagicMock()
        c.search_count.side_effect = RPCError({"message": "model not found"})
        actx = _make_actx(client=c)
        ctx = _make_ctx(actx)
        list_periods(ctx, range_type=None, limit=50)

    def test_no_periods(self):
        """When date.range available but no periods."""
        from kctl_odoo.commands.periods_cmd import list_periods

        c = MagicMock()
        c.search_count.return_value = 0
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        ctx = _make_ctx(actx)
        list_periods(ctx, range_type=None, limit=50)


# ===================================================================
# Statements tests
# ===================================================================


class TestStatementsOverdue:
    def test_no_move_line_model(self):
        """When account.move.line unavailable, warn and return."""
        from kctl_odoo.commands.statements_cmd import overdue
        from kctl_odoo.core.exceptions import RPCError

        c = MagicMock()
        c.search_count.side_effect = RPCError({"message": "model not found"})
        actx = _make_actx(client=c)
        ctx = _make_ctx(actx)
        overdue(ctx, limit=50)

    def test_no_overdue(self):
        """When no overdue balances found."""
        from kctl_odoo.commands.statements_cmd import overdue

        c = MagicMock()
        c.search_count.return_value = 0
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        ctx = _make_ctx(actx)
        overdue(ctx, limit=50)

    def test_generate_instructions(self):
        """Generate command shows instructions without error."""
        from kctl_odoo.commands.statements_cmd import generate

        actx = _make_actx()
        ctx = _make_ctx(actx)
        generate(ctx, partner="Acme Corp", stmt_type="activity", stmt_date=None)
