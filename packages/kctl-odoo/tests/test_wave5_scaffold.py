"""Tests for Wave 5 scaffold (generate) enhancements."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
import typer


class TestScaffoldBridge:
    def test_import(self):
        from kctl_odoo.commands.generate import scaffold_bridge

        assert callable(scaffold_bridge)

    def test_creates_bridge(self, tmp_path):
        """Verify bridge module files are created correctly."""
        ctx = MagicMock(spec=typer.Context)

        from kctl_odoo.commands.generate import scaffold_bridge

        scaffold_bridge(ctx, module_a="whatsapp_integration", module_b="sale", dest=str(tmp_path))

        bridge_path = tmp_path / "whatsapp_integration_sale"
        assert bridge_path.exists()
        assert (bridge_path / "__manifest__.py").exists()
        assert (bridge_path / "__init__.py").exists()
        assert (bridge_path / "models" / "__init__.py").exists()
        assert (bridge_path / "security" / "ir.model.access.csv").exists()

    def test_manifest_has_auto_install(self, tmp_path):
        """Verify manifest contains auto_install=True."""
        ctx = MagicMock(spec=typer.Context)
        from kctl_odoo.commands.generate import scaffold_bridge

        scaffold_bridge(ctx, module_a="whatsapp_integration", module_b="sale", dest=str(tmp_path))

        manifest = (tmp_path / "whatsapp_integration_sale" / "__manifest__.py").read_text()
        assert "auto_install" in manifest
        assert "True" in manifest

    def test_manifest_has_depends(self, tmp_path):
        """Verify manifest lists both modules as dependencies."""
        ctx = MagicMock(spec=typer.Context)
        from kctl_odoo.commands.generate import scaffold_bridge

        scaffold_bridge(ctx, module_a="whatsapp_integration", module_b="sale", dest=str(tmp_path))

        manifest = (tmp_path / "whatsapp_integration_sale" / "__manifest__.py").read_text()
        assert "whatsapp_integration" in manifest
        assert '"sale"' in manifest


class TestScaffoldCrudApi:
    def test_import(self):
        from kctl_odoo.commands.generate import scaffold_crud_api

        assert callable(scaffold_crud_api)

    def test_creates_files(self, tmp_path):
        """Verify CRUD API files are created in existing module."""
        ctx = MagicMock(spec=typer.Context)

        # Create a mock module directory
        mod_dir = tmp_path / "sfa_management"
        mod_dir.mkdir()

        from kctl_odoo.commands.generate import scaffold_crud_api

        scaffold_crud_api(ctx, module="sfa_management", model="sfa.visit", dest=str(tmp_path))

        assert (mod_dir / "controllers" / "visit_router.py").exists()
        assert (mod_dir / "schemas" / "visit_schema.py").exists()
        assert (mod_dir / "tests" / "test_visit_router.py").exists()

    def test_module_not_found(self, tmp_path):
        """Verify error when module directory doesn't exist."""
        import click

        ctx = MagicMock(spec=typer.Context)
        from kctl_odoo.commands.generate import scaffold_crud_api

        with pytest.raises((SystemExit, click.exceptions.Exit)):
            scaffold_crud_api(ctx, module="nonexistent_module", model="foo.bar", dest=str(tmp_path))
