# xyOps + Ofelia → Dokploy Schedules Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move all 17 scheduled jobs off xyOps and Ofelia onto native Dokploy schedules, then decommission both schedulers.

**Architecture:** One new compose app, `tpp-infra-kctl`, on tpp-prod-04 holds an
idle container with the pinned `kodemeio-cli` image, the kctl config, the job
secrets, and **one script per job** at `/opt/kctl/jobs/<name>.sh`. Each Dokploy
schedule's command is a bare `jobrun <name>` — nothing else. `jobrun` guards the
job's secrets, enforces a timeout and log cap, and emails on failure, which
Dokploy cannot do at all. A rewritten dead-man watchdog on tpp-prod-01 catches
jobs that never fire.

**Tech Stack:** Docker Compose, Dokploy schedules, Python 3.12, `uv`, `pytest`,
`ruff`, `kctl-dokploy` 0.16.6, POSIX `sh`, `bash`, host cron

**Spec:** `docs/superpowers/specs/2026-08-31-xyops-to-dokploy-schedules-design.md`

## Global Constraints

- **NO ODOO DOWNTIME.** This migration touches no Odoo app, no Odoo image and
  no Odoo container. `tpp-infra-kctl` is a brand-new compose app and all 17
  jobs call remote APIs. If a step in this plan would restart an Odoo service,
  the step is wrong — stop.
- **A schedule's `command` must be a bare `jobrun <name>`.** Dokploy passes the
  command to a shell WITHOUT escaping. Forbidden anywhere in a command:
  `'` `(` `)` `<` `>` `|` `&` `;` `$` and backtick. Such a command dies before
  Dokploy logs `Running command:`, leaving a 22-byte log reading only
  `Initializing schedule` — with no alert. All arguments, quoting and secret
  lists live inside the job script.
- Always pass an explicit `kctl-dokploy` profile. TPP work uses `-p idtpp`;
  `kod-*` targets require `-p kodemeio`.
- **Timezone:** every schedule sets `timezone: Asia/Jakarta` explicitly.
- **Image pinning:** `ghcr.io/tgunawandev/kodemeio-cli:sha-<shortsha>`, never
  `latest`. The GHCR name is retained after the repo rename to
  `kodemeio-skills` — it is the image name, not the repo.
- **Compose requirements:** `restart: unless-stopped`; `deploy.resources.limits`
  with both `cpus` and `memory`; a healthcheck; external `dokploy-network`;
  no published ports.
- **Secrets:** never in argv, logs, committed files, or terminal output. Every
  `.env` has a sanitized `.env.example`.
- **Guard:** every job asserts its required variables are non-empty and contain
  no literal `${`, exiting 78 before any work. `expand_env`
  (`kctl-lib/config.py:33`) returns the literal `${VAR}` for an unset variable
  rather than raising, so an unguarded job sends that string to a remote API as
  though it were the credential.
- **`name` is the reconciliation key and is immutable.** Renaming a schedule in
  git creates a new one and orphans the old.
- **A schedule is "working" only when a real run reports `status: done`**, read
  via `ops/scripts/schedule-status.py`. Never "the CLI said OK".
- **xyOps and Ofelia stay deployed and functional** until Task 9. They are the
  rollback path.
- Python tooling is `uv`, never pip. Conventional Commits ending with
  `Co-Authored-By: Claude <noreply@anthropic.com>`.

## Prerequisites

1. **`2026-08-31-fix-dokploy-schedule-failures.md` Tasks 1–2 are complete**
   (they are, as of `2c37ef2`). That plan built `ops/scripts/schedule-status.py`
   — the only working way to read schedule run history — and proved the
   compose-exec mechanism works in this estate (10 schedules green).
2. **Two repos.** Tasks 1–2 and 8 land in `kodemeio-skills`; the rest here.
   This repo must not host `kctl-*` source (`CLAUDE.md`).

## Scope

**7 jobs migrate** — the 4 backup alarms and 3 reports that actually run today.
The 10 maintenance jobs are DEFERRED (see Task 4): every one invokes a command
that does not exist, and they have never run. Ofelia contributes no job xyOps
lacks — its 3 live jobs are the same 3 reports.

| Dokploy `name` | Cron | WIB | xyOps | Ofelia |
|---|---|---|---|---|
| `report-selfcheck` | `50 6 * * *` | 06:50 | enabled | live |
| `report-daily` | `0 7 * * *` | 07:00 | enabled | live |
| `report-weekly` | `0 8 * * 1` | Mon 08:00 | enabled | **live, and the only one mailing the team** |
| `backup-tpp` | `0 5 * * *` | 05:00 | enabled | commented out |
| `backup-tpp25` | `10 5 * * *` | 05:10 | enabled | commented out |
| `backup-mac` | `20 5 * * *` | 05:20 | enabled | commented out |
| `backup-mac-hrms` | `30 5 * * *` | 05:30 | enabled | commented out |
| `maint-tpp-pg-bloat` | `0 2 * * *` | 02:00 | disabled | — |
| `maint-kod-pg-bloat` | `0 2 * * *` | 02:00 | disabled | — |
| `maint-tpp-pg-backup` | `30 2 * * *` | 02:30 | disabled | — |
| `maint-tpp-mailcow-quarantine` | `0 3 * * 0` | Sun 03:00 | disabled | — |
| `maint-tpp-pg-health` | `0 4 * * *` | 04:00 | disabled | — |
| `maint-tpp-odoo-health` | `15 4 * * *` | 04:15 | disabled | — |
| `maint-tpp-mailcow-health` | `30 4 * * *` | 04:30 | disabled | — |
| `maint-kod-pg-health` | `45 4 * * *` | 04:45 | disabled | — |
| `maint-kod-odoo-health` | `45 5 * * *` | 05:45 | disabled | — |
| `maint-kod-dokploy-health` | `50 5 * * *` | 05:50 | disabled | — |

Alarms land before the 06:50/07:00 reports on purpose — a stale backup must be
known before the business report goes out. Preserve that ordering.

**Explicitly NOT in scope: `ofelia-mailcow`** (`compose-…-ofelia-mailcow-1` on
tpp-prod-01, up 4 months). That is Mailcow's own internal scheduler — dovecot,
sogo and php-fpm jobs driven by container labels on the upstream Mailcow stack.
It is vendor-managed. Migrating or stopping it would break Mailcow.

**`phase_schedules` is create-only** until Task 8. That makes staged rollout
natural: add schedules to the manifest in phase order and redeploy, and each
deploy creates only what is new. Changing an *existing* schedule before Task 8
must be done with `ops/scripts/fix-odoo-schedules.py`'s update-in-place pattern
or a direct `schedule.update` call.

---

### Task 1: `jobrun` and the 17 job scripts

**Repo:** `kodemeio-skills`

**Files:**
- Create: `docker/jobrun`
- Create: `docker/jobs/<name>.sh` × 17
- Modify: `docker/Dockerfile.cli`
- Test: `tests/test_jobrun.sh`

