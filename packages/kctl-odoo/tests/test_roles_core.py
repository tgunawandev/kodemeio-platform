# tests/test_roles_core.py
from pathlib import Path
import pytest
import yaml

from kctl_odoo.core.roles import (
    RoleSpec,
    RolesFile,
    IgnoredFile,
    load_roles_file,
    load_ignored_file,
    resolve_role_groups,
    CircularExtendError,
    UnknownExtendError,
)


def test_roles_file_parses_minimal():
    data = {
        "version": 1,
        "roles": {
            "finance_user": {
                "name": "Finance User",
                "category": "User roles / Finance",
                "groups": ["account.group_account_invoice"],
            }
        },
    }
    rf = RolesFile.model_validate(data)
    assert rf.version == 1
    assert "finance_user" in rf.roles
    assert rf.roles["finance_user"].name == "Finance User"
    assert rf.roles["finance_user"].extends is None


def test_roles_file_parses_extends():
    data = {
        "version": 1,
        "roles": {
            "finance_user": {"name": "Finance User", "groups": ["account.group_account_invoice"]},
            "finance_manager": {
                "name": "Finance Manager",
                "extends": "finance_user",
                "groups": ["account.group_account_manager"],
            },
        },
    }
    rf = RolesFile.model_validate(data)
    assert rf.roles["finance_manager"].extends == "finance_user"


def test_resolve_role_groups_flattens_extends_chain():
    rf = RolesFile.model_validate(
        {
            "version": 1,
            "roles": {
                "a": {"name": "A", "groups": ["x", "y"]},
                "b": {"name": "B", "extends": "a", "groups": ["z"]},
                "c": {"name": "C", "extends": "b", "groups": ["w"]},
            },
        }
    )
    assert resolve_role_groups(rf, "c") == ["x", "y", "z", "w"]


def test_resolve_role_groups_detects_circular():
    rf = RolesFile.model_validate(
        {
            "version": 1,
            "roles": {
                "a": {"name": "A", "extends": "b", "groups": []},
                "b": {"name": "B", "extends": "a", "groups": []},
            },
        }
    )
    with pytest.raises(CircularExtendError):
        resolve_role_groups(rf, "a")


def test_resolve_role_groups_detects_unknown_extend():
    rf = RolesFile.model_validate(
        {
            "version": 1,
            "roles": {"a": {"name": "A", "extends": "ghost", "groups": []}},
        }
    )
    with pytest.raises(UnknownExtendError):
        resolve_role_groups(rf, "a")


def test_resolve_dedupes_groups_preserving_order():
    rf = RolesFile.model_validate(
        {
            "version": 1,
            "roles": {
                "a": {"name": "A", "groups": ["x", "y"]},
                "b": {"name": "B", "extends": "a", "groups": ["y", "z"]},
            },
        }
    )
    assert resolve_role_groups(rf, "b") == ["x", "y", "z"]


def test_load_roles_file_from_yaml(tmp_path: Path):
    yaml_path = tmp_path / "roles.yaml"
    yaml_path.write_text("version: 1\nroles:\n  x:\n    name: X\n    groups: [a.b]\n")
    rf = load_roles_file(yaml_path)
    assert rf.roles["x"].name == "X"


def test_load_ignored_file_from_yaml(tmp_path: Path):
    yaml_path = tmp_path / "ignored.yaml"
    yaml_path.write_text("version: 1\nignored: [a.b, c.d]\n")
    ig = load_ignored_file(yaml_path)
    assert ig.ignored == ["a.b", "c.d"]


def test_load_ignored_file_missing_returns_empty(tmp_path: Path):
    ig = load_ignored_file(tmp_path / "does-not-exist.yaml")
    assert ig.ignored == []
