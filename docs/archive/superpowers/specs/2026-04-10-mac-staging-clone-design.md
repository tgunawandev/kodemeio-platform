# MAC Staging Clone — Design Spec

**Date:** 2026-04-10
**Goal:** Deploy staging instances of `mac-odoo-erp` and `mac-odoo-hrms` at `stg-mac-odoo-erp.idtpp.com` and `stg-mac-odoo-hrms.idtpp.com`, cloned from production databases.

**Problem:** MAC users need a staging environment to test new modules, data changes, training exercises, and integrations without risking the production database. The staging instance files already exist in `deploys/instances/staging/` but have never been deployed. Training materials have been written against production — users should not learn against a live system.

---

## 1. Scope

**In scope:**
- Deploy `stg-mac-odoo-erp.idtpp.com` and `stg-mac-odoo-hrms.idtpp.com`
- Clone databases from production (`mac_odoo_erp` → `stg_mac_odoo_erp`, `mac_odoo_hrms` → `stg_mac_odoo_hrms`)
- Neutralize staging so it can't send real email, charge cards, or hit production integrations
- Update `web.base.url` system parameter so Odoo generates correct links
- Document the refresh procedure so staging can be re-cloned from prod on demand

**Out of scope:**
- Creating a dedicated `tpp-stg-01` Hetzner server (see Decision 1)
- Staging for React frontends (`mac-react-erp`, `mac-react-hrm`) — add later in a follow-up
- Nextjs careers staging — not needed for training
- Automated nightly refresh from prod — manual trigger only for v1

---

## 2. Key Decisions

### Decision 1: Server Placement — Reuse `tpp-prod-02`, not provision `tpp-stg-01`

**Options considered:**

| Option | Cost | Pros | Cons |
|---|---|---|---|
| A. Reuse `tpp-prod-02` | €0 | Zero new infra, matches current `tenants/mac.yaml`, databases are tiny (~7MB each) | Staging shares resources with prod |
| B. Provision `tpp-stg-01` (cpx32) | ~€15/mo | Fully isolated, dedicated for staging | Cost, provisioning time, additional node to maintain |
| C. Reuse `tpp-dev-01` (cx33) | €0 | Isolated from prod, already running | Shared with developer workloads |

**Decision:** Option A — reuse `tpp-prod-02`.

**Rationale:**
- MAC databases are 7MB each. CPU and memory impact on `tpp-prod-02` is negligible.
- `tpp-prod-02` is already listed as the staging server in `deploys/tenants/mac.yaml`, so this is the path of least resistance.
- If staging workload grows enough to cause contention, we can migrate to `tpp-stg-01` by changing the `server:` field and redeploying. The decision is reversible with minimal effort.
- We save €180/year until there's evidence we need isolation.

### Decision 2: Refresh Strategy — Manual on demand

**Options considered:**

| Option | Pros | Cons |
|---|---|---|
| A. Manual refresh (`./refresh-mac-staging.sh`) | Simple, predictable | Someone has to remember to run it |
| B. Nightly cron refresh | Always fresh | Complex, requires careful timing to avoid clobbering in-progress test work |
| C. On-demand via kctl-odoo command | CLI-native | Requires CLI enhancement |

**Decision:** Option A — manual shell script for v1, upgrade to kctl-odoo command in v2.

### Decision 3: Production Safety — Neutralize staging post-clone

When staging is cloned from prod, it inherits all production settings. Without intervention, the cloned instance would:
- Send emails via real SMTP (mailcow)
- Hit production payment gateways (Midtrans/Xendit)
- Talk to production webhooks
- Allow OAuth via the same Authentik clients

**Decision:** Run a **post-clone neutralization** step that:
1. Updates `web.base.url` system parameter to `stg-mac-odoo-*.idtpp.com`
2. Deactivates outgoing `ir.mail_server` records (prevents accidental customer emails)
3. Disables all `payment.provider` records (no real charges)
4. Disables webhook endpoints (`base_webhook` records)
5. Prepends `[STG]` to company name for visual warning
6. Resets admin password to a known staging password (so anyone on the team can log in)
7. Clears session cookies (forces re-login)

