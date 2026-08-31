"""Tests for ops/scripts/schedule-status.py.

The whole point of this script is to distinguish "the schedule exists" from
"the schedule works". 16 schedules existed and none worked for five months.
So `healthy` must be False for a schedule that has never run, and False for
one whose last run errored -- never merely "unknown".
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "ops" / "scripts" / "schedule-status.py"
_spec = importlib.util.spec_from_file_location("schedule_status", _SRC)
schedule_status = importlib.util.module_from_spec(_spec)
sys.modules["schedule_status"] = schedule_status
_spec.loader.exec_module(schedule_status)

SCHEDULE_REAL = {
    "scheduleId": "t8Z-S74jvMO7i9w9rTL2w",
    "name": "mac-odoo-erp-vacuum",
    "cronExpression": "0 4 * * 0",
    "serviceName": "odoo",
    "enabled": True,
}

# Captured from the live API on 2026-08-31.
RUNS_REAL = [
    {
        "deploymentId": "ubVo8wh3fUOLlH2n-bRU8",
        "title": "Schedule",
        "status": "error",
        "startedAt": "2026-08-29T21:00:01.220Z",
        "finishedAt": "2026-08-29T21:00:01.710Z",
        "errorMessage": None,
    },
    {
        "deploymentId": "aaaaaaaaaaaaaaaaaaaaa",
        "title": "Schedule",
        "status": "error",
        "startedAt": "2026-08-22T21:00:01.100Z",
        "finishedAt": "2026-08-22T21:00:01.600Z",
        "errorMessage": None,
    },
]


def test_all_error_runs_are_not_healthy():
    from schedule_status import summarize

    s = summarize(SCHEDULE_REAL, RUNS_REAL)
    assert s["total"] == 2
    assert s["ok"] == 0
    assert s["error"] == 2
    assert s["last_status"] == "error"
    assert s["healthy"] is False


def test_never_run_is_not_healthy():
    """dbg-v2/dbg-v3 exist and have zero runs. Absence of failure is not success."""
    from schedule_status import summarize

    s = summarize({**SCHEDULE_REAL, "name": "dbg-v2"}, [])
    assert s["total"] == 0
    assert s["last_status"] is None
    assert s["healthy"] is False


def test_last_run_done_is_healthy():
    from schedule_status import summarize

    runs = [{"status": "done", "startedAt": "2026-08-31T21:00:00.000Z"}, *RUNS_REAL]
    s = summarize(SCHEDULE_REAL, runs)
    assert s["ok"] == 1
    assert s["last_status"] == "done"
    assert s["healthy"] is True


def test_disabled_schedule_is_not_reported_healthy():
    """A disabled schedule is not a passing schedule; it is simply not running."""
    from schedule_status import summarize

    s = summarize({**SCHEDULE_REAL, "enabled": False}, [{"status": "done", "startedAt": "x"}])
    assert s["healthy"] is False


def test_runs_are_ordered_newest_first_by_started_at():
    """The API returns newest first, but do not rely on it -- sort explicitly."""
    from schedule_status import summarize

    older = {"status": "error", "startedAt": "2026-08-01T00:00:00.000Z"}
    newer = {"status": "done", "startedAt": "2026-08-30T00:00:00.000Z"}
    s = summarize(SCHEDULE_REAL, [older, newer])
    assert s["last_status"] == "done"
    assert s["last_started"] == "2026-08-30T00:00:00.000Z"


# --- Shape of /project.all --------------------------------------------------
# Composes are nested project -> environments[] -> compose[]. Reading
# project["compose"] directly returns an empty list and NO error, which made
# this script report "All 0 schedule(s) healthy" against an estate with 18
# schedules. Captured from the live API on 2026-08-31.
PROJECT_ALL_REAL = [
    {
        "projectId": "p1",
        "name": "tpp",
        "projectTags": [],
        "environments": [
            {
                "environmentId": "e1",
                "isDefault": True,
                "applications": [],
                "compose": [
                    {"composeId": "Qki8U2u4Ltstq0_6zW7UE", "name": "tpp-odoo-erp"},
                    {"composeId": "2iEl8DzSWOMFOClweOhiZ", "name": "tpp-infra-postgres"},
                ],
            },
            {"environmentId": "e2", "isDefault": False, "applications": [], "compose": []},
        ],
    }
]


def test_flatten_composes_walks_environments():
    from schedule_status import flatten_composes

    out = flatten_composes(PROJECT_ALL_REAL)
    assert [c["name"] for c in out] == ["tpp-odoo-erp", "tpp-infra-postgres"]
    assert out[0]["composeId"] == "Qki8U2u4Ltstq0_6zW7UE"
    assert out[0]["project"] == "tpp"


def test_flatten_composes_does_not_read_project_level_compose():
    """The old bug: project['compose'] is absent, so this must not silently pass."""
    from schedule_status import flatten_composes

    assert flatten_composes([{"name": "x", "compose": [{"composeId": "nope", "name": "wrong"}]}]) == []


def test_flatten_composes_tolerates_missing_keys():
    from schedule_status import flatten_composes

    assert flatten_composes([]) == []
    assert flatten_composes([{"name": "x"}]) == []
    assert flatten_composes([{"name": "x", "environments": [{}]}]) == []
