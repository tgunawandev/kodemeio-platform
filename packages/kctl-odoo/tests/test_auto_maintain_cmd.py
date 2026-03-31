"""Tests for auto-maintain command group."""

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


class TestAutoMaintainImport:
    def test_import(self):
        from kctl_odoo.commands.auto_maintain_cmd import app

        assert app is not None

    def test_commands_exist(self):
        from kctl_odoo.commands.auto_maintain_cmd import report, run, schedule

        assert callable(run)
        assert callable(schedule)
        assert callable(report)


class TestAutoMaintainRun:
    def test_dry_run(self):
        c = MagicMock()
        c.search_count.return_value = 5
        c.search.return_value = [1, 2, 3]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.auto_maintain_cmd import run

        ctx = _make_ctx(actx)
        run(ctx, dry_run=True)
        # Should not call unlink or write in dry_run mode
        c.unlink.assert_not_called()
        c.write.assert_not_called()

    def test_run_no_items(self):
        c = MagicMock()
        c.search.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.auto_maintain_cmd import run

        ctx = _make_ctx(actx)
        run(ctx, dry_run=False)
        # No items found, no unlink/write needed
        c.unlink.assert_not_called()
        c.write.assert_not_called()

    def test_run_with_items(self):
        c = MagicMock()
        c.search.return_value = [1, 2, 3]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.auto_maintain_cmd import run

        ctx = _make_ctx(actx)
        run(ctx, dry_run=False)
        # Should call unlink or write for each action
        assert c.unlink.called or c.write.called

    def test_run_handles_exception(self):
        c = MagicMock()
        c.search.side_effect = Exception("RPC error")
        actx = _make_actx(client=c)
        from kctl_odoo.commands.auto_maintain_cmd import run

        ctx = _make_ctx(actx)
        # Should not raise — exceptions are caught per action
        run(ctx, dry_run=False)


class TestAutoMaintainSchedule:
    def test_schedule(self):
        c = MagicMock()
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.auto_maintain_cmd import schedule

        ctx = _make_ctx(actx)
        schedule(ctx)

    def test_schedule_with_crons(self):
        c = MagicMock()
        c.search_read.return_value = [
            {
                "id": 1,
                "name": "Clean Old Mails",
                "active": True,
                "nextcall": "2026-04-01 03:00:00",
                "interval_number": 1,
                "interval_type": "days",
            }
        ]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.auto_maintain_cmd import schedule

        ctx = _make_ctx(actx)
        schedule(ctx)


class TestAutoMaintainReport:
    def test_report_default(self):
        c = MagicMock()
        c.search_count.return_value = 0
        actx = _make_actx(client=c)
        from kctl_odoo.commands.auto_maintain_cmd import report

        ctx = _make_ctx(actx)
        report(ctx, days=7)

    def test_report_with_stale_data(self):
        c = MagicMock()
        c.search_count.return_value = 42
        actx = _make_actx(client=c)
        from kctl_odoo.commands.auto_maintain_cmd import report

        ctx = _make_ctx(actx)
        report(ctx, days=7)

    def test_report_handles_exception(self):
        c = MagicMock()
        c.search_count.side_effect = Exception("Connection refused")
        actx = _make_actx(client=c)
        from kctl_odoo.commands.auto_maintain_cmd import report

        ctx = _make_ctx(actx)
        # Should not raise — exceptions are handled per stat
        report(ctx, days=7)
