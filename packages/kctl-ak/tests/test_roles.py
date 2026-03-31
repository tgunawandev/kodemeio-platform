"""Tests for role loader (roles/loader.py)."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from kctl_ak.roles.loader import RoleLoader


@pytest.fixture()
def roles_dir(tmp_path: Path) -> Path:
    """Create temp directory with sample role YAML files."""
    d = tmp_path / "roles"
    d.mkdir()

    (d / "admin.yaml").write_text(
        dedent("""\
        name: IT Administrator
        description: Full IT admin access
        groups:
          - ak-admin-super
          - ak-app-mattermost-all
    """)
    )

    (d / "basic-user.yaml").write_text(
        dedent("""\
        name: Basic User
        description: Standard employee access
        groups:
          - ak-role-basic
          - ak-app-mattermost-all
    """)
    )

    (d / "empty.yaml").write_text("")  # Edge case: empty file

    return d


class TestRoleLoader:
    def test_list_roles(self, roles_dir: Path) -> None:
        loader = RoleLoader(search_paths=[roles_dir])
        roles = loader.list_roles()
        names = [r.name for r in roles]
        assert "Basic User" in names
        assert "IT Administrator" in names

    def test_list_roles_count(self, roles_dir: Path) -> None:
        loader = RoleLoader(search_paths=[roles_dir])
        roles = loader.list_roles()
        # empty.yaml parses as None → becomes {} → creates role with stem name
        assert len(roles) == 3

    def test_get_role_by_stem(self, roles_dir: Path) -> None:
        loader = RoleLoader(search_paths=[roles_dir])
        role = loader.get_role("admin")
        assert role is not None
        assert role.name == "IT Administrator"
        assert "ak-admin-super" in role.groups

    def test_get_role_by_name(self, roles_dir: Path) -> None:
        loader = RoleLoader(search_paths=[roles_dir])
        role = loader.get_role("Basic User")
        assert role is not None
        assert "ak-role-basic" in role.groups

    def test_get_role_not_found(self, roles_dir: Path) -> None:
        loader = RoleLoader(search_paths=[roles_dir])
        assert loader.get_role("nonexistent") is None

    def test_resolve_groups_single(self, roles_dir: Path) -> None:
        loader = RoleLoader(search_paths=[roles_dir])
        groups = loader.resolve_groups(["admin"])
        assert "ak-admin-super" in groups
        assert "ak-app-mattermost-all" in groups

    def test_resolve_groups_multiple(self, roles_dir: Path) -> None:
        loader = RoleLoader(search_paths=[roles_dir])
        groups = loader.resolve_groups(["admin", "basic-user"])
        assert "ak-admin-super" in groups
        assert "ak-role-basic" in groups
        # Shared group should not be duplicated
        assert groups.count("ak-app-mattermost-all") == 1

    def test_resolve_groups_sorted(self, roles_dir: Path) -> None:
        loader = RoleLoader(search_paths=[roles_dir])
        groups = loader.resolve_groups(["admin"])
        assert groups == sorted(groups)

    def test_resolve_groups_unknown_role(self, roles_dir: Path) -> None:
        loader = RoleLoader(search_paths=[roles_dir])
        with pytest.raises(ValueError, match="Role not found: ghost"):
            loader.resolve_groups(["ghost"])

    def test_empty_search_paths(self, tmp_path: Path) -> None:
        loader = RoleLoader(search_paths=[tmp_path / "nope"])
        assert loader.list_roles() == []

    def test_file_path_set(self, roles_dir: Path) -> None:
        loader = RoleLoader(search_paths=[roles_dir])
        role = loader.get_role("admin")
        assert role is not None
        assert role.file_path is not None
        assert "admin.yaml" in role.file_path

    def test_first_path_wins_on_duplicate(self, tmp_path: Path) -> None:
        """First search path should take precedence if same stem exists in both."""
        d1 = tmp_path / "roles1"
        d1.mkdir()
        d2 = tmp_path / "roles2"
        d2.mkdir()
        (d1 / "test.yaml").write_text("name: From Path 1\ndescription: first\ngroups: []\n")
        (d2 / "test.yaml").write_text("name: From Path 2\ndescription: second\ngroups: []\n")

        loader = RoleLoader(search_paths=[d1, d2])
        role = loader.get_role("test")
        assert role is not None
        assert role.name == "From Path 1"

    def test_malformed_yaml_skipped(self, tmp_path: Path) -> None:
        d = tmp_path / "roles"
        d.mkdir()
        (d / "good.yaml").write_text("name: Good\ndescription: OK\ngroups:\n  - g1\n")
        (d / "bad.yaml").write_text("not: {valid: yaml: [")  # broken
        loader = RoleLoader(search_paths=[d])
        roles = loader.list_roles()
        assert len(roles) == 1
        assert roles[0].name == "Good"
