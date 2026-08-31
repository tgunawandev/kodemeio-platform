# xyOps → Dokploy Schedules Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move all 17 xyOps jobs to native Dokploy schedules and decommission the xyOps conductor.

**Architecture:** A new `tpp-infra-kctl` compose app on tpp-prod-04 holds one
idle container with the pinned `kodemeio-cli` image, the kctl config, and the
job secrets. Each job is a compose-type Dokploy schedule that `docker exec`s a
`jobrun` wrapper into it. `jobrun` supplies the three things Dokploy has no
equivalent for — failure email, a per-job timeout, and a log cap. A rewritten
dead-man watchdog on tpp-prod-01 catches jobs that never fire at all.

**Tech Stack:** Docker Compose, Dokploy schedules, Python 3.12, `uv`, `pytest`,
`ruff`, `kctl-dokploy` 0.16.6, POSIX `sh`, `bash`, host cron

**Spec:** `docs/superpowers/specs/2026-08-31-xyops-to-dokploy-schedules-design.md`

## Global Constraints

- Always pass an explicit `kctl-dokploy` profile. TPP work uses `-p idtpp`;
  `kod-*` targets require `-p kodemeio`, not the default.
- **Timezone:** every schedule sets `timezone: Asia/Jakarta` explicitly. Never
  rely on container `TZ`.
- **Image pinning:** `ghcr.io/tgunawandev/kodemeio-cli:sha-2816c3c`. Pinned to
  an immutable `sha-<shortsha>` tag, never `latest`. The GHCR name is
  deliberately retained after the repo was renamed to `kodemeio-skills` — it is
  the image name, not the repo.
- **Compose requirements:** `restart: unless-stopped`; `deploy.resources.limits`
  with both `cpus` and `memory`; a `healthcheck`; external network
  `dokploy-network`; **no published ports**.
- **Secrets:** never in argv, logs, committed files, or terminal output. Every
  `.env` has a sanitized `.env.example`. Never commit a real `.env`.
- **Guard:** every job asserts its required variables are non-empty and contain
  no literal `${`, exiting 78 before any work. `expand_env`
  (`kctl-lib/config.py:33`) returns the literal `${VAR}` for an unset variable
  rather than raising, so an unguarded job sends that string to a remote API as
  though it were the credential.
- **Git is authoritative.** A schedule edited in the Dokploy UI is drift.
- **`name` is the reconciliation key and is immutable.** Renaming a schedule in
  git creates a new one and orphans the old, losing its run history.
- **A schedule is "working" only when a real run reports `status: done`.**
  Verify with `ops/scripts/schedule-status.py`, never with "the CLI said OK".
- Python tooling is `uv`, never pip. Conventional Commits ending with
  `Co-Authored-By: Claude <noreply@anthropic.com>`.
- **xyOps stays deployed and functional** until Task 9. It is the rollback path.

## Prerequisites

1. **`2026-08-31-fix-dokploy-schedule-failures.md` is complete** and
   `ops/scripts/schedule-status.py --profile idtpp` exits 0. That plan builds
   the verification tool this one depends on, and proves the compose-exec
   mechanism actually works in this estate.
2. **Two repos are in play.** Tasks 1–2 and 8 land in `kodemeio-skills`
   (`~/project/00-new-projects/kodemeio-workspace/kodemeio-skills`); the rest
   land here. This repo must not host `kctl-*` source (`CLAUDE.md`).

## Job inventory

The 17 jobs, from `kodemeio-xyops/events/*.yaml`. Enabled state is xyOps' today.

| Dokploy `name` | Cron | WIB | xyOps state |
|---|---|---|---|
| `report-selfcheck` | `50 6 * * *` | 06:50 | enabled |
| `report-daily` | `0 7 * * *` | 07:00 | enabled |
| `report-weekly` | `0 8 * * 1` | Mon 08:00 | enabled |
| `backup-tpp` | `0 5 * * *` | 05:00 | enabled |
| `backup-tpp25` | `10 5 * * *` | 05:10 | enabled |
| `backup-mac` | `20 5 * * *` | 05:20 | enabled |
| `backup-mac-hrms` | `30 5 * * *` | 05:30 | enabled |
| `maint-tpp-pg-bloat` | `0 2 * * *` | 02:00 | disabled |
| `maint-kod-pg-bloat` | `0 2 * * *` | 02:00 | disabled |
| `maint-tpp-pg-backup` | `30 2 * * *` | 02:30 | disabled |
| `maint-tpp-mailcow-quarantine` | `0 3 * * 0` | Sun 03:00 | disabled |
| `maint-tpp-pg-health` | `0 4 * * *` | 04:00 | disabled |
| `maint-tpp-odoo-health` | `15 4 * * *` | 04:15 | disabled |
| `maint-tpp-mailcow-health` | `30 4 * * *` | 04:30 | disabled |
| `maint-kod-pg-health` | `45 4 * * *` | 04:45 | disabled |
| `maint-kod-odoo-health` | `45 5 * * *` | 05:45 | disabled |
| `maint-kod-dokploy-health` | `50 5 * * *` | 05:50 | disabled |

Alarm ordering before the 06:50/07:00 reports is deliberate: a stale backup
must be known before the business report goes out. Preserve it.

**`phase_schedules` is create-only.** That is a defect (spec §3.1 G4), but it
makes staged rollout natural: add schedules to the manifest in phase order and
redeploy, and each deploy creates only what is new. Until Task 8 lands, a
change to an *existing* schedule must be applied by hand.

---

### Task 1: `jobrun` — the wrapper that makes failures visible

**Repo:** `kodemeio-skills`

**Files:**
- Create: `docker/jobrun`
- Modify: `docker/Dockerfile.cli`
- Test: `tests/test_jobrun.sh`

**Interfaces:**
- Consumes: nothing.
- Produces: `/usr/local/bin/jobrun` in the image, invoked as
  `jobrun <job-name> <cmd> [args…]`. Reads `JOBRUN_REQUIRE` (space-separated
  variable names to guard), `JOBRUN_TIMEOUT` (seconds, default 900),
  `JOBRUN_LOG_MAX` (bytes, default 5242880), `ALERT_TO`, `SMTP_HOST`,
  `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `MAIL_FROM`. Exits with the wrapped
  command's exit code, or 78 on a guard failure, or 2 on its own misuse.

Baked into the image rather than bind-mounted on purpose: a missing mount would
make every job exit 0 and alert nobody, which is the worst available failure
mode for an alarm.

- [ ] **Step 1: Write the failing test**

Create `tests/test_jobrun.sh`:

```bash
#!/usr/bin/env bash
# jobrun's contract. Every assertion here is a failure mode that would make a
# scheduled alarm silently useless.
set -uo pipefail

JOBRUN="${JOBRUN:-docker/jobrun}"
fails=0
check() {  # check <label> <expected-exit> <actual-exit>
  if [ "$2" = "$3" ]; then echo "ok   - $1"; else echo "FAIL - $1: expected exit $2, got $3"; fails=$((fails+1)); fi
}

# A successful command must exit 0 and send no mail.
JOBRUN_NOTIFY=echo "$JOBRUN" t-ok true >/dev/null 2>&1
check "success exits 0" 0 $?

# A failing command must propagate its REAL exit code, not 0 and not 1.
JOBRUN_NOTIFY=echo "$JOBRUN" t-fail sh -c 'exit 42' >/dev/null 2>&1
check "failure propagates exit code" 42 $?

# A guarded variable that is unset must exit 78 BEFORE running the command.
out=$(JOBRUN_NOTIFY=echo JOBRUN_REQUIRE="MISSING_VAR" "$JOBRUN" t-guard sh -c 'echo SHOULD_NOT_RUN' 2>&1)
check "unset guarded var exits 78" 78 $?
case "$out" in *SHOULD_NOT_RUN*) echo "FAIL - guard ran the command anyway"; fails=$((fails+1));; *) echo "ok   - guard blocks execution";; esac

# A guarded variable still holding a literal ${...} must also exit 78.
# expand_env returns the literal "${VAR}" for an unset variable, so without
# this the string is sent to a remote API as though it were the credential.
MISSING_VAR='${SOME_SECRET}' JOBRUN_NOTIFY=echo JOBRUN_REQUIRE="MISSING_VAR" "$JOBRUN" t-lit true >/dev/null 2>&1
check "unexpanded \${} exits 78" 78 $?

# An empty guarded variable must exit 78.
MISSING_VAR="" JOBRUN_NOTIFY=echo JOBRUN_REQUIRE="MISSING_VAR" "$JOBRUN" t-empty true >/dev/null 2>&1
check "empty guarded var exits 78" 78 $?

