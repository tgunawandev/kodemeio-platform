"""Tests for admin gap fixes."""

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


class TestSetPassword:
    def test_import(self):
        from kctl_odoo.commands.users import set_password

        assert callable(set_password)


class TestParamsExport:
    def test_import(self):
        from kctl_odoo.commands.config_server import params_export

        assert callable(params_export)


class TestParamsImport:
    def test_import(self):
        from kctl_odoo.commands.config_server import params_import

        assert callable(params_import)


class TestCreateCron:
    def test_import(self):
        from kctl_odoo.commands.cron import create_cron

        assert callable(create_cron)


class TestMigrateToDb:
    def test_import(self):
        from kctl_odoo.commands.storage import migrate_to_db

        assert callable(migrate_to_db)


class TestMigrateToFs:
    def test_import(self):
        from kctl_odoo.commands.storage import migrate_to_fs

        assert callable(migrate_to_fs)
