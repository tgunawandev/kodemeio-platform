# dokploy-admin — extra runbooks

> This file is merged into SKILL.md by `kctl-dokploy skill generate`.
> Put anything here that should survive regeneration: narrative workflows,
> gotchas, one-command recipes, troubleshooting.

## Compose Postgres Backup → S3 → Local Restore (prod → local)

Two different "restore" stories, pick the right one:

| Target | Command | What happens |
|---|---|---|
| Dokploy-managed compose (same or different Dokploy host) | `backups restore` | Streams Dokploy's native SSE log (`backup.restoreBackupWithLogs`). No local download. |
| Raw postgres on your laptop (or any non-Dokploy postgres) | `backups pull` | boto3 download → decompress → drop+recreate → pg_restore. |

For developers pulling prod dumps down to a local postgres running on
`localhost:5434`, use `backups pull`. It's the one-command flow below.

### One-command recipe — prod → local postgres

```bash
kctl-dokploy -p idtpp backups pull <backup_id> \
    --target-host localhost --target-port 5434 \
    --target-user odoo --target-password <pwd> \
    --target-db tpp_odoo_erp \
    --trigger --force
```

What this does:

1. Looks up the backup config via `/backup.one` — extracts destinationId,
   S3 bucket, prefix, source DB name.
2. With `--trigger`: fires the appropriate `/backup.manualBackup*` endpoint
   (postgres / compose / mysql / ...) and polls S3 every 10 s (configurable
   via `--poll-interval`) for a NEW object with `LastModified` after
   trigger time, up to `--wait-timeout` seconds (default 300).
3. Without `--trigger`: picks the newest existing object under the backup's
   prefix — no fresh dump, no production load.
4. Downloads the object via boto3 using the destination's stored credentials.
5. Gunzips if `.gz`; magic-byte-detects `PGDMP` for pg_restore custom format
   vs. plain SQL.
6. Drops the target DB (terminating active connections via `pg_terminate_backend`)
   and recreates it with `OWNER=<--owner | --target-user>`. Prompts
   unless `--force`.
7. `pg_restore --no-owner --no-privileges --clean --if-exists` (custom) or
   `psql -f` (plain) against `--target-host:--target-port`.
8. Smoke test: `SELECT count(*) FROM res_users` (best-effort, non-fatal).
9. Cleans up the downloaded file unless `--keep-download`.

### Finding the backup_id

```bash
# 1. List composes on the source profile, grab the composeId for the DB service.
kctl-dokploy -p idtpp compose list

# 2. List backup configs scoped to that compose.
kctl-dokploy -p idtpp backups list --compose <compose_id>

# 3. Pick the row whose "Database" matches the DB you want — that's <backup_id>.
kctl-dokploy -p idtpp backups get <backup_id>
```

### `--trigger` vs. latest existing

- **Default (no `--trigger`)**: reuses the newest scheduled backup already in
  S3. Zero production load, dump freshness = `<= schedule interval`.
- **`--trigger`**: fires a manual dump first. Dump freshness = "right now".
  Costs prod CPU/IO for the dump duration; use when yesterday's nightly
  isn't fresh enough (e.g. debugging a bug introduced today).

Prefer `--trigger` when debugging _today's_ state; prefer default when
catching up development data.

### Target types

**`--target-host` (raw postgres — local dev)**

```bash
kctl-dokploy -p idtpp backups pull <backup_id> \
    --target-host localhost --target-port 5434 \
    --target-user odoo --target-password <pwd> \
    --target-db tpp_odoo_erp --force
```

`PGPASSWORD` env var is used as the fallback if `--target-password` is omitted.

