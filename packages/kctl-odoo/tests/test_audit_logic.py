"""Tests for dev audit-logic command."""

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


class TestAuditLogicImport:
    def test_import(self):
        from kctl_odoo.commands.dev import audit_logic

        assert callable(audit_logic)


class TestAuditLogicRun:
    def test_run_on_module(self, monkeypatch):
        """audit-logic should work on a real module."""
        import os

        cwd = os.getcwd()
        project_root = cwd
        while project_root and not os.path.exists(os.path.join(project_root, "src", "private")):
            parent = os.path.dirname(project_root)
            if parent == project_root:
                break
            project_root = parent

        if os.path.exists(os.path.join(project_root, "src", "private", "base_management")):
            monkeypatch.chdir(project_root)
            actx = _make_actx()
            from kctl_odoo.commands.dev import audit_logic

            ctx = _make_ctx(actx)
            try:
                audit_logic(ctx, module="base_management")
            except SystemExit:
                pass
