# dokploy-admin — extra runbooks

> This file is merged into SKILL.md by `kctl-dokploy skill generate`.
> Put anything here that should survive regeneration: narrative workflows,
> gotchas, one-command recipes, troubleshooting.

## Compose Postgres Backup → S3 → Local Restore (prod → local)

The canonical restore workflow uses Dokploy's native SSE endpoint
(`/api/trpc/backup.restoreBackupWithLogs`). Dokploy's server does the
actual `pg_restore` via `docker exec` on the Dokploy host — no SSH from
the client, no local temp files.

Full reference: `runbooks/postgres-restore.md`.

### Prerequisites

- **kctl-dokploy ≥ 0.4.0** with a valid profile in
  `~/.config/kodemeio/config.yaml`.
- **S3 destination registered on the target Dokploy** — same bucket as
  the source. Run `backups add-destination` once against the target
  profile. Destination `provider` must be `"Other"` (not `"s3"`) for
  Hetzner Object Storage — rclone rejects the `"s3"` enum value.
- **`odoo` role is SUPERUSER** on both the source and target postgres
  instances. On TPP/MAC prod and local, this is already the case.
- **Target DB pre-created** — Dokploy's native restore does NOT create
  the DB. Use the `kodemeio-postgres` image's `SERVICE_DATABASES` env var
  to pre-create with `OWNER=odoo` and `LC_COLLATE=en_US.utf8`. See §3 of
  the runbook.

### ID lookup cheat sheet

```bash
# Compose IDs
kctl-dokploy --profile idtpp compose list
kctl-dokploy --profile local  compose list

# Destination IDs
kctl-dokploy --profile idtpp backups destinations
kctl-dokploy --profile local  backups destinations

# DB name convention: <tenant>_odoo_<app>
# e.g. tpp_odoo_erp, tpp_odoo_hrms, mac_odoo_erp, mac_odoo_hrms
```

### One-shot restore (latest S3 key)

```bash
kctl-dokploy -p <target-profile> backups restore \
    --compose <target-compose-id> \
    --destination <target-destination-id> \
    --database-name <db-name> \
    --service-name postgres \
    --database-user odoo \
    --latest <db-name>
```

Picks the newest S3 object whose key contains `<db-name>`, invokes
Dokploy's native restore, streams log lines prefixed `[Dokploy]` to your
terminal. Exit 0 on success, 1 on Dokploy error, 2 on transport failure.

**Example — restore latest prod `mac_odoo_erp` to local:**

```bash
kctl-dokploy -p local backups restore \
    --compose BAP6JmrmLJYnSIJ3YZOb_ \
    --destination v6gJBPvatXxuArLtEqR09 \
    --database-name mac_odoo_erp \
    --service-name postgres \
    --database-user odoo \
    --latest mac_odoo_erp
```

### Restore from a specific historical backup

List candidates via rclone (Dokploy's own `listBackupFiles` is buggy):

```bash
docker run --rm rclone/rclone \
    --s3-provider=Other \
    --s3-access-key-id=<KEY> --s3-secret-access-key=<SECRET> \
    --s3-region=<REGION> --s3-endpoint=<ENDPOINT> \
    --s3-no-check-bucket --s3-force-path-style \
    lsl ':s3:<BUCKET>/' | grep <db-name>
```

Then pass the key with `--file <s3-key>` instead of `--latest`.

### Metadata flags — why they matter

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
| `Error: ... no such container` in Dokploy log | `--service-name` doesn't match the postgres service label in the compose YAML. Check with `kctl-dokploy --profile <name> compose loadServices --compose <id>`. |
| `pg_restore: error: role "<user>" does not exist` | `--database-user` is wrong or role hasn't been created on the target. Verify with `psql -U postgres -c '\du'`. |
| `UndefinedColumn` errors after restore | Source DB schema is ahead of target (module upgraded on source). Run `kctl-odoo -p <target-profile> modules upgrade <module>`. |
| Transport / auth failure (exit 2) | API key or Dokploy URL wrong for the target profile. Run `kctl-dokploy -p <profile> config test`. |
| `No S3 files ... contain '<db-name>'` | No scheduled backup written yet for that DB. Check cron schedule via `kctl-dokploy -p idtpp backups list`. |

## Fast Log Debugging

See `packages/kctl-odoo/README.md` and CLAUDE.md for `kctl-odoo logs
tail`, which layers Odoo-aware filters (`--level`, `--module`,
`--request`, `--worker`, `--grep`) on top of `kctl-dokploy compose
service-logs -f`. Tracebacks are captured as whole blocks so
`--level ERROR` keeps the full `Traceback (most recent call last): ...`
body.
