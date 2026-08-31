"""What the watchdog pages for, and what it deliberately stays quiet about.

The quiet cases matter as much as the loud ones. A watchdog that pages for
schedules nobody expects to run is one people mute -- and a muted watchdog is
how 16 schedules failed for five months unnoticed.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

_OPS = Path(__file__).resolve().parents[2] / "ops" / "scripts"
sys.path.insert(0, str(_OPS))
_spec = importlib.util.spec_from_file_location("deadman_report", _OPS / "deadman_report.py")
deadman_report = importlib.util.module_from_spec(_spec)
sys.modules["deadman_report"] = deadman_report
_spec.loader.exec_module(deadman_report)

NOW = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)


def _row(**kw) -> dict:
    base = {
        "app": "tpp-infra-kctl",
        "name": "backup-tpp",
        "enabled": True,
        "total": 3,
        "last_status": "done",
        "last_started": (NOW - timedelta(minutes=60)).isoformat().replace("+00:00", "Z"),
        "cron": "0 5 * * *",
    }
    base.update(kw)
    return base


def test_healthy_recent_run_is_silent():
    out = deadman_report.classify([_row()], NOW)
    assert out["problems"] == []


def test_disabled_schedule_is_a_note_never_a_problem():
    out = deadman_report.classify([_row(enabled=False)], NOW)
    assert out["problems"] == []
    assert any("disabled" in n for n in out["notes"])


def test_enabled_but_never_run_is_a_problem():
    """dbg-v2/dbg-v3 existed with zero runs. Absence of failure is not success."""
    out = deadman_report.classify([_row(total=0)], NOW)
    assert any("NO RUNS" in p for p in out["problems"])


def test_last_run_errored_is_a_problem():
    out = deadman_report.classify([_row(last_status="error")], NOW)
    assert any("FAILED" in p for p in out["problems"])


def test_stale_run_is_a_problem():
    old = (NOW - timedelta(minutes=5000)).isoformat().replace("+00:00", "Z")
    out = deadman_report.classify([_row(last_started=old)], NOW)
    assert any("STALE" in p for p in out["problems"])


def test_currently_running_is_not_judged():
    """A long report mid-flight must not be paged as a failure."""
    out = deadman_report.classify([_row(last_status="running")], NOW)
    assert out["problems"] == []
    assert any("currently running" in n for n in out["notes"])


def test_completed_run_with_no_timestamp_is_a_problem():
    out = deadman_report.classify([_row(last_started=None)], NOW)
    assert any("NO TIMESTAMP" in p for p in out["problems"])


def test_weekly_job_is_not_stale_after_two_days():
    """A Monday-only report must not page on Wednesday."""
    two_days = (NOW - timedelta(days=2)).isoformat().replace("+00:00", "Z")
    out = deadman_report.classify([_row(cron="0 8 * * 1", last_started=two_days)], NOW)
    assert out["problems"] == []


# --- Acknowledgements ------------------------------------------------------
# Acks stop the watchdog paging daily about problems that are already tracked.
# The expiry is the safety catch: suppression without a deadline is how a
# watchdog quietly becomes decorative.


def _acks_file(tmp_path, body: str):
    p = tmp_path / "acks.yaml"
    p.write_text(body)
    return p


def test_unexpired_ack_is_loaded(tmp_path):
    from datetime import date

    p = _acks_file(tmp_path, "acks:\n  - name: foo\n    reason: tracked\n    expires: 2026-12-31\n")
    acks = deadman_report.load_acks(date(2026, 8, 31), p)
    assert acks == {"foo": "tracked"}


def test_expired_ack_is_ignored(tmp_path):
    """On the day after it expires, the schedule pages again — no exceptions."""
    from datetime import date

    p = _acks_file(tmp_path, "acks:\n  - name: foo\n    reason: tracked\n    expires: 2026-08-30\n")
    assert deadman_report.load_acks(date(2026, 8, 31), p) == {}


def test_ack_expiring_today_is_still_live(tmp_path):
    from datetime import date

    p = _acks_file(tmp_path, "acks:\n  - name: foo\n    reason: tracked\n    expires: 2026-08-31\n")
    assert deadman_report.load_acks(date(2026, 8, 31), p) == {"foo": "tracked"}


def test_ack_without_an_expiry_is_ignored(tmp_path):
    """A permanent suppression must be impossible to write by accident."""
    from datetime import date

    p = _acks_file(tmp_path, "acks:\n  - name: foo\n    reason: forever\n")
    assert deadman_report.load_acks(date(2026, 8, 31), p) == {}


def test_ack_with_a_non_date_expiry_is_ignored(tmp_path):
    from datetime import date

    p = _acks_file(tmp_path, 'acks:\n  - name: foo\n    reason: oops\n    expires: "soon"\n')
    assert deadman_report.load_acks(date(2026, 8, 31), p) == {}


def test_missing_acks_file_is_not_an_error(tmp_path):
    from datetime import date

    assert deadman_report.load_acks(date(2026, 8, 31), tmp_path / "nope.yaml") == {}


def test_acked_failure_becomes_a_note_not_a_problem():
    out = deadman_report.classify([_row(last_status="error")], NOW, {"backup-tpp": "tracked elsewhere"})
    assert out["problems"] == []
    assert any("suppressed by ack" in n for n in out["notes"])


def test_unacked_failure_still_pages_alongside_an_acked_one():
    rows = [_row(name="backup-tpp", last_status="error"), _row(name="backup-mac", last_status="error")]
    out = deadman_report.classify(rows, NOW, {"backup-tpp": "tracked"})
    assert len(out["problems"]) == 1
    assert "backup-mac" in out["problems"][0]


def test_shipped_acks_file_has_an_expiry_on_every_entry():
    """Guards the real file, not a fixture: no entry may lack a date."""
    from datetime import date as _date

    import yaml

    doc = yaml.safe_load(deadman_report.ACKS_PATH.read_text())
    for entry in doc["acks"]:
        assert isinstance(entry.get("expires"), _date), f"{entry.get('name')} has no valid expires date"
        assert entry.get("reason"), f"{entry.get('name')} has no reason"
