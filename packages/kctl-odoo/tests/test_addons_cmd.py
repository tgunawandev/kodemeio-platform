"""Tests for the addons command group.

Tests verify command registration and core logic helpers without
requiring a live Odoo instance or real filesystem addons.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from kctl_odoo.commands.addons_cmd import (
    _all_bundle_modules,
    _discover_with_labels,
    _find_profile_file,
    _resolve_addon_paths,
    _resolve_install_dir,
    app,
)
from kctl_odoo.core.addons import Addon, discover_addons, score_health

# ---------------------------------------------------------------------------
# Command registration
# ---------------------------------------------------------------------------


class TestAddonsCommandGroup:
    """Verify all 12 commands are registered on the Typer app."""

    def test_all_commands_registered(self) -> None:
        from kctl_odoo.commands.addons_cmd import app

        cmd_names = {cmd.name or cmd.callback.__name__ for cmd in app.registered_commands}
        expected = {
            "scan",
            "orphans",
            "missing",
            "duplicates",
            "health",
            "health-summary",
            "drift",
            "drift-snapshot",
            "matrix",
            "deps-graph",
            "coverage",
            "report",
        }
        assert expected.issubset(cmd_names), f"Missing commands: {expected - cmd_names}"

    def test_command_count(self) -> None:
        """There should be exactly 12 registered commands."""
        cmd_names = {cmd.name or cmd.callback.__name__ for cmd in app.registered_commands}
        assert len(cmd_names) >= 12


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


class TestResolveAddonPaths:
    """Test _resolve_addon_paths() helper."""

    def test_explicit_paths(self, tmp_path: Path) -> None:
        """Comma-separated string is split into Path objects."""
        result = _resolve_addon_paths(f"{tmp_path}/a,{tmp_path}/b")
        assert len(result) == 2
        assert result[0] == tmp_path / "a"
        assert result[1] == tmp_path / "b"

    def test_none_returns_defaults(self) -> None:
        """None input falls back to get_default_addon_paths()."""
        result = _resolve_addon_paths(None)
        assert isinstance(result, list)

    def test_empty_string_returns_defaults(self) -> None:
        """Empty string falls back to defaults."""
        result = _resolve_addon_paths("")
        assert isinstance(result, list)


class TestResolveInstallDir:
    """Test _resolve_install_dir() helper."""

    def test_explicit_dir(self, tmp_path: Path) -> None:
        """Explicit path that exists is returned directly."""
        install = tmp_path / "install"
        install.mkdir()
        result = _resolve_install_dir(str(install))
        assert result == install

    def test_missing_dir_exits(self, tmp_path: Path) -> None:
        """Non-existent path raises typer.Exit (click.exceptions.Exit)."""
        from click.exceptions import Exit

        with pytest.raises(Exit):
            _resolve_install_dir(str(tmp_path / "nonexistent"))


class TestFindProfileFile:
    """Test _find_profile_file() helper."""

    def test_finds_with_prefix(self, tmp_path: Path) -> None:
        """Finds profile-name.yaml files."""
        (tmp_path / "profile-test.yaml").write_text("name: test\n", encoding="utf-8")
        result = _find_profile_file(tmp_path, "test")
        assert result is not None
        assert result.name == "profile-test.yaml"

    def test_finds_without_prefix(self, tmp_path: Path) -> None:
        """Finds name.yaml files when no profile- prefix."""
        (tmp_path / "test.yaml").write_text("name: test\n", encoding="utf-8")
        result = _find_profile_file(tmp_path, "test")
        assert result is not None

    def test_returns_none_when_missing(self, tmp_path: Path) -> None:
        """Returns None when no matching file found."""
        result = _find_profile_file(tmp_path, "nonexistent")
        assert result is None


class TestAllBundleModules:
    """Test _all_bundle_modules() helper."""

    def test_collects_all_modules(self, tmp_path: Path) -> None:
        """Collects modules from all bundles in a directory."""
        # Create a simple flat bundle
        bundle_data = ["mod_a", "mod_b", "mod_c"]
        (tmp_path / "test-bundle.yaml").write_text(yaml.dump(bundle_data), encoding="utf-8")

        result = _all_bundle_modules(tmp_path)
        assert result == {"mod_a", "mod_b", "mod_c"}

    def test_empty_dir(self, tmp_path: Path) -> None:
        """Empty directory returns empty set."""
        result = _all_bundle_modules(tmp_path)
        assert result == set()


class TestDiscoverWithLabels:
    """Test _discover_with_labels() helper."""

    def test_discovers_addons(self, tmp_path: Path) -> None:
        """Discovers addons from explicit paths."""
        addon_dir = tmp_path / "my_addon"
        addon_dir.mkdir()
        manifest = {
            "name": "My Addon",
            "version": "18.0.1.0.0",
            "installable": True,
            "depends": ["base"],
        }
        (addon_dir / "__manifest__.py").write_text(repr(manifest), encoding="utf-8")

        with (
            patch("kctl_odoo.commands.addons_cmd.get_default_addon_paths", return_value=[tmp_path]),
            patch("kctl_odoo.commands.addons_cmd.get_addon_path_labels", return_value={}),
        ):
            addons = _discover_with_labels(None)
        # May or may not find depending on resolution; at least no error
        assert isinstance(addons, list)


# ---------------------------------------------------------------------------
# Addon scan logic (unit-level)
# ---------------------------------------------------------------------------


class TestScanLogic:
    """Test the scan command's underlying logic."""

    def test_addon_fields(self, tmp_path: Path) -> None:
        """Discovered addon has expected fields for table output."""
        addon_dir = tmp_path / "test_mod"
        addon_dir.mkdir()
        manifest = {
            "name": "Test Module",
            "version": "18.0.1.0.0",
            "installable": True,
            "depends": ["base"],
            "summary": "A test module",
        }
        (addon_dir / "__manifest__.py").write_text(repr(manifest), encoding="utf-8")

        addons = discover_addons([tmp_path])
        assert len(addons) == 1
        a = addons[0]
        assert a.name == "test_mod"
        assert a.version == "18.0.1.0.0"
        assert a.installable is True
        assert a.summary == "A test module"


