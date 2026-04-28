"""Tests for audit access-report command and report builder."""

from __future__ import annotations

import io

import pytest

from kctl_ak.reports.access_control import (
    AccessRow,
    ReportData,
    ReportFilters,
    ReportMeta,
    build_rows,
    to_json,
    write_markdown,
    write_xlsx,
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


class TestWriteMarkdown:
    def test_markdown_header_contains_meta(self) -> None:
        meta = ReportMeta(
            profile="kodemeio",
            generated_at="2026-04-28T14:30:00+07:00",
            user_count=2,
            app_count=2,
            row_count=4,
        )
        rows = build_rows(_make_data(), ReportFilters())
        buf = io.StringIO()
        write_markdown(rows, meta, buf)
        output = buf.getvalue()
        assert "# Access Control Report" in output
        assert "kodemeio" in output
        assert "2026-04-28" in output

    def test_markdown_has_pipe_table(self) -> None:
        meta = ReportMeta(
            profile="test",
            generated_at="2026-04-28T00:00:00Z",
            user_count=2,
            app_count=2,
            row_count=4,
        )
        rows = build_rows(_make_data(), ReportFilters())
        buf = io.StringIO()
        write_markdown(rows, meta, buf)
        output = buf.getvalue()
        assert "| Username |" in output
        assert "| alice " in output

    def test_markdown_to_file(self, tmp_path) -> None:
        meta = ReportMeta(
            profile="test",
            generated_at="2026-04-28T00:00:00Z",
            user_count=2,
            app_count=2,
            row_count=4,
        )
        rows = build_rows(_make_data(), ReportFilters())
        out_path = tmp_path / "report.md"
        with open(out_path, "w") as f:
            write_markdown(rows, meta, f)
        content = out_path.read_text()
        assert "# Access Control Report" in content
        assert len(content.strip().split("\n")) > 5


class TestWriteXlsx:
    def test_xlsx_creates_file(self, tmp_path) -> None:
        meta = ReportMeta(
            profile="kodemeio",
            generated_at="2026-04-28T14:30:00+07:00",
            user_count=2,
            app_count=2,
            row_count=4,
        )
        rows = build_rows(_make_data(), ReportFilters())
        out_path = tmp_path / "report.xlsx"
        write_xlsx(rows, meta, out_path)
        assert out_path.exists()
        assert out_path.stat().st_size > 0

    def test_xlsx_has_two_sheets(self, tmp_path) -> None:
        openpyxl = pytest.importorskip("openpyxl")
        meta = ReportMeta(
            profile="kodemeio",
            generated_at="2026-04-28T14:30:00+07:00",
            user_count=2,
            app_count=2,
            row_count=4,
        )
        rows = build_rows(_make_data(), ReportFilters())
        out_path = tmp_path / "report.xlsx"
        write_xlsx(rows, meta, out_path)
        wb = openpyxl.load_workbook(out_path)
        assert "Access Control" in wb.sheetnames
        assert "Summary" in wb.sheetnames

    def test_xlsx_data_sheet_row_count(self, tmp_path) -> None:
        openpyxl = pytest.importorskip("openpyxl")
        meta = ReportMeta(
            profile="kodemeio",
            generated_at="2026-04-28T14:30:00+07:00",
            user_count=2,
            app_count=2,
            row_count=4,
        )
        rows = build_rows(_make_data(), ReportFilters())
        out_path = tmp_path / "report.xlsx"
        write_xlsx(rows, meta, out_path)
        wb = openpyxl.load_workbook(out_path)
        ws = wb["Access Control"]
        assert ws.max_row == 5  # 1 header + 4 data rows

    def test_xlsx_header_row_is_bold(self, tmp_path) -> None:
        openpyxl = pytest.importorskip("openpyxl")
        meta = ReportMeta(
            profile="kodemeio",
            generated_at="2026-04-28T14:30:00+07:00",
            user_count=2,
            app_count=2,
            row_count=4,
        )
        rows = build_rows(_make_data(), ReportFilters())
        out_path = tmp_path / "report.xlsx"
        write_xlsx(rows, meta, out_path)
        wb = openpyxl.load_workbook(out_path)
        ws = wb["Access Control"]
        assert ws.cell(1, 1).font.bold is True

    def test_xlsx_auto_filter_enabled(self, tmp_path) -> None:
        openpyxl = pytest.importorskip("openpyxl")
        meta = ReportMeta(
            profile="kodemeio",
            generated_at="2026-04-28T14:30:00+07:00",
            user_count=2,
            app_count=2,
            row_count=4,
        )
        rows = build_rows(_make_data(), ReportFilters())
        out_path = tmp_path / "report.xlsx"
        write_xlsx(rows, meta, out_path)
        wb = openpyxl.load_workbook(out_path)
        ws = wb["Access Control"]
        assert ws.auto_filter.ref is not None


class TestToJson:
    def test_json_has_meta_and_rows(self) -> None:
        meta = ReportMeta(
            profile="kodemeio",
            generated_at="2026-04-28T14:30:00+07:00",
            user_count=2,
            app_count=2,
            row_count=4,
        )
        rows = build_rows(_make_data(), ReportFilters())
        result = to_json(rows, meta)
        assert "meta" in result
        assert "rows" in result
        assert result["meta"]["profile"] == "kodemeio"
        assert len(result["rows"]) == 4

    def test_json_rows_are_dicts(self) -> None:
        meta = ReportMeta(
            profile="test",
            generated_at="2026-04-28T00:00:00Z",
            user_count=2,
            app_count=2,
            row_count=4,
        )
        rows = build_rows(_make_data(), ReportFilters())
        result = to_json(rows, meta)
        first = result["rows"][0]
        assert "username" in first
        assert "has_access" in first


from typer.testing import CliRunner

from kctl_ak.cli import app as cli_app

cli_runner = CliRunner()


class TestAccessReportCLI:
    def test_help(self) -> None:
        result = cli_runner.invoke(cli_app, ["audit", "access-report", "--help"])
        assert result.exit_code == 0
        assert "--output" in result.output
        assert "--format" in result.output
        assert "--active-only" in result.output
        assert "--include-service-accounts" in result.output
        assert "--include-deactivated" in result.output
        assert "--app" in result.output
