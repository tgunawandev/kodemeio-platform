#!/usr/bin/env python3
"""Repair the Odoo maintenance schedules in place.

Two bugs, both live since 2026-04-09 and both silent because Dokploy has no
failure alerting for scheduled jobs:

1. `serviceName: odoo` matches no compose service. The real services are
   odoo-web / odoo-cron / odoo-gevent. Dokploy resolves the container as
   {compose.appName}-{serviceName}-1, and an unmatched name yields an EMPTY
   string, so it ran `docker exec  bash -c ...` and Docker read `bash` as the
   container name.
2. `DELETE FROM ir_sessions` targets a table that does not exist. Odoo 18 runs
   the session_db server-wide module, whose table is
   http_sessions(sid, write_date, payload).
3. The command contains shell metacharacters. Dokploy passes a schedule's
   command to a shell WITHOUT escaping, so < > ( ) and ' all kill the run
   before it logs "Running command:", leaving a 22-byte log reading only
   "Initializing schedule". A date comparison needs <, an interval needs
   quotes and a function needs parens, so the session cleanup cannot be
   inline at all -- it moves into a script baked into the Odoo image.

Updates in place rather than delete-and-recreate: schedule IDs are preserved
and there is never a window where a schedule does not exist. `kctl-dokploy
schedules update` cannot do this -- it exposes no --service flag -- but the
schedule.update API accepts serviceName. That endpoint requires the full
record (scheduleId, name, cronExpression, command), so the current values are
read back and resent with the corrections applied.

Idempotent: a schedule already correct is left untouched.

Usage:
    uv run python ops/scripts/fix-odoo-schedules.py --profile idtpp --dry-run
    uv run python ops/scripts/fix-odoo-schedules.py --profile idtpp
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dokploy_api import api_post, list_composes, list_schedules, load_profile  # noqa: E402

BROKEN_SERVICE = "odoo"
FIXED_SERVICE = "odoo-cron"
BROKEN_TABLE = "ir_sessions"
FIXED_TABLE = "http_sessions"

# Dokploy runs `docker exec <container> bash -c '<command>'`, so a single quote
# in the command closes that wrapper early. bash dies with "unexpected EOF
# while looking for matching quote", the run is marked error, and the log
# contains only "Initializing schedule" -- no output at all. Dollar quoting is
# not a workaround: bash expands $$ to its own PID before psql sees it.
# Parentheses are ALSO fatal: verified by bisection on 2026-08-31, a command
# containing ( or ) fails before Dokploy logs its "Running command:" line at
# all. So make_interval(days => 7) is not a workaround either. CURRENT_DATE - 7
# has neither quotes nor parens.
# The session cleanup cannot be inline SQL at all: it needs a comparison (<),
# an interval (quotes) and a function (parens), and Dokploy passes all three
# through to a shell unescaped. It lives in the Odoo image instead.
# REQUIRES an image built at or after kodemeio-odoo c7581b9.
SESSION_CLEANUP_COMMAND = "bash /opt/odoo/scripts/session-cleanup.sh"


def corrections(schedule: dict) -> dict:
    """Return only the fields that need changing for this schedule."""
    out: dict = {}
    if schedule.get("serviceName") == BROKEN_SERVICE:
        out["serviceName"] = FIXED_SERVICE
    command = schedule.get("command", "")
    if "session-cleanup" in schedule.get("name", "") and command != SESSION_CLEANUP_COMMAND:
        out["command"] = SESSION_CLEANUP_COMMAND
    elif BROKEN_TABLE in command:
        out["command"] = command.replace(BROKEN_TABLE, FIXED_TABLE)
    return out


def build_payload(schedule: dict, fixes: dict) -> dict:
    """schedule.update requires the full record, not a partial patch."""
    payload = {
        "scheduleId": schedule["scheduleId"],
        "name": schedule["name"],
        "cronExpression": schedule["cronExpression"],
        "command": schedule.get("command", ""),
        "serviceName": schedule.get("serviceName"),
        "scheduleType": schedule.get("scheduleType", "compose"),
        "shellType": schedule.get("shellType", "bash"),
        "timezone": schedule.get("timezone"),
        "enabled": schedule.get("enabled", True),
        "composeId": schedule.get("composeId"),
    }
    payload.update(fixes)
    return {k: v for k, v in payload.items() if v is not None}


def main() -> int:
    ap = argparse.ArgumentParser(description="Repair broken Odoo schedules in place.")
    ap.add_argument("--profile", "-p", required=True)
    ap.add_argument("--dry-run", action="store_true", help="show what would change, change nothing")
    args = ap.parse_args()

    base_url, api_key = load_profile(args.profile)
    changed = skipped = failed = 0

    for comp in list_composes(base_url, api_key):
        for sched in list_schedules(base_url, api_key, comp["composeId"]):
            fixes = corrections(sched)
            if not fixes:
                continue
            label = f"{comp['name']}/{sched['name']}"
            detail = ", ".join(f"{k}: {sched.get(k)!r} -> {v!r}" for k, v in fixes.items())
            if args.dry_run:
                print(f"WOULD FIX {label}\n          {detail}")
                skipped += 1
                continue
            try:
                api_post(base_url, api_key, "/schedule.update", build_payload(sched, fixes))
                print(f"FIXED     {label}\n          {detail}")
                changed += 1
            except Exception as exc:  # noqa: BLE001 - report and continue the sweep
                print(f"FAILED    {label}: {exc}", file=sys.stderr)
                failed += 1

    if args.dry_run:
        print(f"\ndry run: {skipped} schedule(s) would be fixed")
        return 0
    print(f"\nfixed {changed}, failed {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
