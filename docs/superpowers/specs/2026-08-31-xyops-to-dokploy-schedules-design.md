# Migrating xyOps jobs to native Dokploy Schedule Jobs

**Status:** approved design, not yet implemented
**Date:** 2026-08-31
**Supersedes for scheduling:** `kodemeio-xyops` (Project 1 of the xyOps adoption)
**Related:** `docs/adrs/0001-dokploy-consolidation.md`

> **Read §3.3 first.** Surveying Dokploy for this design uncovered a live,
> undetected production failure: 16 already-deployed schedules with a 100%
> failure rate since 2026-04-09. Fixing that is a prerequisite for this
> migration and is more urgent than the migration itself.

## 1. Why

Kodemeio runs **three** schedulers today for one set of jobs:

| Scheduler | Where | State |
|---|---|---|
| Ofelia (`tpp-ofelia-reports`) | tpp-prod-01 | still deployed, still owns business reports |
| xyOps (`tpp-infra-xyops`) | tpp-prod-04 | 17 events; 7 enabled and live since 2026-08-15 |
| Dokploy native schedules | the Dokploy control plane | 18 deployed; **16 failing 100% of runs** (§3.3) |

Every one of those 17 xyOps jobs is the same shape: *fire on a cron, run one
`kctl-*` command in a container, alert a human if it exits non-zero.* That is
precisely what Dokploy's Schedule Jobs feature does, and Dokploy is already
the control plane for every other deployed thing in the estate.

Running a separate conductor for it costs, concretely:

- Two Dokploy apps (`tpp-infra-xyops`, `tpp-infra-xyops-backup`) and a restic
  stack that exists only to back up the first one's SQLite volume.
- `XYOPS_SECRET_KEY` — a vault key whose loss makes all 25 stored job secrets
  permanently unrecoverable, backup or no backup. A single point of total loss
  with no equivalent anywhere else in the estate.
- A bespoke reconciler (`scripts/reconcile.py`), its drift CI workflow, its
  event schema, and an operator runbook — all maintained for one service.
- A `/var/run/docker.sock` read-write bind mount on tpp-prod-04, which is
  root-equivalent on that host.

The decision is to **retire xyOps entirely** and move all 17 jobs onto native
Dokploy schedules.

## 2. Decisions

| # | Decision | Alternative rejected |
|---|---|---|
| D1 | **Full retirement.** All 17 jobs become Dokploy schedules; both xyOps apps are decommissioned. | Keeping xyOps for jobs needing catchup/alerting — leaves two schedulers forever, which is the thing being fixed. |
| D2 | **Toolbox compose app + compose-type schedules.** One idle `tpp-infra-kctl` container; each job is a `docker exec` into it. | Server-type jobs doing `docker run --rm` per job — preserves per-job isolation but pushes secrets back into an ungoverned mode-600 host file, the exact Ofelia pattern being retired. |
| D3 | **SMTP email alerts**, same recipient and same relay as today. | Mattermost webhook — new credential, and both Mattermost apps have shown `error` state in Dokploy. An alert path that depends on a flaky service fails when it is needed most. |

## 3. What Dokploy actually provides

Verified against the live instance at `dokploy.idtpp.com` — the OpenAPI spec
(`kctl-dokploy -p idtpp settings openapi`), real API responses, and schedule
log files read over SSH. Not from documentation.

**Endpoints:** `schedule.create`, `schedule.update`, `schedule.delete`,
`schedule.list`, `schedule.one`, `schedule.runManually`.

**`schedule.create` accepts:** `name`, `cronExpression`, `command` (required);
plus `description`, `script`, `serviceName`, `shellType` (`bash`|`sh`),
`scheduleType` (`application`|`compose`|`server`|`dokploy-server`),
`applicationId`, `composeId`, `serverId`, `enabled`, `timezone`.

**Run history** lives at `GET /deployment.allByType?id=<scheduleId>&type=schedule`
— **not** on `schedule.one`. Each row carries `status` (`done`|`error`),
`startedAt`, `finishedAt`, `errorMessage`, and `logPath`. Roughly the last 11
runs are retained. This is the watchdog's data source (§5.7).

**Confirmed working:** `timezone` is honoured — schedules with
`timezone: Asia/Jakarta` and cron `0 3 * * *` fire at `20:00Z`, which is 03:00
WIB. Verified across 8 apps over months of run history.

`kctl-dokploy` 0.16.6 already has the CRUD surface, the manifest already carries
a `schedules:` block (`ScheduleConfig`: `name`/`cron`/`command`/`service`/
`shell`/`timezone`), and the deploy pipeline already runs `phase_schedules`.
`deploys/bases/odoo.yaml` and `deploys/bases/plausible.yaml` already declare
schedules this way.

### 3.1 The four capability gaps

These are the substance of the migration. Each is closed explicitly or
accepted explicitly.

