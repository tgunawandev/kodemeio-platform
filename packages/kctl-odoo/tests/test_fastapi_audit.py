"""Tests for FastAPI audit commands."""

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


class TestDevAuditApi:
    def test_import(self):
        from kctl_odoo.commands.dev import audit_api

        assert callable(audit_api)


class TestFastapiAudit:
    def test_import(self):
        from kctl_odoo.commands.fastapi_cmd import audit_api_live

        assert callable(audit_api_live)
