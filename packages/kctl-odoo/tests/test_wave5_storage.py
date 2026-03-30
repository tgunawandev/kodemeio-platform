"""Tests for Wave 5 storage enhancements."""

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


class TestLargeAttachments:
    def test_import(self):
        from kctl_odoo.commands.storage import large_attachments

        assert callable(large_attachments)

    def test_empty(self):
        c = MagicMock()
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.storage import large_attachments

        ctx = _make_ctx(actx)
        large_attachments(ctx, min_size=1000000, limit=20)

    def test_with_results(self):
        c = MagicMock()
        c.search_read.return_value = [
            {
                "id": 1,
                "name": "bigfile.pdf",
                "res_model": "sale.order",
                "file_size": 5000000,
                "create_date": "2026-01-01 00:00:00",
            }
        ]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.storage import large_attachments

        ctx = _make_ctx(actx)
        large_attachments(ctx, min_size=1000000, limit=20)


class TestIntegrityCheck:
    def test_import(self):
        from kctl_odoo.commands.storage import integrity_check

        assert callable(integrity_check)

    def test_no_attachments(self):
        c = MagicMock()
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.storage import integrity_check

        ctx = _make_ctx(actx)
        integrity_check(ctx)


class TestDownloadAttachment:
    def test_import(self):
        from kctl_odoo.commands.storage import download_attachment

        assert callable(download_attachment)

    def test_not_found(self):
        import click
        import pytest

        c = MagicMock()
        c.read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.storage import download_attachment

        ctx = _make_ctx(actx)
        with pytest.raises((SystemExit, click.exceptions.Exit)):
            download_attachment(ctx, attachment_id=999, output=None)
