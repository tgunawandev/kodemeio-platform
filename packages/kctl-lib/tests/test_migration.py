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


class TestApplyRenameAndDrop:
    def test_renames_canonical_keepers(self) -> None:
        from kctl_lib._migration import apply_rename_and_drop

        before = {
            "profiles": {
                "tpp-odoo-erp": {"odoo": {"database": "tpp_odoo_erp"}},
                "idtpp": {"dokploy": {"url": "https://dokploy.idtpp.com"}},
            }
        }
        after = apply_rename_and_drop(before)
        assert "tpp-odoo-erp" not in after["profiles"]
        assert after["profiles"]["idtpp-tpp-odoo-erp"] == {"odoo": {"database": "tpp_odoo_erp"}}
        # Unaffected profile is preserved.
        assert after["profiles"]["idtpp"] == {"dokploy": {"url": "https://dokploy.idtpp.com"}}

    def test_drops_test_pollution(self) -> None:
        from kctl_lib._migration import apply_rename_and_drop

        before = {
            "profiles": {
                "settest": {"redis": {"host": "10.0.0.99"}},
                "idtpp": {"dokploy": {"url": "x"}},
            }
        }
        after = apply_rename_and_drop(before)
        assert "settest" not in after["profiles"]
        assert "idtpp" in after["profiles"]

    def test_drops_stale_duplicates(self) -> None:
        from kctl_lib._migration import apply_rename_and_drop

        before = {
            "profiles": {
                "mac-erp": {"odoo": {"api_key": "admin"}},
                "mac-odoo-erp": {"odoo": {"api_key": "Mac@2026#"}},
            }
        }
        after = apply_rename_and_drop(before)
        assert "mac-erp" not in after["profiles"]
        # mac-odoo-erp gets renamed to idtpp-mac-odoo-erp.
        assert after["profiles"]["idtpp-mac-odoo-erp"] == {"odoo": {"api_key": "Mac@2026#"}}

    def test_preserves_unknown_profiles(self) -> None:
        from kctl_lib._migration import apply_rename_and_drop

        before = {"profiles": {"some-future-profile": {"odoo": {"url": "x"}}}}
        after = apply_rename_and_drop(before)
        assert after["profiles"]["some-future-profile"] == {"odoo": {"url": "x"}}

    def test_rename_collision_raises(self) -> None:
        from kctl_lib._migration import apply_rename_and_drop

        # If both old and new names already exist, refuse rather than silently merge.
        before = {
            "profiles": {
                "tpp-odoo-erp": {"odoo": {"api_key": "old"}},
                "idtpp-tpp-odoo-erp": {"odoo": {"api_key": "new"}},
            }
        }
        try:
            apply_rename_and_drop(before)
        except ValueError as exc:
            assert "collision" in str(exc).lower()
            assert "idtpp-tpp-odoo-erp" in str(exc)
        else:
            raise AssertionError("Expected ValueError on rename collision")


class TestDedupeServiceKeys:
    def test_drops_onepassword_when_op_present(self) -> None:
        from kctl_lib._migration import dedupe_service_keys

        before = {
            "profiles": {
                "kodemeio": {
                    "op": {"vault": "Kodemeio", "service_account_token": "keep"},
                    "onepassword": {"vault": "Kodemeio", "service_account_token": "legacy"},
                }
            }
        }
        after = dedupe_service_keys(before)
        assert "onepassword" not in after["profiles"]["kodemeio"]
        assert after["profiles"]["kodemeio"]["op"]["service_account_token"] == "keep"

    def test_promotes_onepassword_when_op_missing(self) -> None:
        from kctl_lib._migration import dedupe_service_keys

        before = {"profiles": {"legacy": {"onepassword": {"vault": "Foo", "service_account_token": "legacy"}}}}
        after = dedupe_service_keys(before)
        assert "onepassword" not in after["profiles"]["legacy"]
        assert after["profiles"]["legacy"]["op"] == {"vault": "Foo", "service_account_token": "legacy"}

    def test_drops_sentry_dup_in_kodemeio(self) -> None:
        from kctl_lib._migration import dedupe_service_keys

        # kodemeio.sentry.auth_token was a copy of kodemeio.glitchtip.token
        # pointing at the same URL (glitchtip.kodeme.io). Drop it — kctl-sentry
        # can use the kodemeio.glitchtip block (same Sentry-compat API).
        before = {
            "profiles": {
                "kodemeio": {
                    "glitchtip": {
                        "url": "https://glitchtip.kodeme.io",
                        "token": "abc",
                    },
                    "sentry": {
                        "url": "https://glitchtip.kodeme.io",
                        "auth_token": "abc",
                    },
                }
            }
        }
        after = dedupe_service_keys(before)
        assert "sentry" not in after["profiles"]["kodemeio"]
        assert after["profiles"]["kodemeio"]["glitchtip"]["token"] == "abc"

    def test_keeps_sentry_if_distinct_server(self) -> None:
        from kctl_lib._migration import dedupe_service_keys

        before = {
            "profiles": {
                "kodemeio": {
                    "glitchtip": {
                        "url": "https://glitchtip.kodeme.io",
                        "token": "gtip",
                    },
                    "sentry": {
                        "url": "https://sentry.io",
                        "auth_token": "real-sentry",
                    },
                }
            }
        }
        after = dedupe_service_keys(before)
        assert after["profiles"]["kodemeio"]["sentry"]["url"] == "https://sentry.io"

    def test_leaves_other_profiles_alone(self) -> None:
        from kctl_lib._migration import dedupe_service_keys

        before = {"profiles": {"abcfood": {"op": {"vault": "ABCFood"}}}}
        after = dedupe_service_keys(before)
        assert after == before


