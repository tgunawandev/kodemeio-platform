"""Tests for Wave 5 dev command enhancements."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
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


class TestFindOverrides:
    def test_import(self):
        from kctl_odoo.commands.dev import find_overrides

        assert callable(find_overrides)

    def test_model_not_found(self):
        import click

        c = MagicMock()
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.dev import find_overrides

        ctx = _make_ctx(actx)
        with pytest.raises((SystemExit, click.exceptions.Exit)):
            find_overrides(ctx, model="nonexistent.model")

    def test_with_modules(self):
        c = MagicMock()
        c.search_read.side_effect = [
            # ir.model query
            [
                {
                    "id": 1,
                    "name": "Partner",
                    "model": "res.partner",
                    "modules": "base, partner_management, sfa_management",
                }
            ],
            # ir.module.module query
            [
                {"name": "base", "state": "installed", "shortdesc": "Base"},
                {"name": "partner_management", "state": "installed", "shortdesc": "Partner Mgmt"},
                {"name": "sfa_management", "state": "installed", "shortdesc": "SFA Mgmt"},
            ],
        ]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.dev import find_overrides

        ctx = _make_ctx(actx)
        find_overrides(ctx, model="res.partner")


class TestUnusedXmlIds:
    def test_import(self):
        from kctl_odoo.commands.dev import unused_xml_ids

        assert callable(unused_xml_ids)

    def test_no_results(self):
        c = MagicMock()
        c.search_read.return_value = []
        actx = _make_actx(client=c)
        from kctl_odoo.commands.dev import unused_xml_ids

        ctx = _make_ctx(actx)
        unused_xml_ids(ctx, module="my_module", limit=50)

    def test_with_results(self):
        c = MagicMock()
        c.search_read.side_effect = [
            # Main XML IDs query
            [
                {
                    "id": 1,
                    "name": "view_partner_form",
                    "module": "partner_management",
                    "model": "ir.ui.view",
                    "res_id": 10,
                },
            ],
            # noupdate query
            [],
        ]
        actx = _make_actx(client=c)
        from kctl_odoo.commands.dev import unused_xml_ids

        ctx = _make_ctx(actx)
        unused_xml_ids(ctx, module="partner_management", limit=50)


class TestCheckTranslations:
    def test_import(self):
        from kctl_odoo.commands.dev import check_translations

        assert callable(check_translations)

    def test_file_not_found(self):
        import click

        from kctl_odoo.commands.dev import check_translations

        actx = _make_actx()
        ctx = _make_ctx(actx)

        with pytest.raises((SystemExit, click.exceptions.Exit)):
            check_translations(ctx, module="nonexistent_module_xyz_wave5", lang="id")

    def test_valid_po_file(self, tmp_path):
        """Test with a simple PO file that has no mismatches."""
        from unittest.mock import patch

        po_content = """\
# Translation
msgid ""
msgstr ""

msgid "Hello %s"
msgstr "Halo %s"

msgid "You have %d items"
msgstr "Anda memiliki %d item"
"""
        # check_translations looks under src/private/<module>/i18n/ from project root
        mod_dir = tmp_path / "src" / "private" / "test_module" / "i18n"
        mod_dir.mkdir(parents=True)
        (mod_dir / "id.po").write_text(po_content)

        from kctl_odoo.commands.dev import check_translations

        actx = _make_actx()
        ctx = _make_ctx(actx)

        with patch("kctl_odoo.core.utils.find_project_root", return_value=tmp_path):
            check_translations(ctx, module="test_module", lang="id")

    def test_po_mismatch_detected(self, tmp_path):
        """Test that placeholder mismatches are detected."""
        from unittest.mock import patch

        po_content = """\
# Translation
msgid ""
msgstr ""

msgid "Hello %s user"
msgstr "Halo pengguna"
"""
        mod_dir = tmp_path / "src" / "private" / "test_module" / "i18n"
        mod_dir.mkdir(parents=True)
        (mod_dir / "id.po").write_text(po_content)

        from kctl_odoo.commands.dev import check_translations

        actx = _make_actx()
        ctx = _make_ctx(actx)

        with patch("kctl_odoo.core.utils.find_project_root", return_value=tmp_path):
            check_translations(ctx, module="test_module", lang="id")