# A command that overruns the timeout must be killed, not hang.
JOBRUN_NOTIFY=echo JOBRUN_TIMEOUT=1 "$JOBRUN" t-timeout sleep 10 >/dev/null 2>&1
rc=$?
if [ "$rc" -ne 0 ]; then echo "ok   - timeout kills and fails"; else echo "FAIL - timeout returned 0"; fails=$((fails+1)); fi

# Misuse must be loud, never a silent no-op.
JOBRUN_NOTIFY=echo "$JOBRUN" >/dev/null 2>&1
check "no args exits 2" 2 $?
JOBRUN_NOTIFY=echo "$JOBRUN" only-a-name >/dev/null 2>&1
check "name without command exits 2" 2 $?

# A failure must actually invoke the notifier exactly once.
n=$(JOBRUN_NOTIFY=echo "$JOBRUN" t-notify sh -c 'exit 3' 2>&1 | grep -c 'JOBRUN-ALERT')
if [ "$n" -eq 1 ]; then echo "ok   - failure notifies once"; else echo "FAIL - notifier called $n times"; fails=$((fails+1)); fi

# A success must NOT notify.
n=$(JOBRUN_NOTIFY=echo "$JOBRUN" t-quiet true 2>&1 | grep -c 'JOBRUN-ALERT')
if [ "$n" -eq 0 ]; then echo "ok   - success is quiet"; else echo "FAIL - success notified"; fails=$((fails+1)); fi

echo; [ "$fails" -eq 0 ] && { echo "ALL PASS"; exit 0; } || { echo "$fails FAILED"; exit 1; }
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `chmod +x tests/test_jobrun.sh && ./tests/test_jobrun.sh`
Expected: FAIL — `docker/jobrun` does not exist

- [ ] **Step 3: Write `jobrun`**

Create `docker/jobrun`:

```sh
#!/bin/sh
# Run one scheduled job, and make sure a failure is never silent.
#
# Dokploy has NO failure alerting for scheduled jobs -- there is no
# cron-failure flag anywhere in its API. Sixteen schedules in this estate
# failed 100% of the time for five months without anyone finding out. This
# wrapper is what stops that happening to a backup-freshness alarm.
#
# Usage: jobrun <job-name> <command> [args...]
#   JOBRUN_REQUIRE  space-separated variable names to guard (default: none)
#   JOBRUN_TIMEOUT  seconds before the job is killed (default: 900)
#   JOBRUN_LOG_MAX  bytes of output retained for the alert (default: 5 MiB)
#   JOBRUN_NOTIFY   override the notifier; used by tests
set -u

JOB="${1:-}"
[ -z "$JOB" ] && { echo "jobrun: FATAL: no job name given" >&2; exit 2; }
shift
[ "$#" -eq 0 ] && { echo "jobrun: FATAL: no command given for '$JOB'" >&2; exit 2; }

TIMEOUT="${JOBRUN_TIMEOUT:-900}"
LOG_MAX="${JOBRUN_LOG_MAX:-5242880}"
OUT="$(mktemp)"
trap 'rm -f "$OUT"' EXIT

notify() {  # notify <subject> <body-file>
    if [ -n "${JOBRUN_NOTIFY:-}" ]; then
        "$JOBRUN_NOTIFY" "JOBRUN-ALERT $1"
        return
    fi
    ALERT_TO="${ALERT_TO:-}" \
    SUBJECT="$1" BODY_FILE="$2" JOB_NAME="$JOB" \
    python3 - <<'PY' || echo "jobrun: FATAL: alert mail FAILED for '$JOB' -- failure is now silent" >&2
import os, smtplib, ssl, socket
from email.message import EmailMessage

to = os.environ.get("ALERT_TO", "").strip()
if not to:
    raise SystemExit("jobrun: ALERT_TO is empty; cannot send alert")
body = open(os.environ["BODY_FILE"], errors="replace").read()
m = EmailMessage()
m["From"] = os.environ.get("MAIL_FROM", "TPP Ops <reports@idtpp.com>")
m["To"] = to
m["Subject"] = os.environ["SUBJECT"]
m.set_content(
    f"job:  {os.environ['JOB_NAME']}\n"
    f"host: {socket.gethostname()}\n\n"
    f"--- output ---\n{body}\n"
)
s = smtplib.SMTP(os.environ.get("SMTP_HOST", "mail.idtpp.com"),
                 int(os.environ.get("SMTP_PORT", "587")), timeout=60)
s.starttls(context=ssl.create_default_context())
s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASS"])
s.send_message(m)
s.quit()
PY
}

# --- Guard -----------------------------------------------------------------
# kctl-lib's expand_env returns the LITERAL "${VAR}" string when a variable is
# unset, rather than raising. Without this guard that literal is handed to a
# remote API as a credential, and the job fails at authentication instead of at
# config load -- a far more confusing failure that can look like an outage.
for v in ${JOBRUN_REQUIRE:-}; do
    eval "val=\${$v-}"
    case "$val" in
        "")     echo "jobrun: FATAL: $v is empty" >&2
                echo "guard failed: $v is empty" > "$OUT"
                notify "[ALERT] $JOB guard failed ($v empty)" "$OUT"; exit 78 ;;
        *'${'*) echo "jobrun: FATAL: $v looks unexpanded" >&2
                echo "guard failed: $v still contains a literal \${...}" > "$OUT"
                notify "[ALERT] $JOB guard failed ($v unexpanded)" "$OUT"; exit 78 ;;
    esac
done

# --- Run -------------------------------------------------------------------
timeout "$TIMEOUT" "$@" > "$OUT" 2>&1
CODE=$?

# Cap retained output so one runaway job cannot mail a gigabyte.
if [ "$(wc -c < "$OUT")" -gt "$LOG_MAX" ]; then
    tail -c "$LOG_MAX" "$OUT" > "$OUT.trim" && mv "$OUT.trim" "$OUT"
fi
cat "$OUT"

if [ "$CODE" -ne 0 ]; then
    if [ "$CODE" -eq 124 ]; then
        echo "jobrun: '$JOB' exceeded ${TIMEOUT}s and was killed" >&2
        notify "[ALERT] $JOB timed out after ${TIMEOUT}s" "$OUT"
    else
        echo "jobrun: '$JOB' failed with exit $CODE" >&2
        notify "[ALERT] $JOB failed (exit $CODE)" "$OUT"
    fi
fi

# Exit with the job's REAL code so Dokploy records status: error and the
# watchdog can see it. Never mask a failure as success.
exit "$CODE"
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `./tests/test_jobrun.sh`
Expected: `ALL PASS`

- [ ] **Step 5: Add `jobrun` to the image**

In `docker/Dockerfile.cli`, in the **runtime** stage (the second
`FROM python:3.12-slim`), after the `COPY --from=builder /app /app` line:

```dockerfile
# jobrun wraps every scheduled job: guards its secrets, enforces a timeout and
# a log cap, and emails on failure. Dokploy has no failure alerting for
# scheduled jobs, so without this a failing alarm is completely silent.
COPY docker/jobrun /usr/local/bin/jobrun
RUN chmod 755 /usr/local/bin/jobrun
```

- [ ] **Step 6: Build the image and verify `jobrun` works inside it**

```bash
docker build -f docker/Dockerfile.cli -t kodemeio-cli:jobrun-test .
docker run --rm kodemeio-cli:jobrun-test sh -c 'command -v jobrun && command -v timeout && command -v python3'
docker run --rm -e JOBRUN_NOTIFY=echo kodemeio-cli:jobrun-test jobrun t-in-image sh -c 'exit 7'; echo "exit=$?"
```
Expected: all three binaries found; final line `exit=7`.

- [ ] **Step 7: Commit**

```bash
git add docker/jobrun docker/Dockerfile.cli tests/test_jobrun.sh
git commit -m "feat: add jobrun wrapper for scheduled jobs

Dokploy has no failure alerting for scheduled jobs -- no cron-failure flag
exists anywhere in its API. jobrun supplies the three things xyOps got from
category limits: an error email, a per-job timeout, and a log cap.

Baked into the image rather than bind-mounted: a missing mount would make
every job exit 0 and alert nobody.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

- [ ] **Step 8: Publish a pinned image and record the tag**

Push to GHCR through the repo's normal release path and record the resulting
`sha-<shortsha>` tag. **Every later task uses this tag**, replacing
`sha-2816c3c`. Write it down now — an image without `jobrun` would run every
job with no alerting at all and look completely healthy.

