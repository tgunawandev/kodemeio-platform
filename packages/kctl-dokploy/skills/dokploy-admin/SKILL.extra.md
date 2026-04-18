# dokploy-admin — extra runbooks

> This file is merged into SKILL.md by `kctl-dokploy skill generate`.
> Put anything here that should survive regeneration: narrative workflows,
> gotchas, one-command recipes, troubleshooting.

## Compose Postgres Backup → S3 → Local Restore (prod → local)

Dokploy's native `/backup.manualBackupCompose` endpoint is unreliable for
postgres running inside a compose stack (it assumes the env's `POSTGRES_DB`
matches an actual database, which often isn't true on shared postgres
instances). kctl-dokploy ships an alternative that runs `pg_dump` directly
via SSH+docker exec and streams straight to S3 — **bypasses Dokploy's
backup system entirely**.

### One-time setup per bucket

```bash
# 1. Create Hetzner S3 bucket
kctl-hz s3 mb hz-tpp-postgres-backup

# 2. Register as Dokploy destination on SOURCE AND TARGET profiles
#    (same bucket, same creds — just one entry on each Dokploy instance)
kctl-dokploy --profile idtpp backups add-destination \
    --name hz-tpp-postgres-backup --bucket hz-tpp-postgres-backup \
    --access-key "$HZ_ACCESS" --secret-key "$HZ_SECRET" \
    --region fsn1 --endpoint https://fsn1.your-objectstorage.com

kctl-dokploy --profile local backups add-destination \
    --name hz-tpp-postgres-backup --bucket hz-tpp-postgres-backup \
    --access-key "$HZ_ACCESS" --secret-key "$HZ_SECRET" \
    --region fsn1 --endpoint https://fsn1.your-objectstorage.com
```

### One-shot refresh

```bash
kctl-dokploy --profile local backups refresh \
    --source-profile idtpp \
    --source-compose <prod-compose-id> \
    --source-destination <idtpp-dest-id> \
    --target-compose <local-compose-id> \
    --database tpp_odoo_erp \
    --force
```

Tested live against `tpp-odoo-erp.idtpp.com` (16.55 MB dump, ~30s
round-trip including restore into local postgres-16).

### Step-by-step flow

For scripting, investigation, or when you want the downloaded dump on
disk for later reuse:

```bash
# 1. Dump source compose's DB → S3 (auto-SSHes to compose's serverId)
kctl-dokploy --profile idtpp backups dump-compose \
    --compose <id> --destination <dest-id> \
    --database tpp_odoo_erp --service postgres

# 2. Download the dump from S3 to local disk
kctl-dokploy --profile local backups download \
    tpp-infra-postgres/tpp_odoo_erp-2026-04-18T03-37-23Z.dump \
    --destination <local-dest-id> \
    --output /tmp/dump.dump

# 3. Restore into local compose's postgres container
kctl-dokploy --profile local backups restore-local \
    /tmp/dump.dump --compose <local-compose-id> \
    --service postgres --db-name tpp_odoo_erp --force
```

### How it works

- `dump-compose` resolves the compose's `serverId` from the Dokploy API,
  SSHes to that server, finds the postgres container via `docker ps` +
  `com.docker.compose.service` label, runs `pg_dump -F c`, and streams
  stdout straight to S3. Never writes to the SSH host's disk.
- `restore-local` auto-resolves the target postgres container using the
  compose's `appName` + service label. Uses `pg_restore --exit-on-error`
  for custom-format dumps (magic bytes `PGDMP`), or
  `psql -v ON_ERROR_STOP=1` for plain SQL.
- `refresh` orchestrates both in a single call with proper tempdir cleanup.
- S3 credentials are read from the Dokploy destination record — no
  separate credential setup beyond `add-destination`.

### Gotchas

- If the prod postgres has a DB name different from its `POSTGRES_DB`
  env var (shared-postgres pattern), **name it explicitly** with
  `--database`. Dokploy's native backup can't handle this; our command
  can.
- For `--follow`-style live progress on a large dump, tail the SSH log
  in another terminal: `kctl-dokploy compose service-logs <id> -f`.
- Custom-format dumps (`-F c`, default) are internally compressed —
  **do not** append `.gz` to filenames; `pg_restore` will refuse to
  gunzip a non-gzip file.

## Fast Log Debugging

See `packages/kctl-odoo/README.md` and CLAUDE.md for `kctl-odoo logs
tail`, which layers Odoo-aware filters (`--level`, `--module`,
`--request`, `--worker`, `--grep`) on top of `kctl-dokploy compose
service-logs -f`. Tracebacks are captured as whole blocks so
`--level ERROR` keeps the full `Traceback (most recent call last): ...`
body.
