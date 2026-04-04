"""Tests for apps sync logic."""

from __future__ import annotations

import pytest
import yaml
from pathlib import Path
from typer.testing import CliRunner
from kctl_ak.cli import app

runner = CliRunner()


class TestAppsSyncHelp:
    def test_sync_has_prune_flag(self) -> None:
        result = runner.invoke(app, ["apps", "sync", "--help"])
        assert result.exit_code == 0
        assert "--prune" in result.output
        assert "--no-dry-run" in result.output


class TestAppsSyncAlgorithm:
    def test_create_phase_detects_missing_apps(self) -> None:
        from kctl_ak.commands.apps import _compute_app_sync_plan

        desired = [
            {"slug": "mac-odoo-dist", "name": "MAC — Odoo", "group": "MAC"},
            {"slug": "shared-gatus", "name": "Shared — Gatus", "group": "Infra"},
        ]
        existing = [
            {
                "slug": "shared-gatus",
                "name": "Shared — Gatus",
                "group": "Infra",
                "meta_launch_url": "",
                "meta_icon": "",
            }
        ]
        plan = _compute_app_sync_plan(desired, existing)
        assert len(plan["create"]) == 1
        assert plan["create"][0]["slug"] == "mac-odoo-dist"

    def test_update_phase_detects_name_change(self) -> None:
        from kctl_ak.commands.apps import _compute_app_sync_plan

        desired = [{"slug": "gatus", "name": "Shared — Gatus", "group": "Infra"}]
        existing = [
            {
                "slug": "gatus",
                "name": "Gatus",
                "group": "",
                "meta_launch_url": "",
                "meta_icon": "",
            }
        ]
        plan = _compute_app_sync_plan(desired, existing)
        assert len(plan["update"]) == 1
        assert "name" in plan["update"][0]["changes"]

    def test_update_phase_detects_group_change(self) -> None:
        from kctl_ak.commands.apps import _compute_app_sync_plan

        desired = [{"slug": "gatus", "name": "Gatus", "group": "Shared — Infrastructure"}]
        existing = [
            {
                "slug": "gatus",
                "name": "Gatus",
                "group": "",
                "meta_launch_url": "",
                "meta_icon": "",
            }
        ]
        plan = _compute_app_sync_plan(desired, existing)
        assert len(plan["update"]) == 1
        assert "group" in plan["update"][0]["changes"]

    def test_prune_detects_stale_prefixed_apps(self) -> None:
        from kctl_ak.commands.apps import _compute_app_sync_plan

        desired = [{"slug": "mac-odoo-dist", "name": "MAC", "group": "MAC"}]
        existing = [
            {
                "slug": "mac-odoo-dist",
                "name": "MAC",
                "group": "MAC",
                "meta_launch_url": "",
                "meta_icon": "",
            },
            {
                "slug": "mac-react-old",
                "name": "OLD",
                "group": "MAC",
                "meta_launch_url": "",
                "meta_icon": "",
            },
            {
                "slug": "ldap",
                "name": "LDAP",
                "group": "",
                "meta_launch_url": "",
                "meta_icon": "",
            },
        ]
        plan = _compute_app_sync_plan(desired, existing)
        assert len(plan["prune"]) == 1
        assert plan["prune"][0]["slug"] == "mac-react-old"

    def test_prune_ignores_system_apps(self) -> None:
        from kctl_ak.commands.apps import _compute_app_sync_plan

        desired: list[dict] = []
        existing = [
            {
                "slug": "ldap",
                "name": "LDAP",
                "group": "",
                "meta_launch_url": "",
                "meta_icon": "",
            },
            {
                "slug": "dokploy",
                "name": "Dokploy",
                "group": "",
                "meta_launch_url": "",
                "meta_icon": "",
            },
        ]
        plan = _compute_app_sync_plan(desired, existing)
        assert len(plan["prune"]) == 0

    def test_no_changes(self) -> None:
        from kctl_ak.commands.apps import _compute_app_sync_plan

        desired = [{"slug": "mac-odoo-dist", "name": "MAC", "group": "MAC"}]
        existing = [
            {
                "slug": "mac-odoo-dist",
                "name": "MAC",
                "group": "MAC",
                "meta_launch_url": "",
                "meta_icon": "",
            }
        ]
        plan = _compute_app_sync_plan(desired, existing)
        assert len(plan["create"]) == 0
        assert len(plan["update"]) == 0
        assert len(plan["prune"]) == 0