**Interfaces:**
- Consumes: nothing.
- Produces: `/usr/local/bin/jobrun` and `/opt/kctl/jobs/*.sh` in the image.
  `jobrun <name>` resolves `/opt/kctl/jobs/<name>.sh`, reads that script's
  `REQUIRE=` declaration, guards those variables, runs it under `timeout`, and
  emails on failure. Exit code is the job's own, or 78 on a guard failure, or
  2 on misuse (unknown job, no argument).

- [ ] **Step 1: Write the failing test**

Create `tests/test_jobrun.sh`:

```bash
#!/usr/bin/env bash
# jobrun's contract. Every assertion is a failure mode that would make a
# scheduled alarm silently useless.
set -uo pipefail

JOBRUN="${JOBRUN:-docker/jobrun}"
JOBS_DIR="$(mktemp -d)"
export JOBRUN_JOBS_DIR="$JOBS_DIR"
fails=0
check() { if [ "$2" = "$3" ]; then echo "ok   - $1"; else echo "FAIL - $1: expected $2, got $3"; fails=$((fails+1)); fi; }

printf '#!/bin/sh\nexit 0\n'                        > "$JOBS_DIR/t-ok.sh"
printf '#!/bin/sh\nexit 42\n'                       > "$JOBS_DIR/t-fail.sh"
printf '#!/bin/sh\n# REQUIRE: MISSING_VAR\necho SHOULD_NOT_RUN\n' > "$JOBS_DIR/t-guard.sh"
printf '#!/bin/sh\nsleep 10\n'                      > "$JOBS_DIR/t-slow.sh"
chmod +x "$JOBS_DIR"/*.sh

JOBRUN_NOTIFY=echo "$JOBRUN" t-ok >/dev/null 2>&1
check "success exits 0" 0 $?

JOBRUN_NOTIFY=echo "$JOBRUN" t-fail >/dev/null 2>&1
check "failure propagates real exit code" 42 $?

out=$(JOBRUN_NOTIFY=echo "$JOBRUN" t-guard 2>&1); rc=$?
check "unset REQUIRE var exits 78" 78 $rc
case "$out" in *SHOULD_NOT_RUN*) echo "FAIL - guard ran the job anyway"; fails=$((fails+1));; *) echo "ok   - guard blocks execution";; esac

MISSING_VAR='${SOME_SECRET}' JOBRUN_NOTIFY=echo "$JOBRUN" t-guard >/dev/null 2>&1
check "unexpanded \${} exits 78" 78 $?

MISSING_VAR="" JOBRUN_NOTIFY=echo "$JOBRUN" t-guard >/dev/null 2>&1
check "empty REQUIRE var exits 78" 78 $?

MISSING_VAR=real JOBRUN_NOTIFY=echo "$JOBRUN" t-guard >/dev/null 2>&1
check "satisfied guard runs the job" 0 $?

JOBRUN_NOTIFY=echo JOBRUN_TIMEOUT=1 "$JOBRUN" t-slow >/dev/null 2>&1
rc=$?; [ "$rc" -ne 0 ] && echo "ok   - timeout kills and fails" || { echo "FAIL - timeout returned 0"; fails=$((fails+1)); }

# Misuse must be LOUD. A wrapper that silently no-ops recreates the incident.
JOBRUN_NOTIFY=echo "$JOBRUN" >/dev/null 2>&1
check "no args exits 2" 2 $?
JOBRUN_NOTIFY=echo "$JOBRUN" no-such-job >/dev/null 2>&1
check "unknown job exits 2" 2 $?

n=$(JOBRUN_NOTIFY=echo "$JOBRUN" t-fail 2>&1 | grep -c 'JOBRUN-ALERT')
[ "$n" -eq 1 ] && echo "ok   - failure notifies once" || { echo "FAIL - notifier called $n times"; fails=$((fails+1)); }
n=$(JOBRUN_NOTIFY=echo "$JOBRUN" t-ok 2>&1 | grep -c 'JOBRUN-ALERT')
[ "$n" -eq 0 ] && echo "ok   - success is quiet" || { echo "FAIL - success notified"; fails=$((fails+1)); }

rm -rf "$JOBS_DIR"
echo; [ "$fails" -eq 0 ] && { echo "ALL PASS"; exit 0; } || { echo "$fails FAILED"; exit 1; }
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `chmod +x tests/test_jobrun.sh && ./tests/test_jobrun.sh`
Expected: FAIL — `docker/jobrun` does not exist

- [ ] **Step 3: Write `jobrun`**

Create `docker/jobrun`:

```sh
#!/bin/sh
# Run one scheduled job by NAME, and make sure a failure is never silent.
#
# Usage: jobrun <job-name>        -- and nothing else on the command line.
#
# WHY THE NAME IS THE ONLY ARGUMENT
# Dokploy passes a schedule's `command` to a shell WITHOUT escaping shell
# metacharacters. A command containing ' ( ) < > | & ; or $ dies before
# Dokploy logs its "Running command:" line, leaving a 22-byte log reading only
# "Initializing schedule" -- and no alert, because Dokploy has no failure
# notification for scheduled jobs at all. So the command field carries a bare
# name, and every argument, quote and secret list lives in the job script.
# Ofelia has the same limitation and the same fix (/opt/kodemeio/run-report.sh).
#
#   JOBRUN_JOBS_DIR  where job scripts live (default /opt/kctl/jobs)
#   JOBRUN_TIMEOUT   seconds before the job is killed (default 900)
#   JOBRUN_LOG_MAX   bytes of output retained for the alert (default 5 MiB)
#   JOBRUN_NOTIFY    override the notifier; used by tests
set -u

JOBS_DIR="${JOBRUN_JOBS_DIR:-/opt/kctl/jobs}"
JOB="${1:-}"
[ -z "$JOB" ] && { echo "jobrun: FATAL: no job name given" >&2; exit 2; }
[ "$#" -gt 1 ] && { echo "jobrun: FATAL: jobrun takes ONE argument (the job name); got: $*" >&2; exit 2; }

SCRIPT="${JOBS_DIR}/${JOB}.sh"
# An unknown job must be a hard error. Exiting 0 here would make a typo in a
# schedule look like a healthy job forever -- the exact incident this replaces.
[ -f "$SCRIPT" ] || { echo "jobrun: FATAL: no job script at ${SCRIPT}" >&2; exit 2; }

TIMEOUT="${JOBRUN_TIMEOUT:-900}"
LOG_MAX="${JOBRUN_LOG_MAX:-5242880}"
OUT="$(mktemp)"
trap 'rm -f "$OUT"' EXIT

notify() {  # notify <subject> <body-file>
    if [ -n "${JOBRUN_NOTIFY:-}" ]; then "$JOBRUN_NOTIFY" "JOBRUN-ALERT $1"; return; fi
    SUBJECT="$1" BODY_FILE="$2" JOB_NAME="$JOB" python3 - <<'PYEOF' \
        || echo "jobrun: FATAL: alert mail FAILED for '$JOB' -- this failure is now silent" >&2
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
m.set_content(f"job:  {os.environ['JOB_NAME']}\nhost: {socket.gethostname()}\n\n--- output ---\n{body}\n")
s = smtplib.SMTP(os.environ.get("SMTP_HOST", "mail.idtpp.com"),
                 int(os.environ.get("SMTP_PORT", "587")), timeout=60)
s.starttls(context=ssl.create_default_context())
s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASS"])
s.send_message(m); s.quit()
PYEOF
}

