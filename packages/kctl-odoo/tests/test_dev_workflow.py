"""Tests for dev workflow commands."""

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


class TestModuleHealth:
    def test_import(self):
        from kctl_odoo.commands.dev import module_health

        assert callable(module_health)


class TestCheckConventions:
    def test_import(self):
        from kctl_odoo.commands.dev import check_conventions

        assert callable(check_conventions)


class TestCoverageReport:
    def test_import(self):
        from kctl_odoo.commands.dev import coverage_report

        assert callable(coverage_report)


class TestReleaseCheck:
    def test_import(self):
        from kctl_odoo.commands.dev import release_check

        assert callable(release_check)


class TestLintSummary:
    def test_import(self):
        from kctl_odoo.commands.lint import lint_summary

        assert callable(lint_summary)


class TestTestCoverage:
    def test_import(self):
        from kctl_odoo.commands.testing import test_coverage

        assert callable(test_coverage)
