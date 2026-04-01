"""Tests for the validate, graph, and find-module bundle helpers.

Exercises the three pure-logic helpers added in commands/bundles.py:
- _find_module_in_bundles
- _build_bundle_graph
- _has_circular_dep
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from kctl_odoo.commands.bundles import (
    _build_bundle_graph,
    _find_module_in_bundles,
    _has_circular_dep,
)
from kctl_odoo.core.bundles import Bundle, BundleGroup


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _write_bundle(tmp_path: Path, name: str, data: object) -> Path:
    """Write a bundle YAML file into *tmp_path* and return its path."""
    path = tmp_path / f"{name}.yaml"
    path.write_text(yaml.dump(data), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# _find_module_in_bundles
# ---------------------------------------------------------------------------


class TestFindModuleInBundles:
    """Unit tests for _find_module_in_bundles."""

    def test_finds_module_in_grouped_bundle(self, tmp_path: Path) -> None:
        """Module present in a grouped bundle is returned with its group name."""
        _write_bundle(
            tmp_path,
            "oca-server",
            {
                "name": "oca-server",
                "groups": {
                    "search": {"modules": ["filter_multi_user", "onchange_helper"]},
                    "data_tools": {"modules": ["jsonifier", "base_revision"]},
                },
                "default": ["search"],
            },
        )

        matches = _find_module_in_bundles(tmp_path, "jsonifier")
        assert matches == [("oca-server", "data_tools")]

    def test_finds_module_in_flat_bundle(self, tmp_path: Path) -> None:
        """Module present in a flat bundle is returned with group '(flat)'."""
        _write_bundle(tmp_path, "flat-bundle", ["mod_a", "mod_b", "mod_c"])

        matches = _find_module_in_bundles(tmp_path, "mod_b")
        assert matches == [("flat-bundle", "(flat)")]

    def test_finds_module_in_multiple_bundles(self, tmp_path: Path) -> None:
        """When a module appears in more than one bundle, all matches are returned."""
        _write_bundle(
            tmp_path,
            "bundle-one",
            {
                "name": "bundle-one",
                "groups": {"core": {"modules": ["shared_mod", "only_one"]}},
                "default": ["core"],
            },
        )
        _write_bundle(
            tmp_path,
            "bundle-two",
            {
                "name": "bundle-two",
                "groups": {"extra": {"modules": ["shared_mod", "only_two"]}},
                "default": ["extra"],
            },
        )

        matches = _find_module_in_bundles(tmp_path, "shared_mod")
        bundle_names = [m[0] for m in matches]
        assert "bundle-one" in bundle_names
        assert "bundle-two" in bundle_names
        assert len(matches) == 2

    def test_returns_empty_list_when_not_found(self, tmp_path: Path) -> None:
        """Returns an empty list when the module does not exist in any bundle."""
        _write_bundle(tmp_path, "some-bundle", ["mod_x", "mod_y"])

        matches = _find_module_in_bundles(tmp_path, "nonexistent_module")
        assert matches == []

    def test_empty_directory_returns_empty_list(self, tmp_path: Path) -> None:
        """Returns empty list when no bundles are present in the directory."""
        matches = _find_module_in_bundles(tmp_path, "any_module")
        assert matches == []

    def test_finds_module_in_correct_group_among_many(self, tmp_path: Path) -> None:
        """Returns the correct group when a bundle has several groups."""
        _write_bundle(
            tmp_path,
            "multi-group",
            {
                "name": "multi-group",
                "groups": {
                    "alpha": {"modules": ["mod_a"]},
                    "beta": {"modules": ["mod_b"]},
                    "gamma": {"modules": ["mod_c", "target_mod"]},
                },
                "default": ["alpha", "beta", "gamma"],
            },
        )

        matches = _find_module_in_bundles(tmp_path, "target_mod")
        assert matches == [("multi-group", "gamma")]


# ---------------------------------------------------------------------------
# _build_bundle_graph
# ---------------------------------------------------------------------------


class TestBuildBundleGraph:
    """Unit tests for _build_bundle_graph."""

    def test_returns_requires_for_bundle(self, tmp_path: Path) -> None:
        """A bundle with 'requires' returns the correct dependency list."""
        _write_bundle(
            tmp_path,
            "private-sale",
            {
                "name": "private-sale",
                "requires": ["core-sale", "oca-sale"],
                "groups": {"core": {"modules": ["sale_ext"]}},
                "default": ["core"],
            },
        )

        graph = _build_bundle_graph(tmp_path)
        assert "private-sale" in graph
        assert graph["private-sale"] == ["core-sale", "oca-sale"]

    def test_returns_empty_list_for_no_requires(self, tmp_path: Path) -> None:
        """A bundle without 'requires' maps to an empty list."""
        _write_bundle(
            tmp_path,
            "standalone",
            {
                "name": "standalone",
                "groups": {"core": {"modules": ["mod_a"]}},
                "default": ["core"],
            },
        )

        graph = _build_bundle_graph(tmp_path)
        assert graph["standalone"] == []

    def test_multiple_bundles_in_graph(self, tmp_path: Path) -> None:
        """All bundles are present as keys in the returned graph."""
        for name in ("bundle-a", "bundle-b", "bundle-c"):
            _write_bundle(tmp_path, name, ["mod_x"])

        graph = _build_bundle_graph(tmp_path)
        assert set(graph.keys()) == {"bundle-a", "bundle-b", "bundle-c"}

    def test_flat_bundle_has_empty_requires(self, tmp_path: Path) -> None:
        """Flat bundles (simple list format) have an empty requires list."""
        _write_bundle(tmp_path, "flat", ["mod_a", "mod_b"])

        graph = _build_bundle_graph(tmp_path)
        assert graph["flat"] == []

    def test_empty_directory_returns_empty_graph(self, tmp_path: Path) -> None:
        """An install directory with no bundles returns an empty graph dict."""
        graph = _build_bundle_graph(tmp_path)
        assert graph == {}


# ---------------------------------------------------------------------------
# _has_circular_dep
# ---------------------------------------------------------------------------


class TestHasCircularDep:
    """Unit tests for _has_circular_dep."""

    def _make_bundle(self, groups: dict[str, list[str]]) -> Bundle:
        """Build a synthetic Bundle with the given {group: depends} mapping."""
        return Bundle(
            name="test-bundle",
            groups={gname: BundleGroup(modules=["mod"], depends=deps) for gname, deps in groups.items()},
            default=list(groups.keys()),
        )

    def test_no_cycle_linear_chain(self) -> None:
        """A linear A -> B -> C chain has no circular dependency."""
        bundle = self._make_bundle(
            {
                "a": ["b"],
                "b": ["c"],
                "c": [],
            }
        )
        assert _has_circular_dep(bundle, "a", set(), []) is False

    def test_detects_direct_self_loop(self) -> None:
        """A group that depends on itself is a circular dependency."""
        bundle = self._make_bundle({"loop": ["loop"]})
        chain: list[str] = []
        result = _has_circular_dep(bundle, "loop", set(), chain)
        assert result is True

    def test_detects_two_node_cycle(self) -> None:
        """A <-> B is detected as a circular dependency."""
        bundle = self._make_bundle(
            {
                "a": ["b"],
                "b": ["a"],
            }
        )
        chain: list[str] = []
        result = _has_circular_dep(bundle, "a", set(), chain)
        assert result is True

    def test_detects_longer_cycle(self) -> None:
        """A -> B -> C -> A cycle is detected."""
        bundle = self._make_bundle(
            {
                "a": ["b"],
                "b": ["c"],
                "c": ["a"],
            }
        )
        chain: list[str] = []
        result = _has_circular_dep(bundle, "a", set(), chain)
        assert result is True

    def test_no_cycle_independent_groups(self) -> None:
        """Groups with no inter-dependencies have no circular deps."""
        bundle = self._make_bundle(
            {
                "g1": [],
                "g2": [],
                "g3": [],
            }
        )
        for gname in ("g1", "g2", "g3"):
            assert _has_circular_dep(bundle, gname, set(), []) is False

    def test_unknown_dep_does_not_raise(self) -> None:
        """A dependency on a non-existent group does not cause an error."""
        bundle = self._make_bundle({"a": ["phantom_group"]})
        assert _has_circular_dep(bundle, "a", set(), []) is False
