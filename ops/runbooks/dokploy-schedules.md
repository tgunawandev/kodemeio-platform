# Dokploy scheduled jobs — constraints and verification

Dokploy's Schedule Jobs feature has two properties that make a broken schedule
invisible. Both were established against the live instance on 2026-08-31, after
16 of 18 schedules were found to have failed **100% of their runs since
2026-04-09** with nobody noticing.

## 1. There is no failure alerting. At all.

Notification channels carry only `appDeploy`, `appBuildError`,
`databaseBackup`, `volumeBackup`, `dokployRestart`, `dokployBackup`,
`dockerCleanup`, `serverThreshold`. Grepping the entire OpenAPI spec for
schedule-related keys returns only `scheduleId`, `schedule`, `scheduleType`.

**A scheduled job that fails every single time notifies nobody, forever.**

Anything whose value is its exit code — a freshness alarm, a health check —
must carry its own alerting. Do not schedule a check and assume you will hear
about it.

## 2. Shell metacharacters are not escaped

Dokploy passes a schedule's `command` to a shell without escaping. Established
by single-character bisection on `mac-odoo-erp-session-cleanup`:

| Command | Result |
|---|---|
| `psql … -tAc "SELECT 1 WHERE 1 = 1"` | `done` |
| `psql … -tAc "SELECT 1 WHERE 1 < 2"` | `error` |
| `psql … -tAc "SELECT count(*) FROM …"` | `error` |
| `psql … -c "… INTERVAL '7 days'"` | `error` |
| `bash -lc "echo probe"` | `done` |

**Forbidden in a command: `'` `(` `)` `<` `>` `|` `&` `;` `$` `` ` ``.**
Double quotes are safe.

A command containing one of these dies *before* Dokploy logs its
`Running command:` line. The log is 22 bytes reading only
`Initializing schedule` — no error text, no exit code, no alert.

**Consequence:** anything needing a comparison, a function call, a quoted
literal, a pipe or a redirect **cannot be expressed inline**. Put it in a
script baked into the image and invoke it with a bare
`bash /path/to/script.sh`. See `kodemeio-odoo/scripts/session-cleanup.sh`.

`deploys/tests/test_odoo_base_schedules.py::test_no_command_contains_shell_metacharacters`
guards the Odoo base against regression.

## 3. `serviceName` must match a real compose service

Dokploy resolves the target container as `{compose.appName}-{serviceName}-1`,
where `appName` is Dokploy's own randomized name, not the manifest's. An
unmatched name resolves to an **empty string**, producing:

```
Running command: docker exec  bash -c 'vacuumdb -U odoo -d mac_odoo_erp --analyze'
Error response from daemon: No such container: bash
```

That double space is the empty container name. `deploys/bases/odoo.yaml`
declared `service: odoo` while the real services are `odoo-web` / `odoo-cron` /
`odoo-gevent`, which is what broke 14 schedules for five months.

Always check `docker ps` on the target host before trusting a new schedule.

## How to verify — never trust "created"

`kctl-dokploy schedules history` is unusable: it reads `executionLogs` off
`schedule.one`, which carries no run history, so it reports "No execution
history" for every schedule. `kctl-dokploy deployments by-type` never sends the
API's required `id` and always returns HTTP 400.

Real run history is at `GET /deployment.allByType?id=<scheduleId>&type=schedule`.

Use the repo tool, which exits non-zero if any enabled schedule is unhealthy:

```bash
uv run python ops/scripts/schedule-status.py --profile idtpp
uv run python ops/scripts/schedule-status.py --profile idtpp --json
```

A schedule counts as healthy only when its **most recent run reports
`status: done`**. An enabled schedule that has never run is unhealthy, not
unknown — and finding zero schedules at all exits non-zero too, because that
means the query broke.

To read a failing run's log, get its `logPath` from `/deployment.allByType`
and cat it on the app's host:

```bash
ssh root@<host> 'cat /etc/dokploy/schedules/<appName>/<appName>-<timestamp>.log'
```

## Repairing the Odoo maintenance schedules

`ops/scripts/fix-odoo-schedules.py` updates them in place (idempotent; `--dry-run`
first). It updates rather than deletes because `schedule.update` accepts
`serviceName` even though `kctl-dokploy schedules update` exposes no `--service`
flag.

## Known open items

- The 7 `*-session-cleanup` schedules invoke
  `bash /opt/odoo/scripts/session-cleanup.sh`. They stay red until the Odoo
  image is rebuilt at or after `kodemeio-odoo c7581b9` and those apps are
  redeployed.
- `tpp-odoo-erp`, `tpp-odoo-hrms` and `tpp25-odoo-erp` have a `-vacuum`
  schedule but no `-session-cleanup` yet, deliberately — it will be created by
  `phase_schedules` on their next deploy, once the image carries the script.
- `kctl-dokploy schedules list --json` and `notifications list --json` return
  app env blobs and SMTP passwords in cleartext. Do not paste that output.
