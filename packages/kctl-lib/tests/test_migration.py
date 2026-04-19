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


class TestDropProfiles:
    def test_test_pollution_profiles_dropped(self) -> None:
        from kctl_lib._migration import DROP_PROFILES

        pollution = {
            "settest",
            "setbad",
            "masktest",
            "shortpass",
            "longpass",
            "saved-profile",
            "full-profile",
            "myprofile",
            "show-test",
            "inttest",
            "active",
            "alpha",
            "beta",
            "prod",
        }
        assert pollution <= DROP_PROFILES

    def test_stale_duplicates_dropped(self) -> None:
        from kctl_lib._migration import DROP_PROFILES

        # These have placeholder api_key: admin while canonical entries
        # (see spec step 4 of migration) hold the real credentials.
        stale = {"mac-erp", "odoo-hrms-mac", "odoo-hrms-tpp"}
        assert stale <= DROP_PROFILES

    def test_drop_and_rename_disjoint(self) -> None:
        from kctl_lib._migration import DROP_PROFILES, RENAME_MAP

        overlap = DROP_PROFILES & set(RENAME_MAP.keys())
        assert not overlap, f"Profiles cannot be both dropped and renamed: {overlap}"
