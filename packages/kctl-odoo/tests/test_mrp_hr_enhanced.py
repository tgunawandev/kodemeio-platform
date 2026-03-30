"""Tests for enhanced MRP + HR commands."""

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


class TestMrpCreateOrder:
    def test_import(self):
        from kctl_odoo.commands.mrp_cmd import create_order

        assert callable(create_order)


class TestMrpCosts:
    def test_import(self):
        from kctl_odoo.commands.mrp_cmd import costs

        assert callable(costs)


class TestMrpBomCost:
    def test_import(self):
        from kctl_odoo.commands.mrp_cmd import bom_cost

        assert callable(bom_cost)


class TestMrpStartWorkorder:
    def test_import(self):
        from kctl_odoo.commands.mrp_cmd import start_workorder

        assert callable(start_workorder)


class TestMrpFinishWorkorder:
    def test_import(self):
        from kctl_odoo.commands.mrp_cmd import finish_workorder

        assert callable(finish_workorder)


class TestHrGetEmployee:
    def test_import(self):
        from kctl_odoo.commands.hr_cmd import get_employee

        assert callable(get_employee)


class TestHrAttendanceReport:
    def test_import(self):
        from kctl_odoo.commands.hr_cmd import attendance_report

        assert callable(attendance_report)


class TestHrGetPayslip:
    def test_import(self):
        from kctl_odoo.commands.hr_cmd import get_payslip

        assert callable(get_payslip)


class TestHrLeaveSummary:
    def test_import(self):
        from kctl_odoo.commands.hr_cmd import leave_summary

        assert callable(leave_summary)