**`--target-compose` (Dokploy-managed on the current profile's host)**

```bash
kctl-dokploy -p local backups pull <backup_id> \
    --target-compose <target_compose_id> \
    --target-user odoo --target-db tpp_odoo_erp \
    --target-service postgres --force
```

Resolves the running postgres container via `docker ps` labels
(`com.docker.compose.project=<appName>`, `com.docker.compose.service=<svc>`)
and runs `docker exec -i <container> pg_restore`. The command that calls
this needs docker socket access on the local host — for cross-host restores
use `backups restore` (native Dokploy SSE) instead.

### Other pull-flow commands

**`backups run-wait`** — trigger + poll without downloading/restoring.
Useful in CI to wait for a nightly without restoring locally:

```bash
kctl-dokploy -p idtpp backups run-wait <backup_id> --timeout 600
# prints: s3://<bucket>/<key>
```

**`backups download`** — standalone S3 download using a destination's creds:

```bash
kctl-dokploy -p idtpp backups download <s3_key> \
    --destination <destination_id> --output /tmp/dump.sql.gz
```

**`backups list-files`** — list objects in a destination (now boto3-backed;
no more "Input validation failed"):

```bash
# List everything (up to --limit, default 200)
kctl-dokploy -p idtpp backups list-files --destination <destination_id>

# Filter client-side by substring
kctl-dokploy -p idtpp backups list-files --destination <destination_id> --search tpp_odoo_erp

# Filter S3-side by prefix (faster for huge buckets)
kctl-dokploy -p idtpp backups list-files --destination <destination_id> \
    --prefix 'compose-xyz/postgres/'
```

### Dokploy-managed restore (`backups restore`)

When the target lives inside Dokploy (on the same host as the CLI's
profile), use the native SSE path — Dokploy runs pg_restore itself via
`docker exec`, no local download:

```bash
kctl-dokploy -p <target-profile> backups restore \
    --compose <target-compose-id> \
    --destination <target-destination-id> \
    --database-name <db-name> \
    --service-name postgres \
    --database-user odoo \
    --latest <db-name>
```

Exit 0 on success, 1 on Dokploy error, 2 on transport failure. Dokploy's
log lines stream to stdout prefixed `[Dokploy]`.

### Metadata flags — why they matter (applies to `backups restore`)

`--service-name` and `--database-user` map to `metadata.serviceName` and
`metadata.postgres.databaseUser` in the tRPC payload. Without them
Dokploy runs `docker exec -i sh` (wrong container) and `pg_restore -U ''`
(empty user). The CLI exits 1 immediately if either is omitted.

| DB type | Required flags |
|---|---|
| `postgres` (default) | `--service-name`, `--database-user` |
| `mariadb` / `mongo` | `--service-name`, `--database-user`, `--database-password` |
| `mysql` | `--service-name`, `--database-password` |

### Troubleshooting

| Symptom | Cause + fix |
|---|---|
| `Compose '<id>' not found` | Wrong compose ID for that profile. Re-run `kctl-dokploy --profile <name> compose list` and copy the ID column exactly (case-sensitive). |
| `Backup '<id>' not found` (during `backups pull`) | `backup_id` belongs to a different profile. `pull` uses the profile passed to `-p`; run `kctl-dokploy -p <src> backups list --compose <id>` on the correct profile. |
| `Timed out after Ns waiting for a new backup` (with `--trigger`) | Source dump is slow or cron is disabled. Bump `--wait-timeout 900`; check `backups get <id>` to confirm `enabled=True`. |
| `No S3 objects found under prefix '...'` (without `--trigger`) | No scheduled dump exists yet. Run once with `--trigger` or verify the nightly schedule via `backups list --compose <id>`. |
| `Error: ... no such container` in Dokploy log (during `backups restore`) | `--service-name` doesn't match the postgres service label in the compose YAML. Check with `kctl-dokploy --profile <name> compose loadServices --compose <id>`. |
| `pg_restore: error: role "<user>" does not exist` | `--target-user` / `--database-user` is wrong or role hasn't been created on the target. Verify with `psql -U postgres -c '\du'`. |
| `docker exec` errors with `No running postgres container found` (during `backups pull --target-compose`) | `--target-service` doesn't match the service in the target compose (default is `postgres`). Inspect with `docker ps --filter label=com.docker.compose.project=<appName>`. |
| `UndefinedColumn` errors after restore | Source DB schema is ahead of target (module upgraded on source). Run `kctl-odoo -p <target-profile> modules upgrade <module>`. |
| Transport / auth failure (exit 2 from `backups restore`) | API key or Dokploy URL wrong for the target profile. Run `kctl-dokploy -p <profile> config test`. |

## Fast Log Debugging

See `packages/kctl-odoo/README.md` and CLAUDE.md for `kctl-odoo logs
tail`, which layers Odoo-aware filters (`--level`, `--module`,
`--request`, `--worker`, `--grep`) on top of `kctl-dokploy compose
service-logs -f`. Tracebacks are captured as whole blocks so
`--level ERROR` keeps the full `Traceback (most recent call last): ...`
body.
