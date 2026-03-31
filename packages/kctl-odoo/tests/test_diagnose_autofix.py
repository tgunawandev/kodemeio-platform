"""Tests for doctor auto-fix-modules command."""

from __future__ import annotations

from unittest.mock import MagicMock

import typer

from kctl_odoo.core.callbacks import AppContext


def _make_actx(client: MagicMock | None = None) -> AppContext:
    actx = MagicMock(spec=AppContext)
    actx.json_mode = False
    actx.client = client or MagicMock()
    from kctl_lib import Output

    actx.output = Output(json_mode=False)
    return actx


def _make_ctx(actx: AppContext) -> typer.Context:
    ctx = MagicMock(spec=typer.Context)
    ctx.obj = actx
    return ctx


class TestAutoFixModules:
    def test_import_succeeds(self) -> None:
        """auto-fix-modules should be importable."""
        from kctl_odoo.commands.diagnose import auto_fix_modules

        assert callable(auto_fix_modules)

    def test_no_errors_found(self) -> None:
        """auto-fix-modules should report OK when no column errors."""
        c = MagicMock()
        c.search_read.return_value = [{"id": 1, "login": "admin"}]
        actx = _make_actx(client=c)

        from kctl_odoo.commands.diagnose import auto_fix_modules

        ctx = _make_ctx(actx)
        auto_fix_modules(ctx, dry_run=False)
        # Should not raise
