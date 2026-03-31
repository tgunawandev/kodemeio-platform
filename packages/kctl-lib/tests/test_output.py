"""Tests for kctl_lib.output."""

from __future__ import annotations

import json

from kctl_lib.output import Output


class TestOutputInit:
    def test_defaults(self) -> None:
        out = Output()
        assert out.json_mode is False
        assert out.quiet is False
        assert out.format == "pretty"
        assert out.no_header is False

    def test_json_flag_sets_format(self) -> None:
        out = Output(json_mode=True)
        assert out.json_mode is True
        assert out.format == "json"

    def test_format_json_sets_json_mode(self) -> None:
        out = Output(format="json")
        assert out.json_mode is True


class TestStripMarkup:
    def test_removes_rich_tags(self) -> None:
        assert Output._strip_markup("[green]OK[/green] done") == "OK done"

    def test_no_tags(self) -> None:
        assert Output._strip_markup("plain text") == "plain text"


class TestTableCsv:
    def test_csv_output(self, capsys: object) -> None:
        out = Output(format="csv")
        cols = [("Name", "cyan"), ("Port", "dim")]
        rows = [["app1", "3000"], ["app2", "3001"]]
        out.table("Apps", cols, rows)
        captured = capsys.readouterr()
        assert "Name,Port" in captured.out
        assert "app1,3000" in captured.out

    def test_csv_no_header(self, capsys: object) -> None:
        out = Output(format="csv", no_header=True)
        cols = [("Name", "cyan")]
        rows = [["app1"]]
        out.table("Apps", cols, rows)
        captured = capsys.readouterr()
        assert "Name" not in captured.out
        assert "app1" in captured.out


class TestTableYaml:
    def test_yaml_output(self, capsys: object) -> None:
        out = Output(format="yaml")
        cols = [("Name", "cyan")]
        rows = [["app1"]]
        out.table("Apps", cols, rows)
        captured = capsys.readouterr()
        assert "name: app1" in captured.out


class TestStatusMessages:
    def test_success_not_quiet(self) -> None:
        out = Output()
        out.success("done")

    def test_info_suppressed_when_quiet(self) -> None:
        out = Output(quiet=True)
        out.info("hidden")

    def test_error_always_shown(self) -> None:
        out = Output(quiet=True)
        out.error("visible")


class TestRawJson:
    def test_raw_json(self, capsys: object) -> None:
        out = Output()
        out.raw_json({"key": "value"})
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data == {"key": "value"}


class TestBuildJsonData:
    def test_from_columns_and_rows(self) -> None:
        out = Output()
        cols = [("App Name", "cyan"), ("Port", "dim")]
        rows = [["portfolio", "3000"]]
        result = out._build_json_data(cols, rows, None)
        assert result == [{"app_name": "portfolio", "port": "3000"}]

    def test_data_for_json_takes_precedence(self) -> None:
        out = Output()
        custom = [{"custom": True}]
        result = out._build_json_data([], [], custom)
        assert result == custom
