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
import urllib.parse
import urllib.request
from pathlib import Path

import yaml

CONFIG_PATH = Path.home() / ".config" / "kodemeio" / "config.yaml"

# Dokploy sits behind Cloudflare, which rejects the default Python-urllib user
# agent with "error code: 1010" before the request ever reaches Dokploy. Any
# ordinary browser UA passes. Without this every call 403s and the script would
# report a healthy-looking empty estate.
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"


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


def load_profile(profile: str) -> tuple[str, str]:
    """Return (base_url, api_key) for a profile from the shared kctl config."""
    cfg = yaml.safe_load(CONFIG_PATH.read_text()) or {}
    try:
        block = cfg["profiles"][profile]["dokploy"]
    except KeyError as exc:
        raise SystemExit(f"profile {profile!r} has no dokploy block in {CONFIG_PATH}") from exc
    url = str(block.get("url", "")).rstrip("/")
    key = str(block.get("api_key", ""))
    if not url or not key:
        raise SystemExit(f"profile {profile!r} is missing dokploy url or api_key")
    return url, key


def api_get(base_url: str, api_key: str, path: str, params: dict | None = None) -> object:
    """GET one Dokploy API endpoint, returning decoded JSON."""
    qs = f"?{urllib.parse.urlencode(params)}" if params else ""
    req = urllib.request.Request(
        f"{base_url}/api{path}{qs}",
        headers={"x-api-key": api_key, "User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 - fixed https host from config
        return json.load(resp)


def flatten_composes(projects: list[dict]) -> list[dict]:
    """Flatten compose services out of the /project.all tree.

    There is no /compose.all endpoint. Composes are nested TWO levels deep:
    project -> environments[] -> compose[]. Reading project["compose"] directly
    yields an empty list and no error, which made this script cheerfully report
    "All 0 schedule(s) healthy" -- the same shape of silent nothing it exists
    to detect.
    """
    out: list[dict] = []
    for project in projects if isinstance(projects, list) else []:
        for env in project.get("environments") or []:
            for comp in env.get("compose") or []:
                if comp.get("composeId"):
                    out.append(
                        {
                            "composeId": comp["composeId"],
                            "name": comp.get("name", ""),
                            "project": project.get("name", ""),
                        }
                    )
    return out


def list_composes(base_url: str, api_key: str) -> list[dict]:
    """Every compose service the profile can see."""
    return flatten_composes(api_get(base_url, api_key, "/project.all"))


def collect(profile: str) -> list[dict]:
    """Summarize every compose schedule the profile can see."""
    base_url, api_key = load_profile(profile)
    out: list[dict] = []
    for comp in list_composes(base_url, api_key):
        try:
            schedules = api_get(
                base_url, api_key, "/schedule.list", {"id": comp["composeId"], "scheduleType": "compose"}
            )
        except (urllib.error.URLError, ValueError):
            # One unreadable app must not abort the whole sweep.
            continue
        for s in schedules if isinstance(schedules, list) else []:
            try:
                runs = api_get(base_url, api_key, "/deployment.allByType", {"id": s["scheduleId"], "type": "schedule"})
            except (urllib.error.URLError, ValueError):
                runs = []
            row = summarize(s, runs if isinstance(runs, list) else [])
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