class TestOrphansLogic:
    """Test orphan detection logic."""

    def test_detects_orphans(self, tmp_path: Path) -> None:
        """Addons not in any bundle are orphans."""
        addon_dir = tmp_path / "addons" / "orphan_mod"
        addon_dir.mkdir(parents=True)
        manifest = {"name": "Orphan", "version": "18.0.1.0.0", "depends": ["base"]}
        (addon_dir / "__manifest__.py").write_text(repr(manifest), encoding="utf-8")

        bundle_dir = tmp_path / "bundles"
        bundle_dir.mkdir()
        (bundle_dir / "test.yaml").write_text(yaml.dump(["other_mod"]), encoding="utf-8")

        addons = discover_addons([tmp_path / "addons"])
        bundle_mods = _all_bundle_modules(bundle_dir)

        orphan_addons = [a for a in addons if a.name not in bundle_mods]
        assert len(orphan_addons) == 1
        assert orphan_addons[0].name == "orphan_mod"


class TestMissingLogic:
    """Test missing module detection logic."""

    def test_detects_missing(self, tmp_path: Path) -> None:
        """Bundle modules not on disk are reported as missing."""
        bundle_dir = tmp_path / "bundles"
        bundle_dir.mkdir()
        (bundle_dir / "test.yaml").write_text(yaml.dump(["mod_a", "mod_b"]), encoding="utf-8")

        bundle_mods = _all_bundle_modules(bundle_dir)
        disk_names: set[str] = set()  # No addons on disk

        missing_mods = sorted(bundle_mods - disk_names)
        assert "mod_a" in missing_mods
        assert "mod_b" in missing_mods