These steps run via a kctl-odoo command: `kctl-odoo neutralize-staging` (new command).

---

## 3. Architecture

### Infrastructure Layout

```
tpp-prod-02 (46.224.93.123, cpx32)
├── mac-odoo-erp         (existing prod)     → mac-odoo-erp.idtpp.com       → db: mac_odoo_erp
├── mac-odoo-hrms        (existing prod)     → mac-odoo-hrms.idtpp.com      → db: mac_odoo_hrms
├── mac-odoo-erp-stg     (NEW)               → stg-mac-odoo-erp.idtpp.com   → db: stg_mac_odoo_erp
└── mac-odoo-hrms-stg    (NEW)               → stg-mac-odoo-hrms.idtpp.com  → db: stg_mac_odoo_hrms
```

Database server is shared (`tpp-prod-01` PostgreSQL). The staging databases live alongside prod databases in the same PG cluster. They're isolated by `PGDATABASE` and `ODOO_DB_FILTER`.

### Compose Service Naming

Dokploy compose services use the `-stg` suffix to distinguish from prod:

| Prod | Staging |
|---|---|
| `mac-odoo-erp` | `mac-odoo-erp-stg` |
| `mac-odoo-hrms` | `mac-odoo-hrms-stg` |

### DNS

| Subdomain | Target | Zone |
|---|---|---|
| `stg-mac-odoo-erp.idtpp.com` | `tpp-prod-02` IP (46.224.93.123) | idtpp.com (Cloudflare) |
| `stg-mac-odoo-hrms.idtpp.com` | `tpp-prod-02` IP | idtpp.com (Cloudflare) |

DNS is created via Dokploy's built-in Let's Encrypt + Traefik setup when the compose service starts with the domain configured.

---

## 4. Deployment Procedure

### Prerequisites

- SSH key for `tpp-prod-01` (PostgreSQL host) and `tpp-prod-02` (compose host) available at `~/.ssh/id_ed25519`
- Cloudflare API access via `kctl-cf`
- Dokploy admin access via `kctl-dokploy`
- MAC admin password for post-clone neutralization

### Phase 1: Database Clone

Execute from any machine with `kctl-pg` configured.

```bash
# 1. Dump production databases
mkdir -p ~/backups/mac-stg-clone
cd ~/backups/mac-stg-clone

kctl-pg backup dump mac_odoo_erp \
  --output mac_odoo_erp_$(date +%Y%m%d_%H%M%S).sql.gz

kctl-pg backup dump mac_odoo_hrms \
  --output mac_odoo_hrms_$(date +%Y%m%d_%H%M%S).sql.gz

# 2. Drop existing staging databases (if any)
kctl-pg db drop stg_mac_odoo_erp --force
kctl-pg db drop stg_mac_odoo_hrms --force

# 3. Create staging databases
kctl-pg db create stg_mac_odoo_erp --owner odoo
kctl-pg db create stg_mac_odoo_hrms --owner odoo

# 4. Restore from prod dumps
kctl-pg backup restore stg_mac_odoo_erp mac_odoo_erp_*.sql.gz
kctl-pg backup restore stg_mac_odoo_hrms mac_odoo_hrms_*.sql.gz
```

**Verification:** `kctl-pg db list` shows both `stg_*` databases with non-zero size.

### Phase 2: Env Files

Copy production env files to staging env files, then override critical values.

```bash
cd ~/code/kodemeio-platform/deploys/env/staging

# Start from example (already in repo)
cp .env.mac-odoo-erp.example .env.mac-odoo-erp
cp .env.mac-odoo-hrms.example .env.mac-odoo-hrms
```