---

### Task 2: Toolbox compose and config

**Repo:** `kodemeio-skills`

**Files:**
- Create: `compose/toolbox.yml`
- Create: `config/kctl-config.yaml`

**Interfaces:**
- Consumes: the pinned image tag from Task 1 Step 8.
- Produces: a compose stack with exactly one service named **`kctl`** — that
  name becomes `serviceName` on all 17 schedules.

- [ ] **Step 1: Copy the config template out of xyOps into git**

```bash
cp ../kodemeio-xyops/config/kctl-config.template.yaml config/kctl-config.yaml
```

This file holds only `${VAR}` placeholders and non-secret ids (Accurate
`db_id`s, the `tpp-trading-active` group, the Hetzner S3 endpoint/region). It
carries no secret values and is safe to commit — confirm that before you do:

```bash
grep -nE ':\s*[A-Za-z0-9+/=]{16,}\s*$' config/kctl-config.yaml || echo "no literal secrets"
```
Expected: `no literal secrets`. If anything matches, replace it with a
`${VAR}` placeholder and add the variable to Task 3's `.env.example`.

- [ ] **Step 2: Write the toolbox compose**

Create `compose/toolbox.yml`:

```yaml
# kctl toolbox -- the execution host for every scheduled kctl-* job.
#
# This container does nothing on its own. Dokploy compose schedules
# `docker exec` into it, which is why it must simply stay up.
#
# It deliberately does NOT mount /var/run/docker.sock. Both schedulers this
# replaces (Ofelia and xyOps) bind-mount it read-write, which is
# root-equivalent on the host. Every job here only calls remote APIs, so the
# socket is not needed and is not granted.
services:
  kctl:
    # The service name `kctl` IS the schedules' serviceName. Dokploy resolves
    # {compose.appName}-{serviceName}-1; a mismatch resolves to an empty
    # string and silently runs `docker exec  sh -c ...` forever. Renaming this
    # service breaks all 17 schedules at once.
    image: ghcr.io/tgunawandev/kodemeio-cli:REPLACE_WITH_TASK1_TAG
    container_name: tpp-infra-kctl
    command: ["sleep", "infinity"]
    restart: unless-stopped
    env_file:
      - .env
    volumes:
      - ./config/kctl-config.yaml:/root/.config/kodemeio/config.yaml:ro
    healthcheck:
      test: ["CMD", "kctl-hz", "--version"]
      interval: 60s
      timeout: 30s
      retries: 3
      start_period: 15s
    deploy:
      resources:
        limits:
          # Sized for the heaviest job: the weekly report pulls 10 Accurate
          # tenants and writes an xlsx. Idle cost is negligible.
          cpus: "1.0"
          memory: 1G
    networks:
      - dokploy-network

networks:
  dokploy-network:
    external: true
```

Replace `REPLACE_WITH_TASK1_TAG` with the tag recorded in Task 1 Step 8.

- [ ] **Step 3: Validate the compose renders**

```bash
SMTP_PASS=x REPORT_OWNER=x docker compose -f compose/toolbox.yml config >/dev/null && echo "compose OK"
```
Expected: `compose OK`

- [ ] **Step 4: Commit**

```bash
git add compose/toolbox.yml config/kctl-config.yaml
git commit -m "feat: add kctl toolbox compose for Dokploy scheduled jobs

One idle container that Dokploy compose schedules exec into. Replaces the
xyOps conductor's per-job ephemeral containers.

No docker.sock mount: every job calls remote APIs only, so the
root-equivalent socket both previous schedulers mounted is not granted.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: Deploy the toolbox and prove `docker exec` reaches it

**Repo:** `kodemeio-dokploy`

**Files:**
- Create: `deploys/instances/production/tpp-infra-kctl.yaml`
- Create: `deploys/env/production/.env.tpp-infra-kctl.example`
- Create (gitignored): `deploys/env/production/.env.tpp-infra-kctl`

**Interfaces:**
- Consumes: `compose/toolbox.yml` from Task 2.
- Produces: a deployed compose app whose `composeId` and resolved container
  name every later task needs.

- [ ] **Step 1: Write the env example**

Create `deploys/env/production/.env.tpp-infra-kctl.example`:

```bash
# kctl toolbox (tpp-infra-kctl) on tpp-prod-04 -- execution host for all 17
# scheduled kctl-* jobs. Real values live in Dokploy's env store and 1Password.
#
# WARNING: Dokploy's schedule.list API returns this app's ENTIRE env blob in
# cleartext to any caller holding an API key. That is not new in kind --
# PGPASSWORD for every Odoo app is already readable the same way -- but it is
# new in volume. See spec section 3.4 item 4.

TZ=Asia/Jakarta
COMPOSE_PROJECT_NAME=tpp-infra-kctl

# --- Mail (jobrun alerts + report delivery) --------------------------------
SMTP_HOST=mail.idtpp.com
SMTP_PORT=587
SMTP_USER=reports@idtpp.com
SMTP_PASS=__SET_IN_DOKPLOY__
MAIL_FROM=TPP Trade Reports <reports@idtpp.com>
ALERT_TO=__SET_IN_DOKPLOY__

# --- Report recipients ------------------------------------------------------
REPORT_OWNER=__SET_IN_DOKPLOY__
REPORT_ARCHIVE=__SET_IN_DOKPLOY__

# --- Hetzner S3 (backup freshness alarms) -----------------------------------
# kctl-hz does not propagate the global -p flag to `s3 freshness`, so the
# profile must also be exported here.
KCTL_HZ_PROFILE=idtpp
IDTPP_S3_ACCESS_KEY=__SET_IN_DOKPLOY__
IDTPP_S3_SECRET_KEY=__SET_IN_DOKPLOY__

# --- Accurate tenants (10 pairs, group tpp-trading-active) ------------------
TUNGGAL_PRAWIRA_PAKERTI_API_TOKEN=__SET_IN_DOKPLOY__
TUNGGAL_PRAWIRA_PAKERTI_SIGNATURE_SECRET=__SET_IN_DOKPLOY__
TUNGGAL_PANGAN_PAKERTI_API_TOKEN=__SET_IN_DOKPLOY__
TUNGGAL_PANGAN_PAKERTI_SIGNATURE_SECRET=__SET_IN_DOKPLOY__
TUNGGAL_PUTRA_PAKERTI_API_TOKEN=__SET_IN_DOKPLOY__
TUNGGAL_PUTRA_PAKERTI_SIGNATURE_SECRET=__SET_IN_DOKPLOY__
CAKRAWALA_SARANA_PRIORITAS_API_TOKEN=__SET_IN_DOKPLOY__
CAKRAWALA_SARANA_PRIORITAS_SIGNATURE_SECRET=__SET_IN_DOKPLOY__
CAKRAWALA_INTERNUSA_PRIORITAS_API_TOKEN=__SET_IN_DOKPLOY__
CAKRAWALA_INTERNUSA_PRIORITAS_SIGNATURE_SECRET=__SET_IN_DOKPLOY__
MAKMUR_PANGAN_JAYA_API_TOKEN=__SET_IN_DOKPLOY__
MAKMUR_PANGAN_JAYA_SIGNATURE_SECRET=__SET_IN_DOKPLOY__
LINTAS_FRESH_INTERNUSA_API_TOKEN=__SET_IN_DOKPLOY__
LINTAS_FRESH_INTERNUSA_SIGNATURE_SECRET=__SET_IN_DOKPLOY__
LUMBUNG_YASA_DAGANG_API_TOKEN=__SET_IN_DOKPLOY__
LUMBUNG_YASA_DAGANG_SIGNATURE_SECRET=__SET_IN_DOKPLOY__
LESTARI_FRESH_INTERNUSA_API_TOKEN=__SET_IN_DOKPLOY__
LESTARI_FRESH_INTERNUSA_SIGNATURE_SECRET=__SET_IN_DOKPLOY__
YATA_SIKHA_ULTIMA_API_TOKEN=__SET_IN_DOKPLOY__
YATA_SIKHA_ULTIMA_SIGNATURE_SECRET=__SET_IN_DOKPLOY__
```

- [ ] **Step 2: Create the real env file from xyOps' vault values**

Copy the 25 values out of the xyOps vault (or 1Password) into
`deploys/env/production/.env.tpp-infra-kctl`. Confirm it is ignored:

```bash
git check-ignore -v deploys/env/production/.env.tpp-infra-kctl
```
Expected: a matching gitignore rule. If it prints nothing, **stop** — the file
is not ignored and committing would leak 25 credentials.

Then check parity:
```bash
just check-env
```
Expected: pass — every key in `.env.tpp-infra-kctl` has a counterpart in the
`.example`.

- [ ] **Step 3: Write the manifest with no schedules yet**

Create `deploys/instances/production/tpp-infra-kctl.yaml`:

```yaml
kind: instance
extends: ../../bases/infra.yaml

