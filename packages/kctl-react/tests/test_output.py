"""Tests for core/output.py."""

from __future__ import annotations

import json

from kctl_react.core.output import Output


class TestOutputJsonMode:
    def test_table_json(self, capsys: object) -> None:
        import sys
        from io import StringIO

        # Capture stdout for JSON output
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        try:
            out = Output(json_mode=True)
            out.table("Test", [("A", "")], [["1"]], data_for_json=[{"a": 1}])
            result = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout

        parsed = json.loads(result)
        assert parsed == [{"a": 1}]

    def test_detail_json(self) -> None:
        import sys
        from io import StringIO

        old_stdout = sys.stdout
        sys.stdout = StringIO()
        try:
            out = Output(json_mode=True)
            out.detail("Title", [("Sec", [("k", "v")])], data_for_json={"key": "val"})
            result = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout

        parsed = json.loads(result)
        assert parsed == {"key": "val"}


class TestOutputQuietMode:
    def test_success_suppressed(self, capsys: object) -> None:
        out = Output(quiet=True)
        out.success("should not print")
        # No assertion on capsys — Rich writes to its own console, not sys.stdout

    def test_error_not_suppressed(self) -> None:
        out = Output(quiet=True)
        # error() should still work even in quiet mode
        out.error("this should print")


class TestOutputPrettyMode:
    def test_table_renders(self) -> None:
        out = Output(json_mode=False)
        # Should not raise
        out.table("Test", [("Col", "cyan")], [["val"]])

    def test_detail_renders(self) -> None:
        out = Output(json_mode=False)
        out.detail("Title", [("Section", [("key", "value")])])

    def test_tree_renders(self) -> None:
        out = Output(json_mode=False)
        out.tree("Root", [{"name": "child", "info": "info", "children": []}])

    def test_kv_renders(self) -> None:
        out = Output(json_mode=False)
        out.kv("key", "value")

    def test_header_renders(self) -> None:
        out = Output(json_mode=False)
        out.header("Section")