| Gap | Evidence | Resolution |
|---|---|---|
| **G1. No failure alerting.** Notification channels carry only `appDeploy`, `appBuildError`, `databaseBackup`, `volumeBackup`, `dokployRestart`, `dokployBackup`, `dockerCleanup`, `serverThreshold`. Grepping the entire OpenAPI spec for schedule-related keys returns only `scheduleId`, `schedule`, `scheduleType`. There is no cron-failure hook. | live spec + `notification.all` | **Closed** by `jobrun` (§5.2). §3.3 is what this gap costs in practice. |
| **G2. No time or log limits.** xyOps categories enforce 300–900 s and 1–5 MB per job. Dokploy has no per-schedule timeout; a hung job hangs forever. | absent from `schedule.create` schema | **Closed** by `jobrun` (§5.2). |
| **G3. No catch-up.** The 3 report events carry `catchup: true`; Dokploy cron silently skips a missed firing. | absent from `schedule.create` schema | **Accepted** (§6.3). |
| **G4. `phase_schedules` only creates.** It builds `existing_names` from `schedules list` and `continue`s on a match — never updates, enables, disables, or prunes. Editing a cron in git would silently do nothing. | `kctl-dokploy` `core/deploy/orchestrator.py:1055` | **Closed** by §5.6, cross-repo. |

G1 is the one that matters most. Four of the seven live xyOps jobs are
`kctl-hz s3 freshness` alarms whose entire product is an exit code. Moving them
onto a scheduler that discards that exit code turns working alarms into
decoration. `events/maintenance.yaml` already states the principle: *"A
scheduled check that nothing runs is worse than no check, because it reads as
coverage."*

### 3.2 What carries over unchanged

- **`${VAR}` config expansion is a kctl-lib feature**, not an xyOps one
  (`packages/kctl-lib/src/kctl_lib/config.py:33`, `expand_env`). The mounted
  config template behaves identically in any container.
- **`expand_env` returns the literal `${VAR}` string for an unset variable**
  rather than raising. The existing guard pattern is therefore still mandatory
  — without it, a missing secret is sent to a remote API *as though it were the
  credential*.
- **xyOps weekday numbering is already cron's** (`0`=Sunday, `1`=Monday), so
  schedule translation carries no off-by-one risk.
- **`docker exec` inherits the container's environment**, giving the same
  "never in argv" property as xyOps' `-e NAME` passthrough.

### 3.3 Live incident found while surveying — fix before migrating

Dokploy already runs 18 schedules. **Sixteen have never succeeded.** Around 160
executions, zero `done`, going back to 2026-04-09. Nobody noticed, because of G1.

| App | Schedules | Cron | Runs | OK | Error |
|---|---|---|---|---|---|
| `mac-odoo-erp`, `mac-odoo-hrms`, `mac-odoo-erp-stg`, `mac-odoo-hrms-stg`, `tpp-odoo-erp-stg`, `tpp-odoo-hrms-stg`, `tpp-odoo-helpdesk` | `*-vacuum`, `*-session-cleanup` (14 total) | `0 4 * * 0`, `0 3 * * *` | ~11 each | 0 | all |
| `tpp-infra-authentik` | `reset-akadmin-pw` | `* * * * *` | 11 | 0 | all |
| `tpp-infra-postgres` | `create-authentik-db` | `* * * * *` | 11 | 0 | all |
| `tpp-infra-postgres` | `dbg-v2`, `dbg-v3` | `0 0 31 12 0` | 0 | — | — |

**Root cause for the 14 Odoo schedules.** From
`/etc/dokploy/schedules/schedule-reboot-back-end-bandwidth-7vqtf3/…log` on
tpp-prod-02:

```
Initializing schedule
Running command: docker exec  bash -c 'vacuumdb -U odoo -d mac_odoo_erp --analyze'
Error response from daemon: No such container: bash
❌ Command failed
```

The double space is the tell: the container name resolved to an **empty
string**, so Docker read `bash` as the container name. `deploys/bases/odoo.yaml`
declares `service: odoo`, but the real compose services are **`odoo-web`,
`odoo-cron`, `odoo-gevent`** — confirmed by `docker ps` on tpp-prod-02, where
containers are named `compose-calculate-neural-matrix-phtlsl-odoo-web-1`. There
has never been a service called `odoo`, so the lookup has always returned
nothing.

**A second, independent bug in the same schedules.** `session-cleanup` runs
`DELETE FROM ir_sessions ...`, but **there is no `ir_sessions` table**. Odoo 18
here runs the `session_db` server-wide module, whose table is
`http_sessions (sid, write_date, payload)`. Fixing `service:` alone therefore
does NOT fix session-cleanup — it only changes the error from "no such
container" to "relation does not exist". Both bugs must be fixed together.

**Actual damage is low — the finding is the mechanism, not the harm.** Measured
on `mac_odoo_erp` on 2026-08-31:

- **Vacuum:** PostgreSQL autovacuum has been doing the work regardless — 159 of
  1387 user tables autovacuumed, 224 analyzed, most recent 2026-08-31. The
  weekly `vacuumdb --analyze` is belt-and-braces, and its absence caused no
  measurable harm.
- **Sessions:** `http_sessions` holds 31 rows / 688 kB. Nothing grew unbounded.

This is worth stating plainly because it drives prioritization: the fix is
**not** an emergency. What matters is that 16 schedules failed 100% of the time
for five months and nothing anywhere reported it. The damage was low this time
by luck — autovacuum happened to cover the gap. The same blindness applied to a
backup-freshness alarm is the migration's central risk, which is exactly why
§5.2 and §5.7 exist.

**Two `* * * * *` schedules** (`reset-akadmin-pw`, `create-authentik-db`) fire
and fail **every minute**. Both were created 2026-04-07 — roughly 146 days, so
on the order of 210,000 failed executions each. Only the last ~11 runs are
retained, so the deployment table is not growing without bound, but the work is
pure waste and the noise buries anything real. They appear to be leftover
bootstrap artifacts from the Authentik rehost, as do `dbg-v2` and `dbg-v3`
(created 2026-04-30, cron `0 0 31 12 0`, never run). All four should be deleted.

