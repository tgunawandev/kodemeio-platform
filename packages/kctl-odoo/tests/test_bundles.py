"""Tests for the bundle YAML parser engine.

The bundle engine (``kctl_odoo.core.bundles``) is the most critical pure-logic
module in the CLI -- it must match the parsing semantics of ``bin/mod`` exactly.
Tests marked ``@pytest.mark.integration`` read real YAML files from the project's
``install/`` directory.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from kctl_odoo.core.bundles import (
    Bundle,
    BundleGroup,
    _find_bundle_file,
    _parse_bundle_entry,
    discover_bundles,
    discover_profiles,
    load_bundle,
    load_profile,
    resolve_modules,
    resolve_profile_modules,
)

# ---------------------------------------------------------------------------
# load_bundle
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestLoadBundleGroupsFormat:
    """Test loading a real groups-format bundle (core-mandatory.yaml)."""

    def test_groups_count(self, install_dir: Path) -> None:
        """core-mandatory.yaml has 10 groups."""
        bundle = load_bundle(install_dir / "core-mandatory.yaml")
        assert len(bundle.groups) == 10

    def test_default_modules_count(self, install_dir: Path) -> None:
        """core-mandatory default resolution produces 51 modules."""
        bundle = load_bundle(install_dir / "core-mandatory.yaml")
        modules = resolve_modules(bundle)
        assert len(modules) == 51

    def test_is_not_flat(self, install_dir: Path) -> None:
        """Groups-format bundles are not flat."""
        bundle = load_bundle(install_dir / "core-mandatory.yaml")
        assert bundle.is_flat is False

    def test_name_from_yaml(self, install_dir: Path) -> None:
        """Name is taken from the YAML 'name' key."""
        bundle = load_bundle(install_dir / "core-mandatory.yaml")
        assert bundle.name == "core-mandatory"

    def test_source_path(self, install_dir: Path) -> None:
        """Source path is recorded on the Bundle."""
        bundle = load_bundle(install_dir / "core-mandatory.yaml")
        assert bundle.source == install_dir / "core-mandatory.yaml"


class TestLoadBundleFlatFormat:
    """Test loading a simple list-format bundle from a temp file."""

    def test_flat_bundle(self, tmp_path: Path) -> None:
        """A YAML list file is loaded with is_flat=True."""
        content = ["mod_a", "mod_b", "mod_c"]
        path = tmp_path / "flat-test.yaml"
        path.write_text(yaml.dump(content), encoding="utf-8")

        bundle = load_bundle(path)
        assert bundle.is_flat is True
        assert bundle.flat_modules == ["mod_a", "mod_b", "mod_c"]
        assert bundle.name == "flat-test"

    def test_flat_total_modules(self, tmp_path: Path) -> None:
        """total_modules counts flat module list."""
        path = tmp_path / "flat.yaml"
        path.write_text(yaml.dump(["x", "y"]), encoding="utf-8")
        bundle = load_bundle(path)
        assert bundle.total_modules == 2


class TestLoadBundleEmpty:
    """Test loading empty or null YAML."""

    def test_empty_file(self, tmp_path: Path) -> None:
        """An empty YAML file returns an empty bundle with the file stem as name."""
        path = tmp_path / "empty.yaml"
        path.write_text("", encoding="utf-8")

        bundle = load_bundle(path)
        assert bundle.name == "empty"
        assert bundle.groups == {}
        assert bundle.flat_modules == []

    def test_null_content(self, tmp_path: Path) -> None:
        """A YAML file containing only 'null' returns an empty bundle."""
        path = tmp_path / "null-bundle.yaml"
        path.write_text("null\n", encoding="utf-8")

        bundle = load_bundle(path)
        assert bundle.name == "null-bundle"
        assert bundle.is_flat is False
        assert bundle.total_modules == 0


# ---------------------------------------------------------------------------
# resolve_modules
# ---------------------------------------------------------------------------


class TestResolveModulesDefault:
    """Test resolve with None groups (uses defaults)."""

    @pytest.mark.integration
    def test_uses_bundle_default(self, install_dir: Path) -> None:
        """Passing None for groups uses the bundle's default list."""
        bundle = load_bundle(install_dir / "oca-server.yaml")
        modules = resolve_modules(bundle, None)
        # oca-server defaults are [search, access_control] -> 6 modules
        assert len(modules) == 6
        assert "filter_multi_user" in modules
        assert "base_export_manager" in modules


