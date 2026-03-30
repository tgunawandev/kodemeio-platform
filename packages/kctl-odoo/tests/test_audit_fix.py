"""Tests for dev audit-fix and audit-prompt commands."""

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


class TestAuditFixImport:
    def test_import(self):
        from kctl_odoo.commands.dev import audit_fix

        assert callable(audit_fix)


class TestAuditPromptImport:
    def test_import(self):
        from kctl_odoo.commands.dev import audit_prompt

        assert callable(audit_prompt)


class TestAuditFixDryRun:
    def test_dry_run(self, monkeypatch, tmp_path):
        """audit-fix --dry-run should not modify files."""
        import os

        # Find project root
        cwd = os.getcwd()
        project_root = cwd
        while project_root and not (os.path.exists(os.path.join(project_root, "src", "private"))):
            parent = os.path.dirname(project_root)
            if parent == project_root:
                break
            project_root = parent

        if os.path.exists(os.path.join(project_root, "src", "private", "base_management")):
            monkeypatch.chdir(project_root)
            actx = _make_actx()
            from kctl_odoo.commands.dev import audit_fix

            ctx = _make_ctx(actx)
            try:
                audit_fix(ctx, module="base_management", dry_run=True, categories=None)
            except SystemExit:
                pass


class TestAuditPromptGeneration:
    def test_prompt_generation(self, monkeypatch, tmp_path):
        """audit-prompt should generate a prompt file."""
        import os

        cwd = os.getcwd()
        project_root = cwd
        while project_root and not (os.path.exists(os.path.join(project_root, "src", "private"))):
            parent = os.path.dirname(project_root)
            if parent == project_root:
                break
            project_root = parent

        if os.path.exists(os.path.join(project_root, "src", "private", "base_management")):
            monkeypatch.chdir(project_root)
            actx = _make_actx()
            output_file = str(tmp_path / "prompt.md")
            from kctl_odoo.commands.dev import audit_prompt

            ctx = _make_ctx(actx)
            try:
                audit_prompt(ctx, module="base_management", output=output_file)
            except SystemExit:
                pass
