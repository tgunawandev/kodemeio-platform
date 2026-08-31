"""The watchdog's freshness threshold comes from the cron expression.

Getting this wrong ruins the watchdog in either direction: too tight and it
pages constantly until people mute it; too loose and a dead job stays dead.
Both failure modes end the same way -- nobody reads the alerts.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import UTC
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "ops" / "scripts" / "deadman_intervals.py"
_spec = importlib.util.spec_from_file_location("deadman_intervals", _SRC)
deadman_intervals = importlib.util.module_from_spec(_spec)
sys.modules["deadman_intervals"] = deadman_intervals
_spec.loader.exec_module(deadman_intervals)


def test_daily_cron_is_one_day():
    from deadman_intervals import interval_minutes

    assert interval_minutes("0 5 * * *") == 1440
    assert interval_minutes("0 7 * * *") == 1440


def test_weekly_monday_cron_is_one_week():
    from deadman_intervals import interval_minutes

    assert interval_minutes("0 8 * * 1") == 10080


def test_weekly_sunday_cron_is_one_week():
    from deadman_intervals import interval_minutes

    assert interval_minutes("0 3 * * 0") == 10080


def test_every_minute_cron_is_one_minute():
    """The estate had two of these failing every minute for 146 days."""
    from deadman_intervals import interval_minutes

    assert interval_minutes("* * * * *") == 1


def test_grace_is_a_quarter_with_a_thirty_minute_floor():
    from deadman_intervals import threshold_minutes

    assert threshold_minutes(1440) == 1440 + 360
    assert threshold_minutes(10080) == 10080 + 2520
    assert threshold_minutes(60) == 60 + 30  # a quarter would be 15, below the floor
    assert threshold_minutes(1) == 1 + 30


def test_unparseable_cron_does_not_crash_the_sweep():
    """One bad expression must not stop the watchdog checking everything else."""
    from deadman_intervals import interval_minutes

    assert interval_minutes("not a cron") == 10080


def test_is_stale_uses_interval_plus_grace():
    from datetime import datetime, timedelta

    from deadman_intervals import is_stale

    now = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)
    # Daily job: threshold is 1440 + 360 = 1800 minutes.
    assert not is_stale("0 5 * * *", now - timedelta(minutes=1799), now)
    assert is_stale("0 5 * * *", now - timedelta(minutes=1801), now)
