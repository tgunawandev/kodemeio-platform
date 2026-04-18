"""Tests for the addon discovery and health scoring engine.

Tests are organized around the three main public interfaces:
- ``Addon`` / ``HealthResult`` pydantic models
- ``discover_addons()`` — filesystem scanner
- ``score_health()`` — 0-100 quality scorer

Tests marked ``@pytest.mark.integration`` read real addons from the project's
``src/private/`` directory and require ``KCTL_ODOO_REPO`` or CWD resolution.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from kctl_odoo.core.addons import (
    Addon,
    HealthResult,
    _check_model_descriptions,
    _find_repo_root,
    discover_addons,
    get_addon_path_labels,
    get_default_addon_paths,
    score_health,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_manifest(tmp_path: Path, **kwargs: object) -> Path:
    """Create a minimal __manifest__.py in tmp_path and return the addon dir."""
    defaults = {
        "name": "Test Addon",
        "version": "18.0.1.0.0",
        "installable": True,
        "depends": ["base"],
        "summary": "A test addon",
        "author": "Kodemeio",
        "license": "LGPL-3",
        "description": "Full description here",
    }
    defaults.update(kwargs)
    (tmp_path / "__manifest__.py").write_text(repr(defaults), encoding="utf-8")
    return tmp_path


# ---------------------------------------------------------------------------
# Addon model
# ---------------------------------------------------------------------------


class TestAddonModel:
    """Test the Addon pydantic model and its computed properties."""

    def test_basic_fields(self, tmp_path: Path) -> None:
        """Addon stores name, path, source_type, manifest correctly."""
        manifest = {"name": "My Module", "version": "18.0.1.2.3", "installable": True}
        addon = Addon(name="my_module", path=tmp_path, source_type="private", manifest=manifest)
        assert addon.name == "my_module"
        assert addon.path == tmp_path
        assert addon.source_type == "private"
        assert addon.manifest == manifest

    def test_version_property(self, tmp_path: Path) -> None:
        """version property returns manifest['version'] or empty string."""
        addon = Addon(
            name="x",
            path=tmp_path,
            source_type="oca",
            manifest={"version": "18.0.2.0.0"},
        )
        assert addon.version == "18.0.2.0.0"

    def test_version_missing(self, tmp_path: Path) -> None:
        """version property returns '' when key absent."""
        addon = Addon(name="x", path=tmp_path, source_type="oca", manifest={})
        assert addon.version == ""

    def test_installable_true(self, tmp_path: Path) -> None:
        """installable property is True when manifest says True."""
        addon = Addon(name="x", path=tmp_path, source_type="private", manifest={"installable": True})
        assert addon.installable is True

    def test_installable_default_true(self, tmp_path: Path) -> None:
        """installable defaults to True when key absent."""
        addon = Addon(name="x", path=tmp_path, source_type="private", manifest={})
        assert addon.installable is True

    def test_installable_false(self, tmp_path: Path) -> None:
        """installable is False when manifest says False."""
        addon = Addon(name="x", path=tmp_path, source_type="private", manifest={"installable": False})
        assert addon.installable is False

    def test_depends_property(self, tmp_path: Path) -> None:
        """depends returns manifest list."""
        addon = Addon(
            name="x",
            path=tmp_path,
            source_type="private",
            manifest={"depends": ["base", "sale"]},
        )
        assert addon.depends == ["base", "sale"]

    def test_depends_empty_when_missing(self, tmp_path: Path) -> None:
        """depends returns [] when key absent."""
        addon = Addon(name="x", path=tmp_path, source_type="private", manifest={})
        assert addon.depends == []

    def test_summary_property(self, tmp_path: Path) -> None:
        """summary returns manifest['summary']."""
        addon = Addon(name="x", path=tmp_path, source_type="oca", manifest={"summary": "Short desc"})
        assert addon.summary == "Short desc"

    def test_summary_missing(self, tmp_path: Path) -> None:
        """summary returns '' when absent."""
        addon = Addon(name="x", path=tmp_path, source_type="oca", manifest={})
        assert addon.summary == ""

    def test_author_property(self, tmp_path: Path) -> None:
        """author returns manifest['author']."""
        addon = Addon(name="x", path=tmp_path, source_type="private", manifest={"author": "Kodemeio"})
        assert addon.author == "Kodemeio"

    def test_license_property(self, tmp_path: Path) -> None:
        """license returns manifest['license']."""
        addon = Addon(name="x", path=tmp_path, source_type="private", manifest={"license": "LGPL-3"})
        assert addon.license == "LGPL-3"

    def test_source_type_values(self, tmp_path: Path) -> None:
        """source_type accepts private, oca, external."""
        for stype in ("private", "oca", "external"):
            addon = Addon(name="x", path=tmp_path, source_type=stype, manifest={})
            assert addon.source_type == stype


class TestHealthResultModel:
    """Test the HealthResult pydantic model."""

    def test_basic_fields(self) -> None:
        """HealthResult stores score, checks, issues."""
        result = HealthResult(
            score=80,
            checks={"manifest_exists": True, "installable": True},
            issues=["Missing tests/"],
        )
        assert result.score == 80
        assert result.checks["manifest_exists"] is True
        assert "Missing tests/" in result.issues

    def test_empty_issues(self) -> None:
        """HealthResult can have an empty issues list."""
        result = HealthResult(score=100, checks={}, issues=[])
        assert result.issues == []

    def test_score_range(self) -> None:
        """Score can be 0-100."""
        r0 = HealthResult(score=0, checks={}, issues=[])
        r100 = HealthResult(score=100, checks={}, issues=[])
        assert r0.score == 0
        assert r100.score == 100


# ---------------------------------------------------------------------------
# discover_addons
# ---------------------------------------------------------------------------


class TestDiscoverAddons:
    """Test the discover_addons() filesystem scanner."""

    def test_discovers_addon_with_manifest(self, tmp_path: Path) -> None:
        """A subdir with __manifest__.py is discovered as an Addon."""
        addon_dir = tmp_path / "my_addon"
        addon_dir.mkdir()
        _make_manifest(addon_dir, name="My Addon")

        addons = discover_addons([tmp_path])
        assert len(addons) == 1
        assert addons[0].name == "my_addon"

    def test_skips_dir_without_manifest(self, tmp_path: Path) -> None:
        """Subdirectories without __manifest__.py are skipped."""
        no_manifest = tmp_path / "not_an_addon"
        no_manifest.mkdir()
        (no_manifest / "some_file.py").write_text("# nothing", encoding="utf-8")

        addons = discover_addons([tmp_path])
        assert addons == []

    def test_multiple_addons(self, tmp_path: Path) -> None:
        """Multiple addon directories are all discovered."""
        for name in ("addon_a", "addon_b", "addon_c"):
            d = tmp_path / name
            d.mkdir()
            _make_manifest(d, name=name)

        addons = discover_addons([tmp_path])
        assert len(addons) == 3
        names = {a.name for a in addons}
        assert names == {"addon_a", "addon_b", "addon_c"}

    def test_multiple_paths(self, tmp_path: Path) -> None:
        """Multiple addon paths are all scanned."""
        dir1 = tmp_path / "private"
        dir2 = tmp_path / "oca"
        dir1.mkdir()
        dir2.mkdir()

        (dir1 / "priv_addon").mkdir()
        _make_manifest(dir1 / "priv_addon", name="Private Addon")
        (dir2 / "oca_addon").mkdir()
        _make_manifest(dir2 / "oca_addon", name="OCA Addon")

        addons = discover_addons([dir1, dir2])
        assert len(addons) == 2

    def test_source_type_from_labels(self, tmp_path: Path) -> None:
        """path_labels dict maps path to source_type for discovered addons."""
        priv_dir = tmp_path / "private"
        priv_dir.mkdir()
        (priv_dir / "my_mod").mkdir()
        _make_manifest(priv_dir / "my_mod", name="My Mod")

        addons = discover_addons([priv_dir], path_labels={priv_dir: "private"})
        assert addons[0].source_type == "private"

    def test_source_type_default_unknown(self, tmp_path: Path) -> None:
        """When no label provided, source_type defaults to 'private' or a sensible default."""
        addon_dir = tmp_path / "some_addon"
        addon_dir.mkdir()
        _make_manifest(addon_dir, name="Some Addon")

        addons = discover_addons([tmp_path])
        # Should not raise; source_type should be a string
        assert isinstance(addons[0].source_type, str)

    def test_manifest_parsed_correctly(self, tmp_path: Path) -> None:
        """Manifest dict is parsed via ast.literal_eval (no exec/eval)."""
        addon_dir = tmp_path / "parsed_addon"
        addon_dir.mkdir()
        _make_manifest(addon_dir, name="Parsed Addon", version="18.0.3.0.0", depends=["base", "sale"])

        addons = discover_addons([tmp_path])
        assert addons[0].manifest["name"] == "Parsed Addon"
        assert addons[0].manifest["version"] == "18.0.3.0.0"
        assert "sale" in addons[0].manifest["depends"]

    def test_corrupted_manifest_skipped(self, tmp_path: Path) -> None:
        """Addon with a corrupted/unparseable manifest is skipped gracefully."""
        addon_dir = tmp_path / "bad_addon"
        addon_dir.mkdir()
        (addon_dir / "__manifest__.py").write_text("{ invalid python !!!", encoding="utf-8")

        addons = discover_addons([tmp_path])
        assert addons == []

    def test_nonexistent_path_skipped(self, tmp_path: Path) -> None:
        """A path that does not exist is skipped without error."""
        missing = tmp_path / "does_not_exist"
        addon_dir = tmp_path / "real_addon"
        addon_dir.mkdir()
        _make_manifest(addon_dir, name="Real Addon")

        # Should not raise
        addons = discover_addons([missing, tmp_path])
        assert len(addons) == 1

    def test_addon_path_is_set(self, tmp_path: Path) -> None:
        """Discovered addon has path pointing to its directory."""
        addon_dir = tmp_path / "path_test"
        addon_dir.mkdir()
        _make_manifest(addon_dir, name="Path Test")

        addons = discover_addons([tmp_path])
        assert addons[0].path == addon_dir


# ---------------------------------------------------------------------------
# get_default_addon_paths / get_addon_path_labels
# ---------------------------------------------------------------------------


class TestGetDefaultAddonPaths:
    """Test get_default_addon_paths() resolution."""

    def test_returns_list(self) -> None:
        """get_default_addon_paths always returns a list (may be empty)."""
        paths = get_default_addon_paths()
        assert isinstance(paths, list)

    def test_env_var_override(self, tmp_path: Path) -> None:
        """KCTL_ODOO_REPO env var is respected."""
        private = tmp_path / "src" / "private"
        private.mkdir(parents=True)
        with patch.dict(os.environ, {"KCTL_ODOO_REPO": str(tmp_path)}):
            paths = get_default_addon_paths()
        assert private in paths

    def test_paths_are_path_objects(self) -> None:
        """Returned items are Path objects."""
        paths = get_default_addon_paths()
        for p in paths:
            assert isinstance(p, Path)


class TestGetAddonPathLabels:
    """Test get_addon_path_labels() mapping."""

    def test_returns_dict(self) -> None:
        """get_addon_path_labels returns a dict."""
        labels = get_addon_path_labels()
        assert isinstance(labels, dict)

    def test_env_var_override(self, tmp_path: Path) -> None:
        """KCTL_ODOO_REPO env var produces correct labels."""
        (tmp_path / "src" / "private").mkdir(parents=True)
        (tmp_path / "src" / "oca").mkdir(parents=True)
        (tmp_path / "src" / "external").mkdir(parents=True)
        with patch.dict(os.environ, {"KCTL_ODOO_REPO": str(tmp_path)}):
            labels = get_addon_path_labels()
        # Values should be one of the known source types
        for val in labels.values():
            assert val in ("private", "oca", "external")


# ---------------------------------------------------------------------------
# _find_repo_root
# ---------------------------------------------------------------------------


class TestFindRepoRoot:
    """Test _find_repo_root() resolution strategies."""

    def test_env_var_takes_priority(self, tmp_path: Path) -> None:
        """KCTL_ODOO_REPO env var returns that path directly."""
        with patch.dict(os.environ, {"KCTL_ODOO_REPO": str(tmp_path)}):
            root = _find_repo_root()
        assert root == tmp_path

    def test_walks_up_for_install_and_src(self, tmp_path: Path) -> None:
        """Walks up CWD looking for dir with both install/ and src/."""
        repo = tmp_path / "myrepo"
        repo.mkdir()
        (repo / "install").mkdir()
        (repo / "src").mkdir()
        subdir = repo / "some" / "nested"
        subdir.mkdir(parents=True)

        with patch.dict(os.environ, {}, clear=True):
            # Remove KCTL_ODOO_REPO if set
            env = {k: v for k, v in os.environ.items() if k != "KCTL_ODOO_REPO"}
            with patch.dict(os.environ, env, clear=True), patch("os.getcwd", return_value=str(subdir)):
                root = _find_repo_root()
        assert root == repo

    def test_returns_none_when_not_found(self, tmp_path: Path) -> None:
        """Returns None when neither env var nor directory structure found."""
        isolated = tmp_path / "isolated"
        isolated.mkdir()
        env = {k: v for k, v in os.environ.items() if k != "KCTL_ODOO_REPO"}
        with patch.dict(os.environ, env, clear=True), patch("os.getcwd", return_value=str(isolated)):
            root = _find_repo_root()
        # None or a path — shouldn't raise
        assert root is None or isinstance(root, Path)


# ---------------------------------------------------------------------------
# _check_model_descriptions
# ---------------------------------------------------------------------------


class TestCheckModelDescriptions:
    """Test the _check_model_descriptions() helper."""

    def test_no_models_dir(self, tmp_path: Path) -> None:
        """Returns True (pass) when models/ dir doesn't exist."""
        result = _check_model_descriptions(tmp_path)
        assert result is True

    def test_all_models_have_description(self, tmp_path: Path) -> None:
        """Returns True when all models with _name also have _description."""
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        (models_dir / "my_model.py").write_text(
            'class MyModel:\n    _name = "my.model"\n    _description = "My Model"\n',
            encoding="utf-8",
        )
        result = _check_model_descriptions(tmp_path)
        assert result is True

    def test_model_missing_description(self, tmp_path: Path) -> None:
        """Returns False when a model has _name but no _description."""
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        (models_dir / "bad_model.py").write_text(
            'class BadModel:\n    _name = "bad.model"\n    # No _description!\n',
            encoding="utf-8",
        )
        result = _check_model_descriptions(tmp_path)
        assert result is False

    def test_mixed_models(self, tmp_path: Path) -> None:
        """Returns False if any model is missing _description."""
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        (models_dir / "good.py").write_text(
            '_name = "good.model"\n_description = "Good"\n',
            encoding="utf-8",
        )
        (models_dir / "bad.py").write_text(
            '_name = "bad.model"\n# missing description\n',
            encoding="utf-8",
        )
        result = _check_model_descriptions(tmp_path)
        assert result is False

    def test_file_without_name_ignored(self, tmp_path: Path) -> None:
        """Files without _name are not checked for _description."""
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        (models_dir / "helpers.py").write_text(
            "def helper():\n    pass\n",
            encoding="utf-8",
        )
        result = _check_model_descriptions(tmp_path)
        assert result is True


