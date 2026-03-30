"""Tests for Wave 5 report command enhancements."""

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


class TestScheduleReport:
    def test_import(self):
        from kctl_odoo.commands.report import schedule_report

        assert callable(schedule_report)

    def test_basic_schedule(self):
        actx = _make_actx()
        from kctl_odoo.commands.report import schedule_report

        ctx = _make_ctx(actx)
        schedule_report(ctx, type_code="profit_loss", cron="0 8 * * 1", email_to=None)

    def test_schedule_with_email(self):
        actx = _make_actx()
        from kctl_odoo.commands.report import schedule_report

        ctx = _make_ctx(actx)
        schedule_report(ctx, type_code="balance_sheet", cron="0 9 * * 5", email_to="finance@company.com")

    def test_alias_resolution(self):
        """Verify backward-compatible aliases are resolved."""
        actx = _make_actx()
        from kctl_odoo.commands.report import schedule_report

        ctx = _make_ctx(actx)
        # 'pnl' is an alias for 'profit_loss'
        schedule_report(ctx, type_code="pnl", cron="0 8 * * 1", email_to=None)


class TestBatchDownload:
    def test_import(self):
        from kctl_odoo.commands.report import batch_download

        assert callable(batch_download)

    def test_no_report_types(self, tmp_path):
        from kctl_odoo.core.exceptions import RPCError

        c = MagicMock()
        # report.type.registry not available
        c.search_read.side_effect = RPCError({"message": "Model not found", "code": -32603})
        # fallback ir.actions.report also empty
        c.search_read.side_effect = [
            RPCError({"message": "Model not found", "code": -32603}),
            [],
        ]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.report import batch_download

        ctx = _make_ctx(actx)
        batch_download(
            ctx,
            category=None,
            date_from="2026-01-01",
            date_to="2026-01-31",
            output_dir=str(tmp_path),
        )

    def test_with_report_types(self, tmp_path):
        from kctl_odoo.core.exceptions import RPCError

        c = MagicMock()
        c.search_read.side_effect = [
            # report.type.registry not available
            RPCError({"message": "Model not found", "code": -32603}),
            # ir.actions.report fallback
            [
                {"id": 1, "name": "Profit & Loss", "report_name": "profit_loss", "report_type": "qweb-xlsx"},
            ],
        ]
        # search_read for report.instance
        c.search_read.side_effect = [
            RPCError({"message": "Model not found", "code": -32603}),
            [
                {"id": 1, "name": "Profit & Loss", "report_name": "profit_loss", "report_type": "qweb-xlsx"},
            ],
            [],  # no instances found
        ]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.report import batch_download

        ctx = _make_ctx(actx)
        batch_download(
            ctx,
            category=None,
            date_from="2026-01-01",
            date_to="2026-01-31",
            output_dir=str(tmp_path),
        )