# --- Guard -----------------------------------------------------------------
# Each job script declares its own required variables in a comment line:
#     # REQUIRE: SMTP_PASS REPORT_OWNER
# kctl-lib's expand_env returns the LITERAL "${VAR}" for an unset variable
# rather than raising, so without this guard that literal is handed to a remote
# API as a credential and the job fails at authentication instead of at config
# load -- a far more confusing failure that can look like a service outage.
REQUIRED="$(sed -n 's/^# *REQUIRE: *//p' "$SCRIPT" | tr '\n' ' ')"
for v in $REQUIRED; do
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
timeout "$TIMEOUT" sh "$SCRIPT" > "$OUT" 2>&1
CODE=$?

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

- [ ] **Step 5: Write the 4 alarm job scripts**

Create `docker/jobs/backup-tpp.sh` (the other three are identical but for the
bucket and prefix — write all four):

```sh
#!/bin/sh
# REQUIRE: IDTPP_S3_ACCESS_KEY IDTPP_S3_SECRET_KEY
set -eu
# kctl-hz does not propagate the global -p flag to `s3 freshness`, so the
# profile must be exported as well as passed.
export KCTL_HZ_PROFILE=idtpp
exec kctl-hz -p idtpp s3 freshness hz-tpp-odoo-filestore \
    --prefix tpp-odoo-erp/snapshots/ --max-age-hours 4
```

| Script | bucket | `--prefix` |
|---|---|---|
| `backup-tpp.sh` | `hz-tpp-odoo-filestore` | `tpp-odoo-erp/snapshots/` |
| `backup-tpp25.sh` | `hz-tpp-odoo-filestore` | `tpp25-odoo-erp/snapshots/` |
| `backup-mac.sh` | `hz-mac-odoo-filestore` | `mac-odoo-erp/snapshots/` |
| `backup-mac-hrms.sh` | `hz-mac-odoo-filestore` | `mac-odoo-hrms/snapshots/` |

- [ ] **Step 6: Write the 3 report job scripts**

`docker/jobs/report-selfcheck.sh`:

```sh
#!/bin/sh
# REQUIRE: SMTP_PASS REPORT_OWNER LUMBUNG_YASA_DAGANG_API_TOKEN LUMBUNG_YASA_DAGANG_SIGNATURE_SECRET
set -eu
export SMTP_HOST=mail.idtpp.com SMTP_PORT=587 SMTP_USER=reports@idtpp.com
export MAIL_FROM="TPP Trade Reports <reports@idtpp.com>"
# Small, fast canary: proves the whole scheduler -> report -> mail chain.
exec kctl-accurate reports sales-invoice-summary \
    --profiles lumbung-yasa-dagang --from 2026-08-01 --to-today \
    --email-to "$REPORT_OWNER" --out /tmp/selfcheck.xlsx
```

`docker/jobs/report-daily.sh`:

```sh
#!/bin/sh
# REQUIRE: SMTP_PASS REPORT_OWNER
set -eu
export SMTP_HOST=mail.idtpp.com SMTP_PORT=587 SMTP_USER=reports@idtpp.com
export MAIL_FROM="TPP Trade Reports <reports@idtpp.com>"
exec kctl-accurate reports sales-invoice-summary \
    --group tpp-trading-active --from 2026-01-01 --to-today \
    --email-to "$REPORT_OWNER" --out /tmp/trade_sales_summary.xlsx
```

`docker/jobs/report-weekly.sh`:

```sh
#!/bin/sh
# REQUIRE: SMTP_PASS REPORT_TEAM REPORT_ARCHIVE
set -eu
export SMTP_HOST=mail.idtpp.com SMTP_PORT=587 SMTP_USER=reports@idtpp.com
export MAIL_FROM="TPP Trade Reports <reports@idtpp.com>"
# --email-to is the TEAM, matching what Ofelia's run-report.sh sends today.
# xyOps' version mails only the owner; if this shipped that way, retiring
# Ofelia would silently stop the team's weekly report.
exec kctl-accurate reports sales-invoice-summary \
    --group tpp-trading-active --from 2026-01-01 --to-today \
    --email-to "$REPORT_TEAM" --email-bcc "$REPORT_ARCHIVE" \
    --out /tmp/trade_sales_summary.xlsx
```

- [ ] **Step 7: Write the 10 maintenance job scripts**

Each is three lines. `REQUIRE:` stays empty until Task 4 Step 1 adds the
config blocks and their variables — then it names them.

```sh
#!/bin/sh
# REQUIRE:
set -eu
exec kctl-pg -p idtpp bloat check
```

| Script | command |
|---|---|
| `maint-tpp-pg-bloat.sh` | `kctl-pg -p idtpp bloat check` |
| `maint-kod-pg-bloat.sh` | `kctl-pg -p kodemeio bloat check` |
| `maint-tpp-pg-backup.sh` | `kctl-pg -p idtpp backup check` |
| `maint-tpp-mailcow-quarantine.sh` | `kctl-mailcow -p idtpp quarantine cleanup --days 30` |
| `maint-tpp-pg-health.sh` | `kctl-pg -p idtpp health check` |
| `maint-tpp-odoo-health.sh` | `kctl-odoo -p idtpp health check` |
| `maint-tpp-mailcow-health.sh` | `kctl-mailcow -p idtpp health check` |
| `maint-kod-pg-health.sh` | `kctl-pg -p kodemeio health check` |
| `maint-kod-odoo-health.sh` | `kctl-odoo -p kodemeio health check` |
| `maint-kod-dokploy-health.sh` | `kctl-dokploy -p kodemeio health check` |

- [ ] **Step 8: Add a test that every job script is well-formed**

Append to `tests/test_jobrun.sh`:

```bash
echo
echo "--- job script hygiene ---"
for f in docker/jobs/*.sh; do
  head -1 "$f" | grep -q '^#!/bin/sh' || { echo "FAIL - $f: missing shebang"; fails=$((fails+1)); }
  grep -q '^# REQUIRE:' "$f" || { echo "FAIL - $f: missing '# REQUIRE:' line"; fails=$((fails+1)); }
  grep -q '^set -eu' "$f"   || { echo "FAIL - $f: missing 'set -eu'"; fails=$((fails+1)); }
  sh -n "$f"                || { echo "FAIL - $f: syntax error"; fails=$((fails+1)); }
done
echo "checked $(ls docker/jobs/*.sh | wc -l) job scripts"
```

- [ ] **Step 9: Add both to the image**

In `docker/Dockerfile.cli`, in the runtime stage after `COPY --from=builder /app /app`:

```dockerfile
# jobrun wraps every scheduled job: guards its secrets, enforces a timeout and
# a log cap, and emails on failure. Dokploy has no failure alerting for
# scheduled jobs, so without this a failing alarm is completely silent.
#
# Job scripts are baked in rather than passed as command arguments because
# Dokploy does not escape shell metacharacters in a schedule's command.
COPY docker/jobrun /usr/local/bin/jobrun
COPY docker/jobs /opt/kctl/jobs
RUN chmod 755 /usr/local/bin/jobrun && chmod 755 /opt/kctl/jobs/*.sh
```

