"""Tests for dev audit command."""

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


class TestAuditImport:
    def test_import(self):
        from kctl_odoo.commands.dev import audit

        assert callable(audit)


class TestAuditSingleModule:
    def test_audit_base_management(self, monkeypatch):
        """audit should work on a real module without crashing."""
        import os
        from pathlib import Path

        # Use KCTL_ODOO_REPO env var to find the Odoo project root
        repo = os.environ.get("KCTL_ODOO_REPO")
        if repo:
            project_root = Path(repo)
        else:
            # Walk up looking for src/private/
            project_root = Path(__file__).resolve().parent
            for _ in range(10):
                if (project_root / "src" / "private").is_dir():
                    break
                project_root = project_root.parent
            else:
                import pytest

                pytest.skip("Odoo project root not found -- set KCTL_ODOO_REPO env var")

        if not (project_root / "src" / "private" / "base_management").is_dir():
            import pytest

            pytest.skip("base_management module not found -- set KCTL_ODOO_REPO env var")

        monkeypatch.chdir(project_root)

        actx = _make_actx()
        from kctl_odoo.commands.dev import audit

        ctx = _make_ctx(actx)
        # This will run against actual src/private/base_management
        try:
            audit(ctx, module="base_management", all_modules=False, min_score=0, output=None)
        except SystemExit:
            pass  # typer.Exit is fine