class TestStripDefaultProfile:
    def test_removes_default_profile_key(self) -> None:
        from kctl_lib._migration import strip_default_profile

        before = {"default_profile": "idtpp", "profiles": {"idtpp": {}}}
        after = strip_default_profile(before)
        assert "default_profile" not in after
        assert after["profiles"] == {"idtpp": {}}

    def test_no_op_when_absent(self) -> None:
        from kctl_lib._migration import strip_default_profile

        before = {"profiles": {}}
        after = strip_default_profile(before)
        assert after == {"profiles": {}}


class TestMigrateConfig:
    def test_composes_all_transforms(self) -> None:
        from kctl_lib._migration import migrate_config

        before = {
            "default_profile": "idtpp",
            "profiles": {
                "idtpp": {
                    "dokploy": {"url": "https://dokploy.idtpp.com"},
                    "op": {"vault": "TPP"},
                    "onepassword": {"vault": "TPP-legacy"},
                },
                "kodemeio": {
                    "glitchtip": {"url": "https://glitchtip.kodeme.io", "token": "x"},
                    "sentry": {"url": "https://glitchtip.kodeme.io", "auth_token": "x"},
                },
                "tpp-odoo-erp": {"odoo": {"database": "tpp_odoo_erp"}},
                "mac-erp": {"odoo": {"api_key": "admin"}},
                "settest": {"redis": {"host": "10.0.0.99"}},
            },
        }
        after = migrate_config(before)

        # default_profile gone
        assert "default_profile" not in after
        # rename applied
        assert "tpp-odoo-erp" not in after["profiles"]
        assert "idtpp-tpp-odoo-erp" in after["profiles"]
        # stale duplicate dropped
        assert "mac-erp" not in after["profiles"]
        # test pollution dropped
        assert "settest" not in after["profiles"]
        # dedupe: onepassword gone, op kept
        assert "onepassword" not in after["profiles"]["idtpp"]
        assert after["profiles"]["idtpp"]["op"] == {"vault": "TPP"}
        # dedupe: sentry dropped in kodemeio
        assert "sentry" not in after["profiles"]["kodemeio"]
        # untouched fields preserved
        assert after["profiles"]["idtpp"]["dokploy"]["url"] == "https://dokploy.idtpp.com"

    def test_idempotent(self) -> None:
        from kctl_lib._migration import migrate_config

        before = {
            "default_profile": "idtpp",
            "profiles": {"tpp-odoo-erp": {"odoo": {"database": "tpp_odoo_erp"}}},
        }
        once = migrate_config(before)
        twice = migrate_config(once)
        assert once == twice


class TestFixtureEndToEnd:
    def test_dirty_fixture_migrates_to_clean_fixture(self) -> None:
        from pathlib import Path

        import yaml

        from kctl_lib._migration import migrate_config

        fixtures = Path(__file__).parent / "fixtures"
        dirty = yaml.safe_load((fixtures / "dirty_config.yaml").read_text())
        expected = yaml.safe_load((fixtures / "clean_config.yaml").read_text())

        actual = migrate_config(dirty)
        assert actual == expected, (
            f"Migration result diverged from expected fixture. "
            f"Got keys {sorted(actual.get('profiles', {}))}; "
            f"expected {sorted(expected.get('profiles', {}))}"
        )