- [ ] **Step 10: Build and verify inside the image**

```bash
docker build -f docker/Dockerfile.cli -t kodemeio-cli:jobrun-test .
docker run --rm kodemeio-cli:jobrun-test sh -c 'command -v jobrun && command -v timeout && command -v python3 && ls /opt/kctl/jobs | wc -l'
docker run --rm -e JOBRUN_NOTIFY=echo kodemeio-cli:jobrun-test jobrun no-such-job; echo "unknown-job exit=$?"
```
Expected: all binaries found, `17` job scripts, and `unknown-job exit=2`.

- [ ] **Step 11: Commit and publish a pinned image**

```bash
git add docker/jobrun docker/jobs docker/Dockerfile.cli tests/test_jobrun.sh
git commit -m "feat: add jobrun and 17 baked-in job scripts for Dokploy schedules

Dokploy has no failure alerting for scheduled jobs and does not escape
shell metacharacters in a schedule's command, so a command carrying
arguments or quotes fails silently. jobrun takes ONE argument -- the job
name -- and resolves it to a baked-in script where quoting is safe. Same
constraint and same fix Ofelia already uses for run-report.sh.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

Publish through the repo's release path and **record the resulting
`sha-<shortsha>` tag**. Every later task uses it. An image without `jobrun`
would run nothing and look healthy.

---

### Task 2: Toolbox compose and config

**Repo:** `kodemeio-skills`

**Files:**
- Create: `compose/toolbox.yml`
- Create: `config/kctl-config.yaml`

- [ ] **Step 1: Copy the config template into git**

```bash
cp ../kodemeio-xyops/config/kctl-config.template.yaml config/kctl-config.yaml
grep -nE ':\s*[A-Za-z0-9+/=]{16,}\s*$' config/kctl-config.yaml || echo "no literal secrets"
```
Expected: `no literal secrets`. Anything matching must become a `${VAR}`
placeholder and be added to Task 3's `.env.example`.

- [ ] **Step 2: Write `compose/toolbox.yml`**

```yaml
# kctl toolbox -- the execution host for every scheduled kctl-* job.
#
# This container does nothing on its own. Dokploy compose schedules
# `docker exec` into it, which is why it must simply stay up.
#
# It deliberately does NOT mount /var/run/docker.sock. Both schedulers this
# replaces (Ofelia and xyOps) bind-mount it read-write, which is
# root-equivalent on the host. Every job here only calls remote APIs.
services:
  kctl:
    # The service name `kctl` IS the schedules' serviceName. Dokploy resolves
    # {compose.appName}-{serviceName}-1; a mismatch resolves to an EMPTY string
    # and silently runs `docker exec  sh -c ...` forever -- the bug that kept
    # 14 Odoo schedules dead from 2026-04-09 to 2026-08-31. Renaming this
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

Replace `REPLACE_WITH_TASK1_TAG` with the tag from Task 1 Step 11.

- [ ] **Step 3: Validate and commit**

```bash
SMTP_PASS=x REPORT_OWNER=x docker compose -f compose/toolbox.yml config >/dev/null && echo "compose OK"
git add compose/toolbox.yml config/kctl-config.yaml
git commit -m "feat: add kctl toolbox compose for Dokploy scheduled jobs

One idle container that Dokploy compose schedules exec into. No docker.sock
mount: every job calls remote APIs only, so the root-equivalent socket both
previous schedulers mounted is not granted.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: Deploy the toolbox and prove `docker exec` reaches it

**Repo:** `kodemeio-dokploy`

**Files:**
- Create: `deploys/instances/production/tpp-infra-kctl.yaml`
- Create: `deploys/env/production/.env.tpp-infra-kctl.example`
- Create (gitignored): `deploys/env/production/.env.tpp-infra-kctl`

> **No Odoo downtime:** this creates a new compose app on tpp-prod-04. It
> restarts nothing that already exists.

- [ ] **Step 1: Write the env example**

Create `deploys/env/production/.env.tpp-infra-kctl.example` with the 26
variables: `SMTP_PASS`, `REPORT_OWNER`, `REPORT_TEAM`, `REPORT_ARCHIVE`,
`IDTPP_S3_ACCESS_KEY`, `IDTPP_S3_SECRET_KEY`, and the 10 Accurate
`<TENANT>_API_TOKEN` / `<TENANT>_SIGNATURE_SECRET` pairs for
`tunggal-prawira-pakerti`, `tunggal-pangan-pakerti`, `tunggal-putra-pakerti`,
`cakrawala-sarana-prioritas`, `cakrawala-internusa-prioritas`,
`makmur-pangan-jaya`, `lintas-fresh-internusa`, `lumbung-yasa-dagang`,
`lestari-fresh-internusa`, `yata-sikha-ultima` — all with
`__SET_IN_DOKPLOY__` — plus non-secret `TZ=Asia/Jakarta`,
`COMPOSE_PROJECT_NAME=tpp-infra-kctl`, `SMTP_HOST=mail.idtpp.com`,
`SMTP_PORT=587`, `SMTP_USER=reports@idtpp.com`,
`MAIL_FROM=TPP Trade Reports <reports@idtpp.com>`, `ALERT_TO`,
`KCTL_HZ_PROFILE=idtpp`.

Head the file with:

```bash
# WARNING: Dokploy's schedule.list API returns this app's ENTIRE env blob in
# cleartext to any caller holding an API key. Not new in kind -- PGPASSWORD for
# every Odoo app is already readable the same way -- but new in volume.
# See spec section 3.4 item 4.
#
# REPORT_TEAM is the weekly report's real recipient list. It currently lives
# hardcoded in Ofelia's /opt/kodemeio/run-report.sh on tpp-prod-01. If it is
# empty or wrong, the team silently stops receiving the weekly report the
# moment Ofelia is retired.
```

- [ ] **Step 2: Populate the real env file and check parity**

Take the 25 existing values from the xyOps vault or 1Password, and take
`REPORT_TEAM` from Ofelia:

```bash
ssh root@178.104.127.104 'grep -E "^TEAM=|^TEAM_BCC=" /opt/kodemeio/run-report.sh'
git check-ignore -v deploys/env/production/.env.tpp-infra-kctl
uv run python ops/scripts/check-env-parity.py
```
The `check-ignore` must print a matching rule. **If it prints nothing, stop** —
the file is not ignored and committing would leak 26 credentials.

- [ ] **Step 3: Write the manifest, with no schedules yet**

```yaml
kind: instance
extends: ../../bases/infra.yaml

instance:
  name: tpp-infra-kctl
  description: "kctl toolbox — execution host for all scheduled kctl-* jobs (replaces xyOps and Ofelia)"

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

# No dns/domain block: the toolbox has no HTTP surface and takes no Traefik
# route.
#
# The infra base's `backup:` block targets postgres; this app has no database
# and no state -- its entire content is a pinned image plus env. An explicit
# empty map disables the inherited phase. `enabled: false` does NOT work: the
# deployer skips phase_backup only when the resolved config is null.
backup: {}

