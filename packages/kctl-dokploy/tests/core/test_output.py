"""Tests for multi-format output handler."""

from __future__ import annotations

import csv
import io
import json

import pytest
import yaml

from kctl_dokploy.core.output import Output


class TestStripMarkup:
    def test_removes_simple_tags(self) -> None:
        assert Output._strip_markup("[green]OK[/green]") == "OK"

    def test_removes_nested_tags(self) -> None:
        assert Output._strip_markup("[bold cyan]Title[/bold cyan]") == "Title"

    def test_no_tags_unchanged(self) -> None:
        assert Output._strip_markup("hello world") == "hello world"


class TestTableJsonMode:
    def test_outputs_valid_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        out = Output(json_mode=True)
        out.table(
            "Test",
            [("Name", ""), ("Status", "")],
            [["alice", "active"], ["bob", "inactive"]],
        )
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["name"] == "alice"

    def test_uses_data_for_json_when_provided(self, capsys: pytest.CaptureFixture[str]) -> None:
        out = Output(json_mode=True)
        custom = [{"id": 1, "label": "test"}]
        out.table("Test", [("X", "")], [["x"]], data_for_json=custom)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data == custom


class TestTableCsvMode:
    def test_outputs_valid_csv(self, capsys: pytest.CaptureFixture[str]) -> None:
        out = Output(format="csv")
        out.table(
            "Test",
            [("Name", ""), ("Age", "")],
            [["Alice", "30"], ["Bob", "25"]],
        )
        captured = capsys.readouterr()
        reader = csv.reader(io.StringIO(captured.out))
        rows = list(reader)
        assert rows[0] == ["Name", "Age"]
        assert rows[1] == ["Alice", "30"]

    def test_no_header_flag(self, capsys: pytest.CaptureFixture[str]) -> None:
        out = Output(format="csv", no_header=True)
        out.table("Test", [("Name", "")], [["Alice"]])
        captured = capsys.readouterr()
        lines = captured.out.strip().split("\n")
        assert len(lines) == 1
        assert "Alice" in lines[0]


class TestTableYamlMode:
    def test_outputs_valid_yaml(self, capsys: pytest.CaptureFixture[str]) -> None:
        out = Output(format="yaml")
        custom = [{"name": "alice", "status": "active"}]
        out.table("Test", [("Name", "")], [["alice"]], data_for_json=custom)
        captured = capsys.readouterr()
        data = yaml.safe_load(captured.out)
        assert isinstance(data, list)
        assert data[0]["name"] == "alice"


class TestDetailJsonMode:
    def test_outputs_valid_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        out = Output(json_mode=True)
        out.detail(
            "User",
            [("Info", [("Name", "Alice"), ("Role", "Admin")])],
            data_for_json={"name": "Alice", "role": "Admin"},
        )
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["name"] == "Alice"


class TestDetailYamlMode:
    def test_outputs_valid_yaml(self, capsys: pytest.CaptureFixture[str]) -> None:
        out = Output(format="yaml")
        out.detail(
            "User",
            [("Info", [("Name", "Alice")])],
            data_for_json={"name": "Alice"},
        )
        captured = capsys.readouterr()
        data = yaml.safe_load(captured.out)
        assert data["name"] == "Alice"


class TestMessages:
    def test_success_not_shown_in_quiet(self, capsys: pytest.CaptureFixture[str]) -> None:
        out = Output(quiet=True)
        out.success("done")
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_error_shown_in_quiet(self, capsys: pytest.CaptureFixture[str]) -> None:
        out = Output(quiet=True)
        out.error("fail")
        captured = capsys.readouterr()
        assert "fail" in captured.out

    def test_info_suppressed_in_quiet(self, capsys: pytest.CaptureFixture[str]) -> None:
        out = Output(quiet=True)
        out.info("msg")
        captured = capsys.readouterr()
        assert captured.out == ""
