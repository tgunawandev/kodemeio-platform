# kodemeio-accurate-sync — Operator Guide

**Audience:** Operators deploying, running, rotating secrets, and troubleshooting
the Accurate Online sync worker via `kodemeio-dokploy/deploys/`.

**Last reviewed:** 2026-04-16

**Related reading:**
- Design doc — `deploys/docs/2026-04-16-accurate-sync-integration.md`
- Service README — `kodemeio-accurate/packages/accurate-sync/README.md`
- Odoo-side counterpart — `kodemeio-odoo/src/private/integrations/accurate_integration/`

---

## 1. Overview

`kodemeio-accurate-sync` is a standalone Python CLI (packaged as a GHCR image)
that syncs Accurate Online → Odoo Postgres **directly**, bypassing Odoo's
`queue_job` / cron / worker stack. It fetches via the Accurate HTTP API, writes
straight into Odoo's tables via psycopg2 (with per-record savepoints and
`ir.model.data` ext-id dedup), then makes one JSON-RPC call to Odoo to post
the drafted `account.move` rows via the ORM (so tax lines and reconciliation
run correctly). Direct-to-PG avoids the per-record queue_job overhead that
makes in-Odoo bulk backfills unusably slow.

### Where it fits in the stack

```
  ┌────────────────────────┐
  │ Accurate Online API    │   iris.accurate.id — 8 req/sec limit
  └───────────┬────────────┘
              │ httpx (SDK)
              ▼
  ┌────────────────────────────────────────┐
  │ accurate-sync container                │   ghcr.io/tgunawandev/
  │   (Dokploy compose: IHh846Sm…)         │   kodemeio-accurate-sync:<tag>
  │   - Runs on tpp-prod-01                │   Colocated with Odoo Postgres,
  │   - Private PG connection to Odoo DB   │   which lives on tpp-prod-01.
  │   - JSON-RPC to Odoo web for post step │
  └───────┬──────────────────────────┬─────┘
          │ psycopg2 (direct)        │ JSON-RPC
          ▼                          ▼
  ┌───────────────────┐   ┌─────────────────────────┐
  │ Odoo Postgres     │   │ Odoo web (tpp-odoo-erp) │
  │ tpp_odoo_erp      │   │ action_post_draft_moves │
  └───────────────────┘   └─────────────────────────┘
```

The sync container does **not** host an HTTP service. It is an `exec`-driven
worker — the default `CMD` keeps the container alive (`watch` stub) and
operators trigger syncs via `docker exec`.

---

## 2. Environment variables (`.env.<tenant>-accurate-sync`)

The generator writes 13 keys (9 runtime inputs + 4 Docker / metadata). The
complete set:

| Key                  | Required | Example                            | Source                                           |
|----------------------|----------|------------------------------------|--------------------------------------------------|
| `PGHOST`             | yes      | `10.0.0.2`                         | Mirrored from `.env.<tenant>-odoo-<odoo_ref>`    |
| `PGPORT`             | yes      | `5432`                             | Default from base template                       |
| `PGUSER`             | yes      | `odoo`                             | Tenant manifest (hard-coded to `odoo` in gen)    |
| `PGPASSWORD`         | yes      | `<SECRET>`                         | Mirrored from `.env.<tenant>-odoo-<odoo_ref>`    |
| `PGDATABASE`         | yes      | `tpp_odoo_erp`                     | Derived from tenant.code + odoo_ref              |
| `ODOO_URL`           | yes      | `https://tpp-odoo-erp.idtpp.com`   | Derived from tenant.domain + dns_prefix          |
| `ODOO_DB_FILTER`     | yes      | `^tpp_odoo_erp$`                   | Derived (regex anchor around PGDATABASE)         |
| `ODOO_ADMIN_PASSWD`  | yes      | `<SECRET>`                         | Mirrored from `.env.<tenant>-odoo-<odoo_ref>`    |
| `ACCURATE_TENANTS`   | yes      | `tpp`                              | `accurate_sync.tenants` (defaults to tenant.code)|
| `COMPOSE_PROJECT_NAME` | yes    | `tpp-accurate-sync`                | Docker isolation tag                             |
| `TENANT`             | yes      | `tpp`                              | Informational (container labels, logs)           |
| `IMAGE_TAG`          | yes      | `latest`                           | `accurate_sync.image_tag` (defaults `latest`)    |
| `TZ`                 | yes      | `Asia/Jakarta`                     | Default from base template                       |

