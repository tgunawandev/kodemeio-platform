"""Tests for bundle YAML authoring helpers.

Tests the 4 helper functions added in the authoring section of
``kctl_odoo.commands.bundles``:

- ``_create_bundle_yaml``
- ``_add_module_to_bundle``
- ``_remove_module_from_bundle``
- ``_create_profile_yaml``
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from kctl_odoo.commands.bundles import (
    _add_module_to_bundle,
    _create_bundle_yaml,
    _create_profile_yaml,
    _remove_module_from_bundle,
)

# ---------------------------------------------------------------------------
# _create_bundle_yaml
# ---------------------------------------------------------------------------


class TestCreateBundleYaml:
    """Tests for _create_bundle_yaml helper."""

    def test_creates_file(self, tmp_path: Path) -> None:
        """Creates the expected YAML file in install_dir."""
        path = _create_bundle_yaml(tmp_path, "my-bundle")
        assert path == tmp_path / "my-bundle.yaml"
        assert path.exists()

    def test_correct_structure(self, tmp_path: Path) -> None:
        """Created file has name, description, groups with core, and default=[core]."""
        _create_bundle_yaml(tmp_path, "test-bundle", description="A test bundle")
        data = yaml.safe_load((tmp_path / "test-bundle.yaml").read_text(encoding="utf-8"))

        assert data["name"] == "test-bundle"
        assert data["description"] == "A test bundle"
        assert "groups" in data
        assert "core" in data["groups"]
        assert data["groups"]["core"]["modules"] == []
        assert data["default"] == ["core"]

    def test_no_requires_key_when_not_provided(self, tmp_path: Path) -> None:
        """When requires is None, the 'requires' key is absent from the file."""
        _create_bundle_yaml(tmp_path, "no-req")
        data = yaml.safe_load((tmp_path / "no-req.yaml").read_text(encoding="utf-8"))
        assert "requires" not in data

    def test_requires_key_present_when_provided(self, tmp_path: Path) -> None:
        """When requires is given, it appears in the YAML."""
        _create_bundle_yaml(tmp_path, "with-req", requires=["core-mandatory", "oca-mandatory"])
        data = yaml.safe_load((tmp_path / "with-req.yaml").read_text(encoding="utf-8"))
        assert data["requires"] == ["core-mandatory", "oca-mandatory"]

    def test_refuses_existing_file(self, tmp_path: Path) -> None:
        """Raises FileExistsError if the bundle file already exists."""
        _create_bundle_yaml(tmp_path, "duplicate")
        with pytest.raises(FileExistsError, match="already exists"):
            _create_bundle_yaml(tmp_path, "duplicate")

    def test_empty_description_default(self, tmp_path: Path) -> None:
        """Default description is an empty string."""
        _create_bundle_yaml(tmp_path, "nodesc")
        data = yaml.safe_load((tmp_path / "nodesc.yaml").read_text(encoding="utf-8"))
        assert data["description"] == ""


# ---------------------------------------------------------------------------
# _add_module_to_bundle
# ---------------------------------------------------------------------------


class TestAddModuleToBundle:
    """Tests for _add_module_to_bundle helper."""

    def _make_bundle(self, tmp_path: Path, name: str = "test-bundle") -> Path:
        """Create a minimal grouped bundle and return its path."""
        return _create_bundle_yaml(tmp_path, name)

    def test_adds_to_existing_group(self, tmp_path: Path) -> None:
        """Adds module to an existing group."""
        path = self._make_bundle(tmp_path)
        _add_module_to_bundle(path, "my_module", "core")

        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert "my_module" in data["groups"]["core"]["modules"]

    def test_creates_new_group(self, tmp_path: Path) -> None:
        """Creates the group if it does not exist."""
        path = self._make_bundle(tmp_path)
        _add_module_to_bundle(path, "my_module", "optional")

        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert "optional" in data["groups"]
        assert "my_module" in data["groups"]["optional"]["modules"]

    def test_rejects_duplicate_in_same_group(self, tmp_path: Path) -> None:
        """Raises ValueError when module already exists in the target group."""
        path = self._make_bundle(tmp_path)
        _add_module_to_bundle(path, "dup_module", "core")

        with pytest.raises(ValueError, match="already exists"):
            _add_module_to_bundle(path, "dup_module", "core")

    def test_rejects_duplicate_in_different_group(self, tmp_path: Path) -> None:
        """Raises ValueError when module exists in a different group."""
        path = self._make_bundle(tmp_path)
        _add_module_to_bundle(path, "dup_module", "core")

        with pytest.raises(ValueError, match="already exists"):
            _add_module_to_bundle(path, "dup_module", "optional")

    def test_multiple_modules_in_group(self, tmp_path: Path) -> None:
        """Can add multiple distinct modules to the same group."""
        path = self._make_bundle(tmp_path)
        _add_module_to_bundle(path, "mod_a", "core")
        _add_module_to_bundle(path, "mod_b", "core")

        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert data["groups"]["core"]["modules"] == ["mod_a", "mod_b"]

    def test_raises_on_flat_bundle(self, tmp_path: Path) -> None:
        """Raises ValueError on a flat (list) bundle."""
        path = tmp_path / "flat.yaml"
        path.write_text(yaml.dump(["mod_a", "mod_b"]), encoding="utf-8")

        with pytest.raises(ValueError, match="not grouped format"):
            _add_module_to_bundle(path, "new_mod", "core")


# ---------------------------------------------------------------------------
# _remove_module_from_bundle
# ---------------------------------------------------------------------------


class TestRemoveModuleFromBundle:
    """Tests for _remove_module_from_bundle helper."""

    def _make_bundle_with_modules(self, tmp_path: Path) -> Path:
        """Create bundle with modules in two groups."""
        path = _create_bundle_yaml(tmp_path, "test-bundle")
        _add_module_to_bundle(path, "mod_core_1", "core")
        _add_module_to_bundle(path, "mod_core_2", "core")
        _add_module_to_bundle(path, "mod_opt_1", "optional")
        return path

    def test_removes_module_from_group(self, tmp_path: Path) -> None:
        """Removes a module that exists in core group."""
        path = self._make_bundle_with_modules(tmp_path)
        _remove_module_from_bundle(path, "mod_core_1")

        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert "mod_core_1" not in data["groups"]["core"]["modules"]
        assert "mod_core_2" in data["groups"]["core"]["modules"]

    def test_removes_module_from_non_core_group(self, tmp_path: Path) -> None:
        """Removes module from a non-core group."""
        path = self._make_bundle_with_modules(tmp_path)
        _remove_module_from_bundle(path, "mod_opt_1")

        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert "mod_opt_1" not in data["groups"]["optional"]["modules"]

    def test_raises_if_module_not_found(self, tmp_path: Path) -> None:
        """Raises ValueError when module does not exist in any group."""
        path = self._make_bundle_with_modules(tmp_path)

        with pytest.raises(ValueError, match="not found"):
            _remove_module_from_bundle(path, "nonexistent_module")

    def test_raises_on_flat_bundle(self, tmp_path: Path) -> None:
        """Raises ValueError on a flat (list) bundle."""
        path = tmp_path / "flat.yaml"
        path.write_text(yaml.dump(["mod_a", "mod_b"]), encoding="utf-8")

        with pytest.raises(ValueError, match="not grouped format"):
            _remove_module_from_bundle(path, "mod_a")

    def test_other_modules_unchanged(self, tmp_path: Path) -> None:
        """Removing one module leaves all others intact."""
        path = self._make_bundle_with_modules(tmp_path)
        _remove_module_from_bundle(path, "mod_core_1")

        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        # core still has mod_core_2
        assert "mod_core_2" in data["groups"]["core"]["modules"]
        # optional group is untouched
        assert "mod_opt_1" in data["groups"]["optional"]["modules"]


# ---------------------------------------------------------------------------
# _create_profile_yaml
# ---------------------------------------------------------------------------


class TestCreateProfileYaml:
    """Tests for _create_profile_yaml helper."""

    def test_creates_file_with_prefix(self, tmp_path: Path) -> None:
        """Creates 'profile-retail.yaml' when name='retail'."""
        path = _create_profile_yaml(tmp_path, "retail")
        assert path == tmp_path / "profile-retail.yaml"
        assert path.exists()

    def test_no_double_prefix(self, tmp_path: Path) -> None:
        """Does not add prefix twice when name already starts with 'profile-'."""
        path = _create_profile_yaml(tmp_path, "profile-retail")
        assert path == tmp_path / "profile-retail.yaml"
        assert path.exists()

    def test_correct_structure(self, tmp_path: Path) -> None:
        """Created profile has name, description, and bundles keys."""
        _create_profile_yaml(tmp_path, "test-profile", description="Test deployment")
        data = yaml.safe_load((tmp_path / "profile-test-profile.yaml").read_text(encoding="utf-8"))

        assert data["name"] == "profile-test-profile"
        assert data["description"] == "Test deployment"
        assert "bundles" in data
        assert isinstance(data["bundles"], list)

    def test_default_bundles(self, tmp_path: Path) -> None:
        """Default bundles list contains the 4 mandatory bundles."""
        _create_profile_yaml(tmp_path, "default-test")
        data = yaml.safe_load((tmp_path / "profile-default-test.yaml").read_text(encoding="utf-8"))

        assert "core-mandatory" in data["bundles"]
        assert "core-localization" in data["bundles"]
        assert "oca-mandatory" in data["bundles"]
        assert "private-mandatory" in data["bundles"]

    def test_custom_bundles(self, tmp_path: Path) -> None:
        """Custom bundles list replaces the default."""
        custom = ["core-mandatory", "oca-server", "private-retail"]
        _create_profile_yaml(tmp_path, "custom", bundles=custom)
        data = yaml.safe_load((tmp_path / "profile-custom.yaml").read_text(encoding="utf-8"))

        assert data["bundles"] == custom

    def test_extends_present_when_provided(self, tmp_path: Path) -> None:
        """'extends' key is present when an extends value is given."""
        _create_profile_yaml(tmp_path, "child", extends="foundation")
        data = yaml.safe_load((tmp_path / "profile-child.yaml").read_text(encoding="utf-8"))
        assert data["extends"] == "foundation"

    def test_extends_absent_when_empty(self, tmp_path: Path) -> None:
        """'extends' key is absent when not provided."""
        _create_profile_yaml(tmp_path, "standalone")
        data = yaml.safe_load((tmp_path / "profile-standalone.yaml").read_text(encoding="utf-8"))
        assert "extends" not in data

    def test_refuses_existing_file(self, tmp_path: Path) -> None:
        """Raises FileExistsError if the profile file already exists."""
        _create_profile_yaml(tmp_path, "duplicate")
        with pytest.raises(FileExistsError, match="already exists"):
            _create_profile_yaml(tmp_path, "duplicate")
