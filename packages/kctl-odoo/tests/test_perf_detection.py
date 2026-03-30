"""Tests for performance detection commands."""

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


class TestAuditViews:
    def test_import(self):
        from kctl_odoo.commands.dev import audit_views

        assert callable(audit_views)


class TestAuditCompute:
    def test_import(self):
        from kctl_odoo.commands.dev import audit_compute

        assert callable(audit_compute)


class TestAuditBlocking:
    def test_import(self):
        from kctl_odoo.commands.dev import audit_blocking

        assert callable(audit_blocking)


class TestCheckLogLevel:
    def test_import(self):
        from kctl_odoo.commands.dev import check_log_level

        assert callable(check_log_level)


class TestUnusedModules:
    def test_import(self):
        from kctl_odoo.commands.troubleshoot import unused_modules

        assert callable(unused_modules)