instance:
  name: tpp-infra-kctl
  description: "kctl toolbox — execution host for all scheduled kctl-* jobs (replaces xyOps)"

project: tpp
environment: production
# Same host as the xyOps conductor it replaces. tpp-prod-04 is the only host in
# the estate with no production co-tenancy.
server: tpp-prod-04

source_overrides:
  type: github
  owner: tgunawandev
  repo: kodemeio-skills
  branch: main
  compose_path: compose/toolbox.yml

env_file: ../../env/production/.env.tpp-infra-kctl

env_overrides:
  COMPOSE_PROJECT_NAME: tpp-infra-kctl
  TZ: Asia/Jakarta

# No dns/domain block: the toolbox has no HTTP surface, publishes no ports and
# takes no Traefik route.
#
# The infra base's `backup:` block targets postgres; this app has no database
# and no state worth backing up -- its entire content is a pinned image plus
# env. An explicit empty map disables the inherited phase. `enabled: false`
# does NOT work: the deployer skips phase_backup only when the resolved config
# is null, so `enabled: false` merely blanks the destination and the phase
# still fails.
backup: {}

# schedules: added incrementally in Tasks 4-6. phase_schedules is create-only,
# so each redeploy creates exactly the entries that are new.
```

- [ ] **Step 4: Validate the manifest**

```bash
just deploy-validate idtpp deploys/instances/production/tpp-infra-kctl.yaml
just deploy-plan idtpp deploys/instances/production/tpp-infra-kctl.yaml
```
Expected: validation passes; the dry-run plan shows a create with no schedules.

- [ ] **Step 5: Deploy**

```bash
kctl-dokploy -p idtpp deploy apply -f deploys/instances/production/tpp-infra-kctl.yaml
```
Deploys are asynchronous. Wait for completion, then:
```bash
kctl-dokploy -p idtpp deploy status -f deploys/instances/production/tpp-infra-kctl.yaml
```
Expected: healthy. Record the `composeId` — Tasks 4–6 need it.

- [ ] **Step 6: Verify the resolved container name — the step that prevents a repeat**

Dokploy resolves `{compose.appName}-{serviceName}-1` using its own randomized
appName, not the manifest name. A mismatch here is exactly what kept 16
schedules dead for five months.

```bash
ssh root@178.104.169.250 'docker ps --format "{{.Names}}" | grep -i kctl'
```
Expected: a name ending **`-kctl-1`**. Confirm its prefix equals the
`compose.appName` reported by:
```bash
kctl-dokploy -p idtpp --json compose get <composeId> | python3 -c "import json,sys; print(json.load(sys.stdin)['appName'])"
```
If they do not match, stop and reconcile before creating any schedule.

- [ ] **Step 7: Prove `docker exec` reaches the tools and the secrets**

```bash
ssh root@178.104.169.250 'c=$(docker ps --format "{{.Names}}" | grep -- "-kctl-1" | head -1);
  docker exec "$c" sh -c "command -v jobrun && kctl-hz --version";
  docker exec "$c" sh -c "[ -n \"$IDTPP_S3_ACCESS_KEY\" ] && echo SECRET-PRESENT || echo SECRET-MISSING";
  docker exec "$c" sh -c "test ! -S /var/run/docker.sock && echo NO-DOCKER-SOCK || echo DOCKER-SOCK-PRESENT"'
```
Expected: `jobrun` found, a kctl-hz version, `SECRET-PRESENT`,
`NO-DOCKER-SOCK`. Never echo a secret's value — only its presence.

- [ ] **Step 8: Commit**

```bash
git add deploys/instances/production/tpp-infra-kctl.yaml \
        deploys/env/production/.env.tpp-infra-kctl.example
git commit -m "feat: deploy tpp-infra-kctl toolbox for scheduled jobs

One idle container on tpp-prod-04 that Dokploy schedules exec into. No
schedules yet -- added in the following tasks.

Resolved container name verified against docker ps before any schedule
exists, because a serviceName mismatch is silent and cost this estate five
months of dead schedules.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: Migrate the 10 maintenance jobs

Deliberately first: all 10 are disabled in xyOps and run nowhere today, so
there is nothing to break. This is where the mechanics get learned at zero risk.

**Files:**
- Modify: `deploys/instances/production/tpp-infra-kctl.yaml` (add `schedules:`)
- Modify: `kodemeio-skills/config/kctl-config.yaml` (add service blocks)
- Modify: `deploys/env/production/.env.tpp-infra-kctl{,.example}`

**Interfaces:**
- Consumes: `composeId` from Task 3; `jobrun` from Task 1.
- Produces: 10 schedules, each verified `status: done`.

- [ ] **Step 1: Add the missing service blocks to the kctl config**

In `kodemeio-skills/config/kctl-config.yaml`, add `postgres`, `odoo`, `mailcow`
blocks under `profiles.idtpp`, and a `profiles.kodemeio` with `postgres`,
`odoo`, `dokploy`. Values are `${VAR}` placeholders only. Mirror the shape of
the existing `idtpp.hetzner` block and the field names each CLI expects —
confirm with `kctl-pg config --help`, `kctl-odoo config --help`,
`kctl-mailcow config --help`, `kctl-dokploy config --help`.

Add every new `${VAR}` to both `.env.tpp-infra-kctl` and its `.example`, then
run `just check-env`.

- [ ] **Step 2: Verify the four `kod-*` targets still exist**

`kod-prod-02` was removed from the estate and manifests are known to reference
hosts that no longer exist. Before scheduling a check against them:

```bash
kctl-dokploy -p kodemeio servers list
kctl-pg -p kodemeio health check
kctl-odoo -p kodemeio health check
kctl-dokploy -p kodemeio health check
```
Any target that cannot be reached is **left out of Step 3** and recorded as
still blocked. A scheduled check that cannot reach its service is the "reads as
coverage" failure the xyOps events file warns about.

- [ ] **Step 3: Add the maintenance schedules to the manifest**

Append to `deploys/instances/production/tpp-infra-kctl.yaml`. Drop any entry
whose target failed Step 2.

```yaml
schedules:
  # Every command is wrapped in jobrun: it guards the secrets named in
  # JOBRUN_REQUIRE, enforces a 900s timeout, and emails on failure. Dokploy
  # itself will not tell anyone when one of these fails.
  - name: maint-tpp-pg-bloat
    cron: "0 2 * * *"
    command: "jobrun maint-tpp-pg-bloat kctl-pg -p idtpp bloat check"
    service: kctl
    shell: sh
    timezone: Asia/Jakarta
  - name: maint-kod-pg-bloat
    cron: "0 2 * * *"
    command: "jobrun maint-kod-pg-bloat kctl-pg -p kodemeio bloat check"
    service: kctl
    shell: sh
    timezone: Asia/Jakarta
  - name: maint-tpp-pg-backup
    cron: "30 2 * * *"
    command: "jobrun maint-tpp-pg-backup kctl-pg -p idtpp backup check"
    service: kctl
    shell: sh
    timezone: Asia/Jakarta
  - name: maint-tpp-mailcow-quarantine
    cron: "0 3 * * 0"
    command: "jobrun maint-tpp-mailcow-quarantine kctl-mailcow -p idtpp quarantine cleanup --days 30"
    service: kctl
    shell: sh
    timezone: Asia/Jakarta
  - name: maint-tpp-pg-health
    cron: "0 4 * * *"
    command: "jobrun maint-tpp-pg-health kctl-pg -p idtpp health check"
    service: kctl
    shell: sh
    timezone: Asia/Jakarta
  - name: maint-tpp-odoo-health
    cron: "15 4 * * *"
    command: "jobrun maint-tpp-odoo-health kctl-odoo -p idtpp health check"
    service: kctl
    shell: sh
    timezone: Asia/Jakarta
  - name: maint-tpp-mailcow-health
    cron: "30 4 * * *"
    command: "jobrun maint-tpp-mailcow-health kctl-mailcow -p idtpp health check"
    service: kctl
    shell: sh
    timezone: Asia/Jakarta
  - name: maint-kod-pg-health
    cron: "45 4 * * *"
    command: "jobrun maint-kod-pg-health kctl-pg -p kodemeio health check"
    service: kctl
    shell: sh
    timezone: Asia/Jakarta
  - name: maint-kod-odoo-health
    cron: "45 5 * * *"
    command: "jobrun maint-kod-odoo-health kctl-odoo -p kodemeio health check"
    service: kctl
    shell: sh
    timezone: Asia/Jakarta
  - name: maint-kod-dokploy-health
    cron: "50 5 * * *"
    command: "jobrun maint-kod-dokploy-health kctl-dokploy -p kodemeio health check"
    service: kctl
    shell: sh
    timezone: Asia/Jakarta
```

