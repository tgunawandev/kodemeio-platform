"""Tests for management reports and warehouse enhancements."""

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


class TestExecSummary:
    def test_import(self):
        from kctl_odoo.commands.dashboard import exec_summary

        assert callable(exec_summary)


class TestGrossMargin:
    def test_import(self):
        from kctl_odoo.commands.dashboard import gross_margin

        assert callable(gross_margin)


class TestReorderRules:
    def test_import(self):
        from kctl_odoo.commands.inventory_cmd import reorder_rules

        assert callable(reorder_rules)


class TestLocations:
    def test_import(self):
        from kctl_odoo.commands.inventory_cmd import locations

        assert callable(locations)
