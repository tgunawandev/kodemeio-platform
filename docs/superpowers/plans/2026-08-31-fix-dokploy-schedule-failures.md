# Fix Dokploy Schedule Failures Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every existing Dokploy schedule either work and be provably green, or be deleted — and build the tool that proves it.

**Architecture:** Add `ops/scripts/schedule-status.py`, which reads real run
history from `GET /deployment.allByType?id=<scheduleId>&type=schedule` (the
only endpoint that has it). Fix the two bugs in `deploys/bases/odoo.yaml` that
made 14 schedules fail 100% of the time, recreate those schedules against the
corrected values, delete four debris schedules, and create schedules for three
production Odoo apps that have none.

**Tech Stack:** Python 3.12, `uv`, `pytest`, `ruff`, `kctl-dokploy` 0.16.6, `just`

**Spec:** `docs/superpowers/specs/2026-08-31-xyops-to-dokploy-schedules-design.md` (§3.3, §3.4)

## Global Constraints

- Always pass an explicit `kctl-dokploy` profile. Everything here uses `-p idtpp`.
- Python tooling is `uv`, never pip. `pytest` for tests, `ruff` for lint.
- Never commit real `.env` files, credentials, or secrets. Never echo a secret
  to the terminal or into a commit message.
- Conventional Commits, ending with `Co-Authored-By: Claude <noreply@anthropic.com>`.
- Never stop or remove the `dokploy` or `traefik` platform containers.
- Local quality gate is `just check` (test + lint + fmt-check + terraform-validate).
- Repo line length is 120; ruff lint selects `E,F,I,W,UP,B,SIM`.
- **A schedule is "working" only when a real run reports `status: done`.**
  Successful creation proves nothing — that misreading is what hid this
  incident for five months.

## Background: what is actually broken

Verified on 2026-08-31 against live `dokploy.idtpp.com`.

18 schedules exist. 16 have never once succeeded (~160 runs, zero `done`),
going back to 2026-04-09. Nothing reported it, because Dokploy has no
failure alerting for scheduled jobs — see spec §3.1 G1.

**Bug 1 — wrong service name (14 schedules).** `deploys/bases/odoo.yaml`
declares `service: odoo`. The real compose services are `odoo-web`,
`odoo-cron`, `odoo-gevent`. Dokploy resolves the container as
`{compose.appName}-{serviceName}-1`; an unmatched name yields an empty string,
so it runs `docker exec  bash -c '...'` and Docker reads `bash` as the
container name:

```
Running command: docker exec  bash -c 'vacuumdb -U odoo -d mac_odoo_erp --analyze'
Error response from daemon: No such container: bash
```

The same manifests already use `service: odoo-web` correctly for their `domain`
block, which is how the mismatch survived review.

**Bug 2 — wrong table name (7 of those 14).** `session-cleanup` runs
`DELETE FROM ir_sessions`, but no such table exists. Odoo 18 here runs the
`session_db` server-wide module, whose table is
`http_sessions (sid, write_date, payload)`. Fixing Bug 1 alone changes the
error from "no such container" to "relation does not exist".

**Impact is low; the mechanism is the problem.** Measured on `mac_odoo_erp`:
autovacuum covers the missing vacuum job (159 of 1387 user tables autovacuumed,
most recent 2026-08-31), and `http_sessions` holds 31 rows / 688 kB. Nothing
grew unbounded. Treat this as important, not urgent.

**Debris (4 schedules).** `reset-akadmin-pw` and `create-authentik-db` are
`* * * * *`, created 2026-04-07, failing every minute since — on the order of
210,000 firings each. `dbg-v2` and `dbg-v3` (created 2026-04-30, cron
`0 0 31 12 0`) have never run. All four are leftovers.

> **Credential exposure.** The command strings of `reset-akadmin-pw` and
> `create-authentik-db` contain **plaintext passwords** (an Authentik admin
> password and an Authentik database password). They are stored unencrypted in
> Dokploy's database and returned by the API to any caller with an API key.
> Deleting the schedules removes the exposure going forward but does not undo
> it — both credentials must be rotated. Handled in Task 4.

