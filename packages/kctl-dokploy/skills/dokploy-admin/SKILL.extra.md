# dokploy-admin — extra runbooks

> This file is merged into SKILL.md by `kctl-dokploy skill generate`.
> Put anything here that should survive regeneration: narrative workflows,
> gotchas, one-command recipes, troubleshooting.

## Compose Postgres Backup → S3 → Local Restore (prod → local)

Dokploy's native `/backup.manualBackupCompose` endpoint is a **platform-wide
bug**: throws 400 even on known-working configs. **Do not rely on it.**
Two reliable paths instead:

- **Scheduled nightly (cron `0 2 * * *`)** — Dokploy *writes* to S3 on a
  cron just fine; only the on-demand trigger is broken. Recent nightly
  backups already exist in S3 for production composes. Prefer this when
  data from last night is fresh enough.
- **Fresh dump via SSH** — `kctl-dokploy backups dump-compose` SSHes to
  the compose's server, runs `pg_dump -F c`, streams straight to S3.
  Use when you need post-cron data or there's no schedule configured.

### Prerequisites

- **SSH access** to the source compose's server from wherever `kctl-dokploy`
  runs. The command invokes `ssh root@<server-ip>` with
  `StrictHostKeyChecking=accept-new`; your SSH key must be authorised on
  the remote host.
- **Two Dokploy profiles** configured in `~/.config/kodemeio/config.yaml`
  via `kctl-dokploy config init`: one pointing at the source Dokploy
  (e.g. `idtpp` → `dokploy.idtpp.com`), one at the target (e.g. `local`
  → `http://localhost:3000`). The profile model separates *which Dokploy
  instance* each command talks to; the `--source-profile` and `-p` flags
  pick between them.
- **Same S3 bucket registered on both sides**: `backups add-destination`
  must run once against each profile, using identical bucket + creds so
  both sides can read the same files.
- **Target compose running** on the host where `kctl-dokploy` runs.
  `restore-local` uses `docker exec` (no SSH for the target) — the
  postgres container must be reachable via the local docker socket.
- **boto3 + aws CLI not required separately** — boto3 ships as a
  `kctl-dokploy` dep; S3 creds come from the destination record.

### ID lookup cheat sheet

Before any command, grab the four IDs you'll need. **Every command below
takes at least one of these** — they are the most common reason a
generated one-liner fails with `Compose 'X' not found`.

```bash
# Source compose ID (prod side)
kctl-dokploy --profile idtpp compose list
# → ID column. For tpp-odoo-erp compose: Qki8U2u4Ltstq0_6zW7UE

# Target compose ID (local side)
kctl-dokploy --profile local compose list

# Source destination ID (S3 bucket on prod Dokploy)
kctl-dokploy --profile idtpp backups destinations
# → ID column. Example: KiWBiVzZb2EoyUDURKDQO

# Target destination ID (same bucket, registered locally)
kctl-dokploy --profile local  backups destinations

# Database name — Odoo convention is <tenant>_odoo_<app>:
# tpp_odoo_erp, tpp_odoo_hrms, mac_odoo_erp, mac_odoo_hrms, authentik, outline
```

### Decision: fresh dump or `--latest`?

| Situation | Use |
|---|---|
| "Just give me yesterday's data" (most common case) | `refresh --latest` |
| "I need data from the last hour" (no cron window yet) | `refresh` (default = fresh dump) |
| "I want to test restore without touching prod" | `refresh --latest` |
| "Prod is under load, don't add more" | `refresh --latest` |
| "Scheduled backup isn't configured for this compose" | `refresh` (default = fresh dump) |
| "I'm investigating a specific bug that happened 10 min ago" | `refresh` (default = fresh dump) |

### One-shot recipes

**Pull yesterday's nightly (fast, no prod load):**

```bash
kctl-dokploy --profile local backups refresh \
    --source-profile idtpp \
    --source-compose <prod-compose-id> \
    --source-destination <idtpp-dest-id> \
    --target-compose <local-compose-id> \
    --database tpp_odoo_erp \
    --latest \
    --force
```

The newest S3 key containing `tpp_odoo_erp` wins. No SSH. No pg_dump.

**Fresh dump (data must be as of now):**

```bash
kctl-dokploy --profile local backups refresh \
    --source-profile idtpp \
    --source-compose <prod-compose-id> \
    --source-destination <idtpp-dest-id> \
    --target-compose <local-compose-id> \
    --database tpp_odoo_erp \
    --force
```

SSHes to the source server, `docker exec pg_dump -F c`, streams to S3,
then downloads and restores into the target. Typical: 30s for a 15 MB DB.

