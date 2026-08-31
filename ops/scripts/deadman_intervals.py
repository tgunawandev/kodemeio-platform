#!/usr/bin/env python3
"""Derive a freshness threshold from a cron expression.

Split out from deadman-check.sh so the arithmetic is testable. The xyOps
watchdog computed this from trigger arrays; a cron string carries the same
information.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from croniter import croniter

WEEK_MINUTES = 7 * 24 * 60
GRACE_DIVISOR = 4
GRACE_FLOOR_MINUTES = 30


def interval_minutes(cron_expression: str) -> int:
    """Largest gap in minutes between consecutive firings, capped at a week.

    A job firing less often than weekly has no meaningful sub-week gap, so the
    whole cycle is returned. An unparseable expression also returns the full
    cycle: one bad schedule must not stop the watchdog checking the others,
    and a week-long threshold is the conservative choice -- it will still
    eventually alert, it just will not page immediately on a typo.
    """
    base = datetime(2026, 1, 5)  # a Monday, so weekday crons land predictably
    try:
        it = croniter(cron_expression, base)
        times = [it.get_next(datetime) for _ in range(12)]
    except (ValueError, KeyError, AttributeError):
        return WEEK_MINUTES

    gaps = [int((b - a).total_seconds() // 60) for a, b in zip(times, times[1:], strict=False)]
    if not gaps:
        return WEEK_MINUTES
    return min(max(gaps), WEEK_MINUTES)


def threshold_minutes(interval: int) -> int:
    """Interval plus a grace period of a quarter, with a 30-minute floor.

    The floor matters for frequent jobs: a quarter of a 1-minute interval is
    zero, which would alert on any run that started a few seconds late.
    """
    return interval + max(interval // GRACE_DIVISOR, GRACE_FLOOR_MINUTES)


def is_stale(cron_expression: str, last_started: datetime, now: datetime) -> bool:
    """True when the last run is older than the schedule's interval plus grace."""
    return now - last_started > timedelta(minutes=threshold_minutes(interval_minutes(cron_expression)))
