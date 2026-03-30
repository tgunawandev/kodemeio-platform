"""Tests for output handler."""

from __future__ import annotations

import json

from kctl_claw.core.output import Output


def test_table_json_mode(capsys):
    out = Output(json_mode=True)
    out.table(
        "Test",
        [("Name", ""), ("Status", "")],
        [["foo", "ok"], ["bar", "fail"]],
    )
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert len(data) == 2
    assert data[0]["name"] == "foo"
    assert data[1]["status"] == "fail"


def test_table_json_with_explicit_data(capsys):
    out = Output(json_mode=True)
    out.table(
        "Test",
        [("Name", "")],
        [["foo"]],
        data_for_json=[{"custom": "value"}],
    )
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data == [{"custom": "value"}]


def test_table_csv_mode(capsys):
    out = Output(format="csv")
    out.table(
        "Test",
        [("Name", ""), ("Status", "")],
        [["foo", "[green]ok[/green]"]],
    )
    captured = capsys.readouterr()
    lines = [line.strip() for line in captured.out.strip().split("\n")]
    assert lines[0] == "Name,Status"
    assert lines[1] == "foo,ok"  # Rich markup stripped


def test_detail_json_mode(capsys):
    out = Output(json_mode=True)
    out.detail("Test", [("Section", [("key", "value")])], data_for_json={"key": "value"})
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data == {"key": "value"}


def test_success_message(capsys):
    out = Output()
    out.success("Done")
    # Pretty mode prints to console (not captured by capsys easily)
    # Just verify it doesn't raise


def test_quiet_suppresses_info(capsys):
    out = Output(quiet=True)
    out.info("Should be hidden")
    # No output expected


def test_error_always_prints(capsys):
    out = Output(quiet=True)
    out.error("Problem")
    # Error should always print to stderr