### The gitignore / secret contract

- `deploys/env/production/.env.*` is gitignored. The real file with real
  secret values **is never committed**.
- `deploys/env/production/.env.<tenant>-accurate-sync.example` **is committed**
  with `CHANGE_ME` placeholders. It serves as the reference for keys + layout
  and as a fallback when the generator can't be run (e.g. manual Dokploy-UI
  setup from a fresh clone).
- `generate.py` regenerates the real `.env.<tenant>-accurate-sync` on every
  invocation, pulling `PGHOST` / `PGPASSWORD` / `ODOO_ADMIN_PASSWD` from the
  sibling Odoo env file. **Unlike Odoo/React/Notify envs, accurate-sync is
  NOT treated as secret by `is_secret_env()`** — it is always rewritten. This
  is intentional: the sibling Odoo env file is the single source of truth,
  and regenerating keeps the two in lock-step.

### Example `.env.tpp-accurate-sync` (secrets redacted)

```
# =============================================================================
# Pakerti Accurate-Sync — Production Environment
# =============================================================================
# GENERATED from tenants/tpp.yaml (accurate_sync block).
# Secrets (PGPASSWORD, ODOO_ADMIN_PASSWD) are copied from the sibling
# .env.tpp-odoo-erp file at generate time. Re-run generate.py
# after rotating those secrets to keep this file in sync.
# =============================================================================

COMPOSE_PROJECT_NAME=tpp-accurate-sync
TENANT=tpp

# DATABASE — mirrors .env.tpp-odoo-erp
PGHOST=10.0.0.2
PGPORT=5432
PGUSER=odoo
PGPASSWORD=<REDACTED>
PGDATABASE=tpp_odoo_erp

# ODOO — URL of the sibling Odoo instance, admin password for RPC calls
ODOO_URL=https://tpp-odoo-erp.idtpp.com
ODOO_DB_FILTER=^tpp_odoo_erp$
ODOO_ADMIN_PASSWD=<REDACTED>

# TENANT LIST — comma-separated slugs from accurate_company table
ACCURATE_TENANTS=tpp

# IMAGE
IMAGE_TAG=latest
TZ=Asia/Jakarta
```

---

## 3. First-time deployment

### Prerequisites

- The tenant's Odoo ERP instance (`<tenant>-odoo-<ref>`) is deployed and
  `deploys/env/production/.env.<tenant>-odoo-<ref>` has populated `PGPASSWORD`
  and `ODOO_ADMIN_PASSWD`.
- The target Odoo database is reachable from the deploy host on the PG
  private IP (usually the same VPC or private LAN).
- The Accurate API token has been stored on the `accurate_company` row in
  Odoo (`slug` matches the intended `ACCURATE_TENANTS` value). Verify:
  ```sql
  SELECT slug, active, api_token IS NOT NULL AS has_token, last_sync_at
  FROM accurate_company;
  ```
- `ir_config_parameter['accurate.signature_secret']` exists (global secret
  for payload signing).

### Step-by-step

1. **Add the `accurate_sync:` block** to `deploys/tenants/<tenant>.yaml`:

   ```yaml
   accurate_sync:
     enabled: true
     odoo_ref: erp          # matches the short: key of the odoo[] entry
     tenants: [<tenant>]    # slugs for ACCURATE_TENANTS (defaults to [tenant.code])
     # server: tpp-prod-01  # optional — override deploy host
     # image_tag: latest    # optional — pin a specific GHCR tag
   ```

2. **Regenerate**:
   ```bash
   cd kodemeio-dokploy
   python deploys/generate.py --tenant <tenant>
   ```
   Expected output includes:
   ```
   Processing tenant: <tenant>
   ...
   Done. Wrote: N, Skipped (secrets): ..., Unchanged: ...
   ```
   (No "SKIP (secrets): .env.<tenant>-accurate-sync" line — accurate-sync
   is always rewritten.)