**Coverage gap (3 apps).** `tpp-odoo-erp`, `tpp-odoo-hrms`, and `tpp25-odoo-erp`
— all production — have **no schedules at all**. `phase_schedules` only creates
schedules during a deploy and skips names that already exist; it never
backfills apps deployed before the base gained its `schedules:` block. Handled
in Task 5.

---

### Task 1: `schedule-status.py` — the tool that shows the truth

Build this first: every later task's verification depends on it, and
`kctl-dokploy schedules history` cannot be used (it reads `schedule.one`, which
carries no run history, and so reports "No execution history" for every
schedule — spec §3.4 item 1).

**Files:**
- Create: `ops/scripts/schedule-status.py`
- Test: `deploys/tests/test_schedule_status.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `summarize(schedule: dict, runs: list[dict]) -> dict` returning keys
    `name: str`, `schedule_id: str`, `enabled: bool`, `service: str | None`,
    `cron: str`, `total: int`, `ok: int`, `error: int`, `last_status: str | None`,
    `last_started: str | None`, `healthy: bool`.
    `healthy` is `True` only when `enabled` is True, `total > 0`, and
    `last_status == "done"`.
  - CLI: `uv run python ops/scripts/schedule-status.py --profile idtpp [--json]`,
    exiting `1` if any enabled schedule is not healthy, else `0`.

- [ ] **Step 1: Write the failing test**

Create `deploys/tests/test_schedule_status.py`. The `RUNS_REAL` fixture below is
a real `/deployment.allByType?id=t8Z-S74jvMO7i9w9rTL2w&type=schedule` row
captured on 2026-08-31, trimmed to the fields used — do not invent a different
shape, because a mock that does not match the API is how a green test suite
certifies nothing.

```python
"""Tests for ops/scripts/schedule-status.py.

The whole point of this script is to distinguish "the schedule exists" from
"the schedule works". 16 schedules existed and none worked for five months.
So `healthy` must be False for a schedule that has never run, and False for
one whose last run errored -- never merely "unknown".
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ops" / "scripts"))

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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest deploys/tests/test_schedule_status.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'schedule_status'`

- [ ] **Step 3: Write the implementation**

Create `ops/scripts/schedule-status.py`. Note the filename uses a hyphen (matching
`check-env-parity.py` and `verify-backups.py` in this directory) while the test
imports `schedule_status`; add the symlink-free shim in Step 4 — for now write
the module so `summarize` is importable and the CLI works.

```python
#!/usr/bin/env python3
"""Report the REAL health of every Dokploy schedule.

`kctl-dokploy schedules history` cannot be used: it reads `executionLogs` off
`schedule.one`, which carries no run history at all, so it reports "No
execution history" for every schedule -- including ones with 11 recorded runs.

Run history lives at GET /deployment.allByType?id=<scheduleId>&type=schedule.
Each row has status ("done"|"error"), startedAt, finishedAt, errorMessage and
logPath. Roughly the last 11 runs are retained.

