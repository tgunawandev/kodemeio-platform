# Runbook — Dokploy postgres backups (compose-embedded postgres)

**Date:** 2026-04-19
**Scope:** All compose-embedded postgres instances on any `idtpp` / `kodemeio` / `abcfood` Dokploy.

---

## Problem (observed 2026-04-19)

Dokploy's UI-driven compose backup for `tpp-infra-postgres` has been failing every night:

```
info     Initializing backup
info     [... UTC] Executing backup command...
info     [... UTC] Container Up: c9fbd5da400e
error    [... UTC] ❌ Error: Backup failed
error    Error: bash: line 15: null: command not found
```

6 consecutive failures in 24 hours.

## Root cause (REVISED 2026-04-19)

Deeper investigation showed the `Database: pos` typo was a symptom, not the root cause. The actual bug is that Dokploy's compose-backup template depends on `backup.metadata.<db_type>.databaseUser` being set — and our `kctl-dokploy backups create` was not sending it. Dokploy's server source at `utils/backups/utils.js`:

```javascript
if (backupType === "compose" && backup.metadata?.postgres) {
    return getPostgresBackupCommand(backup.database, backup.metadata.postgres.databaseUser);
}
// ... falls through to: return null;
```

When `metadata.postgres` is missing, `generateBackupCommand()` returns `null`. Dokploy then bakes `null` into the shell template:
```bash
BACKUP_OUTPUT=$(null 2>&1 >/dev/null) || { echo "Backup failed"; exit 1; }
```
→ `bash: line 15: null: command not found`.

Fix requires BOTH: (a) a valid database name in the compose's postgres, and (b) `metadata.postgres.databaseUser` set to a role with `--no-password` trust auth inside the container — use `postgres` (superuser) unless you have a specific reason not to.

`kctl-dokploy backups create --database-user postgres` now populates this automatically (added 2026-04-19).

### Why did it end up as `pos`?

Looks like someone started typing `postgres` in the Dokploy UI and saved early. This is a Dokploy UX footgun: the field accepts any string, no validation against actual DBs.

## Actual databases in `tpp-infra-postgres`

Verified live 2026-04-19:

| Database | Owner | Purpose |
|---|---|---|
| `authentik` | authentik | SSO identity provider |
| `glitchtip` | glitchtip | Error tracking |
| `hmdm` | hmdm | Headwind MDM |
| `outline` | outline | Wiki |
| `zulip` | zulip | Team chat |
| `mac_odoo_erp` | odoo | MAC production ERP |
| `mac_odoo_hrms` | odoo | MAC production HRMS |
| `stg_mac_odoo_erp` | odoo | MAC staging ERP |
| `stg_mac_odoo_hrms` | odoo | MAC staging HRMS |
| `tpp_odoo_erp` | odoo | TPP production ERP |
| `tpp_odoo_hrms` | odoo | TPP production HRMS |
| `stg_tpp_odoo_erp` | odoo | TPP staging ERP |
| `stg_tpp_odoo_hrms` | odoo | TPP staging HRMS |
| `postgres` | postgres | system DB (do not back up) |

**13 user DBs** need backup configs. The `postgres` system DB is excluded.

> ⚠️ Note: `mac_odoo_erp` and `mac_odoo_hrms` also exist on `mac-infra-postgres` (tpp-prod-02, 10.0.0.3). The shared postgres copies may be stale from before the MAC migration. Audit before relying on either as canonical.

## Fix — one backup config per database

Dokploy's compose-backup requires **one DB per config** (this is a Dokploy limitation — you can't wildcard all DBs). We delete the broken `pos` backup and create 13 new ones, each with its own S3 prefix and a staggered schedule to spread load.

### Step 1 — Delete the broken backup

```bash
uv run kctl-dokploy -p idtpp backups remove C82NKt1WHggpibGkxH1oe --force
```

### Step 2 — Create 13 per-DB backup configs

All use:
- **Destination ID:** `KiWBiVzZb2EoyUDURKDQO` (the already-configured `hz-tpp-postgres` S3 bucket)
- **Compose ID:** `2iEl8DzSWOMFOClweOhiZ` (tpp-infra-postgres)
- **Service name in compose:** `postgres` (from the live `docker ps` inspection)

Schedules staggered by 5 minutes starting 02:00 UTC so they don't contend for disk/CPU.