**Required fixes, independent of this migration:**

1. Change `service: odoo` to `service: odoo-cron` in `deploys/bases/odoo.yaml`
   (the same manifests already use `service: odoo-web` correctly for their
   domain block, which is how the mismatch survived review). `psql` and
   `vacuumdb` are both confirmed present at `/usr/bin` in the Odoo image, and
   `PGHOST`/`PGPASSWORD` are inherited from the container env — a `SELECT 1`
   over that exact path succeeds — so no command change is needed for vacuum.
2. Fix `session-cleanup` to target the real table:
   `DELETE FROM http_sessions WHERE write_date < NOW() - INTERVAL '7 days'`.
3. Verify a run reaches `status: done` via `/deployment.allByType` — do not
   assume creation means success.
4. Delete `reset-akadmin-pw`, `create-authentik-db`, `dbg-v2`, `dbg-v3`.
5. Re-verify `tpp-infra-authentik`'s `serviceName: server` against real
   container names before assuming it shares the Odoo root cause.
6. Close the coverage gap: `tpp-odoo-erp`, `tpp-odoo-hrms`, and `tpp25-odoo-erp`
   — three **production** Odoo apps — have no schedules at all. `phase_schedules`
   is create-only and skips apps whose schedules were never created, so adding
   the block to the base never reached them. This is G4 (§3.1) showing up in
   production, and it is fixed by the same reconciler.

**What this proves for the migration.** The compose-exec mechanism itself is
sound — it was pointed at a service name that does not exist. But it is direct
empirical evidence that a Dokploy schedule can fail every single time for five
months without anyone finding out. `jobrun` (§5.2) and the watchdog (§5.7) are
not belt-and-braces; they are the difference between this migration working and
this migration silently not working.

### 3.4 `kctl-dokploy` bugs found while surveying

All four are in `kodemeio-skills`, all independent of this migration:

1. **`schedules history` never returns anything.** It reads
   `executionLogs`/`logs` from `schedule.one`, which carries neither. It
   reports "No execution history" for every schedule, including ones with 11
   recorded runs. Correct source is `/deployment.allByType`.
2. **`deployments by-type` always fails.** It exposes `--type` but never sends
   the API's required `id`, so every invocation returns HTTP 400.
3. **`deployments logs` cannot find a log path** that is present in the
   deployment record's `logPath` field.
4. **Secrets printed in cleartext.** `schedules list --json` returns the full
   nested compose object including the app's entire `env` blob — `PGPASSWORD`,
   `ODOO_ADMIN_PASSWD`, `SMTP_PASSWORD`, Sentry DSNs. `notifications list
   --json` likewise prints the SMTP channel password. Both violate the
   standing "never display plaintext secrets — mask `first4****last4`" rule.

### 3.5 Dokploy does not escape shell metacharacters in a command

Discovered while executing the incident fix, and the single most important
constraint on this design.

Dokploy passes a schedule's `command` to a shell **without escaping**.
Established by single-character bisection against live Dokploy on 2026-08-31:

| Command | Result |
|---|---|
| `psql … -tAc "SELECT 1 WHERE 1 = 1"` | `done` |
| `psql … -tAc "SELECT 1 WHERE 1 < 2"` | `error` |
| `psql … -tAc "SELECT count(*) FROM …"` | `error` |
| `psql … -c "… INTERVAL '7 days'"` | `error` |
| `bash -lc "echo probe"` | `done` |

**Forbidden: `'` `(` `)` `<` `>` `|` `&` `;` `$` and backtick.** Double quotes
are safe. A command containing one dies *before* Dokploy logs its
`Running command:` line, leaving a 22-byte log reading only
`Initializing schedule` — no error text, and no alert, because of G1.

**This invalidates the original job-command design.** Commands of the form

    JOBRUN_REQUIRE='A B' jobrun backup-tpp kctl-hz -p idtpp s3 freshness …

contain `'` and `$` and would have failed every single time, silently, on all
17 jobs — reproducing the five-month incident on the alarms themselves.

**Revised design: one script per job, baked into the toolbox image.** Every
schedule's command becomes a bare, metacharacter-free token:

    jobrun backup-tpp

`jobrun` resolves the job name to `/opt/kctl/jobs/<name>.sh` in the image and
runs it. All quoting, all secret guards, and all argument construction live in
that script, where they are testable and where no shell-escaping layer can
mangle them.

This is not a novel pattern here — it is exactly what Ofelia already does.
`/opt/kodemeio/run-report.sh` exists because Ofelia has the same limitation,
and its INI carries the warning: *"NEVER wrap these in `sh -c "..."`. Ofelia
splits `command` on whitespace and DROPS quotes."* Two schedulers, same
constraint, same solution.

### 3.6 Ofelia's real scope — two instances, only one in scope

The estate runs **two** Ofelia containers on tpp-prod-01, not one:

| Container | Jobs | In scope? |
|---|---|---|
| `tpp-ofelia-reports` | 3 live `job-run` jobs: daily, weekly, selfcheck. The 4 freshness alarms are already commented out, migrated to xyOps on 2026-08-16. | **Yes** |
| `compose-…-ofelia-mailcow-1` (up 4 months) | Mailcow's own internal scheduler — `dovecot_maildir_gc`, `dovecot_quarantine`, `sogo_backup`, `phpfpm_ldap_sync`, etc., driven by container labels on the Mailcow stack. | **No — never migrate** |

