"""Tests for the output handler.

The Output class switches between Rich (pretty), JSON, CSV, and YAML modes.
In JSON mode data is printed to stdout as valid JSON, while status messages
go to stderr.
"""

from __future__ import annotations

import json

import pytest
import yaml
from kctl_lib.output import Output

# ---------------------------------------------------------------------------
# JSON mode
# ---------------------------------------------------------------------------


class TestTableJsonMode:
    """Output.table() in JSON mode emits valid JSON to stdout."""

    def test_table_outputs_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        out = Output(json_mode=True)
        out.table(
            title="Servers",
            columns=[("Name", ""), ("Status", "")],
            rows=[["web-1", "running"], ["db-1", "off"]],
        )
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["name"] == "web-1"
        assert data[1]["status"] == "off"

    def test_table_custom_data_for_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        out = Output(json_mode=True)
        custom = [{"id": 1, "label": "custom"}]
        out.table(
            title="T",
            columns=[("X", "")],
            rows=[["row"]],
            data_for_json=custom,
        )
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data == custom

    def test_format_json_flag(self, capsys: pytest.CaptureFixture[str]) -> None:
        """--format json also activates JSON mode."""
        out = Output(format="json")
        assert out.json_mode is True
        out.table("T", [("A", "")], [["v"]])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert isinstance(data, list)


class TestDetailJsonMode:
    """Output.detail() in JSON mode emits valid JSON to stdout."""

    def test_detail_outputs_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        out = Output(json_mode=True)
        out.detail(
            title="Server Info",
            sections=[("Server", [("name", "web-1")])],
            data_for_json={"name": "web-1", "status": "running"},
        )
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data == {"name": "web-1", "status": "running"}

    def test_detail_no_data_for_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        out = Output(json_mode=True)
        out.detail(
            title="Empty",
            sections=[("S", [("k", "v")])],
        )
        captured = capsys.readouterr()
        assert captured.out == ""


# ---------------------------------------------------------------------------
# Pretty (non-JSON) mode
# ---------------------------------------------------------------------------


class TestTablePrettyMode:
    """Output.table() in pretty mode does not emit JSON to stdout."""

    def test_no_json_on_stdout(self, capsys: pytest.CaptureFixture[str]) -> None:
        out = Output(json_mode=False)
        out.table(
            title="Test",
            columns=[("Col", "")],
            rows=[["val"]],
        )
        captured = capsys.readouterr()
        with pytest.raises(json.JSONDecodeError):
            json.loads(captured.out)


# ---------------------------------------------------------------------------
# CSV mode
# ---------------------------------------------------------------------------


class TestCsvMode:
    """Output in CSV format."""

    def test_table_csv_with_header(self, capsys: pytest.CaptureFixture[str]) -> None:
        out = Output(format="csv")
        out.table(
            title="T",
            columns=[("Name", ""), ("Status", "")],
            rows=[["web-1", "running"]],
        )
        captured = capsys.readouterr()
        lines = [line.rstrip("\r") for line in captured.out.strip().split("\n")]
        assert lines[0] == "Name,Status"
        assert lines[1] == "web-1,running"

    def test_table_csv_no_header(self, capsys: pytest.CaptureFixture[str]) -> None:
        out = Output(format="csv", no_header=True)
        out.table(
            title="T",
            columns=[("Name", ""), ("Status", "")],
            rows=[["web-1", "running"]],
        )
        captured = capsys.readouterr()
        lines = captured.out.strip().split("\n")
        assert len(lines) == 1
        assert lines[0] == "web-1,running"

    def test_csv_strips_rich_markup(self, capsys: pytest.CaptureFixture[str]) -> None:
        out = Output(format="csv")
        out.table(
            title="T",
            columns=[("Name", ""), ("Status", "")],
            rows=[["web-1", "[green]running[/green]"]],
        )
        captured = capsys.readouterr()
        assert "[green]" not in captured.out
        assert "running" in captured.out

    def test_detail_csv(self, capsys: pytest.CaptureFixture[str]) -> None:
        out = Output(format="csv")
        out.detail(
            title="Server",
            sections=[("Info", [("name", "web-1"), ("status", "running")])],
        )
        captured = capsys.readouterr()
        assert "section,key,value" in captured.out
        assert "Info,name,web-1" in captured.out


