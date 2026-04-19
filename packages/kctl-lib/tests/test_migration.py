"""Tests for kctl_lib._migration (Stage A config migration)."""

from __future__ import annotations


def test_module_importable() -> None:
    from kctl_lib import _migration

    assert hasattr(_migration, "MigrationResult")


class TestRenameMap:
    def test_rename_map_has_canonical_entries(self) -> None:
        from kctl_lib._migration import RENAME_MAP

        # Sampling the canonical renames from the spec table (step 3 of migrate).
        assert RENAME_MAP["tpp-odoo-erp"] == "idtpp-tpp-odoo-erp"
        assert RENAME_MAP["tpp-odoo-hrms"] == "idtpp-tpp-odoo-hrms"
        assert RENAME_MAP["stg-tpp-odoo-erp"] == "idtpp-tpp-odoo-erp-stg"
        assert RENAME_MAP["stg-tpp-odoo-hrms"] == "idtpp-tpp-odoo-hrms-stg"
        assert RENAME_MAP["mac-odoo-erp"] == "idtpp-mac-odoo-erp"
        assert RENAME_MAP["mac-odoo-hrms"] == "idtpp-mac-odoo-hrms"
        assert RENAME_MAP["odoo-dist-mac"] == "idtpp-mac-odoo-dist"
        assert RENAME_MAP["odoo-trad-tpp"] == "idtpp-tpp-odoo-trad"
        assert RENAME_MAP["abcfood-tmi"] == "abcfood-tmi-odoo"
        assert RENAME_MAP["odoo-full-kod"] == "kodemeio-kod-odoo-full"
        assert RENAME_MAP["odoo_full"] == "local-odoo-full"
        assert RENAME_MAP["odoo_hrms"] == "local-odoo-hrms"
        assert RENAME_MAP["odoo_found"] == "local-odoo-found"
        assert RENAME_MAP["local-tpp"] == "local-odoo-tpp"
        assert RENAME_MAP["dev"] == "local-odoo-dev"
        assert RENAME_MAP["mac-prod"] == "idtpp-mac-postgres"
        assert RENAME_MAP["mac"] == "idtpp-mac"

    def test_rename_targets_unique(self) -> None:
        from kctl_lib._migration import RENAME_MAP

        targets = list(RENAME_MAP.values())
        assert len(targets) == len(set(targets)), (
            f"RENAME_MAP has collisions: {sorted(t for t in targets if targets.count(t) > 1)}"
        )