`ofelia-mailcow` ships as part of the upstream Mailcow compose stack and is
vendor-managed. Migrating it would break Mailcow. It is not a Kodemeio
scheduler and is out of scope by definition.

So the migration's true scope is **17 distinct jobs**, all already represented
in `kodemeio-xyops/events/`. Ofelia contributes no job that xyOps lacks — its
3 live jobs are the same 3 reports.

### 3.7 The reports are double-scheduled today, and the recipients differ

Both schedulers currently run all three reports:

| Report | Ofelia recipient | xyOps recipient |
|---|---|---|
| daily | `$OWNER` | `$REPORT_OWNER` (same person) |
| selfcheck | `$OWNER` | `$REPORT_OWNER` (same person) |
| **weekly** | **the team** — `filbert@idtpp.com`, `wilson@idtpp.com`, `sunrudytpp@gmail.com`, BCC `trigunawan.tpp@gmail.com` | `$REPORT_OWNER` only |

Two consequences, both load-bearing:

1. **The owner receives two copies** of the daily and selfcheck reports today.
   That is existing duplication, not something this migration introduces, and
   it ends when Ofelia is retired.
2. **The team's weekly report comes from Ofelia, not xyOps.** The original
   design deferred "the team-list switch" as out of scope, on the assumption
   that both schedulers mailed the owner. That was wrong. Retiring Ofelia
   without pointing the Dokploy weekly at the team list would **silently stop
   the team's weekly report** — a migration that loses a business deliverable
   while every dashboard stays green.

   The Dokploy `report-weekly` job therefore targets the team list and the BCC
   archive from the moment it goes live, matching Ofelia's behaviour exactly.

## 4. Architecture

```
kodemeio-dokploy (this repo)             kodemeio-skills
  deploys/instances/production/            compose/toolbox.yml    <- compose source
    tpp-infra-kctl.yaml  ----------------> docker/Dockerfile.cli  <- + jobrun
      schedules: [17 entries]              config/kctl-config.yaml
  deploys/env/production/
    .env.tpp-infra-kctl                    (gitignored)
    .env.tpp-infra-kctl.example            (committed contract)
                |
                v   kctl-dokploy deploy apply -> phase_schedules
        Dokploy control plane (dokploy.idtpp.com)
                |   cron -> docker exec <resolved container> sh -c "jobrun <name>"
                v
        tpp-prod-04 : container tpp-infra-kctl      (NO docker.sock)
                |
                +-- kctl-hz      -> Hetzner S3
                +-- kctl-accurate-> Accurate API + mail.idtpp.com
                +-- kctl-pg / kctl-odoo / kctl-mailcow / kctl-dokploy

        tpp-prod-01 : host cron -> deadman-check.sh -> /deployment.allByType
                                                    -> alert mail on silence
```

Three things move out of ungoverned host state into git: the kctl config
template (today a hand-placed `/opt/kodemeio/config.template.yaml`), the 25 job
secrets (today an encrypted xyOps vault), and the job definitions.

**The toolbox needs no Docker socket.** Every job calls a remote API. Both
Ofelia and xyOps bind-mount `/var/run/docker.sock` read-write; this design drops
it, removing root-equivalent host access from the scheduling path.

## 5. Components

### 5.1 `tpp-infra-kctl` — the toolbox app

New Dokploy compose app on **tpp-prod-04** (same host as xyOps today, which has
no other production co-tenancy).

- **Compose source:** `kodemeio-skills`, new file `compose/toolbox.yml`. That
  repo already owns `compose/` and `docker/Dockerfile.cli`, so the toolbox sits
  beside the image it runs.
- **Image:** `ghcr.io/tgunawandev/kodemeio-cli:sha-2816c3c` — the same immutable
  tag every xyOps event uses today. Pinned to `sha-<shortsha>`, never `latest`.
  (The GHCR name is deliberately retained after the repo was renamed to
  `kodemeio-skills`; it is the image name, not the repo.)
- **Service name: `kctl`**, and it must be **verified against real container
  names** before any schedule is enabled — this is the exact bug that has kept
  16 schedules dead for five months (§3.3). Dokploy resolves the target as
  `{compose.appName}-{serviceName}-1`, where `appName` is Dokploy's own
  randomized name, not the manifest's.
- **Command:** `sleep infinity`. The container exists only to be exec'd into.
- **Healthcheck:** a cheap CLI invocation proving the toolset works, in the
  style of `deploys/bases/accurate-sync.yaml`
  (`test: ["CMD", "kctl-hz", "--version"]`).
- **Config mount:** `config/kctl-config.yaml` from the compose repo, read-only
  at `/root/.config/kodemeio/config.yaml`.
- **Compose requirements** (repo invariants): `restart: unless-stopped`;
  `deploy.resources.limits` with both `cpus` and `memory`; healthcheck; external
  `dokploy-network`; **no published ports** — it has no HTTP surface, so no
  Traefik domain and no DNS record.

Size the limits for the heaviest job — the weekly report pulls 10 Accurate
tenants and writes an xlsx — not for the idle state.

### 5.2 `jobrun` — the wrapper that closes G1 and G2

