"""Every tpp-infra-kctl schedule command must be a bare `jobrun <name>`.

Dokploy passes a schedule's command to a shell WITHOUT escaping. A command
containing ' ( ) < > | & ; $ or a backtick dies before Dokploy logs its
"Running command:" line, leaving a 22-byte log reading only "Initializing
schedule" -- and no alert, because Dokploy has no failure notification for
scheduled jobs. Established by single-character bisection on 2026-08-31:

    psql ... -tAc "SELECT 1 WHERE 1 = 1"   -> status: done
    psql ... -tAc "SELECT 1 WHERE 1 < 2"   -> status: error
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

MANIFEST = Path(__file__).resolve().parents[1] / "instances" / "production" / "tpp-infra-kctl.yaml"
FORBIDDEN = ["'", "(", ")", "<", ">", "|", "&", ";", "$", "`"]


def _schedules() -> list[dict]:
    return yaml.safe_load(MANIFEST.read_text()).get("schedules") or []


def test_manifest_declares_schedules():
    assert _schedules(), "tpp-infra-kctl declares no schedules — the migration would be a no-op"


def test_every_command_is_a_bare_jobrun_invocation():
    for sched in _schedules():
        assert re.fullmatch(r"jobrun [a-z0-9-]+", sched["command"]), (
            f"{sched['name']}: command must be exactly `jobrun <name>`; arguments "
            f"belong in the job script. Got: {sched['command']!r}"
        )


def test_no_command_contains_shell_metacharacters():
    for sched in _schedules():
        found = [c for c in FORBIDDEN if c in sched["command"]]
        assert not found, f"{sched['name']}: contains {found}, which Dokploy mangles silently"


def test_job_name_matches_schedule_name():
    """A typo resolves to a missing script. jobrun exits 2, but catch it here first."""
    for sched in _schedules():
        assert sched["command"] == f"jobrun {sched['name']}", (
            f"{sched['name']}: command invokes a different job: {sched['command']!r}"
        )


def test_every_schedule_targets_the_kctl_service_in_jakarta_time():
    for sched in _schedules():
        assert sched["service"] == "kctl", f"{sched['name']}: must target the kctl service"
        assert sched["timezone"] == "Asia/Jakarta", f"{sched['name']}: timezone must be explicit"


def test_alarms_run_before_the_morning_reports():
    """A stale backup must be known before the business report goes out."""
    by_name = {s["name"]: s["cron"] for s in _schedules()}
    for alarm in ("backup-tpp", "backup-tpp25", "backup-mac", "backup-mac-hrms"):
        if alarm not in by_name:
            continue
        minute, hour = by_name[alarm].split()[:2]
        assert int(hour) < 6 or (int(hour) == 6 and int(minute) < 50), (
            f"{alarm} at {by_name[alarm]} runs at or after the 06:50 report canary"
        )