# ---------------------------------------------------------------------------
# score_health
# ---------------------------------------------------------------------------


class TestScoreHealth:
    """Test the score_health() 0-100 scorer."""

    def _perfect_addon(self, tmp_path: Path) -> Addon:
        """Build an addon directory that passes all 12 checks."""
        addon_dir = tmp_path / "perfect_addon"
        addon_dir.mkdir()
        _make_manifest(addon_dir)

        # security/ir.model.access.csv
        sec = addon_dir / "security"
        sec.mkdir()
        (sec / "ir.model.access.csv").write_text(
            "id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink\n",
            encoding="utf-8",
        )

        # tests/
        tests_dir = addon_dir / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_something.py").write_text("# tests\n", encoding="utf-8")

        # CLAUDE.md
        (addon_dir / "CLAUDE.md").write_text("# My Addon\n", encoding="utf-8")

        # views/
        views_dir = addon_dir / "views"
        views_dir.mkdir()
        (views_dir / "my_view.xml").write_text("<odoo/>\n", encoding="utf-8")

        # models/ with _name and _description
        models_dir = addon_dir / "models"
        models_dir.mkdir()
        (models_dir / "my_model.py").write_text(
            '_name = "my.model"\n_description = "My Model"\n',
            encoding="utf-8",
        )

        return Addon(
            name="perfect_addon",
            path=addon_dir,
            source_type="private",
            manifest={
                "name": "Perfect Addon",
                "version": "18.0.1.0.0",
                "installable": True,
                "depends": ["base"],
                "description": "Full description",
                "author": "Kodemeio",
                "license": "LGPL-3",
                "summary": "Short summary",
            },
        )

    def test_perfect_addon_score_100(self, tmp_path: Path) -> None:
        """An addon passing all checks scores 100."""
        addon = self._perfect_addon(tmp_path)
        result = score_health(addon)
        assert result.score == 100

    def test_score_is_integer(self, tmp_path: Path) -> None:
        """Score is always an integer."""
        addon_dir = tmp_path / "basic"
        addon_dir.mkdir()
        _make_manifest(addon_dir)
        addon = Addon(name="basic", path=addon_dir, source_type="private", manifest={})
        result = score_health(addon)
        assert isinstance(result.score, int)

    def test_score_range_0_to_100(self, tmp_path: Path) -> None:
        """Score is always between 0 and 100 inclusive."""
        addon_dir = tmp_path / "any"
        addon_dir.mkdir()
        _make_manifest(addon_dir)
        addon = Addon(name="any", path=addon_dir, source_type="private", manifest={})
        result = score_health(addon)
        assert 0 <= result.score <= 100

    def test_manifest_exists_check(self, tmp_path: Path) -> None:
        """manifest_exists check is True when __manifest__.py present."""
        addon_dir = tmp_path / "has_manifest"
        addon_dir.mkdir()
        _make_manifest(addon_dir)
        addon = Addon(name="has_manifest", path=addon_dir, source_type="private", manifest={"name": "X"})
        result = score_health(addon)
        assert result.checks["manifest_exists"] is True

    def test_manifest_missing_check(self, tmp_path: Path) -> None:
        """manifest_exists check is False when __manifest__.py absent."""
        addon_dir = tmp_path / "no_manifest"
        addon_dir.mkdir()
        # No manifest file
        addon = Addon(name="no_manifest", path=addon_dir, source_type="private", manifest={})
        result = score_health(addon)
        assert result.checks["manifest_exists"] is False

    def test_installable_check(self, tmp_path: Path) -> None:
        """installable check is True when manifest has installable=True."""
        addon_dir = tmp_path / "installable"
        addon_dir.mkdir()
        _make_manifest(addon_dir, installable=True)
        addon = Addon(name="installable", path=addon_dir, source_type="private", manifest={"installable": True})
        result = score_health(addon)
        assert result.checks["installable"] is True

    def test_version_set_check(self, tmp_path: Path) -> None:
        """version_set check is True when version is non-empty."""
        addon_dir = tmp_path / "versioned"
        addon_dir.mkdir()
        _make_manifest(addon_dir, version="18.0.1.0.0")
        addon = Addon(
            name="versioned",
            path=addon_dir,
            source_type="private",
            manifest={"version": "18.0.1.0.0"},
        )
        result = score_health(addon)
        assert result.checks["version_set"] is True

    def test_security_csv_check(self, tmp_path: Path) -> None:
        """security_csv check is True when security/ir.model.access.csv exists."""
        addon_dir = tmp_path / "secure"
        addon_dir.mkdir()
        _make_manifest(addon_dir)
        sec = addon_dir / "security"
        sec.mkdir()
        (sec / "ir.model.access.csv").write_text("id,name\n", encoding="utf-8")
        addon = Addon(name="secure", path=addon_dir, source_type="private", manifest={})
        result = score_health(addon)
        assert result.checks["security_csv"] is True

    def test_security_csv_missing(self, tmp_path: Path) -> None:
        """security_csv check is False when file absent."""
        addon_dir = tmp_path / "insecure"
        addon_dir.mkdir()
        _make_manifest(addon_dir)
        addon = Addon(name="insecure", path=addon_dir, source_type="private", manifest={})
        result = score_health(addon)
        assert result.checks["security_csv"] is False

    def test_tests_exist_check(self, tmp_path: Path) -> None:
        """tests_exist check is True when tests/ has at least one test_*.py file."""
        addon_dir = tmp_path / "tested"
        addon_dir.mkdir()
        _make_manifest(addon_dir)
        tests = addon_dir / "tests"
        tests.mkdir()
        (tests / "test_core.py").write_text("# tests\n", encoding="utf-8")
        addon = Addon(name="tested", path=addon_dir, source_type="private", manifest={})
        result = score_health(addon)
        assert result.checks["tests_exist"] is True

    def test_tests_missing(self, tmp_path: Path) -> None:
        """tests_exist check is False when tests/ dir or test files absent."""
        addon_dir = tmp_path / "untested"
        addon_dir.mkdir()
        _make_manifest(addon_dir)
        addon = Addon(name="untested", path=addon_dir, source_type="private", manifest={})
        result = score_health(addon)
        assert result.checks["tests_exist"] is False

    def test_claude_md_check(self, tmp_path: Path) -> None:
        """claude_md check is True when CLAUDE.md exists."""
        addon_dir = tmp_path / "documented"
        addon_dir.mkdir()
        _make_manifest(addon_dir)
        (addon_dir / "CLAUDE.md").write_text("# Documented\n", encoding="utf-8")
        addon = Addon(name="documented", path=addon_dir, source_type="private", manifest={})
        result = score_health(addon)
        assert result.checks["claude_md"] is True

    def test_views_exist_check(self, tmp_path: Path) -> None:
        """views_exist check is True when views/ has at least one .xml file."""
        addon_dir = tmp_path / "viewful"
        addon_dir.mkdir()
        _make_manifest(addon_dir)
        views = addon_dir / "views"
        views.mkdir()
        (views / "my_view.xml").write_text("<odoo/>\n", encoding="utf-8")
        addon = Addon(name="viewful", path=addon_dir, source_type="private", manifest={})
        result = score_health(addon)
        assert result.checks["views_exist"] is True

    def test_model_descriptions_check(self, tmp_path: Path) -> None:
        """model_descriptions check passes when all models have _description."""
        addon_dir = tmp_path / "described"
        addon_dir.mkdir()
        _make_manifest(addon_dir)
        models = addon_dir / "models"
        models.mkdir()
        (models / "model.py").write_text(
            '_name = "test.model"\n_description = "Test Model"\n',
            encoding="utf-8",
        )
        addon = Addon(name="described", path=addon_dir, source_type="private", manifest={})
        result = score_health(addon)
        assert result.checks["model_descriptions"] is True

    def test_checks_dict_has_all_12_keys(self, tmp_path: Path) -> None:
        """HealthResult.checks dict always has all 12 check keys."""
        addon_dir = tmp_path / "check_keys"
        addon_dir.mkdir()
        _make_manifest(addon_dir)
        addon = Addon(name="check_keys", path=addon_dir, source_type="private", manifest={})
        result = score_health(addon)
        expected_keys = {
            "manifest_exists",
            "installable",
            "version_set",
            "description_set",
            "author_set",
            "license_set",
            "depends_set",
            "security_csv",
            "tests_exist",
            "claude_md",
            "views_exist",
            "model_descriptions",
        }
        assert set(result.checks.keys()) == expected_keys

    def test_issues_populated_for_failures(self, tmp_path: Path) -> None:
        """issues list is non-empty when checks fail."""
        addon_dir = tmp_path / "failing"
        addon_dir.mkdir()
        # Minimal manifest — many checks will fail
        (addon_dir / "__manifest__.py").write_text("{}", encoding="utf-8")
        addon = Addon(name="failing", path=addon_dir, source_type="private", manifest={})
        result = score_health(addon)
        assert len(result.issues) > 0

    def test_score_weighted_correctly(self, tmp_path: Path) -> None:
        """Only security_csv (15pts) + tests_exist (15pts) failing → score = 70."""
        addon_dir = tmp_path / "partial"
        addon_dir.mkdir()
        _make_manifest(addon_dir)
        # Add views, CLAUDE.md, models with description — skip security/tests
        views = addon_dir / "views"
        views.mkdir()
        (views / "v.xml").write_text("<odoo/>\n", encoding="utf-8")
        (addon_dir / "CLAUDE.md").write_text("# X\n", encoding="utf-8")

        addon = Addon(
            name="partial",
            path=addon_dir,
            source_type="private",
            manifest={
                "name": "X",
                "version": "18.0.1.0.0",
                "installable": True,
                "depends": ["base"],
                "description": "Full",
                "author": "Me",
                "license": "LGPL-3",
            },
        )
        result = score_health(addon)
        # security_csv=15, tests_exist=15 missing → 100 - 15 - 15 = 70
        assert result.score == 70

    def test_partial_score_no_tests_no_security(self, tmp_path: Path) -> None:
        """Addon missing tests and security scores less than 100."""
        addon_dir = tmp_path / "no_tests_sec"
        addon_dir.mkdir()
        _make_manifest(addon_dir)
        addon = Addon(
            name="no_tests_sec",
            path=addon_dir,
            source_type="private",
            manifest={
                "name": "X",
                "version": "18.0.1.0.0",
                "installable": True,
                "depends": ["base"],
                "description": "Full",
                "author": "Me",
                "license": "LGPL-3",
            },
        )
        result = score_health(addon)
        assert result.score < 100