```bash
COMPOSE=2iEl8DzSWOMFOClweOhiZ
DEST=KiWBiVzZb2EoyUDURKDQO

declare -a entries=(
    # db:cron
    "authentik:0 2 * * *"
    "glitchtip:5 2 * * *"
    "hmdm:10 2 * * *"
    "outline:15 2 * * *"
    "zulip:20 2 * * *"
    "mac_odoo_erp:25 2 * * *"
    "mac_odoo_hrms:30 2 * * *"
    "tpp_odoo_erp:35 2 * * *"
    "tpp_odoo_hrms:40 2 * * *"
    "stg_mac_odoo_erp:45 2 * * *"
    "stg_mac_odoo_hrms:50 2 * * *"
    "stg_tpp_odoo_erp:55 2 * * *"
    "stg_tpp_odoo_hrms:0 3 * * *"
)

for entry in "${entries[@]}"; do
    db="${entry%%:*}"
    schedule="${entry#*:}"
    uv run kctl-dokploy -p idtpp backups create \
        --destination $DEST \
        --compose $COMPOSE \
        --service postgres \
        --database "$db" \
        --type postgres \
        --database-user postgres \
        --prefix "tpp-infra-postgres/$db" \
        --schedule "$schedule" \
        --enabled
done
```

> `--database-user postgres` is **required** for compose-type postgres backups. Omitting it produces the `null: command not found` failure at runtime (see Root cause above).

### Step 3 — Verify each was created

```bash
uv run kctl-dokploy -p idtpp backups list --compose 2iEl8DzSWOMFOClweOhiZ
# Expect 13 entries (not the old `pos` one)
```

### Step 4 — Trigger one manual run to confirm the command works

Pick a small DB to test end-to-end (e.g. `authentik`):

```bash
# Get the ID of the authentik backup config from step 3 output
BACKUP_ID=<paste-id>
uv run kctl-dokploy -p idtpp backups run $BACKUP_ID
# Watch the deployment log in Dokploy UI or via:
uv run kctl-dokploy -p idtpp backups get $BACKUP_ID
```

If it succeeds, the template is correct and all 13 will work on schedule.

### Step 5 — Verify S3 received the file

```bash
uv run kctl-dokploy -p idtpp backups list-files $DEST --prefix tpp-infra-postgres/authentik/
# Should show a *.sql (or *.tar.gz) file from today
```

## Rollback

If the new configs also fail, delete them all:

```bash
# Get IDs
uv run kctl-dokploy -p idtpp backups list --compose 2iEl8DzSWOMFOClweOhiZ --format json \
    | jq -r '.[].id' \
    | while read id; do
        uv run kctl-dokploy -p idtpp backups remove "$id" --force
    done
```

Then fall back to the **standalone `kctl-dokploy backups dump-compose`** approach — run it from a local cron or CI job, bypassing Dokploy's scheduler entirely. See the "Fallback" section below.

## Fallback — bypass Dokploy scheduler entirely

If Dokploy's built-in backup keeps being flaky (has been in past; see `kodemeio-dokploy/CLAUDE.md` note about `/backup.manualBackupCompose` being unreliable), run `kctl-dokploy backups dump-compose` from a local cron or CI:

```bash
# One DB dump → S3, no Dokploy scheduler involved
uv run kctl-dokploy -p idtpp backups dump-compose \
    --compose 2iEl8DzSWOMFOClweOhiZ \
    --destination KiWBiVzZb2EoyUDURKDQO \
    --service postgres \
    --database tpp_odoo_erp \
    --prefix tpp-infra-postgres/tpp_odoo_erp
```

Wrap in a shell script that iterates the 13 DBs, run from `cron` on a trusted box. Benefit: you control error handling, retries, notifications.

## Also apply to other postgres composes on the platform

Other compose-embedded postgres that need similar care:

| Compose | Compose ID | Databases to back up |
|---|---|---|
| `mac-infra-postgres` (tpp-prod-02) | `UL9UNK_WvbjNKR-KB6aCr` | `mac_odoo_erp`, `mac_odoo_hrms`, `stg_mac_odoo_erp`, `stg_mac_odoo_hrms` |
| `tpp-odoo-erp`, `tpp-odoo-hrms` | per compose | *(only if they have embedded postgres; current setup uses external)* |
| `mac-odoo-erp`, `mac-odoo-hrms` | per compose | *(uses mac-infra-postgres now)* |

Run the same steps for each: delete any existing broken backup config, create per-DB configs, verify.

## Monitoring

Set up Gatus (or other uptime check) to alert if:
- A backup config hasn't produced a new S3 file in the last 26 hours
- `kctl-dokploy backups get <id>` returns status = `error`

One script per environment can iterate configs and push to Gatus' HTTP push endpoint. Out of scope for this runbook.

## Post-fix checklist

- [ ] Broken `pos` backup deleted
- [ ] 13 new backup configs created for tpp-infra-postgres
- [ ] At least 1 manual run succeeded, S3 file verified
- [ ] Same fix applied to `mac-infra-postgres` (4 DBs)
- [ ] First night's scheduled run (02:00 UTC tomorrow) verified green in UI
- [ ] Confirm old broken backups are not still showing "error" in the deployments list
