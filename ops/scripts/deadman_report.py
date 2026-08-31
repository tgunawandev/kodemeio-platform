#!/usr/bin/env python3
"""Turn a schedule-status snapshot into watchdog problems and notes.

Reads the JSON from `schedule-status.py --json` on stdin or the SCHEDULES
environment variable, and emits {"problems": [...], "notes": [...]}.

Kept separate from deadman-check.sh so the classification is testable and so
the shell script contains no nested heredocs -- which is how quoting bugs get
introduced into exactly the kind of script that must never fail quietly.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, date, datetime
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from deadman_intervals import interval_minutes, threshold_minutes  # noqa: E402

ACKS_PATH = Path(__file__).resolve().parent / "deadman-acks.yaml"


def load_acks(today: date, path: Path = ACKS_PATH) -> dict[str, str]:
    """Return {schedule_name: reason} for acks that have NOT expired.

    An ack without a valid future `expires` is ignored, so a suppression can
    never silently outlive its deadline. That is the whole point: the estate's
    original incident was a watchdog-shaped hole, and an ack list with no
    expiry would quietly reopen it.
    """
    if not path.exists():
        return {}
    doc = yaml.safe_load(path.read_text()) or {}
    live: dict[str, str] = {}
    for entry in doc.get("acks") or []:
        name = entry.get("name")
        expires = entry.get("expires")
        if not name or not isinstance(expires, date):
            continue
        if expires >= today:
            live[name] = entry.get("reason", "acknowledged")
    return live


def classify(rows: list[dict], now: datetime, acks: dict[str, str] | None = None) -> dict[str, list[str]]:
    """Sort schedules into alertable problems and non-alertable notes.

    A DISABLED schedule is a note, never a problem. A watchdog that pages for
    jobs nobody expects to run is one people learn to ignore -- and the estate
    already carries deliberately-disabled schedules.
    """
    problems: list[str] = []
    notes: list[str] = []
    acks = acks if acks is not None else {}

    for r in rows:
        label = f"{r.get('app', '?')}/{r.get('name', '?')}"

        if not r.get("enabled"):
            notes.append(f"{label} is disabled -- freshness check skipped.")
            continue

        if not r.get("total"):
            problems.append(f"NO RUNS: {label} is enabled but has never run.")
            continue

        last_status = r.get("last_status")
        if last_status == "running":
            notes.append(f"{label} is currently running -- not judged this pass.")
            continue

        if last_status != "done":
            problems.append(f"FAILED: {label} most recent run status is {last_status!r}, not 'done'.")
            continue

        started_raw = r.get("last_started")
        if not started_raw:
            problems.append(f"NO TIMESTAMP: {label} reports a completed run with no start time.")
            continue

        started = datetime.fromisoformat(str(started_raw).replace("Z", "+00:00"))
        age = int((now - started).total_seconds() // 60)
        threshold = threshold_minutes(interval_minutes(r.get("cron", "")))
        if age > threshold:
            problems.append(
                f"STALE: {label} last ran {age}m ago; cron {r.get('cron')!r} expects a run "
                f"within {threshold}m (interval plus grace)."
            )

    kept: list[str] = []
    for p in problems:
        name = p.split("/", 1)[1].split(" ", 1)[0] if "/" in p else ""
        if name in acks:
            notes.append(f"{name} problem suppressed by ack: {acks[name]}")
        else:
            kept.append(p)
    return {"problems": kept, "notes": notes}


def main() -> int:
    raw = os.environ.get("SCHEDULES") or sys.stdin.read()
    try:
        rows = json.loads(raw)
    except json.JSONDecodeError:
        print(json.dumps({"problems": ["UNREADABLE: schedule-status produced no valid JSON."], "notes": []}))
        return 0
    now = datetime.now(UTC)
    print(json.dumps(classify(rows, now, load_acks(now.date()))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