Baked into `docker/Dockerfile.cli` at `/usr/local/bin/jobrun`, so it is covered
by the image pin and versioned with the tools.

```
jobrun <job-name>          # NOTHING else on the command line -- see 3.5
  0. RESOLVE  /opt/kctl/jobs/<job-name>.sh, baked into the image.
              An unknown job name is a hard error, never a silent no-op.
  1. GUARD    every variable the job declares in its own REQUIRE= line is
              non-empty and contains no literal "${"  ->  exit 78
  2. RUN      timeout ${JOBRUN_TIMEOUT:-900} the job script, output captured
              and capped at ${JOBRUN_LOG_MAX:-5242880} bytes
  3. ON FAIL  python3/smtplib -> SMTP_HOST as SMTP_USER
              To: $ALERT_TO
              Subject: [ALERT] <job-name> failed (exit N)
              Body: job name, host, WIB timestamp, exit code, tail of output
              then exit with the job's real exit code, never 0
```

Design notes:

- **Baked into the image, not bind-mounted.** A missing or broken mount would
  make every job exit 0 and alert nobody — the worst available failure mode for
  an alarm. Baking it in means the image tag covers it.
- **The schedule command is a bare `jobrun <name>` and nothing more.** Per
  §3.5, Dokploy mangles any command containing `'` `(` `)` `<` `>` `|` `&` `;`
  or `$`. Arguments, quoting and secret lists therefore live inside
  `/opt/kctl/jobs/<name>.sh`, never in the Dokploy command field.
- **`timeout` and `python3` are both present** in the runtime stage
  (`python:3.12-slim`, Debian coreutils). No new dependency.
- **The mail path is already proven twice** in production: the Ofelia watchdog
  and `kodemeio-xyops/scripts/deadman-check.sh` both send alerts with exactly
  this python3/smtplib approach against `mail.idtpp.com`.
- **`jobrun` must never swallow the exit code.** Its own exit status is the
  job's, so Dokploy's `deployment` row still records `error` and the watchdog
  can read it.
- **`jobrun` failing to send mail is itself an alert condition** — print loudly
  to stderr and still exit non-zero, never exit 0 because the SMTP leg failed.
- **`jobrun` must fail loudly if invoked wrongly** (no job name, empty command).
  A wrapper that silently no-ops reproduces §3.3 one layer up.

### 5.3 Configuration

`config/kctl-config.yaml` moves from the host into the compose repo, carrying
`${VAR}` placeholders exactly as today (values never committed). It currently
defines the 10 `accurate` tenant profiles, the `tpp-trading-active` group, and
the `idtpp.hetzner` block.

**Unblocking the 10 maintenance jobs is a config change, not a code change.**
They are disabled today only because the deployed config carries no `postgres`,
`odoo`, `mailcow`, or `dokploy` blocks. Moving the config into git is what makes
adding them reviewable. The four `kod-*` jobs additionally need a `kodemeio`
profile — note that `kctl-dokploy`/`kctl-cf` for `kod-*` targets require
`-p kodemeio`, not the default `idtpp`.

### 5.4 Secrets

`deploys/env/production/.env.tpp-infra-kctl` (gitignored) with a committed
sanitized `.env.tpp-infra-kctl.example`, per the repo's standing contract.

**26 variables** — the 25 xyOps stores today, plus `REPORT_TEAM`, which is
new here because the team list currently lives hardcoded in Ofelia's
`/opt/kodemeio/run-report.sh` rather than in any secret store (§3.7):

| Group | Count | Names |
|---|---|---|
| Mail + recipients | 4 | `SMTP_PASS`, `REPORT_OWNER`, `REPORT_TEAM`, `REPORT_ARCHIVE` |
| Hetzner S3 | 2 | `IDTPP_S3_ACCESS_KEY`, `IDTPP_S3_SECRET_KEY` |
| Accurate tenants | 20 | `<TENANT>_API_TOKEN` + `<TENANT>_SIGNATURE_SECRET` for the 10 tenants in `tpp-trading-active` |

Plus non-secret env: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `MAIL_FROM`,
`ALERT_TO`, `TZ`, `KCTL_HZ_PROFILE`, `COMPOSE_PROJECT_NAME`.

`REPORT_TEAM` must be populated from Ofelia's `run-report.sh` before
`report-weekly` goes live. Getting it wrong or leaving it empty means the team
silently stops receiving the weekly report the moment Ofelia is retired.

Unblocking the maintenance jobs adds postgres/odoo/mailcow/dokploy credentials
to this file.

**Two accepted trades, both stated plainly:**

1. All jobs share one environment, versus xyOps' per-category secret grants.
   The real blast radius is unchanged — today all 25 secrets already sit in one
   vault, on one host, behind one key — and this eliminates `XYOPS_SECRET_KEY`.
2. **Dokploy's `schedule.list` returns the app's entire `env` blob in
   cleartext** to any caller holding an API key (§3.4 item 4). Putting 25
   secrets in the toolbox's Dokploy env therefore makes them readable through
   the schedule API. This is not new exposure in kind — `PGPASSWORD` and
   `ODOO_ADMIN_PASSWD` for every Odoo app are already readable the same way —
   but it is new exposure in volume, and it argues for the masking fix in §3.4
   landing sooner rather than later.

**`KCTL_HZ_PROFILE=idtpp` must be set** at the app level. `kctl-hz` does not
propagate the global `-p` flag to its `s3 freshness` subcommand; the four alarm
jobs depend on the environment variable as well as the flag.

