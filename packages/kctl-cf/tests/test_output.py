"""Tests for the output handler.

The Output class switches between Rich (pretty), JSON, CSV, and YAML modes.
In JSON mode data is printed to stdout as valid JSON, while status messages
go to stderr.
"""

from __future__ import annotations

import json

import pytest

from kctl_cf.core.output import Output

# ---------------------------------------------------------------------------
# JSON mode
# ---------------------------------------------------------------------------


class TestTableJsonMode:
    """Output.table() in JSON mode emits valid JSON to stdout."""

    def test_table_outputs_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        """In JSON mode, table() prints a JSON array to stdout."""
        out = Output(json_mode=True)
        out.table(
            title="Zones",
            columns=[("Name", ""), ("Status", "")],
            rows=[["kodeme.io", "active"], ["example.com", "pending"]],
        )
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["name"] == "kodeme.io"
        assert data[1]["status"] == "pending"

    def test_table_custom_data_for_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        """data_for_json overrides the auto-generated JSON."""
        out = Output(json_mode=True)
        custom = [{"id": "zone_123", "name": "kodeme.io"}]
        out.table(
            title="T",
            columns=[("X", "")],
            rows=[["row"]],
            data_for_json=custom,
        )
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data == custom

    def test_table_empty_rows(self, capsys: pytest.CaptureFixture[str]) -> None:
        """JSON mode with empty rows produces empty array."""
        out = Output(json_mode=True)
        out.table("Empty", [("Col", "")], [])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data == []


class TestDetailJsonMode:
    """Output.detail() in JSON mode emits valid JSON to stdout."""

    def test_detail_outputs_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        """In JSON mode, detail() prints a JSON object to stdout."""
        out = Output(json_mode=True)
        out.detail(
            title="Zone Info",
            sections=[("Zone", [("name", "kodeme.io")])],
            data_for_json={"name": "kodeme.io", "status": "active"},
        )
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data == {"name": "kodeme.io", "status": "active"}

    def test_detail_no_data_for_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        """In JSON mode with no data_for_json, detail() prints nothing to stdout."""
        out = Output(json_mode=True)
        out.detail(
            title="Empty",
            sections=[("S", [("k", "v")])],
        )
        captured = capsys.readouterr()
        assert captured.out == ""


# ---------------------------------------------------------------------------
# CSV mode
# ---------------------------------------------------------------------------


class TestTableCsvMode:
    """Output.table() in CSV mode."""

    def test_csv_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        """CSV mode produces comma-separated values."""
        out = Output(format="csv")
        out.table(
            title="Zones",
            columns=[("Name", ""), ("Status", "")],
            rows=[["kodeme.io", "[green]active[/green]"]],
        )
        captured = capsys.readouterr()
        lines = [ln.rstrip("\r") for ln in captured.out.strip().split("\n")]
        assert lines[0] == "Name,Status"
        assert "kodeme.io" in lines[1]
        # Rich markup should be stripped
        assert "[green]" not in lines[1]

    def test_csv_no_header(self, capsys: pytest.CaptureFixture[str]) -> None:
        """CSV mode with no_header skips header row."""
        out = Output(format="csv", no_header=True)
        out.table(
            title="T",
            columns=[("Name", "")],
            rows=[["val"]],
        )
        captured = capsys.readouterr()
        lines = [ln.rstrip("\r") for ln in captured.out.strip().split("\n")]
        assert len(lines) == 1
        assert "Name" not in lines[0]

    def test_csv_detail(self, capsys: pytest.CaptureFixture[str]) -> None:
        """CSV detail outputs section,key,value rows."""
        out = Output(format="csv")
        out.detail(
            title="Info",
            sections=[("Zone", [("name", "kodeme.io")])],
        )
        captured = capsys.readouterr()
        lines = [ln.rstrip("\r") for ln in captured.out.strip().split("\n")]
        assert lines[0] == "section,key,value"
        assert "Zone" in lines[1]
        assert "kodeme.io" in lines[1]


# ---------------------------------------------------------------------------
# YAML mode
# ---------------------------------------------------------------------------


class TestTableYamlMode:
    """Output.table() in YAML mode."""

    def test_yaml_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        """YAML mode produces valid YAML."""
        out = Output(format="yaml")
        out.table(
            title="Zones",
            columns=[("Name", ""), ("Status", "")],
            rows=[["kodeme.io", "active"]],
        )
        captured = capsys.readouterr()
        import yaml

        data = yaml.safe_load(captured.out)
        assert isinstance(data, list)
        assert data[0]["name"] == "kodeme.io"

    def test_yaml_detail(self, capsys: pytest.CaptureFixture[str]) -> None:
        """YAML detail outputs structured data."""
        out = Output(format="yaml")
        out.detail(
            title="Info",
            sections=[("Zone", [("name", "kodeme.io")])],
            data_for_json={"name": "kodeme.io"},
        )
        captured = capsys.readouterr()
        import yaml

        data = yaml.safe_load(captured.out)
        assert data["name"] == "kodeme.io"


# ---------------------------------------------------------------------------
# Pretty (non-JSON) mode
# ---------------------------------------------------------------------------


class TestTablePrettyMode:
    """Output.table() in pretty mode does not emit JSON to stdout."""

    def test_no_json_on_stdout(self, capsys: pytest.CaptureFixture[str]) -> None:
        """In non-JSON mode, table() does not write parseable JSON to stdout."""
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
        nested = {"zones": [{"name": "kodeme.io"}, {"name": "example.com"}]}
        out.raw_json(nested)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert len(data["zones"]) == 2


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


# ---------------------------------------------------------------------------
# Format flag shorthand
# ---------------------------------------------------------------------------


class TestFormatFlag:
    """--format json is equivalent to --json."""

    def test_format_json_is_json_mode(self) -> None:
        out = Output(format="json")
        assert out.json_mode is True

    def test_json_flag_overrides_format(self) -> None:
        out = Output(json_mode=True, format="csv")
        assert out.json_mode is True
        assert out.format == "json"