# schedules: added incrementally in Tasks 4-6. phase_schedules is create-only,
# so each redeploy creates exactly the entries that are new.
```

- [ ] **Step 4: Validate, then deploy**

```bash
uv run pytest deploys/tests -q
kctl-dokploy -p idtpp deploy validate -f deploys/instances/production/tpp-infra-kctl.yaml
kctl-dokploy -p idtpp deploy apply -f deploys/instances/production/tpp-infra-kctl.yaml --dry-run
kctl-dokploy -p idtpp deploy apply -f deploys/instances/production/tpp-infra-kctl.yaml
```
Deploys are asynchronous. Wait, then `deploy status`. Record the `composeId`.

- [ ] **Step 5: Verify the resolved container name — the step that prevents a repeat**

```bash
ssh root@178.104.169.250 'docker ps --format "{{.Names}}" | grep -i kctl'
kctl-dokploy -p idtpp --json compose get <composeId> | python3 -c "import json,sys; print(json.load(sys.stdin)['appName'])"
```
Expected: a container named `<appName>-kctl-1`. If the prefix does not match
the reported `appName`, **stop** — every schedule would resolve to an empty
container name and fail silently.

- [ ] **Step 6: Prove exec, tools, secrets and the absent socket**

```bash
ssh root@178.104.169.250 'c=$(docker ps --format "{{.Names}}" | grep -- "-kctl-1" | head -1)
  docker exec "$c" sh -c "command -v jobrun && kctl-hz --version && ls /opt/kctl/jobs | wc -l"
  docker exec "$c" sh -c "[ -n \"$IDTPP_S3_ACCESS_KEY\" ] && echo SECRET-PRESENT || echo SECRET-MISSING"
  docker exec "$c" sh -c "test ! -S /var/run/docker.sock && echo NO-DOCKER-SOCK || echo DOCKER-SOCK-PRESENT"'
```
Expected: `jobrun` found, a kctl-hz version, `17`, `SECRET-PRESENT`,
`NO-DOCKER-SOCK`. Never echo a secret value — only its presence.

- [ ] **Step 7: Commit**

```bash
git add deploys/instances/production/tpp-infra-kctl.yaml deploys/env/production/.env.tpp-infra-kctl.example
git commit -m "feat: deploy tpp-infra-kctl toolbox for scheduled jobs

One idle container on tpp-prod-04 that Dokploy schedules exec into. No
schedules yet. Resolved container name verified against docker ps before any
schedule exists, because a serviceName mismatch is silent and cost this
estate five months of dead schedules.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: The 10 maintenance jobs — DEFERRED, not migrated

**Status: deliberately out of this migration, decided 2026-08-31.**

This task was sequenced first because the 10 jobs are disabled in xyOps and run
nowhere, so it looked like zero-risk practice. Investigation showed the
opposite: it is the largest and least valuable piece of work in the plan.

**Every one of the 10 invokes a command that does not exist.** Verified against
the CLI actually installed in the toolbox image (kctl-pg 0.11.3, kctl-mailcow
0.13.5 — the image is current; a misleading `0.1.0 → 0.11.3` self-update
warning suggests otherwise and should be ignored):

| xyOps event command | Reality |
|---|---|
| `kctl-pg -p X health check` (×3) | `health` is an `@app.callback(invoke_without_command=True)` — the bare group IS the command; `check` is not a subcommand |
| `kctl-pg -p X bloat check` (×2) | no `bloat` group; the real command is `kctl-pg indexes bloat` |
| `kctl-pg -p idtpp backup check` | `backup` offers `dump` / `restore` / `list` — no `check` |
| `kctl-mailcow -p idtpp health check` | same callback pattern — `check` is not a subcommand |
| `kctl-mailcow -p idtpp quarantine cleanup --days 30` | `quarantine` offers `list` / `release` / `delete` — **no `cleanup` at all** |
| `kctl-odoo -p X health check` (×2) | **kctl-odoo registers no `health` group whatsoever** |
| `kctl-dokploy -p kodemeio health check` | no `health` group; the equivalents are `doctor` and `diagnose` |

They were authored and never validated, because they have been disabled since
the day they were written. The `[BLOCKED: needs config block]` labels in
`kodemeio-xyops/events/maintenance.yaml` understate the problem — the config
block was never the real blocker.

**Three further config problems**, independent of the commands:

- `idtpp.postgres` reaches a private `10.0.0.2` via `ssh_host` / `ssh_key`, so
  the five postgres checks need an SSH private key mounted into the toolbox.
  That is a security decision, not a config edit.
- `idtpp.odoo` does not exist.
- `kodemeio.odoo` is `project_root=/home/tgunawan/...` — a developer-machine
  path, meaningless inside a container.

**Decision:** leave all 10 disabled in xyOps exactly as they are. Nothing is
lost — they have never run. Migrating them is genuine design work (deciding
what each check should assert, against the real CLI surface) plus a CLI feature
project, and it must not block retiring two schedulers.

**Follow-up, tracked separately:** map the 7 salvageable checks onto real
commands, decide the SSH-key exposure for the postgres ones, and author
`kctl-odoo health` and a mailcow quarantine cleanup if they are wanted.

### Task 5: Migrate the 4 backup alarms and prove alerting works

These run in parallel with xyOps. They are read-only idempotent checks, so
duplicate alerts are harmless and are themselves evidence the path works.

- [ ] **Step 1: Add the four alarms to the manifest**

```yaml
  # Alarms run BEFORE the 06:50/07:00 reports on purpose: a stale backup must
  # be known before the business report goes out. Preserve this ordering.
  - {name: backup-tpp,      cron: "0 5 * * *",  command: "jobrun backup-tpp",      service: kctl, shell: sh, timezone: Asia/Jakarta}
  - {name: backup-tpp25,    cron: "10 5 * * *", command: "jobrun backup-tpp25",    service: kctl, shell: sh, timezone: Asia/Jakarta}
  - {name: backup-mac,      cron: "20 5 * * *", command: "jobrun backup-mac",      service: kctl, shell: sh, timezone: Asia/Jakarta}
  - {name: backup-mac-hrms, cron: "30 5 * * *", command: "jobrun backup-mac-hrms", service: kctl, shell: sh, timezone: Asia/Jakarta}
```

- [ ] **Step 2: Deploy, run each once, verify green**

```bash
uv run pytest deploys/tests -q
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
prefix. Both must agree fresh/stale on all four. A disagreement means the
command or profile is wrong — fix before trusting either.

- [ ] **Step 4: Prove a failure reaches a human — the critical test of this plan**

The only step that proves the alerting gap was actually closed, rather than
assumed closed because a wrapper exists.

```bash
# A throwaway job script pointing at a prefix that is certainly stale.
# (Add docker/jobs/zz-alert-proof.sh in kodemeio-skills, rebuild, redeploy the
# toolbox -- or exec it directly for a faster loop:)
ssh root@178.104.169.250 'c=$(docker ps --format "{{.Names}}" | grep -- "-kctl-1" | head -1)
  docker exec "$c" sh -c "printf \"#!/bin/sh\n# REQUIRE: IDTPP_S3_ACCESS_KEY\nset -eu\nexport KCTL_HZ_PROFILE=idtpp\nexec kctl-hz -p idtpp s3 freshness hz-tpp-odoo-filestore --prefix definitely/not/real/ --max-age-hours 1\n\" > /opt/kctl/jobs/zz-alert-proof.sh && chmod +x /opt/kctl/jobs/zz-alert-proof.sh"
  docker exec "$c" jobrun zz-alert-proof; echo "exit=$?"
  docker exec "$c" rm -f /opt/kctl/jobs/zz-alert-proof.sh'
