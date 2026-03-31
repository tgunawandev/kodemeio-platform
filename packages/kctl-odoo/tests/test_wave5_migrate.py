"""Tests for Wave 5 migrate enhancements."""

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


class TestFieldMap:
    def test_import(self):
        from kctl_odoo.commands.migrate import field_map

        assert callable(field_map)


class TestColumnDiff:
    def test_import(self):
        from kctl_odoo.commands.migrate import column_diff

        assert callable(column_diff)


class TestDryRun:
    def test_import(self):
        from kctl_odoo.commands.migrate import dry_run_cmd

        assert callable(dry_run_cmd)
