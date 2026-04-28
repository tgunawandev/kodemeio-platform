"""Tests for audit access-report command and report builder."""

from __future__ import annotations

from kctl_ak.reports.access_control import (
    AccessRow,
    ReportData,
    ReportFilters,
    build_rows,
)


MOCK_USERS = [
    {
        "pk": 1,
        "username": "alice",
        "email": "alice@kodeme.io",
        "name": "Alice A",
        "is_active": True,
        "type": "internal",
        "groups_obj": [{"pk": "g1", "name": "IT-Team"}],
    },
    {
        "pk": 2,
        "username": "bob",
        "email": "bob@kodeme.io",
        "name": "Bob B",
        "is_active": True,
        "type": "internal",
        "groups_obj": [],
    },
    {
        "pk": 3,
        "username": "svc-backup",
        "email": "",
        "name": "Backup Service",
        "is_active": True,
        "type": "internal_service_account",
        "groups_obj": [{"pk": "g2", "name": "Services"}],
    },
    {
        "pk": 4,
        "username": "carol",
        "email": "carol@kodeme.io",
        "name": "Carol C",
        "is_active": False,
        "type": "internal",
        "groups_obj": [{"pk": "g1", "name": "IT-Team"}],
    },
]

MOCK_APPS = [
    {"pk": "app-1", "slug": "mattermost", "name": "Mattermost"},
    {"pk": "app-2", "slug": "grafana", "name": "Grafana"},
]

MOCK_BINDINGS = [
    {
        "pk": "b1",
        "target": "app-1",
        "group_obj": {"pk": "g1", "name": "IT-Team"},
        "user_obj": None,
        "policy_obj": None,
        "enabled": True,
        "negate": False,
    },
    {
        "pk": "b2",
        "target": "app-2",
        "group_obj": None,
        "user_obj": {"pk": 2, "username": "bob"},
        "policy_obj": None,
        "enabled": True,
        "negate": False,
    },
    {
        "pk": "b3",
        "target": "app-2",
        "group_obj": {"pk": "g2", "name": "Services"},
        "user_obj": None,
        "policy_obj": None,
        "enabled": True,
        "negate": False,
    },
    {
        "pk": "b4",
        "target": "app-1",
        "group_obj": {"pk": "g1", "name": "IT-Team"},
        "user_obj": None,
        "policy_obj": None,
        "enabled": False,
        "negate": False,
    },
]


def _make_data() -> ReportData:
    return ReportData(users=MOCK_USERS, apps=MOCK_APPS, bindings=MOCK_BINDINGS)


class TestBuildRows:
    def test_default_filters_excludes_service_and_deactivated(self) -> None:
        filters = ReportFilters()
        rows = build_rows(_make_data(), filters)
        usernames = {r.username for r in rows}
        assert "alice" in usernames
        assert "bob" in usernames
        assert "svc-backup" not in usernames
        assert "carol" not in usernames

    def test_row_count_is_users_times_apps(self) -> None:
        filters = ReportFilters()
        rows = build_rows(_make_data(), filters)
        assert len(rows) == 2 * 2  # 2 active human users x 2 apps

    def test_alice_has_access_to_mattermost_via_group(self) -> None:
        filters = ReportFilters()
        rows = build_rows(_make_data(), filters)
        alice_mm = next(r for r in rows if r.username == "alice" and r.app_slug == "mattermost")
        assert alice_mm.has_access == "yes"
        assert alice_mm.access_via == "group:IT-Team"

    def test_bob_has_direct_access_to_grafana(self) -> None:
        filters = ReportFilters()
        rows = build_rows(_make_data(), filters)
        bob_graf = next(r for r in rows if r.username == "bob" and r.app_slug == "grafana")
        assert bob_graf.has_access == "yes"
        assert bob_graf.access_via == "user:direct"

    def test_alice_no_access_to_grafana(self) -> None:
        filters = ReportFilters()
        rows = build_rows(_make_data(), filters)
        alice_graf = next(r for r in rows if r.username == "alice" and r.app_slug == "grafana")
        assert alice_graf.has_access == "no"
        assert alice_graf.access_via == "none"

    def test_disabled_binding_ignored(self) -> None:
        filters = ReportFilters()
        data = _make_data()
        data.bindings = [b for b in data.bindings if b["pk"] != "b1"]
        rows = build_rows(data, filters)
        alice_mm = next(r for r in rows if r.username == "alice" and r.app_slug == "mattermost")
        assert alice_mm.has_access == "no"

    def test_include_service_accounts(self) -> None:
        filters = ReportFilters(include_service_accounts=True)
        rows = build_rows(_make_data(), filters)
        usernames = {r.username for r in rows}
        assert "svc-backup" in usernames

    def test_include_deactivated(self) -> None:
        filters = ReportFilters(include_deactivated=True)
        rows = build_rows(_make_data(), filters)
        usernames = {r.username for r in rows}
        assert "carol" in usernames

    def test_active_only(self) -> None:
        filters = ReportFilters(active_only=True, include_service_accounts=True)
        rows = build_rows(_make_data(), filters)
        usernames = {r.username for r in rows}
        assert "carol" not in usernames
        assert "svc-backup" in usernames

    def test_app_filter(self) -> None:
        filters = ReportFilters(app_slug="mattermost")
        rows = build_rows(_make_data(), filters)
        app_slugs = {r.app_slug for r in rows}
        assert app_slugs == {"mattermost"}

    def test_rows_sorted_by_username_then_app(self) -> None:
        filters = ReportFilters()
        rows = build_rows(_make_data(), filters)
        keys = [(r.username, r.app_slug) for r in rows]
        assert keys == sorted(keys)

    def test_negate_binding(self) -> None:
        data = _make_data()
        for b in data.bindings:
            if b["pk"] == "b1":
                b["negate"] = True
        filters = ReportFilters()
        rows = build_rows(data, filters)
        alice_mm = next(r for r in rows if r.username == "alice" and r.app_slug == "mattermost")
        assert alice_mm.has_access == "no"
        assert alice_mm.access_via == "group:IT-Team"
        assert alice_mm.binding_negate == "yes"
