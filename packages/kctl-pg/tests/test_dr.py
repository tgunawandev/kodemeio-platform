"""Tests for DR command group."""

from __future__ import annotations

from kctl_pg.commands.dr import (
    _check_style,
    _format_duration,
    _pretty_bytes,
    _rating_style,
    _rpo_rating,
    _rto_rating,
    _run_integrity_checks,
)
from tests.conftest import FakeClient


def test_check_style_pass():
    assert "[green]" in _check_style("pass")


def test_check_style_fail():
    assert "[red]" in _check_style("fail")


def test_check_style_warning():
    assert "[yellow]" in _check_style("warning")


def test_check_style_skip():
    assert "[dim]" in _check_style("skip")


def test_rating_style_pass():
    assert "[green]" in _rating_style("PASS")


def test_rating_style_critical():
    assert "[red]" in _rating_style("CRITICAL")


def test_format_duration_seconds():
    assert _format_duration(30) == "30s"


def test_format_duration_minutes():
    assert _format_duration(120) == "2.0m"


def test_format_duration_hours():
    assert _format_duration(7200) == "2.0h"


def test_format_duration_days():
    assert _format_duration(172800) == "2.0d"


def test_pretty_bytes_small():
    assert _pretty_bytes(500) == "500 bytes"


def test_pretty_bytes_kb():
    assert "kB" in _pretty_bytes(2048)


def test_pretty_bytes_mb():
    assert "MB" in _pretty_bytes(5 * 1024 * 1024)


def test_pretty_bytes_negative():
    assert _pretty_bytes(-1) == "0 bytes"


def test_rpo_rating_good():
    assert _rpo_rating(30) == "GOOD"


def test_rpo_rating_pass():
    assert _rpo_rating(120) == "PASS"


def test_rpo_rating_warning():
    assert _rpo_rating(1800) == "WARNING"


def test_rpo_rating_critical():
    assert _rpo_rating(7200) == "CRITICAL"


def test_rto_rating_good():
    assert _rto_rating(60) == "GOOD"


def test_rto_rating_critical():
    assert _rto_rating(10000) == "CRITICAL"


def test_integrity_checks_all_pass():
    client = FakeClient()
    client.add_result("SELECT 1", [{"v": 1}])
    client.add_result("pg_index", [{"count": 0}])
    client.add_result("pg_constraint", [{"count": 0}])
    client.add_result("pg_extension", [{"count": 3}])
    results = _run_integrity_checks(client)
    assert all(r["status"] in ("pass", "skip") for r in results)
    assert len(results) >= 3