3. **Verify the env file has all 13 keys**:
   ```bash
   grep -cE '^(PGHOST|PGPORT|PGUSER|PGPASSWORD|PGDATABASE|ODOO_URL|ODOO_DB_FILTER|ODOO_ADMIN_PASSWD|ACCURATE_TENANTS|COMPOSE_PROJECT_NAME|TENANT|IMAGE_TAG|TZ)=' \
       deploys/env/production/.env.<tenant>-accurate-sync
   # Expected: 13
   ```

4. **Commit + push the generated instance YAML + example env** (the real
   env file stays local via `.gitignore`):
   ```bash
   git add deploys/tenants/<tenant>.yaml \
           deploys/instances/production/<tenant>-accurate-sync.yaml \
           deploys/env/production/.env.<tenant>-accurate-sync.example
   git commit -m "feat(deploys): add accurate-sync for <tenant>"
   git push origin 18.0   # or main, per repo convention
   ```

5. **Register the compose in Dokploy** (one-time per tenant):
   ```bash
   kctl-dokploy compose create \
     --name <tenant>-accurate-sync \
     --project <tenant> \
     --source-provider github \
     --source-repo tgunawandev/kodemeio-accurate \
     --source-branch main \
     --compose-path compose/accurate-sync.yml
   # Note the returned compose_id — record it alongside IHh846Sm… for tpp.
   ```

6. **Upload the env file to Dokploy** (so the compose container receives it):
   ```bash
   kctl-dokploy compose sync-env <compose_id> \
       --from deploys/env/production/.env.<tenant>-accurate-sync
   ```

7. **Deploy**:
   ```bash
   kctl-dokploy compose start <compose_id>
   ```

8. **Smoke-test**:
   ```bash
   docker exec <tenant>-accurate-sync accurate-sync tenants
   # Expected: lists rows from accurate_company including your slug.
   ```

---

## 4. Running a sync

The CLI entry point is `accurate-sync` (installed in the container at
`/usr/local/bin/accurate-sync`). Always invoke via `docker exec`:

```bash
docker exec tpp-accurate-sync accurate-sync run --tenant tpp              # delta
docker exec tpp-accurate-sync accurate-sync run --tenant tpp --full       # snapshot
docker exec tpp-accurate-sync accurate-sync run --tenant tpp --foundation # + master data
```

### What happens during `run`

1. **Fetch** — `accurate_sdk.client` paginates `list.do` against Accurate API
   (respecting the 8 req/sec ceiling).
2. **Map** — `accurate_sdk.odoo_mapper.MAPPERS` transforms each record into
   `(model_name, vals)` tuples.
3. **Resolve FKs** — `PgFKResolver` looks up referenced partners / accounts /
   taxes by their `ir.model.data` ext_ids.
4. **Write** — `PgWriter` INSERTs or UPDATEs into Odoo tables. Each record
   runs inside `SAVEPOINT rec_<module>_<id>`; failures roll back just that
   one record and continue. One `COMMIT` per module.
5. **Finalize** — a single JSON-RPC call to
   `accurate.company.action_post_draft_moves` transitions draft moves →
   `posted` (tax lines + reconciliation run Odoo-side).

### Typical duration

| Scope                         | Duration     |
|-------------------------------|--------------|
| Foundation only (`--foundation` alone) | ~5 min  |
| Transactions delta (no flags)          | ~10–15 min |
| `--full` initial backfill              | 45–120 min (depends on record count) |

### Exit codes

| Code | Meaning |
|------|---------|
| `0`  | Full success — all records written, all drafts posted |
| `1`  | Record-level failures — partial writes committed, errors in `accurate_sync_log.error_log` |
| `2`  | Tenant not found — bad `--tenant` slug or `accurate_company.active=FALSE` |
| `4`  | Sync OK but `action_post_draft_moves` failed — drafts remain. Recover with `accurate-sync finalize --tenant <slug>` |

### Where to find results

- **Audit table**: `accurate_sync_log` (per-module run records with counts +
  `error_log` JSON).
- **CLI status**: `accurate-sync status` (last 20 log rows across tenants).
- **Last successful delta cursor**: `accurate_company.last_sync_at`.

---

## 5. Troubleshooting

### Container in `error` / `restarting` state

- Likely: image pull failure. Check GHCR visibility —
  `ghcr.io/tgunawandev/kodemeio-accurate-sync:<tag>` must be **public** or
  the deploy host must have a GHCR pull secret.