Exit code is 1 if any ENABLED schedule is unhealthy, so this is usable as a
CI gate and as a cron check.
"""

from __future__ import annotations

import argparse
import json
import sys

from kctl_dokploy.core.client import DokployClient
from kctl_dokploy.core.config import _get_service_config


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


def _client(profile: str) -> DokployClient:
    cfg = _get_service_config(profile, "dokploy")
    return DokployClient(base_url=cfg["url"].rstrip("/") + "/api", api_key=cfg.get("api_key", ""))


def collect(profile: str) -> list[dict]:
    """Summarize every compose schedule the profile can see."""
    c = _client(profile)
    out: list[dict] = []
    for comp in c.get("/compose.allByProjects") or []:
        cid = comp.get("composeId")
        if not cid:
            continue
        try:
            schedules = c.get("/schedule.list", params={"id": cid, "scheduleType": "compose"}) or []
        except Exception:  # noqa: BLE001 - an unreadable app must not abort the whole sweep
            continue
        for s in schedules:
            try:
                runs = c.get("/deployment.allByType", params={"id": s["scheduleId"], "type": "schedule"}) or []
            except Exception:  # noqa: BLE001
                runs = []
            row = summarize(s, runs)
            row["app"] = comp.get("name", "")
            out.append(row)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
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
    unhealthy = [r for r in rows if r["enabled"] and not r["healthy"]]
    if unhealthy:
        print(f"\n{len(unhealthy)} enabled schedule(s) NOT healthy", file=sys.stderr)
        return 1
    print(f"\nAll {len(rows)} schedule(s) healthy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Make the hyphenated filename importable by the test**

`ops/scripts/` uses hyphens, which are not importable. Add a loader to the test
file's import path instead of renaming the script (renaming would break the
`justfile` convention used by `check-env-parity.py` and `verify-backups.py`).

Replace the `sys.path.insert` block at the top of
`deploys/tests/test_schedule_status.py` with:

```python
import importlib.util
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "ops" / "scripts" / "schedule-status.py"
_spec = importlib.util.spec_from_file_location("schedule_status", _SRC)
schedule_status = importlib.util.module_from_spec(_spec)
sys.modules["schedule_status"] = schedule_status
_spec.loader.exec_module(schedule_status)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest deploys/tests/test_schedule_status.py -q`
Expected: PASS, 5 passed

- [ ] **Step 6: Verify the endpoint name against the live API**

`collect()` calls `/compose.allByProjects`. Confirm that path exists before
trusting it; if it does not, find the correct one and fix `collect()`.

Run:
```bash
uv run kctl-dokploy -p idtpp settings openapi compose | grep -i "all"
```
Expected: a path that lists composes. If `/compose.allByProjects` is absent,
substitute the correct path (the shape consumed is a list of dicts with
`composeId` and `name`).

- [ ] **Step 7: Run it against live Dokploy and record the baseline**

Run: `uv run python ops/scripts/schedule-status.py --profile idtpp`
Expected: exit code 1, and a table showing 16 unhealthy schedules. This is the
"before" measurement — Task 3 and Task 5 are graded against it.

- [ ] **Step 8: Lint, format, commit**

```bash
uv run ruff check ops/scripts deploys
uv run ruff format ops/scripts deploys
git add ops/scripts/schedule-status.py deploys/tests/test_schedule_status.py
git commit -m "feat: add schedule-status.py to report real Dokploy schedule health

kctl-dokploy schedules history reads executionLogs off schedule.one, which
carries no run history, so it reports 'No execution history' for every
schedule. Real history is at /deployment.allByType?type=schedule.

healthy is strict on purpose: an enabled schedule that has never run is
unhealthy, not unknown. 16 schedules existed for five months while doing
nothing.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: Fix both bugs in the Odoo base

**Files:**
- Modify: `deploys/bases/odoo.yaml:71-83`
- Test: `deploys/tests/test_odoo_base_schedules.py`

**Interfaces:**
- Consumes: nothing.
- Produces: a corrected `schedules:` block in the base, used by
  `phase_schedules` for any future deploy and copied into the recreate commands
  in Task 3.

- [ ] **Step 1: Write the failing test**

Create `deploys/tests/test_odoo_base_schedules.py`:

```python
"""Guards for the Odoo base's schedules block.

Both assertions encode a bug that ran in production for five months:

1. `service: odoo` matched no container. The real compose services are
   odoo-web / odoo-cron / odoo-gevent. Dokploy resolves
   {compose.appName}-{serviceName}-1, and an unmatched name yields an empty
   string, so it ran `docker exec  bash -c ...` and Docker read `bash` as the
   container name.
2. `DELETE FROM ir_sessions` targeted a table that does not exist. Odoo 18
   here runs the session_db server-wide module, whose table is
   http_sessions(sid, write_date, payload).