class TestResolveModulesAll:
    """Test resolve with ["all"] returns every module across all groups."""

    @pytest.mark.integration
    def test_all_groups(self, install_dir: Path) -> None:
        """Passing ['all'] returns modules from every group."""
        bundle = load_bundle(install_dir / "oca-server.yaml")
        all_modules = resolve_modules(bundle, ["all"])
        # oca-server has 5 groups: search(2), data_tools(2), external_db(1),
        # access_control(4), queue_extended(1) = 10 total
        assert len(all_modules) == 10
        assert "jsonifier" in all_modules
        assert "queue_job_batch" in all_modules


class TestResolveModulesSpecificGroups:
    """Test resolve with specific group names."""

    @pytest.mark.integration
    def test_single_group(self, install_dir: Path) -> None:
        """Resolving a single group returns only that group's modules."""
        bundle = load_bundle(install_dir / "oca-server.yaml")
        modules = resolve_modules(bundle, ["data_tools"])
        assert modules == ["jsonifier", "base_revision"]

    @pytest.mark.integration
    def test_multiple_groups(self, install_dir: Path) -> None:
        """Resolving multiple groups returns modules in order."""
        bundle = load_bundle(install_dir / "oca-server.yaml")
        modules = resolve_modules(bundle, ["search", "external_db"])
        assert modules == ["filter_multi_user", "onchange_helper", "base_external_dbsource"]


class TestResolveModulesWithDependencies:
    """Test that group dependency resolution works correctly."""

    @pytest.mark.integration
    def test_dependency_order(self, install_dir: Path) -> None:
        """Groups with depends resolve their deps first.

        core-mandatory: 'sales' depends on [product, accounting],
        so requesting just 'sales' should include product and accounting
        modules before sales modules.
        """
        bundle = load_bundle(install_dir / "core-mandatory.yaml")
        modules = resolve_modules(bundle, ["sales"])
        # 'sales' depends on product(6) + accounting(5) -> then sales(7) = 18
        assert len(modules) == 18
        # Product modules come before sales
        product_idx = modules.index("product")
        sale_idx = modules.index("sale")
        assert product_idx < sale_idx
        # Accounting modules come before sales
        account_idx = modules.index("account")
        assert account_idx < sale_idx

    def test_synthetic_dependency_chain(self, tmp_path: Path) -> None:
        """A -> B -> C dependency chain resolves in order C, B, A."""
        data = {
            "name": "dep-test",
            "groups": {
                "a": {"depends": ["b"], "modules": ["mod_a"]},
                "b": {"depends": ["c"], "modules": ["mod_b"]},
                "c": {"modules": ["mod_c"]},
            },
            "default": ["a"],
        }
        path = tmp_path / "dep-test.yaml"
        path.write_text(yaml.dump(data), encoding="utf-8")

        bundle = load_bundle(path)
        modules = resolve_modules(bundle)
        assert modules == ["mod_c", "mod_b", "mod_a"]


class TestResolveModulesDeduplication:
    """Test that modules are not duplicated across groups."""

    def test_no_duplicates(self, tmp_path: Path) -> None:
        """If multiple groups share a module, it appears only once."""
        data = {
            "name": "dedup-test",
            "groups": {
                "g1": {"modules": ["shared", "only_g1"]},
                "g2": {"modules": ["shared", "only_g2"]},
            },
            "default": ["g1", "g2"],
        }
        path = tmp_path / "dedup.yaml"
        path.write_text(yaml.dump(data), encoding="utf-8")

        bundle = load_bundle(path)
        modules = resolve_modules(bundle)
        assert modules == ["shared", "only_g1", "only_g2"]
        assert modules.count("shared") == 1


class TestResolveModulesUnknownGroup:
    """Test that unknown group names are silently skipped."""

    def test_unknown_group_raises(self, tmp_path: Path) -> None:
        """Unknown group names fail loud — catches typos early."""
        data = {
            "name": "skip-test",
            "groups": {
                "real": {"modules": ["mod_a"]},
            },
            "default": ["real"],
        }
        path = tmp_path / "skip.yaml"
        path.write_text(yaml.dump(data), encoding="utf-8")

        bundle = load_bundle(path)
        with pytest.raises(ValueError, match="has no groups: nonexistent"):
            resolve_modules(bundle, ["real", "nonexistent"])

    def test_all_unknown_raises(self, tmp_path: Path) -> None:
        """If all requested groups are unknown, resolve_modules raises ValueError."""
        data = {
            "name": "empty-resolve",
            "groups": {
                "real": {"modules": ["mod_a"]},
            },
        }
        path = tmp_path / "empty-resolve.yaml"
        path.write_text(yaml.dump(data), encoding="utf-8")

        bundle = load_bundle(path)
        with pytest.raises(ValueError, match="has no groups: ghost, phantom"):
            resolve_modules(bundle, ["ghost", "phantom"])