- [ ] **Step 4: Deploy and confirm the schedules were created**

```bash
just deploy-validate idtpp deploys/instances/production/tpp-infra-kctl.yaml
kctl-dokploy -p idtpp deploy apply -f deploys/instances/production/tpp-infra-kctl.yaml
kctl-dokploy -p idtpp schedules list <composeId> --type compose
```
Expected: 10 schedules listed with `Type=compose` and the right crons.

- [ ] **Step 5: Run every one manually and verify `status: done`**

```bash
uv run python ops/scripts/schedule-status.py --profile idtpp --json \
  | python3 -c "
import json,sys,subprocess
for r in json.load(sys.stdin):
    if r['name'].startswith('maint-'):
        subprocess.run(['kctl-dokploy','-p','idtpp','schedules','run',r['schedule_id']], check=False)
"
sleep 60
uv run python ops/scripts/schedule-status.py --profile idtpp
```
Expected: all `maint-*` rows `healthy=True`. Any `error` is a real bug — read
the log on tpp-prod-04 under `/etc/dokploy/schedules/<appName>/` and fix before
continuing. Do not proceed to Task 5 with a red maintenance job.

- [ ] **Step 6: Disable the 10 xyOps equivalents**

They are already disabled in `events/maintenance.yaml`, so this is a
confirmation, not a change:
```bash
cd ../kodemeio-xyops && uv run python scripts/reconcile.py diff
```
Expected: no drift.

- [ ] **Step 7: Commit**

```bash
git add deploys/instances/production/tpp-infra-kctl.yaml deploys/env/production/.env.tpp-infra-kctl.example
git commit -m "feat: migrate 10 maintenance jobs from xyOps to Dokploy schedules

These were blocked and disabled in xyOps because the deployed kctl config
carried no postgres/odoo/mailcow/dokploy blocks. Moving the config into git
is what unblocked them.

All verified reaching status: done, not merely created.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 5: Migrate the 4 backup alarms and prove alerting works

These run in parallel with xyOps. They are read-only idempotent checks, so
duplicate alerts are harmless — and are themselves evidence the path works.

**Files:**
- Modify: `deploys/instances/production/tpp-infra-kctl.yaml`

**Interfaces:**
- Consumes: Task 3's `composeId`, Task 1's `jobrun`.
- Produces: 4 alarm schedules, plus the single most important proof in this
  plan — that a failure actually reaches a human.

- [ ] **Step 1: Add the four alarms to the manifest**

```yaml
  # Alarms run BEFORE the 06:50/07:00 reports on purpose: a stale backup must
  # be known before the business report goes out. Preserve this ordering.
  #
  # JOBRUN_REQUIRE guards the S3 credentials. kctl-lib's expand_env returns the
  # literal "${IDTPP_S3_SECRET_KEY}" for an unset variable, and without the
  # guard that string is sent to Hetzner as though it were the key.
  - name: backup-tpp
    cron: "0 5 * * *"
    command: "JOBRUN_REQUIRE='IDTPP_S3_ACCESS_KEY IDTPP_S3_SECRET_KEY' jobrun backup-tpp kctl-hz -p idtpp s3 freshness hz-tpp-odoo-filestore --prefix tpp-odoo-erp/snapshots/ --max-age-hours 4"
    service: kctl
    shell: sh
    timezone: Asia/Jakarta
  - name: backup-tpp25
    cron: "10 5 * * *"
    command: "JOBRUN_REQUIRE='IDTPP_S3_ACCESS_KEY IDTPP_S3_SECRET_KEY' jobrun backup-tpp25 kctl-hz -p idtpp s3 freshness hz-tpp-odoo-filestore --prefix tpp25-odoo-erp/snapshots/ --max-age-hours 4"
    service: kctl
    shell: sh
    timezone: Asia/Jakarta
  - name: backup-mac
    cron: "20 5 * * *"
    command: "JOBRUN_REQUIRE='IDTPP_S3_ACCESS_KEY IDTPP_S3_SECRET_KEY' jobrun backup-mac kctl-hz -p idtpp s3 freshness hz-mac-odoo-filestore --prefix mac-odoo-erp/snapshots/ --max-age-hours 4"
    service: kctl
    shell: sh
    timezone: Asia/Jakarta
  - name: backup-mac-hrms
    cron: "30 5 * * *"
    command: "JOBRUN_REQUIRE='IDTPP_S3_ACCESS_KEY IDTPP_S3_SECRET_KEY' jobrun backup-mac-hrms kctl-hz -p idtpp s3 freshness hz-mac-odoo-filestore --prefix mac-odoo-hrms/snapshots/ --max-age-hours 4"
    service: kctl
    shell: sh
    timezone: Asia/Jakarta
```

- [ ] **Step 2: Deploy and run each once**

```bash
kctl-dokploy -p idtpp deploy apply -f deploys/instances/production/tpp-infra-kctl.yaml
uv run python ops/scripts/schedule-status.py --profile idtpp --json \
  | python3 -c "
import json,sys,subprocess
for r in json.load(sys.stdin):
    if r['name'].startswith('backup-'):
        subprocess.run(['kctl-dokploy','-p','idtpp','schedules','run',r['schedule_id']], check=False)
"
sleep 60
uv run python ops/scripts/schedule-status.py --profile idtpp
```
Expected: all four `healthy=True`.

- [ ] **Step 3: Confirm the verdicts match xyOps**

Compare each alarm's output against the xyOps event for the same bucket and
prefix. Both must agree on fresh/stale for all four. A disagreement means the
command or the profile is wrong — fix before trusting either.

- [ ] **Step 4: Prove a failure reaches a human — the critical test**

This is the only step that proves G1 was actually closed rather than assumed
closed because a wrapper exists. Create a temporary schedule pointing at a
prefix that is certainly stale:

```bash
kctl-dokploy -p idtpp schedules create \
  --name zz-alert-proof \
  --cron "0 0 31 12 *" \
  --command "JOBRUN_REQUIRE='IDTPP_S3_ACCESS_KEY IDTPP_S3_SECRET_KEY' jobrun zz-alert-proof kctl-hz -p idtpp s3 freshness hz-tpp-odoo-filestore --prefix definitely/not/a/real/prefix/ --max-age-hours 1" \
  --type compose --compose <composeId> --service kctl \
  --shell sh --timezone Asia/Jakarta

kctl-dokploy -p idtpp schedules run <newScheduleId>
```

Then confirm **all three**:
1. `schedule-status.py` shows `zz-alert-proof` with `last=error`.
2. An email titled `[ALERT] zz-alert-proof failed (exit N)` arrives in the
   `ALERT_TO` inbox. **Check the inbox. Do not infer it from the exit code.**
3. The email body contains the command's real output, not an empty section.

If the mail does not arrive, stop the migration here and fix `jobrun`'s mail
path. Every alarm after this point depends on it.

- [ ] **Step 5: Delete the proof schedule**

```bash
kctl-dokploy -p idtpp schedules delete <newScheduleId> --force
```

- [ ] **Step 6: Run in parallel for one full day, then disable the xyOps alarms**

Leave both schedulers running the alarms for at least 24 h and confirm they
agree every time. Then in `kodemeio-xyops/events/backup-alarms.yaml` set
`enabled: false` on all four, and:
```bash
cd ../kodemeio-xyops && uv run python scripts/reconcile.py apply && uv run python scripts/reconcile.py diff
```
Expected: apply succeeds, diff clean.

- [ ] **Step 7: Commit**

```bash
git add deploys/instances/production/tpp-infra-kctl.yaml
git commit -m "feat: migrate 4 backup freshness alarms to Dokploy schedules

Ran in parallel with xyOps for a full day with matching verdicts before the
xyOps events were disabled.

Alerting proven by inducing a real failure against a known-stale prefix and
confirming the email arrived -- not inferred from the exit code. Dokploy
itself reports nothing when a scheduled job fails.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 6: Migrate the 3 reports — atomic swap

**Not** parallel-safe: two schedulers would mail two copies of a business
report to people. Enable Dokploy's and disable xyOps' in the same sitting.