### 5.5 The 17 schedules

Declared in `deploys/instances/production/tpp-infra-kctl.yaml` under
`schedules:`, applied by `phase_schedules`. `name` is the reconciliation key and
is **immutable** — renaming one in git creates a new schedule and orphans the
old, losing its run history. This mirrors the `title` immutability rule xyOps
documents in `events/schema.md`.

Names derive from the xyOps slug ids with the `xyo-` prefix dropped, so the
mapping stays traceable during cutover.

All schedules: `service: kctl`, `shell: sh`, `timezone: Asia/Jakarta` (set
explicitly, never inherited from `TZ`), and a command of the form
`jobrun <name>` with no other characters (§3.5).

**Business reports** — from `events/reports.yaml`:

Every Dokploy `command` is exactly `jobrun <name>` — no arguments, no quotes,
no `$`. What each job actually runs lives in `/opt/kctl/jobs/<name>.sh`.

| Name | Cron | WIB | What `/opt/kctl/jobs/<name>.sh` runs |
|---|---|---|---|
| `report-selfcheck` | `50 6 * * *` | 06:50 | `kctl-accurate reports sales-invoice-summary --profiles lumbung-yasa-dagang --from 2026-08-01 --to-today --email-to "$REPORT_OWNER" --out /tmp/selfcheck.xlsx` |
| `report-daily` | `0 7 * * *` | 07:00 | `kctl-accurate reports sales-invoice-summary --group tpp-trading-active --from 2026-01-01 --to-today --email-to "$REPORT_OWNER" --out /tmp/trade_sales_summary.xlsx` |
| `report-weekly` | `0 8 * * 1` | Mon 08:00 | as `report-daily`, but `--email-to "$REPORT_TEAM" --email-bcc "$REPORT_ARCHIVE"` — **the team list, matching Ofelia** (§3.7) |

**Backup freshness alarms** — from `events/backup-alarms.yaml`. All four run
`kctl-hz -p idtpp s3 freshness <bucket> --prefix <prefix> --max-age-hours 4`:

| Name | Cron | WIB | Bucket | Prefix |
|---|---|---|---|---|
| `backup-tpp` | `0 5 * * *` | 05:00 | `hz-tpp-odoo-filestore` | `tpp-odoo-erp/snapshots/` |
| `backup-tpp25` | `10 5 * * *` | 05:10 | `hz-tpp-odoo-filestore` | `tpp25-odoo-erp/snapshots/` |
| `backup-mac` | `20 5 * * *` | 05:20 | `hz-mac-odoo-filestore` | `mac-odoo-erp/snapshots/` |
| `backup-mac-hrms` | `30 5 * * *` | 05:30 | `hz-mac-odoo-filestore` | `mac-odoo-hrms/snapshots/` |

The ordering is deliberate and must be preserved: alarms land **before** the
06:50/07:00 reports, so a stale backup is known before the business report goes
out.

**Infrastructure maintenance** — from `events/maintenance.yaml`, all disabled
today:

| Name | Cron | WIB | Command | Blocked on |
|---|---|---|---|---|
| `maint-tpp-pg-bloat` | `0 2 * * *` | 02:00 | `kctl-pg -p idtpp bloat check` | postgres block |
| `maint-kod-pg-bloat` | `0 2 * * *` | 02:00 | `kctl-pg -p kodemeio bloat check` | postgres block + `kodemeio` profile |
| `maint-tpp-pg-backup` | `30 2 * * *` | 02:30 | `kctl-pg -p idtpp backup check` | postgres block |
| `maint-tpp-mailcow-quarantine` | `0 3 * * 0` | Sun 03:00 | `kctl-mailcow -p idtpp quarantine cleanup --days 30` | mailcow block |
| `maint-tpp-pg-health` | `0 4 * * *` | 04:00 | `kctl-pg -p idtpp health check` | postgres block |
| `maint-tpp-odoo-health` | `15 4 * * *` | 04:15 | `kctl-odoo -p idtpp health check` | odoo block |
| `maint-tpp-mailcow-health` | `30 4 * * *` | 04:30 | `kctl-mailcow -p idtpp health check` | mailcow block |
| `maint-kod-pg-health` | `45 4 * * *` | 04:45 | `kctl-pg -p kodemeio health check` | postgres block + `kodemeio` profile |
| `maint-kod-odoo-health` | `45 5 * * *` | 05:45 | `kctl-odoo -p kodemeio health check` | odoo block + `kodemeio` profile |
| `maint-kod-dokploy-health` | `50 5 * * *` | 05:50 | `kctl-dokploy -p kodemeio health check` | dokploy block + `kodemeio` profile |

A maintenance job is enabled only once its config block lands **and** its
`JOBRUN_REQUIRE` guard names the secrets it now touches. Enabling a check that
cannot reach its service reproduces exactly the "reads as coverage" failure the
events file warns about — and §3.3 is what that looks like at scale.

The four `kod-*` jobs need their target hosts verified before enabling —
`kod-prod-02` was removed from the estate, and manifests are known to reference
hosts that no longer exist.

### 5.6 Reconciliation and drift detection (cross-repo)

xyOps' `reconcile.py diff|apply|apply --prune` plus its hourly drift CI is what
makes git authoritative. `phase_schedules` is weaker: create-only. Migrating
without fixing it silently loses that guarantee.