class TestResolveModulesFlat:
    """Test that flat bundles ignore groups argument."""

    def test_flat_ignores_groups(self, tmp_path: Path) -> None:
        """resolve_modules on a flat bundle returns flat_modules regardless of groups arg."""
        path = tmp_path / "flat.yaml"
        path.write_text(yaml.dump(["x", "y", "z"]), encoding="utf-8")

        bundle = load_bundle(path)
        assert resolve_modules(bundle, ["anything"]) == ["x", "y", "z"]
        assert resolve_modules(bundle, None) == ["x", "y", "z"]


# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestLoadProfile:
    """Test loading a real profile YAML file."""

    def test_profile_foundation(self, install_dir: Path) -> None:
        """profile-foundation.yaml has mandatory + localization bundles."""
        profile = load_profile(install_dir / "profile-foundation.yaml")
        assert profile.name == "profile-foundation"
        assert len(profile.bundles) == 4
        assert "core-mandatory" in profile.bundles
        assert "core-localization" in profile.bundles
        assert "oca-mandatory" in profile.bundles
        assert "private-mandatory" in profile.bundles


@pytest.mark.integration
class TestResolveProfileModules:
    """Test resolving all modules across a profile's bundles."""

    def test_foundation_module_count(self, install_dir: Path) -> None:
        """Foundation profile resolves to a non-trivial number of modules."""
        profile = load_profile(install_dir / "profile-foundation.yaml")
        modules = resolve_profile_modules(profile, install_dir)
        # core-mandatory(51) + oca-mandatory + private-mandatory modules
        # Exact count depends on those bundles, but must be > 51
        assert len(modules) > 51

    def test_no_duplicates_across_bundles(self, install_dir: Path) -> None:
        """Modules are deduplicated across bundles."""
        profile = load_profile(install_dir / "profile-foundation.yaml")
        modules = resolve_profile_modules(profile, install_dir)
        assert len(modules) == len(set(modules))


class TestProfileBundleColonSyntax:
    """Test the bundle:group1,group2 colon syntax used in profiles."""

    def test_colon_syntax_groups(self, tmp_path: Path) -> None:
        """Profile entries like 'mybundle:g1,g2' pass groups to resolve."""
        # Create a bundle
        bundle_data = {
            "name": "mybundle",
            "groups": {
                "g1": {"modules": ["mod_a"]},
                "g2": {"modules": ["mod_b"]},
                "g3": {"modules": ["mod_c"]},
            },
            "default": ["g1", "g2", "g3"],
        }
        (tmp_path / "mybundle.yaml").write_text(yaml.dump(bundle_data), encoding="utf-8")

        # Create a profile that references only g1 and g2
        profile_data = {
            "name": "test-profile",
            "bundles": ["mybundle:g1,g2"],
        }
        (tmp_path / "profile-test.yaml").write_text(yaml.dump(profile_data), encoding="utf-8")

        profile = load_profile(tmp_path / "profile-test.yaml")
        modules = resolve_profile_modules(profile, tmp_path)
        assert modules == ["mod_a", "mod_b"]
        assert "mod_c" not in modules


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestDiscoverBundles:
    """Test discovering bundle files in install/."""

    def test_discover_count(self, install_dir: Path) -> None:
        """Discover at least 60 bundles (excluding profiles)."""
        bundles = discover_bundles(install_dir)
        assert len(bundles) >= 60

    def test_no_profiles_included(self, install_dir: Path) -> None:
        """Discovered bundles do not include profile-* files."""
        bundles = discover_bundles(install_dir)
        for b in bundles:
            assert not b.name.startswith("profile-"), f"Profile leaked into bundles: {b.name}"

    def test_all_have_names(self, install_dir: Path) -> None:
        """Every discovered bundle has a non-empty name."""
        bundles = discover_bundles(install_dir)
        for b in bundles:
            assert b.name, f"Bundle with empty name from {b.source}"


@pytest.mark.integration
class TestDiscoverProfiles:
    """Test discovering profile files in install/."""

    def test_discover_count(self, install_dir: Path) -> None:
        """Discover at least 10 profiles."""
        profiles = discover_profiles(install_dir)
        assert len(profiles) >= 10

    def test_all_sourced_from_profile_files(self, install_dir: Path) -> None:
        """All discovered profiles originate from profile-*.yaml files."""
        profiles = discover_profiles(install_dir)
        for p in profiles:
            assert p.source is not None, f"Profile missing source: {p.name}"
            assert p.source.name.startswith("profile-"), f"Profile sourced from non-profile file: {p.source.name}"


