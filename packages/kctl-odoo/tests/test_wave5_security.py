"""Tests for Wave 5 security enhancements."""

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


class TestBulkGrant:
    def test_import(self):
        from kctl_odoo.commands.security import bulk_grant

        assert callable(bulk_grant)


class TestBulkRevoke:
    def test_import(self):
        from kctl_odoo.commands.security import bulk_revoke

        assert callable(bulk_revoke)


class TestDiffUsers:
    def test_import(self):
        from kctl_odoo.commands.security import diff_users

        assert callable(diff_users)


class TestSudoAudit:
    def test_import(self):
        from kctl_odoo.commands.security import sudo_audit

        assert callable(sudo_audit)
