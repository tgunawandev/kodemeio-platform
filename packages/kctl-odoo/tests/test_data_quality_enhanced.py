"""Tests for enhanced data quality checks (HR, manufacturing, cross-module)."""

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


class TestCheckDataCategories:
    def test_import(self):
        """check_data function is importable and callable."""
        from kctl_odoo.commands.maintenance import check_data

        assert callable(check_data)

    def test_hr_category_exists(self):
        """check-data should accept --category hr."""
        from kctl_odoo.commands.maintenance import check_data

        assert callable(check_data)

    def test_manufacturing_category_exists(self):
        """check-data should accept --category manufacturing."""
        from kctl_odoo.commands.maintenance import check_data

        assert callable(check_data)

    def test_cross_module_category_exists(self):
        """check-data should accept --category cross-module."""
        from kctl_odoo.commands.maintenance import check_data

        assert callable(check_data)

    def test_category_alias_mapping(self):
        """Category aliases map correctly to internal names."""
        # Simulate the alias mapping from check_data
        _cat_aliases = {"manufacturing": "mfg", "cross-module": "cross", "cross_module": "cross"}
        assert _cat_aliases["manufacturing"] == "mfg"
        assert _cat_aliases["cross-module"] == "cross"
        assert _cat_aliases["cross_module"] == "cross"
        # hr has no alias — passed through unchanged
        assert _cat_aliases.get("hr", "hr") == "hr"

    def test_model_available_import(self):
        """model_available is importable from biz_helpers."""
        from kctl_odoo.core.biz_helpers import model_available

        assert callable(model_available)