**Files:**
- Modify: `deploys/instances/production/tpp-infra-kctl.yaml`
- Modify: `kodemeio-xyops/events/reports.yaml`

**Interfaces:**
- Consumes: Task 3's `composeId`, Task 1's `jobrun`.
- Produces: 3 report schedules; xyOps' 3 report events disabled.

- [ ] **Step 1: Add the three reports to the manifest**

`catchup: true` is dropped deliberately — Dokploy has no equivalent. The
watchdog notices a missed report and `schedules run` re-fires it (spec §6.3).

```yaml
  # NOTE: --email-to deliberately targets $REPORT_OWNER, not the team list,
  # exactly as the xyOps events do today. Switching to the team list is a
  # separate, deliberate secret change -- not part of this migration.
  - name: report-selfcheck
    cron: "50 6 * * *"
    command: "JOBRUN_REQUIRE='SMTP_PASS REPORT_OWNER LUMBUNG_YASA_DAGANG_API_TOKEN LUMBUNG_YASA_DAGANG_SIGNATURE_SECRET' jobrun report-selfcheck kctl-accurate reports sales-invoice-summary --profiles lumbung-yasa-dagang --from 2026-08-01 --to-today --email-to \"$REPORT_OWNER\" --out /tmp/selfcheck.xlsx"
    service: kctl
    shell: sh
    timezone: Asia/Jakarta
  - name: report-daily
    cron: "0 7 * * *"
    command: "JOBRUN_REQUIRE='SMTP_PASS REPORT_OWNER' jobrun report-daily kctl-accurate reports sales-invoice-summary --group tpp-trading-active --from 2026-01-01 --to-today --email-to \"$REPORT_OWNER\" --out /tmp/trade_sales_summary.xlsx"
    service: kctl
    shell: sh
    timezone: Asia/Jakarta
  - name: report-weekly
    cron: "0 8 * * 1"
    command: "JOBRUN_REQUIRE='SMTP_PASS REPORT_OWNER REPORT_ARCHIVE' jobrun report-weekly kctl-accurate reports sales-invoice-summary --group tpp-trading-active --from 2026-01-01 --to-today --email-to \"$REPORT_OWNER\" --email-bcc \"$REPORT_ARCHIVE\" --out /tmp/trade_sales_summary.xlsx"
    service: kctl
    shell: sh
    timezone: Asia/Jakarta
```

`report-daily` and `report-weekly` guard only `SMTP_PASS` and the recipients:
the 20 Accurate variables are consumed by the config file, and `kctl-accurate`
fails loudly on a bad token. Listing all 22 in `JOBRUN_REQUIRE` is also correct
if you prefer the stricter guard.

- [ ] **Step 2: Deploy, then run `report-selfcheck` only**

The canary covers a single tenant, so a duplicate is cheap.
```bash
kctl-dokploy -p idtpp deploy apply -f deploys/instances/production/tpp-infra-kctl.yaml
kctl-dokploy -p idtpp schedules run <report-selfcheck scheduleId>
sleep 120
uv run python ops/scripts/schedule-status.py --profile idtpp
```
Expected: `healthy=True`, and the canary email arrives with its xlsx attached.

- [ ] **Step 3: Compare the canary against xyOps' output**

Same row counts, same totals, same attachment name. A mismatch means the
command or the config differs — fix before swapping the real reports.

- [ ] **Step 4: The atomic swap — one sitting, both sides**

Do this in a single session, after that morning's xyOps reports have already
gone out, so no one gets two copies or none.

```bash
# 1. xyOps side: disable all three report events
cd ../kodemeio-xyops
#    edit events/reports.yaml -> enabled: false on all three
uv run python scripts/reconcile.py apply
uv run python scripts/reconcile.py diff     # expect: clean

# 2. Confirm Dokploy's three are enabled and green
cd -
uv run python ops/scripts/schedule-status.py --profile idtpp
```
Expected: xyOps shows all three reports disabled; Dokploy shows all three
`healthy=True`.

- [ ] **Step 5: Watch the next real firing**

The following morning, confirm `report-daily` fired at 07:00 WIB, exactly one
email arrived, and `schedule-status.py` shows `last=done`. On Monday, confirm
`report-weekly` likewise, including the BCC archive copy.

- [ ] **Step 6: Commit**

```bash
git add deploys/instances/production/tpp-infra-kctl.yaml
git commit -m "feat: migrate 3 trade reports to Dokploy schedules

Atomic swap: xyOps' three report events disabled in the same sitting the
Dokploy schedules went live, so no recipient got two copies or none. Same
procedure as the Ofelia to xyOps report cutover.

catchup: true is dropped -- Dokploy has no equivalent. A missed report is
caught by the watchdog and re-fired deliberately via schedules run, which
beats automatically mailing a stale report hours late.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 7: Rewrite the dead-man watchdog

**Files:**
- Create: `ops/scripts/deadman-check.sh`
- Test: `deploys/tests/test_deadman_intervals.py`

**Interfaces:**
- Consumes: `ops/scripts/schedule-status.py` (Task 1 of the incident plan).
- Produces: a host-cron script on tpp-prod-01 that alerts when a schedule stops
  firing, replacing `kodemeio-xyops/scripts/deadman-check.sh`.

**It stays on host cron on tpp-prod-01 and must never become a Dokploy
schedule.** A scheduler cannot report its own death, and if Dokploy is down the
watchdog still has to page. Same reason the Ofelia and xyOps watchdogs live off
the machine they watch.

It checks **every** enabled schedule in the estate, not only the 17 migrated
ones — the existing schedules are exactly the ones nobody was watching.

- [ ] **Step 1: Write the failing test for interval derivation**

Create `deploys/tests/test_deadman_intervals.py`:

```python
"""The watchdog's freshness threshold comes from the cron expression.

Getting this wrong in either direction ruins the watchdog: too tight and it
pages constantly and people mute it; too loose and a dead job stays dead.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "ops" / "scripts" / "deadman_intervals.py"
_spec = importlib.util.spec_from_file_location("deadman_intervals", _SRC)
deadman_intervals = importlib.util.module_from_spec(_spec)
sys.modules["deadman_intervals"] = deadman_intervals
_spec.loader.exec_module(deadman_intervals)


def test_daily_cron_is_one_day():
    from deadman_intervals import interval_minutes

    assert interval_minutes("0 5 * * *") == 1440


def test_weekly_cron_is_one_week():
    from deadman_intervals import interval_minutes

    assert interval_minutes("0 8 * * 1") == 10080


def test_sunday_weekly_cron_is_one_week():
    from deadman_intervals import interval_minutes

    assert interval_minutes("0 3 * * 0") == 10080


def test_grace_is_a_quarter_with_a_thirty_minute_floor():
    from deadman_intervals import threshold_minutes

    assert threshold_minutes(1440) == 1440 + 360
    assert threshold_minutes(60) == 60 + 30       # 15 would be below the floor
    assert threshold_minutes(10) == 10 + 30
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest deploys/tests/test_deadman_intervals.py -q`
Expected: FAIL — `ops/scripts/deadman_intervals.py` does not exist

- [ ] **Step 3: Write the interval helper**

Create `ops/scripts/deadman_intervals.py`:

```python
"""Derive a freshness threshold from a cron expression.

Split out from deadman-check.sh so the arithmetic is testable. The xyOps
version computed this from trigger arrays; a cron string carries the same
information.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from croniter import croniter

WEEK_MINUTES = 7 * 24 * 60