"""

from __future__ import annotations

from pathlib import Path

import yaml

BASE = Path(__file__).resolve().parents[1] / "bases" / "odoo.yaml"
REAL_SERVICES = {"odoo-web", "odoo-cron", "odoo-gevent"}


def _schedules() -> list[dict]:
    return yaml.safe_load(BASE.read_text())["schedules"]


def test_every_schedule_targets_a_real_compose_service():
    for sched in _schedules():
        assert sched["service"] in REAL_SERVICES, (
            f"{sched['name']}: service {sched['service']!r} matches no compose service. "
            f"Dokploy resolves an unmatched name to an empty string and silently "
            f"runs `docker exec  <shell>`, which fails every time. Real services: {sorted(REAL_SERVICES)}"
        )


def test_session_cleanup_targets_the_real_table():
    cleanup = [s for s in _schedules() if "session-cleanup" in s["name"]]
    assert cleanup, "the session-cleanup schedule disappeared from the base"
    for sched in cleanup:
        assert "http_sessions" in sched["command"], (
            "session cleanup must target http_sessions (created by the session_db "
            "server-wide module), not ir_sessions, which does not exist"
        )
        assert "ir_sessions" not in sched["command"]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest deploys/tests/test_odoo_base_schedules.py -q`
Expected: FAIL — both tests fail; service is `odoo`, command references `ir_sessions`

- [ ] **Step 3: Fix the base**

In `deploys/bases/odoo.yaml`, replace the whole `schedules:` block with:

```yaml
# NOTE: `service` MUST name a real compose service. compose/odoo.prod.yml
# defines odoo-web / odoo-cron / odoo-gevent -- there has never been a service
# called `odoo`. Dokploy resolves the target container as
# {compose.appName}-{service}-1; an unmatched name yields an EMPTY string, so
# it runs `docker exec  bash -c ...` and Docker reads `bash` as the container
# name. That typo made these schedules fail 100% of the time from 2026-04-09
# to 2026-08-31 with no alert, because Dokploy has no failure notification for
# scheduled jobs. odoo-cron is chosen over odoo-web so maintenance never
# competes with a user-facing worker.
schedules:
  - name: "{instance_name}-vacuum"
    cron: "0 4 * * 0"
    command: "vacuumdb -U {db_user} -d {db_name} --analyze"
    service: odoo-cron
    shell: bash
    timezone: Asia/Jakarta
  # The table is http_sessions(sid, write_date, payload), created by the
  # session_db server-wide module. `ir_sessions` does not exist in Odoo 18 --
  # the previous command would have failed even with the service name fixed.
  - name: "{instance_name}-session-cleanup"
    cron: "0 3 * * *"
    command: "psql -U {db_user} -d {db_name} -c \"DELETE FROM http_sessions WHERE write_date < NOW() - INTERVAL '7 days'\""
    service: odoo-cron
    shell: bash
    timezone: Asia/Jakarta
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest deploys/tests/test_odoo_base_schedules.py -q`
Expected: PASS, 2 passed

- [ ] **Step 5: Run the full gate**

Run: `just test && just lint && just fmt-check`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add deploys/bases/odoo.yaml deploys/tests/test_odoo_base_schedules.py
git commit -m "fix: point Odoo schedules at a real service and the real session table

Two independent bugs, both live since 2026-04-09 and both silent:

service: odoo matched no compose service (real: odoo-web/odoo-cron/
odoo-gevent). Dokploy resolves {appName}-{service}-1, and an unmatched name
becomes an empty string, so it ran 'docker exec  bash -c ...' and Docker
read bash as the container name.

session-cleanup targeted ir_sessions, which does not exist. Odoo 18 runs
session_db, whose table is http_sessions(sid, write_date, payload) -- so
fixing the service alone would only have changed the error message.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: Recreate the 14 broken Odoo schedules and prove they run

`kctl-dokploy schedules update` exposes only `--name/--cron/--command/--enabled`
— it cannot change `serviceName`, even though the API accepts it. So these are
deleted and recreated. Nothing of value is lost: all recorded history is
failures.

**Files:**
- Create: `ops/scripts/recreate-odoo-schedules.sh`

**Interfaces:**
- Consumes: `ops/scripts/schedule-status.py` from Task 1 (verification).
- Produces: 14 recreated schedules with `serviceName: odoo-cron` and corrected
  commands.

- [ ] **Step 1: Write the recreate script**

Create `ops/scripts/recreate-odoo-schedules.sh`. Schedule IDs, compose IDs and
database names below were captured live on 2026-08-31.

```bash
#!/usr/bin/env bash
# Recreate the 14 Odoo maintenance schedules with a working service name and
# the real session table.
#
# Delete-and-recreate rather than update, because `kctl-dokploy schedules
# update` cannot change serviceName (the API accepts it; the CLI does not
# expose it). No history is lost -- every recorded run is a failure.
#
# Re-resolve the IDs before running if anything has been redeployed:
#   uv run python ops/scripts/schedule-status.py --profile idtpp --json
set -euo pipefail

PROFILE="${PROFILE:-idtpp}"

# app|composeId|vacuumScheduleId|cleanupScheduleId|dbName
ROWS=(
  "mac-odoo-erp|YqcvHMmbxhWCNtnb68szv|t8Z-S74jvMO7i9w9rTL2w|xjRSsTnThHZTRVk0UZ7kc|mac_odoo_erp"
  "mac-odoo-hrms|7LfegFB_B2JymhDdEXzMv|p0mJSU7GhMttMME9wYUuq|tKkMHhu-rDre58ToivI48|mac_odoo_hrms"
  "mac-odoo-erp-stg|0sqYliD0VDorKlPwAuoUm|AZCN3qnLVcSk5Gk37gXve|w12vx3EYiQBcrs9HcCNVT|mac_odoo_erp_stg"
  "mac-odoo-hrms-stg|f6v6i6OAwwgk1npDj7L5t|NttwTKvF6545i2X83sT7D|ZhiVHsEBfZ_BJd1wlXr6D|mac_odoo_hrms_stg"
  "tpp-odoo-helpdesk|J0WbcW9MkaG5q0zjZw0m8|zh3KV0FOca5y8x2Vi8Z0y|Uh0SeYaon3TPktI6UZ9gH|tpp_odoo_helpdesk"
  "tpp-odoo-hrms-stg|cEbFdG2lYVAORt4twXCa3|4TysPxmUfV37HxmLCER8y|vGU58d3_Bmo-F40Qdr_O_|tpp_odoo_hrms_stg"
  "tpp-odoo-erp-stg|qn1FMOpX5HdW9peOKregZ|1dcv9kBOFNTHK6LWndxWJ|-uW27iPF4UWHgUM68-5rb|tpp_odoo_erp_stg"
)

for row in "${ROWS[@]}"; do
  IFS='|' read -r app cid vac_id clean_id db <<<"$row"
  echo "=== $app ==="

  kctl-dokploy -p "$PROFILE" schedules delete "$vac_id" --force
  kctl-dokploy -p "$PROFILE" schedules delete "$clean_id" --force

  kctl-dokploy -p "$PROFILE" schedules create \
    --name "${app}-vacuum" \
    --cron "0 4 * * 0" \
    --command "vacuumdb -U odoo -d ${db} --analyze" \
    --type compose --compose "$cid" --service odoo-cron \
    --shell bash --timezone Asia/Jakarta

  kctl-dokploy -p "$PROFILE" schedules create \
    --name "${app}-session-cleanup" \
    --cron "0 3 * * *" \
    --command "psql -U odoo -d ${db} -c \"DELETE FROM http_sessions WHERE write_date < NOW() - INTERVAL '7 days'\"" \
    --type compose --compose "$cid" --service odoo-cron \
    --shell bash --timezone Asia/Jakarta
done

echo
echo "Recreated. Now run each once and check status -- creation proves nothing."
```

- [ ] **Step 2: Confirm the IDs are still current before touching anything**

Run: `uv run python ops/scripts/schedule-status.py --profile idtpp --json > /tmp/schedules-before.json`
Then: `grep -c scheduleId /tmp/schedules-before.json` — cross-check the 14 IDs
in the script against this file. If any differ, update the script; a stale ID
would delete the wrong schedule.

- [ ] **Step 3: Run the recreate script**

```bash
chmod +x ops/scripts/recreate-odoo-schedules.sh
PROFILE=idtpp ./ops/scripts/recreate-odoo-schedules.sh
```
Expected: 14 delete confirmations and 14 create confirmations, no errors.

- [ ] **Step 4: Trigger one run of every recreated schedule**

```bash
uv run python ops/scripts/schedule-status.py --profile idtpp --json \
  | python3 -c "
import json,sys,subprocess
for r in json.load(sys.stdin):
    if r['service'] == 'odoo-cron':
        print('running', r['name'])
        subprocess.run(['kctl-dokploy','-p','idtpp','schedules','run',r['schedule_id']], check=False)
"
```
Expected: each reports "Scheduled task executed".

- [ ] **Step 5: Verify every one reached `status: done`**

This is the step that matters. Wait ~30 seconds for the runs to land, then:

Run: `uv run python ops/scripts/schedule-status.py --profile idtpp`
Expected: all 14 Odoo rows show `last=done` and `healthy=True`.

If any shows `error`, read the real log rather than guessing — SSH to the app's
host and:
```bash
ls -t /etc/dokploy/schedules/<schedule-appName>/*.log | head -1 | xargs cat
```

- [ ] **Step 6: Commit**

```bash
git add ops/scripts/recreate-odoo-schedules.sh
git commit -m "fix: recreate 14 Odoo schedules with a working service and table

Delete-and-recreate because kctl-dokploy schedules update cannot change
serviceName. All 14 verified reaching status: done via
/deployment.allByType, not merely created.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: Delete the four debris schedules and rotate what they exposed

**Files:**
- None in-repo. This is a live-state change plus a credential rotation.

**Interfaces:**
- Consumes: `ops/scripts/schedule-status.py` from Task 1.
- Produces: four fewer schedules; two rotated credentials.

> **Do not print these schedules' `command` fields to a terminal, a log, or a
> commit message.** They contain plaintext passwords.

- [ ] **Step 1: Confirm what is about to be deleted**

```bash
for id in ZGz95qZfXeAv2NX7Hdo-3 7DJzbiKeGT20MeU_wiRxI E5Zm5HTFyFv-_aFP2YzkG N83YQ5ek9AgqePJ-LA5eZ; do
  kctl-dokploy -p idtpp --json schedules get "$id" \
    | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['scheduleId'], '|', d['name'], '|', d['cronExpression'], '| enabled=', d['enabled'])"
done
```
Expected exactly:
```
ZGz95qZfXeAv2NX7Hdo-3 | create-authentik-db | * * * * * | enabled= True
7DJzbiKeGT20MeU_wiRxI | dbg-v2 | 0 0 31 12 0 | enabled= True
E5Zm5HTFyFv-_aFP2YzkG | dbg-v3 | 0 0 31 12 0 | enabled= True
N83YQ5ek9AgqePJ-LA5eZ | reset-akadmin-pw | * * * * * | enabled= True
```
If any name differs, STOP — an ID has moved and deleting would remove the wrong
schedule.

- [ ] **Step 2: Check whether Authentik still depends on `create-authentik-db`**

This schedule creates an Authentik database and role. Authentik was rehosted to
`kod-prod-03-data` with an embedded Postgres, so `tpp-infra-postgres` is very
likely no longer its database — but confirm rather than assume, because
deleting a bootstrap job that is still load-bearing is a real outage.

```bash
kctl-dokploy -p idtpp --json compose list \
  | python3 -c "import json,sys; print([c for c in json.load(sys.stdin) if 'authentik' in c['name']])"
kctl-dokploy -p idtpp env list --compose R-ArjLoo3c0zWhXB57Xtm | grep -i "^POSTGRES_HOST\|^PG_HOST\|DATABASE" || true
```
Expected: Authentik's database host is not `tpp-infra-postgres`. If it *is*,
do not delete this schedule — convert it to a one-shot and disable it instead,
and note that in the commit.

- [ ] **Step 3: Delete all four**

```bash
for id in ZGz95qZfXeAv2NX7Hdo-3 7DJzbiKeGT20MeU_wiRxI E5Zm5HTFyFv-_aFP2YzkG N83YQ5ek9AgqePJ-LA5eZ; do
  kctl-dokploy -p idtpp schedules delete "$id" --force
done
```
Expected: four "deleted" confirmations.

- [ ] **Step 4: Rotate the two exposed credentials**

Both were stored in plaintext in Dokploy's database and returned by the API for
~146 days. Deletion stops further exposure but does not undo it.

1. **Authentik `akadmin` password** — rotate via Authentik, then store the new
   value in 1Password. Do not put it in any schedule, manifest, or commit.
2. **Authentik database role password** on `tpp-infra-postgres` — rotate with
   `ALTER ROLE authentik WITH PASSWORD '<new>'`, then update whatever consumes
   it. If Step 2 showed Authentik no longer uses this database, drop the unused
   role and database instead of rotating.

Record completion in the runbook, not the value:
```bash
echo "- 2026-08-31: rotated akadmin password and authentik DB role password; both had been stored in plaintext Dokploy schedule commands since 2026-04-07 (see docs/superpowers/specs/2026-08-31-xyops-to-dokploy-schedules-design.md §3.3)" >> ops/runbooks/incident-response.md
```

- [ ] **Step 5: Verify they are gone**

Run: `uv run python ops/scripts/schedule-status.py --profile idtpp`
Expected: `create-authentik-db`, `dbg-v2`, `dbg-v3`, `reset-akadmin-pw` all
absent from the table.

- [ ] **Step 6: Commit**

```bash
git add ops/runbooks/incident-response.md
git commit -m "chore: delete four debris Dokploy schedules and rotate exposed credentials

reset-akadmin-pw and create-authentik-db were '* * * * *' schedules created
2026-04-07 that failed every minute since -- roughly 210,000 firings each.
dbg-v2 and dbg-v3 never ran. All four were leftovers.

Both '* * * * *' schedules stored plaintext passwords in their command
strings, which Dokploy keeps unencrypted and returns over the API. Deleting
them stops further exposure; both credentials were rotated.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 5: Cover the three production Odoo apps that have no schedules

`tpp-odoo-erp`, `tpp-odoo-hrms`, and `tpp25-odoo-erp` have no schedules at all.
`phase_schedules` only creates during a deploy and never backfills, so adding
the block to the base never reached apps deployed before it existed. This is
spec §3.1 G4 showing up in production.

**Files:**
- Modify: `ops/scripts/recreate-odoo-schedules.sh` (add a create-only path)

**Interfaces:**
- Consumes: `ops/scripts/schedule-status.py` from Task 1; the corrected base
  from Task 2.
- Produces: 6 new schedules, verified green.

- [ ] **Step 1: Resolve the three compose IDs and database names**

```bash
kctl-dokploy -p idtpp --json compose list \
  | python3 -c "
import json,sys
want={'tpp-odoo-erp','tpp-odoo-hrms','tpp25-odoo-erp'}
for c in json.load(sys.stdin):
    if c['name'] in want: print(c['name'], c['composeId'])
"
```
Record the three IDs. Database names come from the manifests:
`deploys/instances/production/{tpp-odoo-erp,tpp-odoo-hrms,tpp25-odoo-erp}.yaml`,
key `database.name`.

- [ ] **Step 2: Confirm each really has zero schedules**

```bash
for cid in <the three IDs>; do
  echo "--- $cid ---"
  kctl-dokploy -p idtpp --json schedules list "$cid" --type compose
done
```
Expected: `[]` for all three. If any is non-empty, stop and reconcile rather
than creating duplicates — `name` is the reconciliation key and duplicates
cannot be told apart.

- [ ] **Step 3: Confirm the service name on these apps**

Do not assume `odoo-cron` exists here just because it exists on `mac-odoo-erp`.

```bash
ssh root@<host of the app> 'docker ps --format "{{.Names}}" | grep odoo'
```
Expected: names ending `-odoo-cron-1`. If an app has no cron container (a
`-light` deployment profile may not), use `odoo-web` for that app and note it.

- [ ] **Step 4: Create the six schedules**

Append to `ops/scripts/recreate-odoo-schedules.sh` a `NEW_ROWS` array in the
same `app|composeId|dbName` shape, and a loop that only creates:

```bash
# Apps that never had schedules at all -- create only, nothing to delete.
NEW_ROWS=(
  "tpp-odoo-erp|<composeId>|tpp_odoo_erp"
  "tpp-odoo-hrms|<composeId>|tpp_odoo_hrms"
  "tpp25-odoo-erp|<composeId>|tpp25_odoo_erp"
)

for row in "${NEW_ROWS[@]}"; do
  IFS='|' read -r app cid db <<<"$row"
  echo "=== $app (create only) ==="
  kctl-dokploy -p "$PROFILE" schedules create \
    --name "${app}-vacuum" --cron "0 4 * * 0" \
    --command "vacuumdb -U odoo -d ${db} --analyze" \
    --type compose --compose "$cid" --service odoo-cron \
    --shell bash --timezone Asia/Jakarta
  kctl-dokploy -p "$PROFILE" schedules create \
    --name "${app}-session-cleanup" --cron "0 3 * * *" \
    --command "psql -U odoo -d ${db} -c \"DELETE FROM http_sessions WHERE write_date < NOW() - INTERVAL '7 days'\"" \
    --type compose --compose "$cid" --service odoo-cron \
    --shell bash --timezone Asia/Jakarta
done
```

Fill in the real compose IDs from Step 1 — leaving a placeholder here would
create a schedule pointing at nothing, which is the exact class of bug this
whole plan exists to fix.

- [ ] **Step 5: Run each once and verify `status: done`**

```bash
uv run python ops/scripts/schedule-status.py --profile idtpp --json \
  | python3 -c "
import json,sys,subprocess
for r in json.load(sys.stdin):
    if r['app'] in {'tpp-odoo-erp','tpp-odoo-hrms','tpp25-odoo-erp'}:
        subprocess.run(['kctl-dokploy','-p','idtpp','schedules','run',r['schedule_id']], check=False)
"
sleep 30
uv run python ops/scripts/schedule-status.py --profile idtpp
```
Expected: exit code 0 — every enabled schedule in the estate healthy.

- [ ] **Step 6: Commit**

```bash
git add ops/scripts/recreate-odoo-schedules.sh
git commit -m "fix: add missing maintenance schedules to three production Odoo apps

tpp-odoo-erp, tpp-odoo-hrms and tpp25-odoo-erp had no schedules at all.
phase_schedules only creates during a deploy and never backfills, so adding
the block to the base never reached apps deployed before it existed.

All six verified reaching status: done.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Done when

`uv run python ops/scripts/schedule-status.py --profile idtpp` exits **0** —
every enabled schedule in the estate has a real run whose status is `done`.

Baseline before this plan: exit 1, 16 unhealthy.

## Deliberately not in this plan

- **Alerting.** Nothing here makes a *future* schedule failure visible; it only
  fixes the current ones and gives you a command to check. Continuous
  visibility is the `jobrun` wrapper and the watchdog in
  `2026-08-31-xyops-to-dokploy-migration.md`. Until that lands, run
  `schedule-status.py` manually or from host cron.
- **The four `kctl-dokploy` bugs** (spec §3.4). They belong in
  `kodemeio-skills`; `schedule-status.py` is the local workaround for the one
  that blocks this plan.
- **`phase_schedules` becoming a reconciler.** Without it, Task 2's base fix
  does not propagate on redeploy — which is exactly why Tasks 3 and 5 change
  live state by hand. Tracked in the migration plan.