```

Confirm **all three**:
1. `exit=` is non-zero.
2. An email titled `[ALERT] zz-alert-proof failed (exit N)` arrives in the
   `ALERT_TO` inbox. **Check the inbox. Do not infer it from the exit code.**
3. The body contains the command's real output, not an empty section.

If the mail does not arrive, **stop the migration** and fix `jobrun`'s mail
path. Every alarm after this point depends on it.

- [ ] **Step 5: Run in parallel for a full day, then disable the xyOps alarms**

Confirm both schedulers agree on every alarm for at least 24 h. Then set
`enabled: false` on all four in `kodemeio-xyops/events/backup-alarms.yaml`:

```bash
cd ../kodemeio-xyops && uv run python scripts/reconcile.py apply && uv run python scripts/reconcile.py diff
```
Expected: apply succeeds, diff clean.

- [ ] **Step 6: Commit**

```bash
git add deploys/instances/production/tpp-infra-kctl.yaml
git commit -m "feat: migrate 4 backup freshness alarms to Dokploy schedules

Ran in parallel with xyOps for a full day with matching verdicts before the
xyOps events were disabled. Alerting proven by inducing a real failure
against a known-stale prefix and confirming the email arrived -- not
inferred from the exit code.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 6: Migrate the 3 reports — a three-way atomic swap

**Not parallel-safe.** Three schedulers would mail three copies of a business
report to real people. Dokploy on, xyOps off, **and Ofelia off**, in one sitting.

> Today the owner already receives two copies of the daily and selfcheck
> reports (xyOps + Ofelia). The team's weekly comes from Ofelia alone. This
> task ends both conditions.

- [ ] **Step 1: Add the three reports to the manifest**

`catchup: true` is dropped deliberately — Dokploy has no equivalent. The
watchdog notices a missed report and `schedules run` re-fires it (spec §6.3).

```yaml
  - {name: report-selfcheck, cron: "50 6 * * *", command: "jobrun report-selfcheck", service: kctl, shell: sh, timezone: Asia/Jakarta}
  - {name: report-daily,     cron: "0 7 * * *",  command: "jobrun report-daily",     service: kctl, shell: sh, timezone: Asia/Jakarta}
  - {name: report-weekly,    cron: "0 8 * * 1",  command: "jobrun report-weekly",    service: kctl, shell: sh, timezone: Asia/Jakarta}
```

- [ ] **Step 2: Confirm `REPORT_TEAM` matches Ofelia exactly**

```bash
ssh root@178.104.127.104 'grep -E "^TEAM=|^TEAM_BCC=" /opt/kodemeio/run-report.sh'
```
Compare against `REPORT_TEAM` / `REPORT_ARCHIVE` in `.env.tpp-infra-kctl`.
A mismatch here means the team silently loses its weekly report when Ofelia
stops. This is the single highest-consequence value in the migration.

- [ ] **Step 3: Deploy, then run `report-selfcheck` only**

The canary covers one tenant, so a duplicate is cheap.

```bash
kctl-dokploy -p idtpp deploy apply -f deploys/instances/production/tpp-infra-kctl.yaml
kctl-dokploy -p idtpp schedules run <report-selfcheck scheduleId>
sleep 120
uv run python ops/scripts/schedule-status.py --profile idtpp
```
Expected: `healthy=True`, and the canary email arrives with its xlsx attached.

- [ ] **Step 4: Compare the canary against Ofelia's output**

Same row counts, same totals, same attachment name. A mismatch means the
command or config differs — fix before swapping the real reports.

- [ ] **Step 5: The atomic swap — one sitting, all three sides**

Do this after that morning's reports have already gone out, so nobody gets
two copies or none.

```bash
# 1. xyOps: disable all three report events
cd ../kodemeio-xyops
#    edit events/reports.yaml -> enabled: false on all three
uv run python scripts/reconcile.py apply
uv run python scripts/reconcile.py diff        # expect: clean

# 2. Ofelia: comment out the three live job-run blocks in the reports INI,
#    the same way the four freshness alarms were commented out on 2026-08-16,
#    then redeploy tpp-ofelia-reports so it reloads.
#    (Editing the INI in the kodemeio-ofelia repo, not on the host.)

# 3. Confirm Dokploy's three are enabled and green
cd -
uv run python ops/scripts/schedule-status.py --profile idtpp
```
Expected: xyOps clean with all three disabled; Ofelia running zero report jobs;
Dokploy showing all three `healthy=True`.

- [ ] **Step 6: Watch the next real firings**

Next morning: `report-daily` fired at 07:00 WIB, **exactly one** email arrived.
Monday: `report-weekly` fired at 08:00 WIB, **the team received it**, and the
BCC archive got its copy. Confirm with a team member — this is the deliverable
most easily lost silently.

- [ ] **Step 7: Commit**