### Step-by-step flow (scripting, inspection, or partial runs)

All three kctl-dokploy backup subcommands can stand alone. Each prints
its S3 key on stdout so you can pipe them together.

```bash
# 1. Dump source compose's DB → S3 (auto-SSHes to compose's serverId).
#    Prints the S3 key to stdout on success.
S3_KEY=$(kctl-dokploy --profile idtpp backups dump-compose \
    --compose <id> --destination <dest-id> \
    --database tpp_odoo_erp --service postgres)

# 2. Download the dump from S3 to local disk.
kctl-dokploy --profile local backups download \
    "$S3_KEY" \
    --destination <local-dest-id> \
    --output /tmp/dump.dump

# 3. Restore into local compose's postgres container.
kctl-dokploy --profile local backups restore-local \
    /tmp/dump.dump --compose <local-compose-id> \
    --service postgres --db-name tpp_odoo_erp --force
```

To use a scheduled nightly in the three-step form, list first:

```bash
kctl-dokploy --profile idtpp backups list-files \
    --destination <dest-id> --search tpp_odoo_erp
# Copy the newest key, then proceed to step 2 above.
```

### How it works

- `dump-compose` resolves the compose's `serverId` from the Dokploy API,
  SSHes to that server, finds the postgres container via `docker ps` +
  `com.docker.compose.service` label, runs `pg_dump -F c`, and streams
  stdout straight to S3. Never writes to the SSH host's disk.
- `download` reads the S3 credentials out of the Dokploy destination
  record (via `/destination.one`) and pulls the key to a local path.
- `restore-local` auto-resolves the target postgres container using the
  compose's `appName` + `com.docker.compose.service` label. Uses
  `pg_restore --no-owner --exit-on-error` for custom-format dumps
  (magic bytes `PGDMP`), or `psql -v ON_ERROR_STOP=1` for plain SQL.
  Drops + recreates the target DB first (override with
  `--no-drop-recreate` if you want to keep existing rows).
- `refresh` orchestrates all three with proper tempdir cleanup. With
  `--latest` it skips step 1 entirely and picks the newest S3 key whose
  filename contains the `--database` value (override the substring via
  `--key-filter`).

### Troubleshooting

| Symptom | Cause + fix |
|---|---|
| `Compose '<id>' not found` | Wrong compose ID for that profile. Re-run `kctl-dokploy --profile <name> compose list` and copy the ID column exactly (they're case-sensitive). |
| `No container found for compose '<appName>' service 'postgres'` | Service name in the compose YAML isn't `postgres`. Check with `kctl-dokploy --profile <name> compose loadServices --compose <id>` (or `docker ps` on the server). Pass `--service <actual-name>`. |
| `POSTGRES_PASSWORD not found in compose env` | The compose doesn't expose postgres creds in its merged env. Set them via `kctl-dokploy env set` or populate `POSTGRES_PASSWORD` in the env file. |
| `psycopg2.errors.InFailedSqlTransaction: current transaction is aborted` | A prior request on a postgres worker raised inside a transaction and the connection is poisoned. `docker restart <odoo-web-container>` on the server drops the stale connections. |
| `pg_dump: error: connection to server on socket "/var/run/..." failed` | The `pg_dump` ran *outside* the postgres container. Check that `--service` matches the postgres container, not odoo-web or odoo-cron. |
| `pg_restore: error: input file appears to be a text format dump. Please use psql.` | File is plain SQL but named `.dump`. Either rename to `.sql`, or let `restore-local` detect automatically (it uses the `PGDMP` magic bytes, not the extension). |
| `UndefinedColumn` errors after a fresh restore | Source DB schema drifted (module upgraded on source but target is behind). Run `kctl-odoo -p <target-profile> modules upgrade <module>` on the target. |
| `Permission denied (publickey)` on SSH | Your local key isn't authorised on the source server. Either add it to `/root/.ssh/authorized_keys` or use `--no-ssh` and run from the source host directly. |
| `No S3 files in bucket 'X' contain 'database_name'` (under `--latest`) | No scheduled backup has written that database yet. Either configure a backup via `backups create`, or drop `--latest` for a one-off fresh dump. |

## Fast Log Debugging

See `packages/kctl-odoo/README.md` and CLAUDE.md for `kctl-odoo logs
tail`, which layers Odoo-aware filters (`--level`, `--module`,
`--request`, `--worker`, `--grep`) on top of `kctl-dokploy compose
service-logs -f`. Tracebacks are captured as whole blocks so
`--level ERROR` keeps the full `Traceback (most recent call last): ...`
body.