Required in **`kodemeio-skills`** (`kctl-dokploy`):

1. Add `enabled: bool = True` to `ScheduleConfig`.
2. Turn `phase_schedules` into a reconciler: create missing, update changed
   (cron/command/service/shell/timezone), enable/disable to match, and delete
   orphans behind an explicit `--prune` flag. Key on `name`.
3. Surface a read-only drift check (non-zero exit on divergence) for CI,
   mirroring `reconcile.py diff`.
4. Fix the four bugs in §3.4 — in particular, repoint `schedules history` at
   `/deployment.allByType` and mask secrets in JSON output.

Then in this repo: a CI workflow running the drift check against live Dokploy,
replacing `kodemeio-xyops`'s drift workflow.

This repo does not host `kctl-*` source (`CLAUDE.md`: "Do not add `kctl-*`
source or package scaffolding here"), so items 1–4 land in `kodemeio-skills`.
Item 4's `schedules history` fix is a **hard prerequisite for Phase 5** — the
watchdog cannot be built on a command that always returns nothing.

### 5.7 The dead-man watchdog

`deadman-check.sh` is rewritten against Dokploy's API. Its logic is sound and
survives intact; only its data source changes:

| Today (xyOps) | After |
|---|---|
| `GET /api/app/ping` | `GET /schedule.list` reachable for the toolbox `composeId` |
| `POST /api/app/get_events/v1` -> enabled events | `schedule.list` -> `enabled: true` schedules |
| `POST /api/app/search_jobs/v1` -> last completed run | `GET /deployment.allByType?id=<scheduleId>&type=schedule` -> `status`, `startedAt`, `finishedAt` |
| interval derived from xyOps trigger arrays | interval derived from the cron expression |

Preserved behaviour, all of it load-bearing:

- Alerts when a schedule has **no completed run inside interval + grace**
  (grace = interval/4, floor 30 min). This is the actual point of the script —
  a job silently disabled in the UI still leaves the control plane answering
  normally, so reachability alone asserts almost nothing.
- Alerts when the most recent run's `status` is not `done`. **This one check,
  had it existed, would have caught §3.3 on 2026-04-09 instead of 2026-08-31.**
- **Skips disabled schedules** and reports them as skipped in log output, not as
  email. A watchdog that pages for jobs nobody expects to run is one people
  learn to ignore.
- Missing or empty credentials are themselves an alert condition — fail loudly,
  still try to mail, still exit non-zero.

**It stays on host cron on tpp-prod-01 and must never become a Dokploy
schedule.** A scheduler cannot report its own death, and if Dokploy is down the
watchdog still has to page. Same reasoning that kept the Ofelia watchdog and the
xyOps dead-man off the machines they watch.

It gains one check it could not previously have: alert if the toolbox container
is not running, which under this design is the single failure that silently
kills all 17 jobs at once.

**Scope decision:** the watchdog should check **every** enabled Dokploy
schedule, not only the 17 migrated ones. §3.3 is the argument — the estate's
existing schedules are exactly the ones nobody was watching.

## 6. Error handling

### 6.1 Failure taxonomy

| Failure | Detected by | Signal |
|---|---|---|
| Job runs, command exits non-zero | `jobrun` | immediate alert mail |
| Job runs, hangs | `jobrun` `timeout 900` | killed, alert mail |
| Required secret unset or unexpanded | `jobrun` guard | `exit 78`, alert mail, before any API call |
| Job never fires (disabled, bad cron, Dokploy cron dead) | watchdog | alert mail within interval + grace |
| **Schedule misconfigured so the command never runs** (§3.3) | watchdog `status != done` | alert mail on first failed run |
| Toolbox container down | watchdog + Dokploy healthcheck | alert mail |
| Dokploy itself down | watchdog on tpp-prod-01 | alert mail |
| Mail relay down | nothing — see §8 | **accepted residual risk** |

### 6.2 The `exit 78` guard is not optional

`expand_env` returns the literal string `${IDTPP_S3_SECRET_KEY}` for an unset
variable rather than raising. Without the guard, that literal is handed to a
remote API as a credential, and the job fails at authentication rather than at
config load — a far more confusing failure, and one that can look like a service
outage.

### 6.3 Accepted loss: catch-up (G3)

The three reports carry `catchup: true` today. Dokploy has no equivalent and
none is being built.

Rationale: catch-up exists because the conductor might be down at fire time.
Under this design the watchdog notices a missed report inside its interval +
grace and pages, and recovery is `kctl-dokploy -p idtpp schedules run <id>` — a
deliberate re-fire by an operator who can see current state. Automatic catch-up
can instead mail a stale report hours late, unattended, which for a business
report sent to people is worse than a gap plus a page.

This is a genuine capability reduction and is recorded as such rather than
papered over.

## 7. Verification

Nothing is trusted because it was configured — §3.3 is what that costs. Each
phase has a verification that observes the real system.

| Phase | Verification |
|---|---|
| 0 | Existing-schedule sweep is green, or every failure is explained and fixed. |
| 1 | Toolbox container running and healthy; `docker exec` reaches `kctl-hz --version`; **actual container name matches what Dokploy will resolve**; no docker.sock in the container's mounts. |
| 2 | Each maintenance job run via `schedules run`, then its `deployment.allByType` row confirmed `status: done` — not merely "the CLI said OK". |
| 3 | Alarms produce identical verdicts to xyOps for the same buckets over at least one full day. **Then a failure is deliberately induced** (a prefix known to be stale) and the alert mail is confirmed to arrive in the inbox. |
| 4 | Reports arrive once, with the same attachment, to the same recipients. |
| 5 | Watchdog run manually against live Dokploy: reports OK; then a schedule is disabled and it is confirmed to alert. |
| 6 | Drift check exits non-zero after a deliberate UI edit, and zero after `apply`. |
| 7 | 14 days with no missed job and no silent failure. |

Two tests carry most of the weight. **Phase 3's induced failure** is the only
thing that proves G1 was actually closed rather than assumed closed because a
wrapper exists. **Phase 2's `status: done` check** is the only thing that
distinguishes "the schedule was created" from "the schedule works" — the
distinction that hid §3.3 for five months.

## 8. Risks

| Risk | Severity | Mitigation |
|---|---|---|
| **Schedule silently misconfigured and never runs** — realized, 16 times, for 5 months (§3.3) | **High** | Verify by `status: done` on a real run, never by successful creation. Watchdog covers all schedules, not just migrated ones. |
| Toolbox container dies -> all 17 jobs stop silently | High | Dokploy healthcheck + `restart: unless-stopped` + watchdog checks container state explicitly. |
| `schedules history` is broken, so history is invisible from the CLI | Medium | §3.4 item 1 is a hard prerequisite for Phase 5. Until fixed, use `/deployment.allByType` directly. |
| Mail relay (`mail.idtpp.com`) down -> alerts silently lost | Medium | **Accepted residual.** Same exposure as today; both current schedulers alert by mail through the same relay. A second channel was considered and declined in D3; revisit if it bites. |
| Report double-send during cutover | Medium | Phase 4 is a same-morning atomic swap: enable Dokploy's and disable xyOps' together, never one then the other. Same procedure as the Ofelia -> xyOps report cutover. |
| 25 secrets readable via `schedule.list` | Medium | Accepted (§5.4); argues for §3.4 item 4 landing early. |
| Renaming a schedule in git orphans it | Low | `name` documented as immutable; drift check surfaces the orphan. |
| `kod-*` maintenance jobs target hosts that may not exist | Low | Verify each host before enabling; `kod-prod-02` is known removed. |

The original top risk — *"schedule run-history shape is unverified"* — is
**resolved**. History lives at `/deployment.allByType`, its shape is recorded in
§3, and it was validated against ~160 real rows.

## 9. Sequencing

Riskiest last. Each phase is independently revertible.

| Phase | Work | Risk if wrong |
|---|---|---|
| **0** | **Fix the live incident (§3.3)**, independent of everything below: repoint `deploys/bases/odoo.yaml` to a real service, verify a run reaches `status: done`, delete the four debris schedules. | none — currently 100% broken |
| 1 | `compose/toolbox.yml`, `jobrun` in `Dockerfile.cli`, config into git, `.env` + `.env.example`, manifest, deploy. **No schedules yet.** Verify the resolved container name. | none — nothing scheduled |
| 2 | The 10 maintenance jobs: add config blocks, add guards, create schedules, enable. They do not run today, so there is nothing to break. This is where the mechanics get learned with nothing at stake. | none |
| 3 | The 4 alarms, running **in parallel** with xyOps. Read-only idempotent checks, so duplicate alerts are harmless and are themselves proof the path works. Induce a real failure. | low |
| 4 | The 3 reports. **Not** parallel-safe — two schedulers would mail two copies to people. Same-morning atomic swap. | medium |
| 5 | Watchdog rewrite; swap tpp-prod-01 host cron from the xyOps version to the Dokploy version. Requires §3.4 item 1. | high if wrong |
| 6 | `kctl-dokploy` reconciler (§5.6) + drift CI in this repo. | low |
| 7 | 14-day rollback window, then decommission `tpp-infra-xyops` and `tpp-infra-xyops-backup`. | — |

Phase 0 is not a prerequisite for Phase 1 in a technical sense — it is listed
first because it is a live production defect and the migration is not.

**Rollback.** Through Phase 6, rollback is: disable the Dokploy schedules,
re-enable the xyOps events, done. xyOps stays deployed and functional the entire
time — the same 14-day window discipline the Ofelia cutover used.

**Decommissioning (Phase 7)** removes both xyOps apps, the restic backup stack,
and the `xyops-data` volume. Retain `XYOPS_SECRET_KEY` in 1Password until the
final data-volume backup is discarded — the key is worthless without the volume,
but the volume is unrecoverable without the key.

## 10. Out of scope

- **`ofelia-mailcow`** — Mailcow's own internal scheduler (§3.6). Vendor-managed,
  part of the upstream Mailcow stack, and never to be migrated.

`tpp-ofelia-reports` is NO LONGER out of scope. It owns the team's weekly
report (§3.7), so retiring xyOps without retiring it would leave the estate on
two schedulers and leave the team's report on the one being abandoned. Its
three jobs are decommissioned as part of Phase 4's atomic swap.
- **The four `kctl-dokploy` bugs** (§3.4) — real findings, fixed independently
  in `kodemeio-skills`. Only item 1 blocks a phase here.
- Anything in the xyOps adoption beyond Project 1 (fleet-wide xySat, monitors,
  tickets). Those were never built and are not being replaced.
- Plausible's schedules in `deploys/bases/plausible.yaml` — not surveyed here
  because no Plausible compose app is currently deployed to check against.