```bash
git add deploys/instances/production/tpp-infra-kctl.yaml
git commit -m "feat: migrate 3 trade reports to Dokploy schedules

Three-way atomic swap: xyOps' and Ofelia's report jobs were both disabled in
the same sitting the Dokploy schedules went live, so no recipient got
duplicates or none.

report-weekly targets REPORT_TEAM, matching what Ofelia sends today. xyOps'
version mailed only the owner; shipping that would have silently stopped the
team's weekly report.

catchup: true is dropped -- Dokploy has no equivalent. A missed report is
caught by the watchdog and re-fired deliberately.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 7: Rewrite the dead-man watchdog

**Files:**
- Create: `ops/scripts/deadman-check.sh`
- Create: `ops/scripts/deadman_intervals.py`
- Test: `deploys/tests/test_deadman_intervals.py`

**It stays on host cron on tpp-prod-01 and must never become a Dokploy
schedule.** A scheduler cannot report its own death, and if Dokploy is down the
watchdog still has to page. It checks **every** enabled schedule in the estate,
not only the 17 — the pre-existing schedules were exactly the ones nobody was
watching.

- [ ] **Step 1: Write the failing interval test**

Create `deploys/tests/test_deadman_intervals.py`:

```python
"""The watchdog's freshness threshold comes from the cron expression.

Too tight and it pages constantly and people mute it; too loose and a dead job
stays dead. Both failure modes end the same way: nobody reads the alerts.
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


def test_weekly_monday_cron_is_one_week():
    from deadman_intervals import interval_minutes

    assert interval_minutes("0 8 * * 1") == 10080


def test_weekly_sunday_cron_is_one_week():
    from deadman_intervals import interval_minutes

    assert interval_minutes("0 3 * * 0") == 10080


def test_grace_is_a_quarter_with_a_thirty_minute_floor():
    from deadman_intervals import threshold_minutes

    assert threshold_minutes(1440) == 1440 + 360
    assert threshold_minutes(60) == 60 + 30
    assert threshold_minutes(10) == 10 + 30
```

- [ ] **Step 2: Run it and confirm it fails**

Run: `uv run pytest deploys/tests/test_deadman_intervals.py -q`
Expected: FAIL — module does not exist

- [ ] **Step 3: Write `ops/scripts/deadman_intervals.py`**

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
    """Largest gap in minutes between consecutive firings, capped at a week.

    A job firing less often than weekly has no meaningful sub-week gap, so the
    whole cycle is returned.
    """
    base = datetime(2026, 1, 5)  # a Monday, so weekday crons land predictably
    it = croniter(cron_expression, base)
    times = [it.get_next(datetime) for _ in range(12)]
    gaps = [int((b - a).total_seconds() // 60) for a, b in zip(times, times[1:], strict=False)]
    if not gaps:
        return WEEK_MINUTES
    return min(max(gaps), WEEK_MINUTES)


def threshold_minutes(interval: int) -> int:
    """Interval plus a grace period of a quarter, with a 30-minute floor."""
    return interval + max(interval // 4, 30)


def is_stale(cron_expression: str, last_started: datetime, now: datetime) -> bool:
    return now - last_started > timedelta(minutes=threshold_minutes(interval_minutes(cron_expression)))
```

```bash
uv add croniter
uv run pytest deploys/tests/test_deadman_intervals.py -q   # expect PASS
```

- [ ] **Step 4: Write the watchdog**

Create `ops/scripts/deadman-check.sh`. It reuses `schedule-status.py --json`
for collection and adds staleness. Alerts when: the Dokploy API is unreachable;
credentials are missing or empty; the toolbox container is not running; an
enabled schedule has no run inside interval+grace; or an enabled schedule's most
recent run is not `done`. Disabled schedules are noted in the log and never
mailed — a watchdog that pages for jobs nobody expects to run is one people
learn to ignore.

```bash
#!/usr/bin/env bash
# Dokploy schedule dead-man check -- runs from HOST CRON on tpp-prod-01.
#
# Deliberately NOT a Dokploy schedule and deliberately not on tpp-prod-04.
# A scheduler cannot report its own death, and if Dokploy is down the watchdog
# still has to page. Same reason the Ofelia and xyOps watchdogs lived off the
# machine they watched.
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

if [[ -r "$SMTP_ENV" ]]; then
  set -a; . "$SMTP_ENV"; set +a
else
  PROBLEMS="CREDENTIALS MISSING: $SMTP_ENV is not readable."
fi
ALERT_TO="${ALERT_TO:-trigunawan.note@gmail.com}"

if ! ssh -o BatchMode=yes -o ConnectTimeout=10 "root@${TOOLBOX_HOST}" \
      'docker ps --format "{{.Names}}" | grep -q -- "-kctl-1"' 2>/dev/null; then
  PROBLEMS="${PROBLEMS}
TOOLBOX DOWN: no running *-kctl-1 container on ${TOOLBOX_HOST}. Every scheduled job is dead."
fi

STATUS_JSON=$(python3 /opt/kodemeio/schedule-status.py --profile "$KCTL_PROFILE" --json 2>/dev/null)
if [[ -z "$STATUS_JSON" ]]; then
  PROBLEMS="${PROBLEMS}
DOKPLOY UNREACHABLE: could not list schedules for profile ${KCTL_PROFILE}."
else
  REPORT=$(SCHEDULES="$STATUS_JSON" python3 /opt/kodemeio/deadman_report.py)
  while IFS= read -r line; do [[ -n "$line" ]] && PROBLEMS="${PROBLEMS}
${line}"; done < <(jq -r '.problems[]' <<<"$REPORT")
  while IFS= read -r line; do [[ -n "$line" ]] && NOTES="${NOTES}
${line}"; done < <(jq -r '.notes[]' <<<"$REPORT")
fi

[[ -n "$NOTES" ]] && printf '%s\n' "$NOTES"

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
"
echo "$(date '+%F %T') ALERT" >&2

if [[ -z "${SMTP_PASS:-}" ]]; then
  echo "FATAL: SMTP_PASS unavailable -- cannot send the alert mail either." >&2
  exit 1
fi
ALERT_TO="$ALERT_TO" BODY="$BODY" python3 /opt/kodemeio/deadman_mail.py
exit 1
```

Also create `ops/scripts/deadman_report.py` (reads `SCHEDULES` from env, emits
`{"problems": [...], "notes": [...]}` using `interval_minutes` /
`threshold_minutes`) and `ops/scripts/deadman_mail.py` (the smtplib block, same
shape as `jobrun`'s). Keeping them as separate files avoids nesting heredocs
inside the bash script, which is how quoting bugs get introduced.

- [ ] **Step 5: Verify it reports OK, then verify it actually alerts**

```bash
./ops/scripts/deadman-check.sh                       # expect exit 0, "OK"
kctl-dokploy -p idtpp schedules update <a maint scheduleId> --disabled
./ops/scripts/deadman-check.sh                       # expect exit 0 -- disabled is SKIPPED, not alerted
```
Then force a staleness alert by pointing `TOOLBOX_HOST` at an unreachable
address and confirm the mail arrives:
```bash
TOOLBOX_HOST=192.0.2.1 ./ops/scripts/deadman-check.sh # expect non-zero + email
kctl-dokploy -p idtpp schedules update <that scheduleId> --enabled
```
If it goes quiet instead, the watchdog is useless — fix before Step 6.

- [ ] **Step 6: Install on tpp-prod-01 and retire the xyOps watchdog**

All four files must be installed, and the host needs `croniter` and a
`~/.config/kodemeio/config.yaml` carrying the `idtpp.dokploy` profile.

```bash
scp ops/scripts/deadman-check.sh ops/scripts/deadman_intervals.py \
    ops/scripts/deadman_report.py ops/scripts/deadman_mail.py \
    ops/scripts/schedule-status.py root@178.104.127.104:/opt/kodemeio/
ssh root@178.104.127.104 '
  chmod 755 /opt/kodemeio/deadman-check.sh
  python3 -c "import yaml, croniter; print(\"deps OK\")" || pip install --user croniter pyyaml
  python3 /opt/kodemeio/schedule-status.py --profile idtpp >/dev/null && echo "status tool OK"
  crontab -l'
```
Replace the xyOps watchdog's crontab entries with the new one. Keep the old
script on disk until Task 9 closes the rollback window.

- [ ] **Step 7: Commit**

```bash
git add ops/scripts/deadman-check.sh ops/scripts/deadman_intervals.py \
        ops/scripts/deadman_report.py ops/scripts/deadman_mail.py \
        deploys/tests/test_deadman_intervals.py pyproject.toml uv.lock
git commit -m "feat: rewrite dead-man watchdog against the Dokploy schedule API

Reads run history from /deployment.allByType instead of xyOps'
get_events/search_jobs. Stays on host cron on tpp-prod-01: a scheduler
cannot report its own death.

Checks every enabled schedule in the estate, not just the migrated 17 -- the
pre-existing schedules are exactly the ones nobody was watching, and 16 of
them failed for five months unnoticed.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 8: Make git authoritative again

**Repo:** `kodemeio-skills` (items 1–4), then this repo (item 5)

Without this, `phase_schedules` stays create-only: editing a cron in git
silently does nothing, and a UI edit is undetectable. That is strictly weaker
than the `reconcile.py` guarantee xyOps had, so it must land before either
scheduler is decommissioned.

- [ ] **Step 1: Add `enabled` to `ScheduleConfig`** in `core/manifest.py:86`.

- [ ] **Step 2: Add `--service` and `--timezone` to `schedules update`.**
`commands/schedules.py`'s `update` exposes only `--name/--cron/--command/
--enabled`, though `schedule.update` accepts `serviceName` and `timezone`. That
gap is why 14 broken schedules had to be repaired by direct API call.

- [ ] **Step 3: Turn `phase_schedules` into a reconciler.**
In `core/deploy/orchestrator.py:1055`, replace the create-only loop. Key on
`name`. Create if absent; update when cron/command/service/shell/timezone/
enabled differ; delete orphans only under an explicit `--prune` flag. Record
created/updated/pruned counts.

- [ ] **Step 4: Let a manifest opt out of `verify` and `backup`.**
Two phases fail on every deploy of `tpp-infra-kctl`, and both are gaps rather
than misconfiguration. `phase_verify` unconditionally polls
`{scheme}://{host}{path}`, so an app with no HTTP surface always fails it —
there is no port-0 or skip escape. And `merge_manifests` resolves
`instance.backup if instance.backup is not None else base.backup`, so
`backup: {}` becomes a `BackupConfig` with an empty destination that *wins*
over the base instead of disabling the phase; `phase_backup` skips only on
`None`. Add an explicit opt-out for both. Until then every deploy of a
non-HTTP, stateless app reports two red phases — which is exactly the kind of
expected-noise that trains people to ignore real failures.

- [ ] **Step 5: Fix the four bugs in spec §3.4** — repoint `schedules history`
at `/deployment.allByType`, send the required `id` in `deployments by-type`,
read `logPath` in `deployments logs`, and mask secrets in JSON output.
The `schedules history` fix is a **hard prerequisite for Task 7**.

- [ ] **Step 6: Add a read-only drift check and wire it into CI.**
Add `kctl-dokploy deploy schedules-diff -f <manifest>`: report differences,
exit non-zero on divergence, change nothing. Then create
`.github/workflows/schedule-drift.yml` in this repo running it on push, pull
request and hourly — replacing the xyOps drift workflow.

- [ ] **Step 7: Prove drift is detected.**
Change one schedule's cron in the Dokploy UI, run the drift check, confirm
non-zero and that the output names that schedule. Run `deploy apply`, confirm
it returns to zero.

- [ ] **Step 8: Commit** (in each repo, with a message explaining the
create-only gap and the missing `--service` flag).

---

### Task 9: Decommission xyOps and Ofelia

**Do not start until 14 days have passed** since Task 6 with no missed job and
no silent failure.

- [ ] **Step 1: Confirm the rollback window is clean**

```bash
uv run python ops/scripts/schedule-status.py --profile idtpp    # expect exit 0
ssh root@178.104.127.104 'grep -c ALERT /var/log/deadman-check.log || true'
```
Any missed job restarts the clock. This is the last cheap moment to abort.

- [ ] **Step 2: Confirm both schedulers are idle**

```bash
cd ../kodemeio-xyops && uv run python scripts/reconcile.py diff   # clean, all 17 disabled
ssh root@178.104.127.104 'docker logs --since 168h tpp-ofelia-reports 2>&1 | grep -c "job-run" || true'
```
Expected: xyOps clean with everything disabled; Ofelia showing no report job
executions in the last week.

- [ ] **Step 3: Take a final xyOps backup and prove it restores**

Run the existing restic backup once more and verify the restore the way it was
verified on 2026-08-15 (`PRAGMA integrity_check` on the restored SQLite file).
A backup that has not been restored is not a backup.

- [ ] **Step 4: Remove the three Dokploy apps**

`tpp-infra-xyops`, `tpp-infra-xyops-backup`, `tpp-ofelia-reports`.

> **Do NOT touch `compose-…-ofelia-mailcow-1`.** That is Mailcow's own
> internal scheduler, part of the upstream Mailcow stack. Stopping it breaks
> Mailcow's quarantine notifications, SOGo backups and LDAP sync.

Confirm the containers are gone on tpp-prod-04 and tpp-prod-01, and check what
volumes remain with `docker volume ls | grep -E "xyops|ofelia"`.

- [ ] **Step 5: Retain the vault key, delete the manifests**

Keep `XYOPS_SECRET_KEY` in 1Password until the final data-volume backup is
discarded — the key is worthless without the volume, but the volume is
unrecoverable without the key. Record the retention decision and its expiry.

```bash
git rm deploys/instances/production/tpp-infra-xyops.yaml \
       deploys/instances/production/tpp-infra-xyops-backup.yaml \
       deploys/instances/production/tpp-ofelia-reports.yaml \
       deploys/instances/staging/tpp-ofelia-reports.yaml \
       deploys/instances/staging/tpp-ofelia-maintenance.yaml
```
Leave `deploys/env/production/.env.tpp-infra-xyops*` in place until the backup
is discarded; they are gitignored and hold the only copy of some values.
Also remove `/opt/kodemeio/run-report.sh` and the superseded xyOps watchdog
from tpp-prod-01.

- [ ] **Step 6: Update the architecture doc**

Record in `docs/architecture.md` that scheduled work is now native Dokploy
schedules on `tpp-infra-kctl`, watched by `ops/scripts/deadman-check.sh` on
tpp-prod-01, and that `ofelia-mailcow` remains as Mailcow's vendor-managed
internal scheduler.

- [ ] **Step 7: Commit**

```bash
git add -A deploys/instances docs/architecture.md
git commit -m "chore: decommission xyOps and Ofelia schedulers

All 17 jobs have run as native Dokploy schedules for 14 days with no missed
run and no silent failure. Removes three Dokploy apps, a restic backup
stack, two root-equivalent docker.sock mounts, and XYOPS_SECRET_KEY as a
single point of total loss. The estate goes from three schedulers to one.

ofelia-mailcow is untouched: it is Mailcow's own internal scheduler, part of
the upstream stack, and not a Kodemeio scheduler.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Done when

- All 17 jobs run as Dokploy schedules and `ops/scripts/schedule-status.py
  --profile idtpp` exits 0.
- A deliberately induced failure produced an email in the `ALERT_TO` inbox
  (Task 5 Step 4).
- The team confirmed receiving the weekly report from the new schedule
  (Task 6 Step 6).
- The watchdog alerts on a stale schedule and is installed on tpp-prod-01.
- Drift is detected in CI and cleared by `deploy apply`.
- `tpp-infra-xyops`, `tpp-infra-xyops-backup` and `tpp-ofelia-reports` no
  longer exist; `ofelia-mailcow` still does.

## Still open after this plan

- **`schedules list` leaking env in cleartext** (spec §3.4 item 4). Task 8
  fixes it in the CLI, but the API still returns it — treat any `--json`
  schedule output as secret-bearing.
- **The 7 Odoo `*-session-cleanup` schedules**, tracked in
  `2026-08-31-fix-dokploy-schedule-failures.md`. They need an Odoo image
  rebuild and are unrelated to this migration.