- Likely: `Config error: Missing required env var: X` — check that the
  Dokploy compose has the env file attached. Run
  `kctl-dokploy compose sync-env <id>` to re-upload.
- Inspect logs:
  ```bash
  kctl-dokploy compose logs <compose_id> --tail 200
  ```

### `TenantNotFound: No accurate_company with slug='X'` (exit 2)

- Row missing. Open Odoo → Accurate → Companies → create / reactivate the
  tenant (`slug` must equal `--tenant` argument and be in `ACCURATE_TENANTS`).
- Row present but `active=FALSE` — flip `active=TRUE`.

### Sync OK but drafts not posted (exit 4)

The rows landed in Postgres but Odoo couldn't post them. Recover:

```bash
docker exec tpp-accurate-sync accurate-sync finalize --tenant tpp
```

If `finalize` also fails:
- Check `ODOO_URL` is reachable from the container:
  `docker exec tpp-accurate-sync curl -sI ${ODOO_URL}`
- Check `ODOO_ADMIN_PASSWD` matches the current admin password on the
  `tpp-odoo-erp` instance. If rotated, re-run the generator (see §7).

### Missing records / unexpected counts

Inspect the last module run:

```sql
SELECT module, records_created, records_updated, records_failed, error_log
FROM accurate_sync_log
WHERE company_id = (SELECT id FROM accurate_company WHERE slug = 'tpp')
ORDER BY id DESC LIMIT 5;
```

`error_log` is a JSON array of `{module, record_id, error, traceback}`. Common
causes:

- **FK resolution miss** — a referenced partner / account / tax hasn't been
  synced. Re-run with `--foundation`:
  ```bash
  docker exec tpp-accurate-sync accurate-sync run --tenant tpp --foundation
  ```
- **Unique constraint** — e.g. duplicate VAT on `res.partner`. Clean up the
  Accurate source row, then rerun.
- **Schema drift** — a mapper emitted a column the Odoo schema no longer
  has. Check `accurate_sdk.odoo_mapper.MAPPERS` vs `TableSchema.columns`.

### Permission errors on INSERT/UPDATE

Unlikely with the default `PGUSER=odoo` — Odoo owns its own tables. If it
happens, check that nobody rotated the role:
```sql
SELECT relname, relowner::regrole FROM pg_class
WHERE relname IN ('res_partner', 'account_move') LIMIT 5;
-- Expected: owner 'odoo'.
```

### Concurrent runs corrupted state

**Never** run two `accurate-sync run` invocations against the same tenant
in parallel — there is no `pg_advisory_lock` per tenant. If you suspect a
clash:
1. Stop all active syncs (`docker exec … kill`).
2. Re-run `--full` to bring Odoo back to a known good state (idempotent via
   `ir.model.data` dedup).

---

## 6. Validating P&L parity

After a successful full sync, confirm the books agree:

1. **Snapshot `last_sync_at`**:
   ```sql
   SELECT slug, last_sync_at FROM accurate_company WHERE slug = 'tpp';
   ```
2. **Generate Odoo P&L** — Accounting → Reporting → Profit and Loss. Filter
   to the same period covered by the sync. Export to Excel.
3. **Generate Accurate P&L** — log into iris.accurate.id → Reports → Profit
   and Loss for the same period.
4. **Compare line-for-line**:
   - Match ±1% on each GL account line is expected (rounding during the
     per-record IDR → IDR pass-through, and timing differences at period
     cutoff).
   - Off by more than 1% on any single account → inspect
     `accurate_sync_log.records_failed` for that module.
5. **If mismatch**:
   ```bash
   docker exec tpp-accurate-sync accurate-sync run --tenant tpp --full
   ```
   Idempotent via `ir_model_data` dedup — safe to re-run. After completion,
   regenerate the Odoo P&L and re-compare.

> **Note:** `account.move` line updates are skipped by `PgWriter._update`
> on delta runs (by design — touching posted invoice lines is a correctness
> hazard). If a line was edited in Accurate after the initial sync, only
> `--full` will re-import it.

---

## 7. Rotating secrets