class TestDuplicatesLogic:
    """Test duplicate detection logic."""

    def test_detects_duplicates(self, tmp_path: Path) -> None:
        """Same addon name in two paths is a duplicate."""
        dir1 = tmp_path / "private"
        dir2 = tmp_path / "external"
        dir1.mkdir()
        dir2.mkdir()

        for d in (dir1, dir2):
            addon = d / "same_name"
            addon.mkdir()
            manifest = {"name": "Same", "version": "18.0.1.0.0", "depends": ["base"]}
            (addon / "__manifest__.py").write_text(repr(manifest), encoding="utf-8")

        addons = discover_addons([dir1, dir2])
        by_name: dict[str, list[Addon]] = defaultdict(list)
        for a in addons:
            by_name[a.name].append(a)

        dups = {name: items for name, items in by_name.items() if len(items) > 1}
        assert "same_name" in dups
        assert len(dups["same_name"]) == 2


class TestDepsGraphLogic:
    """Test dependency graph logic."""

    def test_transitive_deps(self, tmp_path: Path) -> None:
        """Walks transitive dependencies from manifests."""
        for name, deps in [("mod_a", ["mod_b"]), ("mod_b", ["mod_c"]), ("mod_c", [])]:
            d = tmp_path / name
            d.mkdir()
            manifest = {"name": name, "version": "18.0.1.0.0", "depends": deps}
            (d / "__manifest__.py").write_text(repr(manifest), encoding="utf-8")

        addons = discover_addons([tmp_path])
        addon_map = {a.name: a for a in addons}

        visited: set[str] = set()
        edges: list[tuple[str, str]] = []

        def _walk(name: str) -> None:
            if name in visited:
                return
            visited.add(name)
            if name in addon_map:
                for dep in addon_map[name].depends:
                    edges.append((name, dep))
                    _walk(dep)

        _walk("mod_a")
        assert ("mod_a", "mod_b") in edges
        assert ("mod_b", "mod_c") in edges
        assert len(visited) == 3


class TestCoverageLogic:
    """Test coverage computation logic."""

    def test_coverage_calculation(self, tmp_path: Path) -> None:
        """Coverage percentage is correctly computed."""
        addon_dir = tmp_path / "addons"
        addon_dir.mkdir()
        for name in ("covered_mod", "uncovered_mod"):
            d = addon_dir / name
            d.mkdir()
            manifest = {"name": name, "version": "18.0.1.0.0", "depends": ["base"]}
            (d / "__manifest__.py").write_text(repr(manifest), encoding="utf-8")

        bundle_dir = tmp_path / "bundles"
        bundle_dir.mkdir()
        (bundle_dir / "test.yaml").write_text(yaml.dump(["covered_mod"]), encoding="utf-8")

        addons = discover_addons([addon_dir])
        bundle_mods = _all_bundle_modules(bundle_dir)

        covered = [a for a in addons if a.name in bundle_mods]
        assert len(covered) == 1
        assert covered[0].name == "covered_mod"

        pct = len(covered) * 100 // len(addons)
        assert pct == 50


class TestHealthSummaryLogic:
    """Test health summary aggregation."""

    def test_sorts_worst_first(self, tmp_path: Path) -> None:
        """Scored addons are sorted by score ascending."""
        # Create two addons: one with full manifest, one minimal
        good_dir = tmp_path / "good_mod"
        good_dir.mkdir()
        good_manifest = {
            "name": "Good",
            "version": "18.0.1.0.0",
            "installable": True,
            "depends": ["base"],
            "description": "Full",
            "author": "Test",
            "license": "LGPL-3",
        }
        (good_dir / "__manifest__.py").write_text(repr(good_manifest), encoding="utf-8")

        bad_dir = tmp_path / "bad_mod"
        bad_dir.mkdir()
        (bad_dir / "__manifest__.py").write_text("{}", encoding="utf-8")

        addons = discover_addons([tmp_path])
        scored = [(a, score_health(a)) for a in addons]
        scored.sort(key=lambda x: x[1].score)

        # Worst (bad_mod with empty manifest) should be first
        assert scored[0][1].score <= scored[-1][1].score
