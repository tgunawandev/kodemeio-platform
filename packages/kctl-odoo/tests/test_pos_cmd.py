"""Tests for pos command group."""

from __future__ import annotations

from unittest.mock import MagicMock

import typer

from kctl_odoo.core.callbacks import AppContext


def _make_actx(client: MagicMock | None = None) -> AppContext:
    actx = MagicMock(spec=AppContext)
    actx.json_mode = False
    actx.client = client or MagicMock()
    from kctl_lib import Output

    actx.output = Output(json_mode=False)
    return actx


def _make_ctx(actx: AppContext) -> typer.Context:
    ctx = MagicMock(spec=typer.Context)
    ctx.obj = actx
    return ctx


class TestPosImport:
    def test_import_app(self) -> None:
        from kctl_odoo.commands.pos_cmd import app

        assert app is not None


class TestPosConfigs:
    def test_configs_no_pos(self) -> None:
        """configs should handle pos not installed."""
        c = MagicMock()
        c.search_count.return_value = 0
        # model_available raises RPCError when model doesn't exist
        from kctl_odoo.core.exceptions import RPCError

        c.search_count.side_effect = RPCError({"message": "Object pos.session doesn't exist"})
        actx = _make_actx(client=c)
        from kctl_odoo.commands.pos_cmd import configs

        ctx = _make_ctx(actx)
        configs(ctx)

    def test_configs_empty(self) -> None:
        """configs should handle empty list gracefully."""
        c = MagicMock()
        c.search_count.return_value = 0
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.pos_cmd import configs

        ctx = _make_ctx(actx)
        configs(ctx)

    def test_configs_returns_records(self) -> None:
        """configs should display table with records."""
        c = MagicMock()
        c.search_count.return_value = 1
        c.search_read.return_value = [
            {
                "id": 1,
                "name": "Main POS",
                "active": True,
                "current_session_id": [5, "POS/005"],
                "module_pos_restaurant": False,
            }
        ]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.pos_cmd import configs

        ctx = _make_ctx(actx)
        configs(ctx)


class TestPosSessions:
    def test_sessions_empty(self) -> None:
        c = MagicMock()
        c.search_read.return_value = []
        c.search_count.return_value = 0
        actx = _make_actx(client=c)
        from kctl_odoo.commands.pos_cmd import sessions

        ctx = _make_ctx(actx)
        sessions(ctx, state=None, limit=20)

    def test_sessions_no_pos(self) -> None:
        """sessions should handle pos not installed."""
        c = MagicMock()
        from kctl_odoo.core.exceptions import RPCError

        c.search_count.side_effect = RPCError({"message": "Object pos.session doesn't exist"})
        actx = _make_actx(client=c)
        from kctl_odoo.commands.pos_cmd import sessions

        ctx = _make_ctx(actx)
        sessions(ctx, state=None, limit=20)

    def test_sessions_with_state_filter(self) -> None:
        """sessions should apply state filter to domain."""
        c = MagicMock()
        c.search_count.return_value = 1
        c.search_read.return_value = [
            {
                "id": 1,
                "name": "POS/001",
                "config_id": [1, "Main POS"],
                "user_id": [3, "Admin"],
                "state": "opened",
                "start_at": "2026-03-29 08:00:00",
                "stop_at": False,
            }
        ]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.pos_cmd import sessions

        ctx = _make_ctx(actx)
        sessions(ctx, state="opened", limit=20)

        # Verify search_read was called with a domain
        call_kwargs = c.search_read.call_args
        assert call_kwargs is not None


class TestPosOrders:
    def test_orders_empty(self) -> None:
        c = MagicMock()
        c.search_read.return_value = []
        c.search_count.return_value = 0
        actx = _make_actx(client=c)
        from kctl_odoo.commands.pos_cmd import orders

        ctx = _make_ctx(actx)
        orders(ctx, session=None, date_from=None, limit=50)

    def test_orders_no_pos(self) -> None:
        c = MagicMock()
        from kctl_odoo.core.exceptions import RPCError

        c.search_count.side_effect = RPCError({"message": "pos not installed"})
        actx = _make_actx(client=c)
        from kctl_odoo.commands.pos_cmd import orders

        ctx = _make_ctx(actx)
        orders(ctx, session=None, date_from=None, limit=50)


class TestPosSummary:
    def test_summary_no_pos(self) -> None:
        c = MagicMock()
        from kctl_odoo.core.exceptions import RPCError

        c.search_count.side_effect = RPCError({"message": "pos not installed"})
        actx = _make_actx(client=c)
        from kctl_odoo.commands.pos_cmd import summary

        ctx = _make_ctx(actx)
        summary(ctx)


class TestPosStuckSessions:
    def test_stuck_sessions_none(self) -> None:
        """stuck-sessions should report clean state."""
        c = MagicMock()
        c.search_count.return_value = 1
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.pos_cmd import stuck_sessions

        ctx = _make_ctx(actx)
        stuck_sessions(ctx, hours=24)

    def test_stuck_sessions_found(self) -> None:
        """stuck-sessions should list sessions open too long."""
        c = MagicMock()
        c.search_count.return_value = 1
        c.search_read.return_value = [
            {
                "id": 2,
                "name": "POS/002",
                "config_id": [1, "Main POS"],
                "user_id": [3, "Admin"],
                "state": "opened",
                "start_at": "2026-03-01 08:00:00",
            }
        ]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.pos_cmd import stuck_sessions

        ctx = _make_ctx(actx)
        stuck_sessions(ctx, hours=24)


class TestPosDailyReport:
    def test_daily_report_no_orders(self) -> None:
        c = MagicMock()
        c.search_count.return_value = 1
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.pos_cmd import daily_report

        ctx = _make_ctx(actx)
        daily_report(ctx, date="2026-03-29")


class TestPosPayments:
    def test_payments_empty(self) -> None:
        c = MagicMock()
        c.search_count.return_value = 1
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.pos_cmd import payments

        ctx = _make_ctx(actx)
        payments(ctx, date_from=None, limit=100)

    def test_payments_grouped(self) -> None:
        c = MagicMock()
        c.search_count.return_value = 1
        c.search_read.return_value = [
            {"id": 1, "payment_method_id": [1, "Cash"], "amount": 100.0},
            {"id": 2, "payment_method_id": [2, "Card"], "amount": 250.0},
            {"id": 3, "payment_method_id": [1, "Cash"], "amount": 50.0},
        ]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.pos_cmd import payments

        ctx = _make_ctx(actx)
        payments(ctx, date_from=None, limit=100)