When `PGPASSWORD` or `ODOO_ADMIN_PASSWD` changes on the Odoo instance
(rotation, compromise, migration), the canonical source of truth is
`deploys/env/production/.env.<tenant>-odoo-<ref>`. Update there, then
propagate:

```bash
# 1. Update the sibling Odoo env file (e.g. via Dokploy UI or direct edit
#    on the deploy host). The new value is now in .env.tpp-odoo-erp.

# 2. Regenerate the accurate-sync env — pulls the new secrets automatically.
cd kodemeio-dokploy
python deploys/generate.py --tenant tpp

# 3. Upload the refreshed env to Dokploy.
kctl-dokploy compose sync-env IHh846SmVHrBMdgFTpMGF \
    --from deploys/env/production/.env.tpp-accurate-sync

# 4. Redeploy so the container picks up the new env.
kctl-dokploy compose redeploy IHh846SmVHrBMdgFTpMGF

# 5. Confirm.
docker exec tpp-accurate-sync accurate-sync tenants
```

### Why the generator pulls from the sibling file

- **No duplication.** The secret lives in exactly one place
  (`.env.<tenant>-odoo-<ref>`). Engineers never copy-paste a password.
- **Atomic rotation.** One rotation → one edit → `generate.py` → redeploy.
  Both the Odoo instance and the accurate-sync container end up on the new
  secret in a single pass.
- **Drift impossible.** The sync container cannot run with a password
  different from the one Odoo is using, as long as the generator has been
  run after rotation.

---

## 8. Adding another tenant

Example: onboarding `mac` (Makassar) once the Accurate row exists.

1. **Edit** `deploys/tenants/mac.yaml`, append:
   ```yaml
   accurate_sync:
     enabled: true
     odoo_ref: erp          # mac has short: erp for its ERP Odoo
     tenants: [mac]
   ```

2. **Regenerate**:
   ```bash
   python deploys/generate.py --tenant mac
   ```
   Produces:
   - `deploys/instances/production/mac-accurate-sync.yaml`
   - `deploys/env/production/.env.mac-accurate-sync` (gitignored)
   - `deploys/env/production/.env.mac-accurate-sync.example` (committed if manually copied from tpp — optional)

3. **Follow §3 steps 4–8** (commit, Dokploy compose create, env upload,
   start, smoke-test) substituting `mac` for `tpp`.

4. **Verify** `accurate_company` has a `mac` row with a valid `api_token`.

### Multi-tenant in a single container

If two Accurate source companies should share one Odoo DB (e.g. group
consolidation), set:

```yaml
accurate_sync:
  enabled: true
  odoo_ref: erp
  tenants: [tpp, tpp_finance, tpp_trading]   # ACCURATE_TENANTS=tpp,tpp_finance,tpp_trading
```

The CLI iterates tenant-by-tenant. Foundation records from a tenant with
`accurate_company.is_foundation_source=TRUE` get a shared ext_id prefix
(`accurate.shared.<module>.<key>`) instead of per-tenant, so two source
companies contributing the same vendor collapse to one Odoo row.

---

## Appendix A — Live TPP deployment reference

| Field             | Value                                 |
|-------------------|---------------------------------------|
| Dokploy compose   | `IHh846SmVHrBMdgFTpMGF`               |
| Deploy host       | `tpp-prod-01`                         |
| Container name    | `tpp-accurate-sync`                   |
| Image             | `ghcr.io/tgunawandev/kodemeio-accurate-sync:latest` |
| Target Odoo DB    | `tpp_odoo_erp` on `tpp-odoo-erp.idtpp.com` |
| Sibling env       | `.env.tpp-odoo-erp`                   |

## Appendix B — File map (deploys/)

```
deploys/
├── bases/
│   └── accurate-sync.yaml                      base template (documented)
├── tenants/
│   └── tpp.yaml                                has accurate_sync: block
├── generate.py                                 gen_accurate_sync() reads sibling env
├── instances/production/
│   └── tpp-accurate-sync.yaml                  rendered Dokploy binding (committed)
├── env/production/
│   ├── .env.tpp-accurate-sync                  rendered secrets (gitignored)
│   └── .env.tpp-accurate-sync.example          committed reference (CHANGE_ME)
└── docs/
    ├── 2026-04-16-accurate-sync-integration.md design doc
    └── accurate-sync-operator-guide.md         this file
```
