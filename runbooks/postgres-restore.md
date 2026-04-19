# Runbook — PostgreSQL restore (Dokploy native)

**Scope:** restore any compose-embedded postgres DB using only `kctl-dokploy backups restore`. Dokploy's server does the actual work; this doc is the invocation reference.

**Prereq:**
- `kctl-dokploy` ≥ 0.4.0
- A valid profile for the target Dokploy in `~/.config/kodemeio/config.yaml`
- The target compose's env has `SERVICE_DATABASES` set so target DBs are pre-created with the right owner/locale at container start (see "§3 Target compose prereq")

## §1 One-shot restore (latest S3 key)

```bash
kctl-dokploy -p <target-profile> backups restore \
    --compose <target-compose-id> \
    --destination <target-destination-id> \
    --database-name <db-name> \
    --service-name postgres \
    --database-user <db-owner> \
    --latest <db-name>
```

Picks the newest S3 object whose key contains `<db-name>`, invokes Dokploy's native restore, streams log lines prefixed `[Dokploy]` to your terminal. Exit 0 on success, 1 on error, 2 on transport failure.

> **Note on `--service-name` + `--database-user`** — Dokploy's native compose restore requires `serviceName` (to build `docker ps --filter label=com.docker.compose.service=<serviceName>`) and `databaseUser` (for `pg_restore -U <user>`). These flags pass through to `metadata.serviceName` and `metadata.postgres.databaseUser` in the tRPC payload. Without them the server executes `docker exec -i sh` (no such container) and `pg_restore -U ''` (empty user). The CLI fails fast if either is omitted for compose/postgres restores.

**Example: restore latest prod `mac_odoo_erp` to local:**
```bash
kctl-dokploy -p local backups restore \
    --compose BAP6JmrmLJYnSIJ3YZOb_ \
    --destination v6gJBPvatXxuArLtEqR09 \
    --database-name mac_odoo_erp \
    --service-name postgres \
    --database-user odoo \
    --latest mac_odoo_erp
```

## §2 Specific historical backup

List candidates first (direct to S3 via rclone — Dokploy's `listBackupFiles` endpoint is buggy and bypassed by kctl-dokploy's own boto3 listing):

```bash
docker run --rm rclone/rclone \
    --s3-provider=Other \
    --s3-access-key-id=<KEY> --s3-secret-access-key=<SECRET> \
    --s3-region=<REGION> --s3-endpoint=<ENDPOINT> \
    --s3-no-check-bucket --s3-force-path-style \
    lsl ':s3:<BUCKET>/' | grep <db-name>
```

> Note: `--s3-provider=Other` (not `s3`) for Hetzner Object Storage — rclone rejects `"s3"` as a provider value. The Dokploy destination record's `provider` field must also be `"Other"`, not `"s3"`.

Then restore a specific key:

```bash
kctl-dokploy -p <target-profile> backups restore \
    --compose <target-compose-id> \
    --destination <target-destination-id> \
    --database-name <db-name> \
    --service-name postgres \
    --database-user <db-owner> \
    --file <s3-key>
```

### Metadata flags per database type

| `--db-type` | Required metadata flags |
|---|---|
| `postgres` (default) | `--service-name`, `--database-user` |
| `mariadb` | `--service-name`, `--database-user`, `--database-password` |
| `mongo` | `--service-name`, `--database-user`, `--database-password` |
| `mysql` | `--service-name`, `--database-password` (used as the MySQL root password) |

## §3 Target compose prereq — SERVICE_DATABASES

Dokploy's native restore does NOT create the target DB if it doesn't exist, and does NOT set its owner or collation. For Odoo databases where `owner=odoo` and `LC_COLLATE=en_US.utf8` matter, pre-create them at the compose layer using `kodemeio-postgres`'s `SERVICE_DATABASES` env var:

```
SERVICE_DATABASES=mac_odoo_erp:odoo:<pw>,mac_odoo_hrms:odoo:<pw>,tpp_odoo_erp:odoo:<pw>
```

On container start, `/scripts/provision.sh` inside the `kodemeio-postgres` image creates each DB with `OWNER=<user>` and the compose-default locale (en_US.utf8 on kodemeio-postgres). Restore then loads data into the pre-prepared DB — no post-restore ALTER OWNER needed from the CLI side.

## §4 Common compose IDs (idtpp)

```
tpp-infra-postgres    2iEl8DzSWOMFOClweOhiZ    (shared on tpp-prod-01)
mac-infra-postgres    UL9UNK_WvbjNKR-KB6aCr    (MAC dedicated on tpp-prod-02)
S3 destination        KiWBiVzZb2EoyUDURKDQO    (bucket: hz-tpp-postgres-backup)
```

## §5 Common compose IDs (local)

```
tpp-infra-postgres    BAP6JmrmLJYnSIJ3YZOb_
S3 destination        v6gJBPvatXxuArLtEqR09    (same bucket as idtpp, local Dokploy record)
```

## §6 Exit codes

| Code | Meaning |
|---|---|
| 0 | Dokploy emitted a success marker; stream closed cleanly. |
| 1 | Dokploy emitted `Error:` / `❌`, or stream closed without a success marker. |
| 2 | Transport / auth failure — never reached Dokploy's log stream (4xx/5xx). |

## §7 What this runbook replaces

The previous version described a multi-step SSH + docker-exec + rclone workflow using commands that no longer exist:
- `backups dump-compose` — deleted (Dokploy's server does pg_dump)
- `backups download` — deleted (restore streams from S3 inside Dokploy's server)
- `backups restore-local` — deleted (Dokploy's server does pg_restore)
- `backups refresh` — deleted (one command `backups restore` replaces the whole flow)
- `backups run-wait` — deleted (the SSE stream is the wait)

Alpine collation workarounds, per-object ALTER OWNER loops, datcollversion clears — all gone. Dokploy's server handles them natively inside the target compose's postgres container.