# ---------------------------------------------------------------------------
# YAML mode
# ---------------------------------------------------------------------------


class TestYamlMode:
    """Output in YAML format."""

    def test_table_yaml(self, capsys: pytest.CaptureFixture[str]) -> None:
        out = Output(format="yaml")
        out.table(
            title="T",
            columns=[("Name", ""), ("Status", "")],
            rows=[["web-1", "running"]],
        )
        captured = capsys.readouterr()
        data = yaml.safe_load(captured.out)
        assert isinstance(data, list)
        assert data[0]["name"] == "web-1"

    def test_detail_yaml(self, capsys: pytest.CaptureFixture[str]) -> None:
        out = Output(format="yaml")
        out.detail(
            title="Server",
            sections=[("Info", [("name", "web-1")])],
            data_for_json={"name": "web-1"},
        )
        captured = capsys.readouterr()
        data = yaml.safe_load(captured.out)
        assert data == {"name": "web-1"}

    def test_detail_yaml_from_sections(self, capsys: pytest.CaptureFixture[str]) -> None:
        out = Output(format="yaml")
        out.detail(
            title="Server",
            sections=[("Info", [("name", "web-1"), ("status", "running")])],
        )
        captured = capsys.readouterr()
        data = yaml.safe_load(captured.out)
        assert data["Info"]["name"] == "web-1"


# ---------------------------------------------------------------------------
# Quiet mode
# ---------------------------------------------------------------------------


class TestQuietMode:
    """Output quiet=True suppresses info/success/warn messages."""

    def test_info_suppressed(self, capsys: pytest.CaptureFixture[str]) -> None:
        out = Output(quiet=True)
        out.info("should not appear")
        captured = capsys.readouterr()
        assert "should not appear" not in captured.out
        assert "should not appear" not in captured.err

    def test_success_suppressed(self, capsys: pytest.CaptureFixture[str]) -> None:
        out = Output(quiet=True)
        out.success("hidden")
        captured = capsys.readouterr()
        assert "hidden" not in captured.out
        assert "hidden" not in captured.err

    def test_warn_suppressed(self, capsys: pytest.CaptureFixture[str]) -> None:
        out = Output(quiet=True)
        out.warn("hidden warning")
        captured = capsys.readouterr()
        assert "hidden warning" not in captured.out
        assert "hidden warning" not in captured.err

    def test_error_not_suppressed(self, capsys: pytest.CaptureFixture[str]) -> None:
        """quiet=True does NOT suppress error() -- errors are always visible."""
        out = Output(quiet=True)
        out.error("visible error")
        captured = capsys.readouterr()
        combined = captured.out + captured.err
        assert "visible error" in combined


# ---------------------------------------------------------------------------
# raw_json
# ---------------------------------------------------------------------------


class TestRawJson:
    """Output.raw_json() outputs valid JSON to stdout."""

    def test_dict(self, capsys: pytest.CaptureFixture[str]) -> None:
        out = Output()
        out.raw_json({"key": "value", "count": 42})
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data == {"key": "value", "count": 42}

    def test_list(self, capsys: pytest.CaptureFixture[str]) -> None:
        out = Output()
        out.raw_json([1, 2, 3])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data == [1, 2, 3]

    def test_nested(self, capsys: pytest.CaptureFixture[str]) -> None:
        out = Output()
        nested = {"servers": [{"name": "web-1"}, {"name": "db-1"}]}
        out.raw_json(nested)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert len(data["servers"]) == 2


# ---------------------------------------------------------------------------
# Tree output
# ---------------------------------------------------------------------------


class TestTreeJsonMode:
    """Output.tree() in JSON mode."""

    def test_tree_outputs_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        out = Output(json_mode=True)
        nodes = [{"name": "root", "children": [{"name": "child"}]}]
        out.tree("Test Tree", nodes)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert isinstance(data, list)
        assert data[0]["name"] == "root"

    def test_tree_pretty(self, capsys: pytest.CaptureFixture[str]) -> None:
        out = Output(json_mode=False)
        nodes = [{"name": "root", "info": "3 items", "children": [{"name": "child"}]}]
        out.tree("Test Tree", nodes)
        captured = capsys.readouterr()
        assert "root" in captured.out