Edit each file to set:
- `PGPASSWORD` — from 1Password (same as prod)
- `ODOO_ADMIN_PASSWD` — **different from prod** (staging admin password)
- `SENTRY_DSN` — empty (don't send staging errors to GlitchTip)
- Any third-party API keys — set to sandbox/empty

### Phase 3: DNS

```bash
# Create DNS A records pointing to tpp-prod-02
kctl-cf dns create --zone idtpp.com --name stg-mac-odoo-erp --type A --content 46.224.93.123 --proxied
kctl-cf dns create --zone idtpp.com --name stg-mac-odoo-hrms --type A --content 46.224.93.123 --proxied
```

### Phase 4: Dokploy Compose Services

```bash
cd ~/code/kodemeio-platform

# Regenerate staging instance YAMLs from tenants/mac.yaml
uv run deploys/generate.py --tenant mac --env staging

# Deploy staging compose services via kctl-dokploy
kctl-dokploy compose create \
  --project mac \
  --environment staging \
  --name mac-odoo-erp-stg \
  --source-type github \
  --compose-path compose/odoo.prod.yml \
  --env-file ~/code/kodemeio-platform/deploys/env/staging/.env.mac-odoo-erp \
  --domain stg-mac-odoo-erp.idtpp.com:8069

kctl-dokploy compose create \
  --project mac \
  --environment staging \
  --name mac-odoo-hrms-stg \
  --source-type github \
  --compose-path compose/odoo.prod.yml \
  --env-file ~/code/kodemeio-platform/deploys/env/staging/.env.mac-odoo-hrms \
  --domain stg-mac-odoo-hrms.idtpp.com:8069

# Start both
kctl-dokploy compose start mac-odoo-erp-stg
kctl-dokploy compose start mac-odoo-hrms-stg
```

### Phase 5: Post-Clone Neutralization

Run the neutralize command against each staging instance:

```bash
# Configure kctl-odoo staging profile (one-time)
kctl-odoo config quick mac-erp-stg https://stg-mac-odoo-erp.idtpp.com stg_mac_odoo_erp admin
kctl-odoo config quick mac-hrms-stg https://stg-mac-odoo-hrms.idtpp.com stg_mac_odoo_hrms admin

# Neutralize (this is a new kctl-odoo command — see Phase 6)
kctl-odoo -p mac-erp-stg neutralize-staging
kctl-odoo -p mac-hrms-stg neutralize-staging
```

### Phase 6: New kctl-odoo Command — `neutralize-staging`

Add to `cli-odoo/commands/staging.py`:

```python
@app.command("neutralize-staging")
def neutralize_staging(
    admin_password: str = typer.Option(..., envvar="STG_ADMIN_PASSWORD"),
    company_prefix: str = "[STG] ",
    dry_run: bool = False,
):
    """Neutralize a staging instance so it can't send email or process payments."""
    # 1. Update web.base.url to current profile URL
    # 2. Deactivate ir.mail_server (all records → active=False)
    # 3. Disable payment.provider records (state='disabled')
    # 4. Disable base_webhook endpoints (active=False)
    # 5. Prefix company name with [STG]
    # 6. Set admin password
    # 7. Optionally clear res.users last_login to force re-auth
```

This command is idempotent — safe to run multiple times.

### Phase 7: Validation

```bash
# Smoke test both instances
curl -I https://stg-mac-odoo-erp.idtpp.com/web/login   # expect 200
curl -I https://stg-mac-odoo-hrms.idtpp.com/web/login  # expect 200

# Verify neutralization
kctl-odoo -p mac-erp-stg shell call ir.mail_server search_count '[[["active","=",true]]]'
# expected: 0

kctl-odoo -p mac-erp-stg shell call payment.provider search_count '[[["state","=","enabled"]]]'
# expected: 0

# Log in via browser and verify:
# - [STG] prefix visible in company name (top right)
# - Database dropdown shows stg_mac_odoo_erp
# - Recent records from production visible
```

---

## 5. Refresh Procedure

To refresh staging from production (e.g., weekly, or before a training session):

```bash
# One script that does Phase 1 + Phase 5
~/code/kodemeio-platform/scripts/refresh-mac-staging.sh
```

Script contents:
```bash
#!/usr/bin/env bash
set -euo pipefail

TS=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR=~/backups/mac-stg-clone
mkdir -p $BACKUP_DIR

echo "==> Dumping mac_odoo_erp..."
kctl-pg backup dump mac_odoo_erp --output $BACKUP_DIR/mac_odoo_erp_${TS}.sql.gz

echo "==> Dumping mac_odoo_hrms..."
kctl-pg backup dump mac_odoo_hrms --output $BACKUP_DIR/mac_odoo_hrms_${TS}.sql.gz

echo "==> Recreating stg_mac_odoo_erp..."
kctl-pg db drop stg_mac_odoo_erp --force
kctl-pg db create stg_mac_odoo_erp --owner odoo
kctl-pg backup restore stg_mac_odoo_erp $BACKUP_DIR/mac_odoo_erp_${TS}.sql.gz

echo "==> Recreating stg_mac_odoo_hrms..."
kctl-pg db drop stg_mac_odoo_hrms --force
kctl-pg db create stg_mac_odoo_hrms --owner odoo
kctl-pg backup restore stg_mac_odoo_hrms $BACKUP_DIR/mac_odoo_hrms_${TS}.sql.gz

echo "==> Neutralizing staging instances..."
kctl-odoo -p mac-erp-stg neutralize-staging
kctl-odoo -p mac-hrms-stg neutralize-staging

echo "==> Restarting Odoo containers..."
kctl-dokploy compose redeploy mac-odoo-erp-stg
kctl-dokploy compose redeploy mac-odoo-hrms-stg

echo "==> Done."
```

---

## 6. Rollback Plan

If any phase fails:

| Phase | Rollback Action |
|---|---|
| 1 (DB clone) | Drop the partially restored staging DBs — prod untouched |
| 2 (Env files) | Delete the new files — prod env files untouched |
| 3 (DNS) | Delete DNS records — no impact if compose not yet deployed |
| 4 (Compose) | `kctl-dokploy compose delete mac-odoo-erp-stg` — prod untouched |
| 5 (Neutralize) | Re-run with correct params, or drop staging DB and re-clone |

Production is never at risk because:
- All operations use `stg_*` database names
- All compose services use `*-stg` suffix
- DNS uses `stg-*` subdomains
- No prod configs are modified

---

## 7. Open Questions

None of these block deployment — they're nice-to-haves for v2:

1. **Should staging use a separate Authentik OAuth client?** Currently staging would reuse prod Authentik credentials. For v1 this is acceptable since staging uses the same user pool. For v2, consider a dedicated `mac-odoo-staging` Authentik application with separate RBAC.

2. **Should staging auto-refresh weekly?** After v1 is stable, add a cron job or GitHub Action that runs `refresh-mac-staging.sh` every Sunday at 2 AM.

3. **Should we add a visual banner?** The `[STG]` company prefix is subtle. Consider adding a CSS override that shows a red banner saying "STAGING ENVIRONMENT" at the top of every page. Requires a small Odoo theme override module.

---

## 8. Acceptance Criteria

This spec is complete when:

- [x] `https://stg-mac-odoo-erp.idtpp.com` loads and shows MAC production data
- [x] `https://stg-mac-odoo-hrms.idtpp.com` loads and shows HRMS production data
- [x] Both databases have `[STG]` company prefix visible
- [x] `ir.mail_server` records are all inactive in staging
- [x] `payment.provider` records are all disabled in staging
- [x] A training user can log in, create a test sales order, and it does NOT generate a real invoice email
- [x] `refresh-mac-staging.sh` completes in under 5 minutes end-to-end
- [x] Production databases are unchanged (verified via row counts before/after)