def interval_minutes(cron_expression: str) -> int:
    """Largest gap in minutes between two consecutive firings, capped at a week.

    A job that fires less often than weekly has no meaningful sub-week gap, so
    the whole cycle is returned.
    """
    base = datetime(2026, 1, 5)  # a Monday, so weekday crons land predictably
    it = croniter(cron_expression, base)
    times = [it.get_next(datetime) for _ in range(12)]
    gaps = [
        int((b - a).total_seconds() // 60)
        for a, b in zip(times, times[1:], strict=False)
    ]
    if not gaps:
        return WEEK_MINUTES
    return min(max(gaps), WEEK_MINUTES)


def threshold_minutes(interval: int) -> int:
    """Interval plus a grace period of a quarter, with a 30-minute floor."""
    return interval + max(interval // 4, 30)


def is_stale(cron_expression: str, last_started: datetime, now: datetime) -> bool:
    threshold = threshold_minutes(interval_minutes(cron_expression))
    return now - last_started > timedelta(minutes=threshold)
```

Add `croniter` to the repo's dependencies:
```bash
uv add croniter
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest deploys/tests/test_deadman_intervals.py -q`
Expected: PASS, 4 passed

- [ ] **Step 5: Write the watchdog**

Create `ops/scripts/deadman-check.sh`. It reuses `schedule-status.py`'s
collection and adds staleness:

```bash
#!/usr/bin/env bash
# Dokploy schedule dead-man check -- runs from HOST CRON on tpp-prod-01.
#
# Deliberately NOT a Dokploy schedule and deliberately not on tpp-prod-04. A
# scheduler cannot report its own death, and if Dokploy is down the watchdog
# still has to page. Same reason the Ofelia and xyOps watchdogs lived off the
# machine they watched.
#
# Alerts when:
#   - the Dokploy API is unreachable
#   - credentials are missing or empty (itself an alert condition, never a
#     reason to go quiet)
#   - an ENABLED schedule has no run inside its own interval plus grace
#   - an ENABLED schedule's most recent run did not reach status: done
#   - the tpp-infra-kctl toolbox container is not running -- the single
#     failure that silently kills all 17 jobs at once
#
# Disabled schedules are SKIPPED and reported as skipped in the log, never by
# email. A watchdog that pages for jobs nobody expects to run is one people
# learn to ignore.
#
# Install: /opt/kodemeio/deadman-check.sh, chmod 755
# Cron:    15 8 * * *   TZ=Asia/Jakarta   (08:15 WIB, after the 07:00 report)
# Creds:   /opt/kodemeio/reports-smtp.env (mode 600) -- SMTP_PASS, ALERT_TO
set -uo pipefail

SMTP_ENV="${SMTP_ENV:-/opt/kodemeio/reports-smtp.env}"
KCTL_PROFILE="${KCTL_PROFILE:-idtpp}"
TOOLBOX_HOST="${TOOLBOX_HOST:-178.104.169.250}"
PROBLEMS=""
NOTES=""

# --- Credentials. A missing file is itself an alert condition: record it,
# --- still try to mail, still exit non-zero. Never go quiet.
if [[ -r "$SMTP_ENV" ]]; then
  set -a; . "$SMTP_ENV"; set +a
else
  PROBLEMS="CREDENTIALS MISSING: $SMTP_ENV is not readable."
fi
ALERT_TO="${ALERT_TO:-trigunawan.note@gmail.com}"

# --- 1. Toolbox container alive? The single failure that silently kills all
# --- 17 jobs at once, and the one a schedule-history check cannot see.
if ! ssh -o BatchMode=yes -o ConnectTimeout=10 "root@${TOOLBOX_HOST}" \
      'docker ps --format "{{.Names}}" | grep -q -- "-kctl-1"' 2>/dev/null; then
  PROBLEMS="${PROBLEMS}
TOOLBOX DOWN: no running *-kctl-1 container on ${TOOLBOX_HOST}. Every scheduled job is dead."
fi

# --- 2. Every enabled schedule has a fresh, successful run.
STATUS_JSON=$(python3 /opt/kodemeio/schedule-status.py --profile "$KCTL_PROFILE" --json 2>/dev/null)
if [[ -z "$STATUS_JSON" ]]; then
  PROBLEMS="${PROBLEMS}
DOKPLOY UNREACHABLE: could not list schedules for profile ${KCTL_PROFILE}."
else
  REPORT=$(SCHEDULES="$STATUS_JSON" python3 - <<'PYEOF'
import json, os, sys
from datetime import datetime, timezone
sys.path.insert(0, "/opt/kodemeio")
from deadman_intervals import interval_minutes, threshold_minutes

now = datetime.now(timezone.utc)
problems, notes = [], []
for r in json.loads(os.environ["SCHEDULES"]):
    label = f"{r.get('app','?')}/{r['name']}"
    if not r["enabled"]:
        notes.append(f"{label} is disabled -- freshness check skipped.")
        continue
    if r["total"] == 0:
        problems.append(f"NO RUNS: {label} is enabled but has never run.")
        continue
    if r["last_status"] != "done":
        problems.append(f"FAILED: {label} most recent run status is {r['last_status']!r}, not done.")
        continue
    started = datetime.fromisoformat(r["last_started"].replace("Z", "+00:00"))
    age = int((now - started).total_seconds() // 60)
    threshold = threshold_minutes(interval_minutes(r["cron"]))
    if age > threshold:
        problems.append(
            f"STALE: {label} last ran {age}m ago; cron {r['cron']!r} expects a run "
            f"within {threshold}m (interval plus grace)."
        )
print(json.dumps({"problems": problems, "notes": notes}))
PYEOF
  )
  while IFS= read -r line; do [[ -n "$line" ]] && PROBLEMS="${PROBLEMS}
${line}"; done < <(jq -r '.problems[]' <<<"$REPORT")
  while IFS= read -r line; do [[ -n "$line" ]] && NOTES="${NOTES}
${line}"; done < <(jq -r '.notes[]' <<<"$REPORT")
fi

# --- Report -----------------------------------------------------------------
[[ -n "$NOTES" ]] && printf '%s
' "$NOTES"

if [[ -z "$PROBLEMS" ]]; then
  echo "$(date '+%F %T') OK"
  exit 0
fi

BODY="Dokploy schedule DEAD-MAN CHECK -- PROBLEMS DETECTED
Host: $(hostname)   Time: $(TZ=Asia/Jakarta date '+%F %T %Z')

${PROBLEMS}
--
Investigate:
  python3 /opt/kodemeio/schedule-status.py --profile ${KCTL_PROFILE}
  ssh root@${TOOLBOX_HOST} 'docker ps | grep kctl'
  ssh root@${TOOLBOX_HOST} 'ls -t /etc/dokploy/schedules/*/*.log | head'
"
echo "$(date '+%F %T') ALERT" >&2

if [[ -z "${SMTP_PASS:-}" ]]; then
  echo "FATAL: SMTP_PASS unavailable -- cannot send the alert mail either." >&2
  exit 1
fi

ALERT_TO="$ALERT_TO" BODY="$BODY" python3 - <<'PYEOF'
import os, smtplib, ssl
from email.message import EmailMessage
m = EmailMessage()
m["From"] = "TPP Ops <reports@idtpp.com>"
m["To"] = os.environ["ALERT_TO"]
m["Subject"] = "[ALERT] Dokploy schedules are UNHEALTHY"
m.set_content(os.environ["BODY"])
s = smtplib.SMTP(os.environ.get("SMTP_HOST", "mail.idtpp.com"), 587, timeout=60)
s.starttls(context=ssl.create_default_context())
s.login(os.environ.get("SMTP_USER", "reports@idtpp.com"), os.environ["SMTP_PASS"])
s.send_message(m); s.quit()
print("alert sent")
PYEOF
exit 1
```

This deliberately mirrors `kodemeio-xyops/scripts/deadman-check.sh`: disabled
schedules are noted but never mailed, missing credentials are an alert rather
than a reason to go quiet, and the script exits non-zero whenever it alerted.

- [ ] **Step 6: Verify it reports OK against the live estate**

```bash
./ops/scripts/deadman-check.sh
```
Expected: exit 0 and `OK`, given Tasks 4–6 are green.

- [ ] **Step 7: Verify it actually alerts**

Disable one maintenance schedule, re-run, and confirm the alert email arrives.
Then re-enable it.
```bash
kctl-dokploy -p idtpp schedules update <a maint scheduleId> --disabled
./ops/scripts/deadman-check.sh   # expect: non-zero, and an email
kctl-dokploy -p idtpp schedules update <that scheduleId> --enabled
```

A disabled schedule is *skipped*, not alerted, so this specifically tests the
staleness path — confirm the alert names the right schedule and the right
reason. If it goes quiet instead, the watchdog is useless; fix before Step 8.

- [ ] **Step 8: Install on tpp-prod-01 and retire the xyOps watchdog**

The watchdog calls `/opt/kodemeio/schedule-status.py`, so **all three** files
must be installed — and tpp-prod-01 needs `kctl-dokploy` and `croniter`
available to the same `python3`, because `schedule-status.py` imports
`kctl_dokploy.core.client` and `deadman_intervals` imports `croniter`.

```bash
scp ops/scripts/deadman-check.sh \
    ops/scripts/deadman_intervals.py \
    ops/scripts/schedule-status.py \
    root@178.104.127.104:/opt/kodemeio/

ssh root@178.104.127.104 '
  chmod 755 /opt/kodemeio/deadman-check.sh
  python3 -c "import kctl_dokploy, croniter; print(\"deps OK\")" \
    || pip install --user "kctl-dokploy==0.16.6" croniter
  python3 /opt/kodemeio/schedule-status.py --profile idtpp >/dev/null && echo "status tool OK"
  crontab -l
'
```
Expected: `deps OK` (or a successful install) and `status tool OK`. The host
also needs a `~/.config/kodemeio/config.yaml` carrying the `idtpp.dokploy`
profile with an API key — confirm before relying on the watchdog.
Replace the xyOps watchdog's crontab entries with the new one. Keep the old
script on disk until Task 9 closes the rollback window.

- [ ] **Step 9: Commit**

```bash
git add ops/scripts/deadman-check.sh ops/scripts/deadman_intervals.py \
        deploys/tests/test_deadman_intervals.py pyproject.toml uv.lock
git commit -m "feat: rewrite dead-man watchdog against the Dokploy schedule API

Reads run history from /deployment.allByType instead of xyOps'
get_events/search_jobs. Stays on host cron on tpp-prod-01: a scheduler
cannot report its own death.

Checks every enabled schedule in the estate, not just the migrated 17 --
the pre-existing schedules are exactly the ones nobody was watching, and 16
of them failed for five months unnoticed.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 8: Make git authoritative again

**Repo:** `kodemeio-skills` (items 1–3), then this repo (item 4)

Without this, `phase_schedules` stays create-only: editing a cron in git
silently does nothing, and nothing detects a UI edit. That is strictly weaker
than the `reconcile.py` guarantee xyOps had, so it must land before xyOps is
decommissioned.

**Files:**
- Modify: `kctl-dokploy` `core/manifest.py` (`ScheduleConfig`)
- Modify: `kctl-dokploy` `core/deploy/orchestrator.py` (`phase_schedules`)
- Modify: `kctl-dokploy` `commands/schedules.py` (add `--service` to `update`)
- Create: `.github/workflows/schedule-drift.yml` in this repo

- [ ] **Step 1: Add `enabled` to `ScheduleConfig`**

In `core/manifest.py`, add `enabled: bool = True` to `ScheduleConfig`
(currently `name`/`cron`/`command`/`service`/`shell`/`timezone` at line 86).

- [ ] **Step 2: Add `--service` and `--timezone` to `schedules update`**

`commands/schedules.py`'s `update` exposes only `--name/--cron/--command/
--enabled`, though `schedule.update` accepts `serviceName` and `timezone`. That
gap is why the incident plan had to delete-and-recreate 14 schedules. Add both
options and map them to `serviceName` and `timezone` in the payload.

- [ ] **Step 3: Turn `phase_schedules` into a reconciler**

In `core/deploy/orchestrator.py:1055`, replace the create-only loop. Key on
`name`. For each manifest schedule: create if absent; if present and any of
cron/command/service/shell/timezone/enabled differ, call `schedule.update`.
Delete live schedules absent from the manifest only when an explicit `--prune`
flag is set. Record created/updated/pruned counts in the phase result.

- [ ] **Step 4: Add a read-only drift check**

Add `kctl-dokploy deploy schedules-diff -f <manifest>`: report differences
between the manifest and live, exit non-zero on any divergence, change nothing.
This mirrors `reconcile.py diff`.

- [ ] **Step 5: Test the reconciler**

Write unit tests in `kctl-dokploy`'s test suite covering: create when absent;
update when cron differs; update when service differs; disable when
`enabled: false`; no-op when identical (running apply twice must be a no-op);
prune only under the flag. Run the package's suite and confirm green.

- [ ] **Step 6: Wire drift detection into CI in this repo**

Create `.github/workflows/schedule-drift.yml` running
`kctl-dokploy -p idtpp deploy schedules-diff -f deploys/instances/production/tpp-infra-kctl.yaml`
on push, pull request, and hourly — mirroring the xyOps drift workflow it
replaces.

- [ ] **Step 7: Prove drift is actually detected**

Change one schedule's cron in the Dokploy UI, run the drift check, confirm
non-zero and that the output names that schedule. Run `deploy apply`, confirm
the drift check returns to zero.

- [ ] **Step 8: Commit**

```bash
git commit -m "feat: make phase_schedules a real reconciler with drift detection

phase_schedules only created schedules -- it never updated, enabled,
disabled or pruned, so editing a cron in git silently did nothing and a UI
edit was undetectable. That is strictly weaker than the reconcile.py
guarantee xyOps had.

Also adds --service and --timezone to schedules update; their absence forced
delete-and-recreate when fixing 14 broken schedules.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 9: Decommission xyOps

**Do not start until 14 days have passed** since Task 6 with no missed job and
no silent failure.

**Files:**
- Delete: `deploys/instances/production/tpp-infra-xyops.yaml`
- Delete: `deploys/instances/production/tpp-infra-xyops-backup.yaml`
- Modify: `docs/architecture.md`

- [ ] **Step 1: Confirm the rollback window is clean**

```bash
uv run python ops/scripts/schedule-status.py --profile idtpp
ssh root@178.104.127.104 'grep -c ALERT /var/log/deadman-check.log || true'
```
Expected: exit 0, and no unexplained alerts across the 14 days. Any missed job
restarts the clock — this is the last cheap moment to abort.

- [ ] **Step 2: Confirm every xyOps event is disabled**

```bash
cd ../kodemeio-xyops && uv run python scripts/reconcile.py diff
```
Expected: clean, with all 17 events disabled.

- [ ] **Step 3: Take a final backup of the xyOps data volume and prove it restores**

Run the existing restic backup once more and verify the restore the way it was
verified on 2026-08-15 (`PRAGMA integrity_check` on the restored SQLite file).
A backup that has not been restored is not a backup.

- [ ] **Step 4: Remove both Dokploy apps**

```bash
kctl-dokploy -p idtpp compose list | grep xyops   # confirm the two IDs first
```
Then delete `tpp-infra-xyops` and `tpp-infra-xyops-backup` through Dokploy.
Confirm the containers are gone on tpp-prod-04 and that
`docker volume ls | grep xyops` shows what remains.

- [ ] **Step 5: Retain the vault key, delete the manifests**

Keep `XYOPS_SECRET_KEY` in 1Password until the final data-volume backup is
discarded — the key is worthless without the volume, but the volume is
unrecoverable without the key. Note the retention decision and its expiry date
in 1Password.

```bash
git rm deploys/instances/production/tpp-infra-xyops.yaml \
       deploys/instances/production/tpp-infra-xyops-backup.yaml
```
Leave `deploys/env/production/.env.tpp-infra-xyops*` in place until the backup
is discarded; they are gitignored and hold the only copy of some values.

- [ ] **Step 6: Update the architecture doc and remove the old watchdog**

Record in `docs/architecture.md` that scheduled work is now native Dokploy
schedules on `tpp-infra-kctl`, watched by `ops/scripts/deadman-check.sh` on
tpp-prod-01. Remove the superseded xyOps watchdog from
`/opt/kodemeio/` on tpp-prod-01.

- [ ] **Step 7: Commit**

```bash
git add -A deploys/instances/production docs/architecture.md
git commit -m "chore: decommission xyOps conductor and its backup stack

All 17 jobs have run as native Dokploy schedules for 14 days with no missed
run and no silent failure. Removes two Dokploy apps, a restic backup stack,
a root-equivalent docker.sock mount on tpp-prod-04, and XYOPS_SECRET_KEY as
a single point of total loss.

The vault key stays in 1Password until the final data-volume backup is
discarded: it is worthless without the volume, and the volume is
unrecoverable without it.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Done when

- All 17 jobs run as Dokploy schedules and `ops/scripts/schedule-status.py
  --profile idtpp` exits 0.
- A deliberately induced failure produced an email in the `ALERT_TO` inbox
  (Task 5 Step 4).
- The watchdog alerts on a stale schedule and is installed on tpp-prod-01.
- Drift is detected in CI and cleared by `deploy apply`.
- `tpp-infra-xyops` and `tpp-infra-xyops-backup` no longer exist.

## Still open after this plan

- **Ofelia.** `tpp-ofelia-reports` is still deployed. Retiring xyOps alone takes
  the estate from three schedulers to two, not one. Sequence Ofelia's
  decommissioning immediately after Task 6, since the same reports are involved.
- **`schedules list` leaking env in cleartext** (spec §3.4 item 4). Task 8 does
  not fix it. It matters more once the toolbox holds 25 secrets.
- **The team-list switch** for `report-daily` / `report-weekly`. Both still mail
  `$REPORT_OWNER`, as they do under xyOps today. That is a deliberate secret
  change, not part of this migration.
