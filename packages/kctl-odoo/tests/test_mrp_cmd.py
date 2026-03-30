"""Tests for mrp command group."""

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


class TestMrpImport:
    def test_import_app(self) -> None:
        from kctl_odoo.commands.mrp_cmd import app

        assert app is not None


class TestMrpSummary:
    def test_summary_no_mrp(self) -> None:
        """summary should handle mrp not installed."""
        c = MagicMock()
        # model_available returns False when search_count raises or returns 0
        c.search_count.return_value = 0
        actx = _make_actx(client=c)
        from kctl_odoo.commands.mrp_cmd import summary

        ctx = _make_ctx(actx)
        summary(ctx)

    def test_summary_with_data(self) -> None:
        """summary should display counts by state."""
        c = MagicMock()
        c.search_count.return_value = 1  # model_available -> True
        c.read_group.return_value = [
            {"state": "confirmed", "state_count": 3, "__count": 3},
            {"state": "progress", "state_count": 1, "__count": 1},
        ]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.mrp_cmd import summary

        ctx = _make_ctx(actx)
        summary(ctx)


class TestMrpOrders:
    def test_orders_empty(self) -> None:
        """orders should handle no results."""
        c = MagicMock()
        c.search_count.return_value = 1  # model_available -> True
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.mrp_cmd import orders

        ctx = _make_ctx(actx)
        orders(ctx, state=None, limit=50)

    def test_orders_no_mrp(self) -> None:
        """orders should handle mrp not installed."""
        c = MagicMock()
        c.search_count.return_value = 0
        actx = _make_actx(client=c)
        from kctl_odoo.commands.mrp_cmd import orders

        ctx = _make_ctx(actx)
        orders(ctx, state=None, limit=50)

    def test_orders_with_results(self) -> None:
        """orders should display results table."""
        c = MagicMock()
        c.search_count.return_value = 5  # model_available -> True
        c.search_read.return_value = [
            {
                "id": 1,
                "name": "WH/MO/00001",
                "product_id": [10, "Finished Product A"],
                "product_qty": 100.0,
                "state": "confirmed",
                "date_start": "2026-03-29 08:00:00",
            }
        ]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.mrp_cmd import orders

        ctx = _make_ctx(actx)
        orders(ctx, state="confirmed", limit=10)


class TestMrpBoms:
    def test_boms_empty(self) -> None:
        """boms should handle no results."""
        c = MagicMock()
        c.search_count.return_value = 1
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.mrp_cmd import boms

        ctx = _make_ctx(actx)
        boms(ctx, product=None, limit=50)

    def test_boms_with_results(self) -> None:
        """boms should display results."""
        c = MagicMock()
        c.search_count.return_value = 2
        c.search_read.return_value = [
            {
                "id": 1,
                "product_tmpl_id": [5, "Widget A"],
                "product_qty": 1.0,
                "type": "normal",
                "code": "BOM-001",
            }
        ]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.mrp_cmd import boms

        ctx = _make_ctx(actx)
        boms(ctx, product="Widget", limit=50)


class TestMrpWorkcenters:
    def test_workcenters_empty(self) -> None:
        """workcenters should handle no results."""
        c = MagicMock()
        c.search_count.return_value = 1
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.mrp_cmd import workcenters

        ctx = _make_ctx(actx)
        workcenters(ctx)

    def test_workcenters_with_results(self) -> None:
        """workcenters should display results."""
        c = MagicMock()
        c.search_count.return_value = 3
        c.search_read.return_value = [
            {
                "id": 1,
                "name": "Assembly Line 1",
                "code": "AL1",
                "active": True,
                "time_efficiency": 85.0,
                "capacity": 2.0,
            }
        ]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.mrp_cmd import workcenters

        ctx = _make_ctx(actx)
        workcenters(ctx)


class TestMrpPlanning:
    def test_planning_empty(self) -> None:
        """planning should handle no upcoming MOs."""
        c = MagicMock()
        c.search_count.return_value = 1
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.mrp_cmd import planning

        ctx = _make_ctx(actx)
        planning(ctx, days=7, limit=50)


class TestMrpStuck:
    def test_stuck_none(self) -> None:
        """stuck should handle no stuck MOs."""
        c = MagicMock()
        c.search_count.return_value = 1
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.mrp_cmd import stuck

        ctx = _make_ctx(actx)
        stuck(ctx, days=7, limit=50)
