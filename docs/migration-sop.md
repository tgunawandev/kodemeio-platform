# Server Migration SOP

> Last updated: 2026-04-05 | Owner: Platform team

Standard operating procedure for migrating a tenant from one server to another using `kctl-dokploy deploy migrate`. Uses the MAC migration (`kod-prod-02` → `mac-prod-01`) as the running example.

---

## Contents

1. [Prerequisites](#1-prerequisites)
2. [Create Migration Manifest](#2-create-migration-manifest)
3. [Pre-Migration Checklist](#3-pre-migration-checklist)
4. [Execute Migration](#4-execute-migration)
5. [Monitor & Verify](#5-monitor--verify)
6. [Rollback](#6-rollback)
7. [Post-Migration Cleanup](#7-post-migration-cleanup-48h-soak)
8. [Troubleshooting](#8-troubleshooting)

---

## 1. Prerequisites

### Tools & Versions

| Tool | Minimum Version | Check |
|------|----------------|-------|
| kctl-dokploy | current | `kctl-dokploy --version` |
| kctl-pg | current | `kctl-pg --version` |
| kctl-cf | current | `kctl-cf --version` |
| kctl-hz | current | `kctl-hz --version` |

### Profiles Required

Configure the following profiles before starting:

```bash
# Verify active profiles
kctl-dokploy config current
kctl-pg config profiles
kctl-cf config current
kctl-hz config current
```

For the MAC migration, you need:

| Profile | CLI | Purpose |
|---------|-----|---------|
| `default` | kctl-dokploy | Dokploy API access |
| `kodemeio` | kctl-pg | Source postgres (kod-prod-01) |
| `mac-prod` | kctl-pg | Target postgres (mac-prod-01) |
| `mandiriagro` | kctl-cf | DNS management for mandiriagro.com |
| `mac` | kctl-hz | Hetzner firewall management |

### Server Mapping

| Tenant | Production Server | Staging Server |
|--------|-----------------|----------------|
| mac | `mac-prod-01` (91.98.80.207) | `mac-stg-01` |
| kod, tpp, tkz, pro, tgw, kid | `kod-prod-01` (49.13.116.191) | `kod-prod-02` |

### Access Verification

```bash
# SSH access to both servers
ssh root@49.13.116.191 "hostname && docker ps | head -3"   # source: kod-prod-01
ssh root@91.98.80.207  "hostname && docker ps | head -3"   # target: mac-prod-01

# Disk space on target (postgres needs ~2x database size)
ssh root@91.98.80.207 "df -h /"
```

---

## 2. Create Migration Manifest

Migration manifests live in `deploys/migrations/`. Convention: `{tenant}-to-{target}.yaml`.

### Manifest Format

```yaml
# deploys/migrations/mac-to-dedicated.yaml
kind: migration
name: mac-to-dedicated
description: "Migrate MAC tenant from kod-prod-02 to mac-prod-01"

source:
  server: kod-prod-02
  postgres_profile: kodemeio    # kctl-pg profile for source postgres

target:
  server: mac-prod-01
  postgres_profile: mac-prod    # kctl-pg profile for target postgres

tenant: mac
environment: production

databases:
  - name: mac_odoo_dist
    owner: odoo
  - name: mac_odoo_hrms
    owner: odoo

services:
  # Deploy manifests to create on target (relative to deploys/)
  - instances/production/mac-infra-postgres.yaml
  - instances/production/mac-odoo-dist.yaml
  - instances/production/mac-odoo-hrms.yaml
  - instances/production/mac-react-sfa.yaml
  - instances/production/mac-react-wms.yaml
  - instances/production/mac-react-hrm.yaml
  - instances/production/mac-react-bia.yaml
  - instances/production/mac-nextjs-web.yaml
  - instances/production/mac-nextjs-careers.yaml
  - instances/production/mac-hono-notify.yaml

dns:
  zone: mandiriagro.com
  records:
    - mac-odoo-dist
    - mac-odoo-hrms
    - mac-sfa
    - mac-wms
    - mac-hrm
    - mac-bia
    - mac-careers
    - mac-notify
    - mandiriagro.com   # apex

firewall:
  profile: mac
  required_ports: [80, 443]

validation:
  pre:
    - type: url_health
      urls:
        - https://mac-odoo-dist.mandiriagro.com/web/login
        - https://mac-odoo-hrms.mandiriagro.com/web/login
        - https://mandiriagro.com
        - https://mac-sfa.mandiriagro.com
        - https://mac-wms.mandiriagro.com
        - https://mac-hrm.mandiriagro.com
        - https://mac-bia.mandiriagro.com
        - https://mac-careers.mandiriagro.com
      expected_status: [200, 301, 303]
    - type: db_row_count
      database: mac_odoo_dist
      profile: kodemeio
      tables: [res_partner, sale_order, stock_picking]
    - type: db_row_count
      database: mac_odoo_hrms
      profile: kodemeio
      tables: [hr_employee, hr_attendance]

  post:
    - type: url_health
      urls:
        - https://mac-odoo-dist.mandiriagro.com/web/login
        - https://mac-odoo-hrms.mandiriagro.com/web/login
        - https://mandiriagro.com
        - https://mac-sfa.mandiriagro.com
        - https://mac-wms.mandiriagro.com
        - https://mac-hrm.mandiriagro.com
        - https://mac-bia.mandiriagro.com
        - https://mac-careers.mandiriagro.com
      expected_status: [200, 301, 303]
    - type: db_row_count
      database: mac_odoo_dist
      profile: mac-prod
      tables: [res_partner, sale_order, stock_picking]
      match_pre: true
    - type: db_row_count
      database: mac_odoo_hrms
      profile: mac-prod
      tables: [hr_employee, hr_attendance]
      match_pre: true
    - type: env_sync

cleanup:
  soak_hours: 48
  drop_source_databases: true
```

### Validate the manifest

```bash
kctl-dokploy deploy migrate validate -f deploys/migrations/mac-to-dedicated.yaml
```

Expected output: `Manifest valid — 2 databases, 10 services, 9 DNS records`

---

## 3. Pre-Migration Checklist

Complete all items before executing. Do not skip.

### Infrastructure

- [ ] SSH to source server works without password prompt
- [ ] SSH to target server works without password prompt
- [ ] Target server has sufficient disk space (`df -h /` — need 2x database size free)
- [ ] Target server has Docker running (`docker ps`)
- [ ] `dokploy-network` exists on target (`docker network inspect dokploy-network`)
- [ ] Hetzner firewall on target has ports 80 and 443 open (`kctl-hz firewalls show --profile mac`)

### Database

- [ ] Source databases are healthy (`kctl-pg health --profile kodemeio`)
- [ ] Source databases have a recent backup (within 24h)
- [ ] Target postgres kctl-pg profile is configured and connects (`kctl-pg health --profile mac-prod`)

### DNS & Env Files

- [ ] Reduce Cloudflare DNS TTL to 60s at least 1 hour before migration:
  ```bash
  kctl-cf dns update --zone mandiriagro.com --name mac-odoo-dist --ttl 60
  # Repeat for each record in the migration manifest
  ```
- [ ] All local env files exist for services in the manifest:
  ```bash
  ls deploys/env/production/.env.mac-*
  ```
- [ ] Notify users of maintenance window (estimated duration: 30-70 minutes)

### Dry-Run

```bash
# Preview all 12 steps without executing
kctl-dokploy deploy migrate plan -f deploys/migrations/mac-to-dedicated.yaml
```

Review the output. Confirm service list, database list, and DNS records are correct.

---

## 4. Execute Migration

### 12-Step Pipeline

| Step | Name | What happens |
|------|------|-------------|
| 1 | PREFLIGHT | 10 preflight gates run on target server |
| 2 | POSTGRES | Deploy `mac-infra-postgres` manifest on target |
| 3 | DB_TEST | Test database connectivity from target |
| 4 | STOP | Stop source services — **maintenance window starts** |
| 5 | DUMP | `pg_dump` databases from source postgres |
| 6 | RESTORE | `pg_restore` databases to target postgres |
| 7 | VERIFY_DATA | Compare row counts (source vs target) |
| 8 | DNS | Update Cloudflare DNS records to target IP |
| 9 | DELETE_OLD | Delete old compose services from Dokploy |
| 10 | DEPLOY | Create + deploy services on target |
| 11 | ENV_SYNC | Push local env files to Dokploy |
| 12 | VERIFY_URLS | HTTP health check on every domain |

Downtime occurs between steps 4 and 12.

### Run the migration

```bash
kctl-dokploy deploy migrate apply -f deploys/migrations/mac-to-dedicated.yaml
```

The command outputs each step as it runs. State is saved to:
```
~/.local/share/kodemeio/kctl-dokploy/migrations/<migration-id>.json
```

### Resume after failure

If the migration stops at any step, resume from where it left off:

```bash
kctl-dokploy deploy migrate apply -f deploys/migrations/mac-to-dedicated.yaml --resume
```

The `--resume` flag reads the state file and skips completed steps. Each step is idempotent — it is safe to re-run.

---

## 5. Monitor & Verify

### Watch live progress

The CLI shows a progress panel while running. To inspect the current state:

```bash
# Show migration state and current step
kctl-dokploy deploy migrate status -f deploys/migrations/mac-to-dedicated.yaml

# Tail logs of a specific service on the target
kctl-dokploy service logs mac-odoo-dist --tail 100

# Check all services on target
kctl-dokploy compose list | grep mac-
```

### Post-migration verification (automatic)

After step 12 completes, the post-validation suite runs automatically. It checks:

- HTTP status for all URLs in `validation.post.urls`
- Row counts on target match pre-migration snapshot
- Env sync: local files match Dokploy for all services

Expected output:
```
Post-Validation: MIGRATION VERIFIED
  10/10 URLs healthy
  DB mac_odoo_dist: 3/3 tables match pre-migration counts
  DB mac_odoo_hrms: 2/2 tables match pre-migration counts
  Env sync: 10/10 services match
```

### Manual spot-checks

```bash
# Odoo login page returns 200/303
curl -s -o /dev/null -w "%{http_code}\n" https://mac-odoo-dist.mandiriagro.com/web/login
curl -s -o /dev/null -w "%{http_code}\n" https://mac-odoo-hrms.mandiriagro.com/web/login

# DNS now points to mac-prod-01
kctl-cf dns list --zone mandiriagro.com | grep mac-odoo

# React PWAs load
curl -s -o /dev/null -w "%{http_code}\n" https://mac-sfa.mandiriagro.com
curl -s -o /dev/null -w "%{http_code}\n" https://mandiriagro.com

# Check SSL certificate
kctl-cf ssl check --domain mac-odoo-dist.mandiriagro.com
```

---

## 6. Rollback

### When to roll back

Roll back if:
- Post-validation fails and cannot be fixed quickly
- Services fail to start on target after repeated attempts
- Data integrity issues are found (row count mismatch)

### How to roll back

```bash
kctl-dokploy deploy migrate rollback -f deploys/migrations/mac-to-dedicated.yaml
```

Rollback steps (automated):
1. Restore DNS records to source server IP
2. Recreate compose services on source server (if they were deleted)
3. Redeploy on source server
4. Push env from local files

**Source databases are never dropped during rollback.** Data on the source is always preserved until you explicitly run cleanup.

### After rollback

```bash
# Verify services are back on source
kctl-dokploy compose list | grep mac-

# Verify DNS is back to source IP
kctl-cf dns list --zone mandiriagro.com | grep mac-odoo

# Health check
curl -s -o /dev/null -w "%{http_code}\n" https://mac-odoo-dist.mandiriagro.com/web/login
```

Restore DNS TTLs to their original values (typically 300s or 3600s) after confirming rollback is stable.

---

## 7. Post-Migration Cleanup (48h Soak)

Wait 48 hours of stable operation before running cleanup. This is the buffer for any issues not immediately visible.

### Soak period checks

During the 48h soak:
- [ ] Monitor error rates in Grafana: `kctl-grafana dashboard list`
- [ ] Check Sentry for new errors: `kctl-sentry issues list --project mac`
- [ ] Confirm OIDC SSO login works for React PWAs
- [ ] Confirm backups are running on the new server

### Run cleanup

```bash
kctl-dokploy deploy migrate cleanup -f deploys/migrations/mac-to-dedicated.yaml
```

Cleanup steps (automated):
1. Drop source databases (`mac_odoo_dist`, `mac_odoo_hrms` from `kod-prod-01` postgres)
2. Remove dump files from both servers
3. Mark migration state as `complete`

### Restore DNS TTL

After cleanup, restore Cloudflare TTL to normal (300s):

```bash
kctl-cf dns update --zone mandiriagro.com --name mac-odoo-dist --ttl 300
# Repeat for each record
```

---

## 8. Troubleshooting

### Preflight fails — firewall blocking port 80/443

```bash
# Check which firewall is applied to mac-prod-01
kctl-hz firewalls list --profile mac

# Show rules
kctl-hz firewalls show --name mac-prod-fw --profile mac

# Add missing rule
kctl-hz firewalls add-rule --name mac-prod-fw --port 443 --protocol tcp --source 0.0.0.0/0 --profile mac
```

### Preflight fails — DNS points to wrong server

```bash
# Check current DNS
kctl-cf dns list --zone mandiriagro.com

# Update A record to target IP
kctl-cf dns update --zone mandiriagro.com --name mac-odoo-dist --value 91.98.80.207
```

### Step 3 (DB_TEST) fails — cannot connect to target postgres

The PGHOST in the target env file may be wrong. The postgres container runs on `dokploy-network`. Find its Docker network IP:

```bash
ssh root@91.98.80.207 \
  "docker inspect \$(docker ps -q -f name=postgres) \
   --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'"
```

Update the env file and re-run:

```bash
# Edit deploys/env/production/.env.mac-odoo-dist
# Change PGHOST to the correct IP
kctl-dokploy deploy migrate apply -f deploys/migrations/mac-to-dedicated.yaml --resume
```

### Step 6 (RESTORE) fails — database already exists

The target databases may have been partially created. Drop and retry:

```bash
kctl-pg exec --profile mac-prod -- \
  psql -U postgres -c "DROP DATABASE IF EXISTS mac_odoo_dist;"
kctl-pg exec --profile mac-prod -- \
  psql -U postgres -c "DROP DATABASE IF EXISTS mac_odoo_hrms;"

kctl-dokploy deploy migrate apply -f deploys/migrations/mac-to-dedicated.yaml --resume
```

### Step 10 (DEPLOY) fails — Docker image pull fails

The image name or registry may be wrong in the deploy manifest.

```bash
# Check the failing service
kctl-dokploy service logs mac-odoo-dist --tail 50

# Verify the image can be pulled manually on target
ssh root@91.98.80.207 "docker pull ghcr.io/kodemeio/odoo:18.0"
```

If using a private registry, confirm the registry credentials are pushed:

```bash
kctl-dokploy deploy setup -f deploys/instances/production/mac-odoo-dist.yaml
# Phase 3 (registry) sets up credentials
```

### Step 11 (ENV_SYNC) — OIDC credentials missing after deploy

Env file may be missing OIDC vars. Verify the local env file has `OIDC_CLIENT_ID` and `OIDC_REDIRECT_URI`, then re-push:

```bash
grep OIDC deploys/env/production/.env.mac-react-sfa

kctl-dokploy compose env push <compose-id> deploys/env/production/.env.mac-react-sfa
```

### Step 12 (VERIFY_URLS) — SSL certificate not issued

Let's Encrypt needs to reach the server directly on port 80. If Cloudflare proxy is active, it may interfere.

```bash
# Temporarily disable Cloudflare proxy for the domain
kctl-cf dns update --zone mandiriagro.com --name mac-odoo-dist --proxied false

# Trigger certificate renewal (Traefik does this automatically on first request)
curl -sf https://mac-odoo-dist.mandiriagro.com/web/login

# Re-enable proxy after cert is issued
kctl-cf dns update --zone mandiriagro.com --name mac-odoo-dist --proxied true
```

### Migration state is corrupted

State file location:
```
~/.local/share/kodemeio/kctl-dokploy/migrations/migrate-mac-<timestamp>.json
```

To view the current state:
```bash
kctl-dokploy deploy migrate status -f deploys/migrations/mac-to-dedicated.yaml
```

If state is corrupt, edit the JSON file directly to mark completed steps as `"done"` and re-run with `--resume`.

---

## Reference: Migration State File

State is persisted to disk so migrations survive network interruptions and can be resumed.

```json
{
  "id": "migrate-mac-20260405-021500",
  "tenant": "mac",
  "from_server": "kod-prod-02",
  "to_server": "mac-prod-01",
  "status": "in_progress",
  "current_step": 8,
  "steps": {
    "1_preflight":    {"status": "done", "timestamp": "2026-04-05T02:15:00Z"},
    "2_postgres":     {"status": "done", "compose_id": "RpB1SJ1T3FvjZ6bgQ7lsE"},
    "3_db_test":      {"status": "done"},
    "4_stop":         {"status": "done", "services_stopped": ["b253C2...", "OEK_dJ..."]},
    "5_dump":         {"status": "done", "dumps": ["/tmp/mac_odoo_dist.dump", "/tmp/mac_odoo_hrms.dump"]},
    "6_restore":      {"status": "done"},
    "7_verify_data":  {"status": "done", "counts": {"mac_odoo_dist.res_partner": 13}},
    "8_dns":          {"status": "pending"},
    "9_delete_old":   {"status": "pending"},
    "10_deploy":      {"status": "pending"},
    "11_env_sync":    {"status": "pending"},
    "12_verify_urls": {"status": "pending"}
  },
  "rollback": {
    "dns_records": [{"id": "61227...", "old_content": "49.13.14.79"}],
    "source_compose_ids": ["b253C2...", "OEK_dJ..."]
  }
}
```

Rollback data is captured automatically at step 4 (STOP) before any destructive actions.
