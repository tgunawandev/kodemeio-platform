"""Tests for groups sync 3-phase logic."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from kctl_ak.cli import app
from kctl_ak.commands.groups import _compute_sync_plan

runner = CliRunner()


# ---------------------------------------------------------------------------
# Helpers — build minimal group dicts matching the API shape
# ---------------------------------------------------------------------------


def _desired(
    name: str,
    is_superuser: bool = False,
    parent: str | None = None,
    description: str = "",
) -> dict:
    """Build a desired-group dict (from YAML)."""
    d: dict = {"name": name, "is_superuser": is_superuser}
    if parent:
        d["parent"] = parent
    if description:
        d["description"] = description
    return d


def _existing(
    name: str,
    pk: str = "pk-placeholder",
    is_superuser: bool = False,
    parent: str | None = None,
    parent_name: str | None = None,
    description: str = "",
) -> dict:
    """Build an existing-group dict (from API)."""
    return {
        "pk": pk,
        "name": name,
        "is_superuser": is_superuser,
        "parent": parent,
        "parent_name": parent_name,
        "attributes": {"description": description} if description else {},
        "users": [],
    }


# ===========================================================================
# Unit tests for _compute_sync_plan
# ===========================================================================


class TestCreatePhase:
    def test_create_phase_detects_missing_groups(self) -> None:
        desired = [_desired("ak-app-new"), _desired("ak-app-existing")]
        existing = [_existing("ak-app-existing", pk="111")]

        plan = _compute_sync_plan(desired, existing)

        assert len(plan["create"]) == 1
        assert plan["create"][0]["name"] == "ak-app-new"

    def test_create_phase_empty_when_all_exist(self) -> None:
        desired = [_desired("ak-app-one")]
        existing = [_existing("ak-app-one", pk="111")]

        plan = _compute_sync_plan(desired, existing)
        assert plan["create"] == []


class TestUpdatePhase:
    def test_update_phase_detects_superuser_change(self) -> None:
        desired = [_desired("ak-admin-super", is_superuser=True)]
        existing = [_existing("ak-admin-super", pk="111", is_superuser=False)]

        plan = _compute_sync_plan(desired, existing)

        assert len(plan["update"]) == 1
        entry = plan["update"][0]
        assert entry["name"] == "ak-admin-super"
        assert entry["changes"]["is_superuser"] is True

    def test_update_phase_detects_parent_change(self) -> None:
        desired = [_desired("ak-app-grafana-all", parent="ak-role-devops")]
        existing = [
            _existing("ak-app-grafana-all", pk="222", parent=None, parent_name=None),
            _existing("ak-role-devops", pk="333"),
        ]

        plan = _compute_sync_plan(desired, existing)

        assert len(plan["update"]) == 1
        entry = plan["update"][0]
        assert entry["name"] == "ak-app-grafana-all"
        assert entry["changes"]["parent"] == "ak-role-devops"

    def test_update_phase_detects_description_change(self) -> None:
        desired = [_desired("ak-app-grafana-all", description="New desc")]
        existing = [_existing("ak-app-grafana-all", pk="222", description="Old desc")]

        plan = _compute_sync_plan(desired, existing)

        assert len(plan["update"]) == 1
        assert plan["update"][0]["changes"]["description"] == "New desc"

    def test_update_phase_no_change_when_matching(self) -> None:
        desired = [_desired("ak-admin-super", is_superuser=True, description="Full access")]
        existing = [_existing("ak-admin-super", pk="111", is_superuser=True, description="Full access")]

        plan = _compute_sync_plan(desired, existing)
        assert plan["update"] == []


class TestPrunePhase:
    def test_prune_phase_detects_stale_ak_groups(self) -> None:
        desired = [_desired("ak-app-grafana-all")]
        existing = [
            _existing("ak-app-grafana-all", pk="111"),
            _existing("ak-app-old-service", pk="222"),
        ]

        plan = _compute_sync_plan(desired, existing)

        assert len(plan["prune"]) == 1
        assert plan["prune"][0]["name"] == "ak-app-old-service"

    def test_prune_ignores_non_ak_groups(self) -> None:
        desired = [_desired("ak-app-grafana-all")]
        existing = [
            _existing("ak-app-grafana-all", pk="111"),
            _existing("authentik Admins", pk="sys-1"),
            _existing("Custom Group", pk="cust-1"),
        ]

        plan = _compute_sync_plan(desired, existing)

        assert plan["prune"] == []


class TestNoChanges:
    def test_no_changes_returns_empty_plan(self) -> None:
        desired = [
            _desired("ak-app-one", is_superuser=False, description="Group one"),
            _desired("ak-app-two", is_superuser=False),
        ]
        existing = [
            _existing("ak-app-one", pk="111", is_superuser=False, description="Group one"),
            _existing("ak-app-two", pk="222", is_superuser=False),
        ]

        plan = _compute_sync_plan(desired, existing)

        assert plan["create"] == []
        assert plan["update"] == []
        assert plan["prune"] == []


# ===========================================================================
# CLI integration test (help text)
# ===========================================================================


class TestSyncCLI:
    def test_sync_has_prune_flag(self) -> None:
        result = runner.invoke(app, ["groups", "sync", "--help"])
        assert result.exit_code == 0
        assert "--prune" in result.output
        assert "--dry-run" in result.output
