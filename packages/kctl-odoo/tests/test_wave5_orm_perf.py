"""Tests for Wave 5 ORM and performance enhancements."""

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


class TestFieldsUsage:
    def test_import(self):
        from kctl_odoo.commands.orm_cmd import fields_usage

        assert callable(fields_usage)


class TestIndexSuggest:
    def test_import(self):
        from kctl_odoo.commands.orm_cmd import index_suggest

        assert callable(index_suggest)


class TestMemory:
    def test_import(self):
        from kctl_odoo.commands.performance import memory_cmd

        assert callable(memory_cmd)


class TestConnections:
    def test_import(self):
        from kctl_odoo.commands.performance import connections

        assert callable(connections)