# ---------------------------------------------------------------------------
# Helpers: _parse_bundle_entry, _find_bundle_file
# ---------------------------------------------------------------------------


class TestParseBundleEntry:
    """Test the _parse_bundle_entry helper."""

    def test_simple_name(self) -> None:
        """A plain name returns (name, None)."""
        name, groups = _parse_bundle_entry("oca-server")
        assert name == "oca-server"
        assert groups is None

    def test_with_single_group(self) -> None:
        """'private-retail:analytics' parses correctly."""
        name, groups = _parse_bundle_entry("private-retail:analytics")
        assert name == "private-retail"
        assert groups == ["analytics"]

    def test_with_multiple_groups(self) -> None:
        """'private-retail:analytics,core' parses both groups."""
        name, groups = _parse_bundle_entry("private-retail:analytics,core")
        assert name == "private-retail"
        assert groups == ["analytics", "core"]

    def test_whitespace_handling(self) -> None:
        """Whitespace around names and groups is stripped."""
        name, groups = _parse_bundle_entry("  my-bundle : g1 , g2 ")
        assert name == "my-bundle"
        assert groups == ["g1", "g2"]

    def test_empty_groups_after_colon(self) -> None:
        """'bundle:' with nothing after colon returns empty groups list."""
        name, groups = _parse_bundle_entry("bundle:")
        assert name == "bundle"
        assert groups == []


class TestFindBundleFile:
    """Test the _find_bundle_file helper."""

    @pytest.mark.integration
    def test_finds_yaml(self, install_dir: Path) -> None:
        """Finds core-mandatory.yaml by name."""
        result = _find_bundle_file(install_dir, "core-mandatory")
        assert result is not None
        assert result.name == "core-mandatory.yaml"

    def test_returns_none_for_missing(self, tmp_path: Path) -> None:
        """Returns None when no matching file exists."""
        result = _find_bundle_file(tmp_path, "does-not-exist")
        assert result is None

    def test_prefers_yaml_over_yml(self, tmp_path: Path) -> None:
        """If both .yaml and .yml exist, .yaml is found first."""
        (tmp_path / "test.yaml").write_text("[]", encoding="utf-8")
        (tmp_path / "test.yml").write_text("[]", encoding="utf-8")
        result = _find_bundle_file(tmp_path, "test")
        assert result is not None
        assert result.suffix == ".yaml"


# ---------------------------------------------------------------------------
# Golden file: oca-server default modules
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestGoldenFileOcaServer:
    """Validate oca-server.yaml default resolution against a known-good output.

    This catches accidental edits to bundle YAML files that would change the
    module install set.
    """

    EXPECTED = (
        "filter_multi_user,"
        "onchange_helper,"
        "base_export_manager,"
        "base_import_security_group,"
        "base_menu_visibility_restriction,"
        "base_optional_quick_create"
    )

    def test_default_modules_match(self, install_dir: Path) -> None:
        """oca-server default resolution matches the golden comma-separated list."""
        bundle = load_bundle(install_dir / "oca-server.yaml")
        modules = resolve_modules(bundle)
        result = ",".join(modules)
        assert result == self.EXPECTED, (
            f"oca-server default modules changed!\n  Expected: {self.EXPECTED}\n  Got:      {result}"
        )


# ---------------------------------------------------------------------------
# Bundle model properties
# ---------------------------------------------------------------------------


class TestBundleModel:
    """Test Bundle pydantic model properties."""

    def test_total_modules_groups(self) -> None:
        """total_modules counts unique modules across groups."""
        bundle = Bundle(
            name="test",
            groups={
                "g1": BundleGroup(modules=["a", "b"]),
                "g2": BundleGroup(modules=["b", "c"]),
            },
        )
        assert bundle.total_modules == 3

    def test_total_modules_flat(self) -> None:
        """total_modules on flat bundle counts flat_modules."""
        bundle = Bundle(name="test", flat_modules=["x", "y"])
        assert bundle.total_modules == 2

    def test_is_flat_true(self) -> None:
        """is_flat is True when flat_modules is populated and groups is empty."""
        bundle = Bundle(name="test", flat_modules=["x"])
        assert bundle.is_flat is True

    def test_is_flat_false_with_groups(self) -> None:
        """is_flat is False when groups are present even if flat_modules set."""
        bundle = Bundle(
            name="test",
            flat_modules=["x"],
            groups={"g": BundleGroup(modules=["y"])},
        )
        assert bundle.is_flat is False
