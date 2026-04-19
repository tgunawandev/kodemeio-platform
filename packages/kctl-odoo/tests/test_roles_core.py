# tests/test_roles_core.py
from pathlib import Path
from unittest.mock import MagicMock
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
    resolve_xmlids,
    RoleDbState,
    plan_sync,
    SyncAction,
    MenuVisibilityAction,
    plan_menu_visibility,
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
    with pytest.raises(CircularExtendError, match=r"a -> b -> a"):
        resolve_role_groups(rf, "a")


def test_resolve_role_groups_detects_unknown_extend():
    rf = RolesFile.model_validate(
        {
            "version": 1,
            "roles": {"a": {"name": "A", "extends": "ghost", "groups": []}},
        }
    )
    with pytest.raises(UnknownExtendError, match=r"'ghost'.*'extends'.*'a'"):
        resolve_role_groups(rf, "a")


def test_resolve_role_groups_entry_unknown_has_clear_message():
    rf = RolesFile.model_validate({"version": 1, "roles": {}})
    with pytest.raises(UnknownExtendError, match=r"Role 'ghost' not defined"):
        resolve_role_groups(rf, "ghost")


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


def test_resolve_xmlids_returns_map_skip_missing():
    client = MagicMock()
    client.search_read.return_value = [
        {"id": 1, "model": "res.groups", "module": "account", "name": "group_account_manager", "res_id": 63},
        {"id": 2, "model": "res.groups", "module": "base", "name": "group_user", "res_id": 1},
    ]
    requested = [
        "account.group_account_manager",
        "base.group_user",
        "point_of_sale.group_pos_user",
    ]
    resolved, missing = resolve_xmlids(client, requested)
    assert resolved == {"account.group_account_manager": 63, "base.group_user": 1}
    assert missing == ["point_of_sale.group_pos_user"]


def test_plan_sync_creates_missing_role():
    rf = RolesFile.model_validate(
        {
            "version": 1,
            "roles": {"a": {"name": "A", "groups": ["base.group_user"]}},
        }
    )
    db_state = RoleDbState(roles_by_name={}, xmlid_to_group_id={"base.group_user": 1})
    plan = plan_sync(rf, db_state)
    assert len(plan) == 1
    assert plan[0].action == "create"
    assert plan[0].role_id == "a"
    assert plan[0].desired_group_ids == [1]


def test_plan_sync_updates_changed_role():
    rf = RolesFile.model_validate(
        {
            "version": 1,
            "roles": {"a": {"name": "A", "groups": ["base.group_user", "base.group_system"]}},
        }
    )
    db_state = RoleDbState(
        roles_by_name={"A": {"id": 100, "implied_ids": [1]}},
        xmlid_to_group_id={"base.group_user": 1, "base.group_system": 5},
    )
    plan = plan_sync(rf, db_state)
    assert len(plan) == 1
    assert plan[0].action == "update"
    assert plan[0].existing_role_id == 100
    assert set(plan[0].desired_group_ids) == {1, 5}


def test_plan_sync_noop_when_matching():
    rf = RolesFile.model_validate(
        {
            "version": 1,
            "roles": {"a": {"name": "A", "groups": ["base.group_user"]}},
        }
    )
    db_state = RoleDbState(
        roles_by_name={"A": {"id": 100, "implied_ids": [1]}},
        xmlid_to_group_id={"base.group_user": 1},
    )
    plan = plan_sync(rf, db_state)
    assert plan == []


def test_plan_sync_prune_flags_extra_roles():
    rf = RolesFile.model_validate({"version": 1, "roles": {}})
    db_state = RoleDbState(
        roles_by_name={"Stale Role": {"id": 99, "implied_ids": []}},
        xmlid_to_group_id={},
    )
    plan = plan_sync(rf, db_state, prune=True)
    assert len(plan) == 1
    assert plan[0].action == "delete"
    assert plan[0].existing_role_id == 99


def test_plan_sync_without_prune_ignores_extra_roles():
    rf = RolesFile.model_validate({"version": 1, "roles": {}})
    db_state = RoleDbState(
        roles_by_name={"Stale Role": {"id": 99, "implied_ids": []}},
        xmlid_to_group_id={},
    )
    plan = plan_sync(rf, db_state, prune=False)
    assert plan == []


def test_plan_menu_visibility_adds_missing_exclusions():
    rf = RolesFile.model_validate(
        {
            "version": 1,
            "roles": {
                "hr_user": {
                    "name": "HR Officer",
                    "groups": ["hr.group_hr_user"],
                    "hide_menus": ["Sales", "Dashboards"],
                },
            },
        }
    )
    actions = plan_menu_visibility(
        rf,
        role_backing_groups={"hr_user": 233},
        menu_ids_by_name={"Sales": 100, "Dashboards": 101, "Unused": 999},
        current_exclusions={100: set(), 101: set()},
    )
    assert len(actions) == 2
    assert all(a.action == "add" for a in actions)
    assert all(a.group_id == 233 for a in actions)
    assert sorted(a.menu_name for a in actions) == ["Dashboards", "Sales"]


def test_plan_menu_visibility_skips_existing():
    rf = RolesFile.model_validate(
        {
            "version": 1,
            "roles": {
                "hr_user": {"name": "HR Officer", "groups": [], "hide_menus": ["Sales"]},
            },
        }
    )
    actions = plan_menu_visibility(
        rf,
        role_backing_groups={"hr_user": 233},
        menu_ids_by_name={"Sales": 100},
        current_exclusions={100: {233}},  # already excluded
    )
    assert actions == []


def test_plan_menu_visibility_prune_removes_stale():
    rf = RolesFile.model_validate(
        {
            "version": 1,
            "roles": {
                "hr_user": {"name": "HR Officer", "groups": [], "hide_menus": []},
            },
        }
    )
    actions = plan_menu_visibility(
        rf,
        role_backing_groups={"hr_user": 233},
        menu_ids_by_name={"Sales": 100},
        current_exclusions={100: {233}},  # was excluded; YAML doesn't ask for it now
        prune=True,
    )
    assert len(actions) == 1
    assert actions[0].action == "remove"
    assert actions[0].menu_id == 100
    assert actions[0].group_id == 233


def test_plan_menu_visibility_skips_unknown_menu_names():
    rf = RolesFile.model_validate(
        {
            "version": 1,
            "roles": {
                "x": {"name": "X", "groups": [], "hide_menus": ["Ghost Menu"]},
            },
        }
    )
    actions = plan_menu_visibility(
        rf,
        role_backing_groups={"x": 1},
        menu_ids_by_name={},  # "Ghost Menu" unknown
        current_exclusions={},
    )
    assert actions == []
