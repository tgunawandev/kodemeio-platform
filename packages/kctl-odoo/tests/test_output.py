"""Tests for the output handler.

The Output class switches between Rich (pretty) and JSON modes.  In JSON mode
data is printed to stdout as valid JSON, while status messages go to stderr.
"""

from __future__ import annotations

import json

import pytest

from kctl_odoo.core.output import Output

# ---------------------------------------------------------------------------
# JSON mode
# ---------------------------------------------------------------------------


class TestTableJsonMode:
    """Output.table() in JSON mode emits valid JSON to stdout."""

    def test_table_outputs_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        """In JSON mode, table() prints a JSON array to stdout."""
        out = Output(json_mode=True)
        out.table(
            title="Users",
            columns=[("Name", ""), ("Email", "")],
            rows=[["Alice", "alice@x.com"], ["Bob", "bob@x.com"]],
        )
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["name"] == "Alice"
        assert data[1]["email"] == "bob@x.com"

    def test_table_custom_data_for_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        """data_for_json overrides the auto-generated JSON."""
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


class TestDetailJsonMode:
    """Output.detail() in JSON mode emits valid JSON to stdout."""

    def test_detail_outputs_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        """In JSON mode, detail() prints a JSON object to stdout."""
        out = Output(json_mode=True)
        out.detail(
            title="Server Info",
            sections=[("Version", [("odoo", "18.0")])],
            data_for_json={"version": "18.0"},
        )
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data == {"version": "18.0"}

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
        # Rich writes to console (stdout by default), but it should NOT be
        # valid JSON -- it includes ANSI formatting and table borders.
        with pytest.raises(json.JSONDecodeError):
            json.loads(captured.out)


# ---------------------------------------------------------------------------
# Quiet mode
# ---------------------------------------------------------------------------


class TestQuietMode:
    """Output quiet=True suppresses info/success/warn messages."""

    def test_info_suppressed(self, capsys: pytest.CaptureFixture[str]) -> None:
        """quiet=True suppresses info()."""
        out = Output(quiet=True)
        out.info("should not appear")
        captured = capsys.readouterr()
        assert "should not appear" not in captured.out
        assert "should not appear" not in captured.err

    def test_success_suppressed(self, capsys: pytest.CaptureFixture[str]) -> None:
        """quiet=True suppresses success()."""
        out = Output(quiet=True)
        out.success("hidden")
        captured = capsys.readouterr()
        assert "hidden" not in captured.out
        assert "hidden" not in captured.err

    def test_warn_suppressed(self, capsys: pytest.CaptureFixture[str]) -> None:
        """quiet=True suppresses warn()."""
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
        """raw_json with a dict outputs valid JSON."""
        out = Output()
        out.raw_json({"key": "value", "count": 42})
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data == {"key": "value", "count": 42}

    def test_list(self, capsys: pytest.CaptureFixture[str]) -> None:
        """raw_json with a list outputs valid JSON array."""
        out = Output()
        out.raw_json([1, 2, 3])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data == [1, 2, 3]

    def test_nested(self, capsys: pytest.CaptureFixture[str]) -> None:
        """raw_json handles nested structures."""
        out = Output()
        nested = {"modules": [{"name": "sale"}, {"name": "stock"}]}
        out.raw_json(nested)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert len(data["modules"]) == 2


# ---------------------------------------------------------------------------
# Tree output
# ---------------------------------------------------------------------------


class TestTreeJsonMode:
    """Output.tree() in JSON mode."""

    def test_tree_outputs_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        """tree() in JSON mode outputs nodes as JSON array."""
        out = Output(json_mode=True)
        nodes = [{"name": "root", "children": [{"name": "child"}]}]
        out.tree("Test Tree", nodes)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert isinstance(data, list)
        assert data[0]["name"] == "root"