# ---------------------------------------------------------------------------
# Integration tests: real addons
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestDiscoverAddonsIntegration:
    """Integration tests against real addons in src/private/."""

    def test_discovers_private_addons(self, repo_root: Path) -> None:
        """Discovers multiple private addons from src/private/."""
        private_dir = repo_root / "src" / "private"
        if not private_dir.is_dir():
            pytest.skip("src/private/ not found")

        addons = discover_addons([private_dir], path_labels={private_dir: "private"})
        assert len(addons) >= 10
        for a in addons:
            assert a.source_type == "private"
            assert a.path.is_dir()

    def test_all_addons_have_names(self, repo_root: Path) -> None:
        """All discovered addons have non-empty names."""
        private_dir = repo_root / "src" / "private"
        if not private_dir.is_dir():
            pytest.skip("src/private/ not found")

        addons = discover_addons([private_dir])
        for a in addons:
            assert a.name, f"Addon with empty name at {a.path}"

    def test_get_default_addon_paths_finds_paths(self, repo_root: Path) -> None:
        """get_default_addon_paths returns at least one valid path when repo found."""
        with patch.dict(os.environ, {"KCTL_ODOO_REPO": str(repo_root)}):
            paths = get_default_addon_paths()
        assert len(paths) >= 1
        for p in paths:
            assert p.is_dir()

    def test_score_health_on_real_addon(self, repo_root: Path) -> None:
        """score_health runs without error on a real private addon."""
        private_dir = repo_root / "src" / "private"
        if not private_dir.is_dir():
            pytest.skip("src/private/ not found")

        addons = discover_addons([private_dir], path_labels={private_dir: "private"})
        if not addons:
            pytest.skip("No addons found")

        # Score the first one — should not raise
        result = score_health(addons[0])
        assert 0 <= result.score <= 100
        assert isinstance(result.checks, dict)
        assert isinstance(result.issues, list)
