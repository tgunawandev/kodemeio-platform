#!/usr/bin/env python3
"""Report the REAL health of every Dokploy schedule.

Why this exists rather than `kctl-dokploy schedules history`: that command
reads `executionLogs` off `schedule.one`, which carries no run history at all,
so it reports "No execution history" for every schedule -- including ones with
11 recorded runs. `kctl-dokploy deployments by-type` is also unusable: it never
sends the API's required `id` parameter and always returns HTTP 400.

Run history actually lives at
    GET /deployment.allByType?id=<scheduleId>&type=schedule
Each row carries status ("done"|"error"), startedAt, finishedAt, errorMessage
and logPath. Roughly the last 11 runs are retained.

Exit code is 1 if any ENABLED schedule is unhealthy, so this works as a CI gate
and as a cron check.

Usage:
    uv run python ops/scripts/schedule-status.py --profile <profile>
    uv run python ops/scripts/schedule-status.py --profile <profile> --json
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dokploy_api import list_composes, list_runs, list_schedules, load_profile  # noqa: E402


def summarize(schedule: dict, runs: list[dict]) -> dict:
    """Reduce one schedule plus its run rows to a health verdict.

    `healthy` is deliberately strict: an enabled schedule that has never run is
    NOT healthy. Sixteen schedules "existed" for five months while doing
    nothing, so absence of evidence is treated as failure, not as unknown.
    """
    ordered = sorted(runs, key=lambda r: r.get("startedAt") or "", reverse=True)
    statuses = [r.get("status") for r in ordered]
    last = ordered[0] if ordered else {}
    enabled = bool(schedule.get("enabled"))
    last_status = last.get("status")
    return {
        "name": schedule.get("name", ""),
        "schedule_id": schedule.get("scheduleId", ""),
        "enabled": enabled,
        "service": schedule.get("serviceName"),
        "cron": schedule.get("cronExpression", ""),
        "total": len(ordered),
        "ok": statuses.count("done"),
        "error": statuses.count("error"),
        "last_status": last_status,
        "last_started": last.get("startedAt"),
        "healthy": bool(enabled and ordered and last_status == "done"),
    }


def collect(profile: str) -> list[dict]:
    """Summarize every compose schedule the profile can see."""
    base_url, api_key = load_profile(profile)
    out: list[dict] = []
    for comp in list_composes(base_url, api_key):
        try:
            schedules = list_schedules(base_url, api_key, comp["composeId"])
        except (urllib.error.URLError, ValueError):
            # One unreadable app must not abort the whole sweep.
            continue
        for sched in schedules:
            try:
                runs = list_runs(base_url, api_key, sched["scheduleId"])
            except (urllib.error.URLError, ValueError):
                runs = []
            row = summarize(sched, runs)
            row["app"] = comp["name"]
            out.append(row)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Report real Dokploy schedule health.")
    ap.add_argument("--profile", "-p", required=True, help="kctl profile, e.g. idtpp")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of a table")
    args = ap.parse_args()

    rows = collect(args.profile)
    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        print(f"{'app':<22}{'schedule':<34}{'svc':<12}{'runs':<6}{'ok':<4}{'err':<5}{'last':<8}healthy")
        print("-" * 104)
        for r in sorted(rows, key=lambda x: (x["healthy"], x["app"])):
            print(
                f"{r['app']:<22}{r['name']:<34}{str(r['service']):<12}"
                f"{r['total']:<6}{r['ok']:<4}{r['error']:<5}{str(r['last_status']):<8}{r['healthy']}"
            )
    # An empty result is a BUG, not a clean bill of health. This estate has
    # schedules; finding none means the API shape changed or the credentials
    # are wrong. Reporting "All 0 healthy" and exiting 0 would be exactly the
    # silent-nothing failure this script exists to catch.
    if not rows:
        print("\nFOUND NO SCHEDULES AT ALL -- treating as failure, not as health.", file=sys.stderr)
        print("Check the profile, the API key, and the /project.all response shape.", file=sys.stderr)
        return 1

    unhealthy = [r for r in rows if r["enabled"] and not r["healthy"]]
    if unhealthy:
        print(f"\n{len(unhealthy)} of {len(rows)} enabled schedule(s) NOT healthy", file=sys.stderr)
        return 1
    print(f"\nAll {len(rows)} schedule(s) healthy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
