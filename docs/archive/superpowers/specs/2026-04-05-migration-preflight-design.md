# Migration & Preflight System Design

**Date:** 2026-04-05
**Status:** Draft
**Scope:** `kctl-dokploy deploy preflight` + `deploy migrate` commands

---

## Problem

Server migrations are manual, error-prone, and cause extended downtime. The MAC migration to `mac-prod-01` had 10 preventable failures over 2.5 hours because nothing was validated before execution. Every failure would have been caught by automated pre-flight checks.

## Goal

1. `deploy preflight` — validate a target server is ready for deployment before touching anything
2. `deploy migrate` — fully automated server-to-server migration with rollback capability
3. `deploy apply` — automatically runs preflight before deploying (abort on failure)
4. Migration SOP documented in `docs/migration-sop.md`

## Lessons from MAC Migration

| Failure | Gate that would catch it |
|---------|------------------------|
| Wrong repo name | Gate 8: Source validation |
| Docker image build failed | Gate 4: Image pull test |
| PGHOST wrong (3 times) | Gate 5: Database connectivity |
| Password auth failed | Gate 5: Database auth test |
| Services on wrong server | Gate 6: Server assignment |
| Deleted running services | Migrate step: safe delete order |
| Firewall blocked 80/443 | Gate 2: Firewall check |
| OIDC credentials wiped | Gate 7: Env sync validation |
| DNS pointed to wrong server | Gate 3: DNS resolution |
| SSL certs not issued | Gate 10: Certificate check |

## Command 1: `deploy preflight`

### Usage

```bash
# Single manifest
kctl-dokploy deploy preflight -f deploys/instances/production/mac-odoo-hrms.yaml

# All manifests for a server
kctl-dokploy deploy preflight-all -d deploys/instances/production/ --server mac-prod-01

# Specific gates only
kctl-dokploy deploy preflight -f manifest.yaml --gates firewall,dns,database
```

### 10 Preflight Gates

Each gate returns PASS, WARN, or FAIL. Any FAIL blocks deployment.

#### Gate 1: Server Connectivity
- SSH to target server works (resolved from manifest `server` field via Dokploy servers API)
- Docker is installed (`docker --version`)
- `dokploy-network` exists (`docker network inspect dokploy-network`)

#### Gate 2: Hetzner Firewall
- Resolve server IP from Dokploy
- Find Hetzner firewall applied to that server (try all kctl-hz profiles)
- Verify port 80 (HTTP) is open inbound from 0.0.0.0/0
- Verify port 443 (HTTPS) is open inbound from 0.0.0.0/0
- If manifest has `database` section: verify port 5432 is open from private network

#### Gate 3: DNS Resolution
- Resolve `domain.host` from manifest
- Verify it points to the target server's public IP (not another server)
- Report Cloudflare proxy status (proxied vs direct)
- WARN if proxied (may need temporary disable for Let's Encrypt)

#### Gate 4: Docker Image Pull
- SSH to target server
- `docker pull <image>` for the compose's primary service image
- For GitHub source composes: verify the repo is accessible and branch exists

#### Gate 5: Database Connectivity (if manifest has `database` section)
- SSH to target server
- From a container on `dokploy-network`, test: `psql -h $PGHOST -U $PGUSER -d $PGDATABASE -c 'SELECT 1'`
- Verify password authentication works (uses PGPASSWORD from local env file)
- If migration: verify source database has data (`SELECT count(*) FROM ir_module_module`)

#### Gate 6: Compose Server Assignment
- If compose exists in Dokploy: verify `serverId` matches target server
- If compose doesn't exist: PASS (will be created)
- Verify compose is in the correct Dokploy environment (production/staging)

#### Gate 7: Env File Sync
- Local env file exists at path specified in manifest `env_file`
- Pull current Dokploy env and diff against local
- Report any drift (extra vars in Dokploy, missing vars locally)
- If `VITE_AUTH_MODE=oidc`: verify `OIDC_CLIENT_ID` and `OIDC_REDIRECT_URI` are non-empty
- FAIL if local env file is missing

#### Gate 8: Source Configuration
- GitHub repo `source.owner/source.repo` exists (via GitHub API or `git ls-remote`)
- Branch `source.branch` exists
- Compose file at `source.compose_path` exists in the repo

#### Gate 9: Network Topology
- SSH to target server
- Check Hetzner private IP (`ip addr show eth1`)
- Verify PGHOST in env file is reachable from the server
- Test TCP connection: `nc -z $PGHOST 5432`
- WARN if PGHOST is a Docker container name (fragile)

#### Gate 10: SSL/TLS
- Check if Let's Encrypt cert exists for the domain on the target server
- If not: WARN that first deploy will need CF proxy disabled temporarily
- Check Cloudflare SSL mode (should be "Full" or "Full (Strict)")

### Output Format

```
╭──────────── Preflight: mac-odoo-hrms ─────────────╮
│ Target: mac-prod-01 (91.98.80.207)                 │
│                                                     │
│  ✓ Gate 1: Server Connectivity          PASS        │
│  ✓ Gate 2: Hetzner Firewall             PASS        │
│  ✓ Gate 3: DNS Resolution               PASS        │
│  ✓ Gate 4: Docker Image Pull            PASS        │
│  ✓ Gate 5: Database Connectivity        PASS        │
│  ✓ Gate 6: Compose Server Assignment   PASS        │
│  ✓ Gate 7: Env File Sync               PASS        │
│  ✓ Gate 8: Source Configuration         PASS        │
│  ⚠ Gate 9: Network Topology            WARN        │
│    PGHOST=10.0.0.3 (private IP — verify no collision) │
│  ✓ Gate 10: SSL/TLS                    PASS        │
│                                                     │
│ Result: READY (9 pass, 1 warn, 0 fail)             │
╰─────────────────────────────────────────────────────╯
```

## Command 2: `deploy migrate`

### Usage

```bash
# Migrate a single tenant to a new server
kctl-dokploy deploy migrate \
  --from kod-prod-02 \
  --to mac-prod-01 \
  --tenant mac \
  -d deploys/instances/production/

# Migrate with explicit database list
kctl-dokploy deploy migrate \
  --from kod-prod-01 \
  --to mac-prod-01 \
  --tenant mac \
  --databases mac_odoo_dist,mac_odoo_hrms \
  -d deploys/instances/production/

# Dry-run (show what would happen)
kctl-dokploy deploy migrate --dry-run ...

# Resume a failed migration
kctl-dokploy deploy migrate --resume <migration-id>
```

### 12-Step Migration Pipeline

Each step is idempotent. State is persisted to `~/.local/share/kodemeio/kctl-dokploy/migrations/<id>.json` so migrations can be resumed after failure.

```
Step 1:  PREFLIGHT     Run all 10 preflight gates on target server
Step 2:  POSTGRES       Deploy postgres on target (if manifest exists)
Step 3:  DB_TEST        Test database connectivity from target server
Step 4:  STOP           Stop services on source server (maintenance window starts)
Step 5:  DUMP           pg_dump databases from source postgres
Step 6:  RESTORE        pg_restore databases to target postgres
Step 7:  VERIFY_DATA    Compare row counts (source vs target)
Step 8:  DNS            Update Cloudflare DNS records to target server IP
Step 9:  DELETE_OLD     Delete old compose services from Dokploy
Step 10: DEPLOY         Create + deploy services on target (deploy apply from manifests)
Step 11: ENV_SYNC       Push local env files to Dokploy (single source of truth)
Step 12: VERIFY_URLS    HTTP health check on every domain (curl -k https://...)
```

### State File

```json
{
  "id": "migrate-mac-20260405-021500",
  "tenant": "mac",
  "from_server": "kod-prod-02",
  "to_server": "mac-prod-01",
  "status": "in_progress",
  "current_step": 8,
  "steps": {
    "1_preflight": {"status": "done", "timestamp": "..."},
    "2_postgres": {"status": "done", "compose_id": "RpB1SJ1T3FvjZ6bgQ7lsE"},
    "3_db_test": {"status": "done"},
    "4_stop": {"status": "done", "services_stopped": ["b253C2...", "OEK_dJ..."]},
    "5_dump": {"status": "done", "dumps": ["/tmp/mac_odoo_dist.dump", "/tmp/mac_odoo_hrms.dump"]},
    "6_restore": {"status": "done"},
    "7_verify_data": {"status": "done", "counts": {"mac_odoo_dist.res_partner": 13}},
    "8_dns": {"status": "pending"},
    "9_delete_old": {"status": "pending"},
    "10_deploy": {"status": "pending"},
    "11_env_sync": {"status": "pending"},
    "12_verify_urls": {"status": "pending"}
  },
  "rollback": {
    "dns_records": [{"id": "61227...", "old_content": "49.13.14.79"}],
    "source_compose_ids": ["b253C2...", "OEK_dJ..."]
  }
}
```

### Rollback

If migration fails after step 4 (services stopped):

```bash
kctl-dokploy deploy migrate --rollback <migration-id>
```

Rollback steps:
1. Restore DNS records to source server IP
2. Recreate compose services on source server (if deleted)
3. Redeploy on source server
4. Push env from local files

Data is never lost — source databases are kept until explicit cleanup.

### Cleanup (after 48h soak)

```bash
kctl-dokploy deploy migrate --cleanup <migration-id>
```

Cleanup steps:
1. Drop source databases
2. Remove dump files
3. Mark migration as complete

## Command 3: `deploy apply` — Preflight Integration

Add automatic preflight to `deploy apply`:

```python
def phase_preflight(self) -> None:
    """Run preflight checks before deployment."""
    if self.skip_preflight:
        self._record_phase("preflight", "skipped", "Skipped via --skip-preflight")
        return

    results = run_preflight(self.manifest, self._get_client())
    failures = [g for g in results if g.status == "fail"]

    if failures:
        for f in failures:
            self._log(f"PREFLIGHT FAIL: Gate {f.gate}: {f.message}")
        self._record_phase("preflight", "failed", f"{len(failures)} gate(s) failed")
        return  # Abort deployment

    self._record_phase("preflight", "passed", f"{len(results)} gates checked")
```

The `--skip-preflight` flag exists for emergencies but logs a warning.

## Env File SOP (Enforced)

The `deploy apply` and `deploy migrate` commands enforce:

1. **Local env file must exist** — if `manifest.env_file` points to a missing file, abort
2. **Local is pushed to Dokploy** — never read from Dokploy, always push from local
3. **Drift detection** — warn if Dokploy has vars not in local file

## File Map

| File | Purpose |
|------|---------|
| `core/preflight.py` | 10 preflight gates implementation |
| `core/migrator.py` | 12-step migration pipeline with state persistence |
| `core/migration_manifest.py` | Migration YAML manifest parser (Pydantic models) |
| `core/validator.py` | Pre/post validation checks (URL health, DB row counts, env sync) |
| `commands/deploy.py` | Add `preflight`, `preflight-all`, `migrate` subcommands |
| `commands/migrate.py` | `migrate validate`, `migrate plan`, `migrate apply`, `migrate rollback`, `migrate cleanup` |
| `core/deployer.py` | Add `phase_preflight()` to deploy pipeline |
| `deploys/migrations/` | Migration manifest YAML files |
| `docs/migration-sop.md` | Migration standard operating procedure |
| `tests/core/test_preflight.py` | Preflight gate tests |
| `tests/core/test_migrator.py` | Migration pipeline tests |
| `tests/core/test_validator.py` | Pre/post validation tests |

## Migration Manifest YAML

Instead of passing flags, migrations are defined declaratively:

```yaml
# deploys/migrations/mac-to-dedicated.yaml
kind: migration
name: mac-to-dedicated
description: "Migrate MAC tenant from kod-prod-02 to mac-prod-01"

source:
  server: kod-prod-02
  postgres_profile: kodemeio    # kctl-pg profile for source

target:
  server: mac-prod-01
  postgres_profile: mac-prod   # kctl-pg profile for target

tenant: mac
environment: production

databases:
  - name: mac_odoo_dist
    owner: odoo
  - name: mac_odoo_hrms
    owner: odoo

services:
  # List of instance manifests to migrate (relative to deploys/)
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
  profile: mac           # kctl-hz profile
  required_ports: [80, 443]

validation:
  pre:
    # Checks BEFORE migration starts
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
    # Checks AFTER migration completes
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
      match_pre: true  # row counts must match pre-migration snapshot
    - type: db_row_count
      database: mac_odoo_hrms
      profile: mac-prod
      tables: [hr_employee, hr_attendance]
      match_pre: true
    - type: env_sync
      # Verify local env files match Dokploy for all services
    - type: oidc_login
      # Verify OIDC redirect works for React apps (optional, requires Playwright)
      urls:
        - https://mac-sfa.mandiriagro.com
        - https://mac-wms.mandiriagro.com

cleanup:
  soak_hours: 48
  drop_source_databases: true
```

### Usage with Migration Manifest

```bash
# Validate the migration manifest
kctl-dokploy deploy migrate validate -f deploys/migrations/mac-to-dedicated.yaml

# Dry-run (show all steps without executing)
kctl-dokploy deploy migrate plan -f deploys/migrations/mac-to-dedicated.yaml

# Execute migration
kctl-dokploy deploy migrate apply -f deploys/migrations/mac-to-dedicated.yaml

# Resume failed migration
kctl-dokploy deploy migrate apply -f deploys/migrations/mac-to-dedicated.yaml --resume

# Rollback
kctl-dokploy deploy migrate rollback -f deploys/migrations/mac-to-dedicated.yaml

# Cleanup after 48h soak
kctl-dokploy deploy migrate cleanup -f deploys/migrations/mac-to-dedicated.yaml
```

## Pre/Post Validation System

### Pre-Validation (runs before step 1)

Captures the current state as a baseline:

1. **URL Health Snapshot** — HTTP status for every URL in the migration
2. **Database Row Counts** — key table counts for data integrity verification
3. **DNS Snapshot** — current DNS records and IPs
4. **Env Snapshot** — hash of each local env file

All results saved to the migration state file. Migration ABORTS if pre-validation fails (e.g., source services are already down).

### Post-Validation (runs after step 12)

Compares against the pre-validation baseline:

1. **URL Health Check** — every URL returns expected status code
2. **Database Row Count Match** — row counts match pre-migration snapshot (within tolerance)
3. **DNS Verification** — all records point to new server IP
4. **Env Sync Verification** — local env files match Dokploy env for every service
5. **OIDC Login Test** — (optional) Playwright test that SSO redirect works

Post-validation failures trigger automatic rollback if `auto_rollback: true` is set.

### Validation Output

```
╭──────────── Pre-Validation ─────────────╮
│ ✓ mac-odoo-dist.mandiriagro.com   303   │
│ ✓ mac-odoo-hrms.mandiriagro.com   303   │
│ ✓ mandiriagro.com                 200   │
│ ✓ mac-sfa.mandiriagro.com         200   │
│ ✓ mac-wms.mandiriagro.com         200   │
│ ✓ mac-hrm.mandiriagro.com         200   │
│ ✓ mac-bia.mandiriagro.com         200   │
│ ✓ mac-careers.mandiriagro.com     200   │
│                                         │
│ DB: mac_odoo_dist                       │
│   res_partner: 13                       │
│   sale_order: 45                        │
│   stock_picking: 128                    │
│ DB: mac_odoo_hrms                       │
│   hr_employee: 20                       │
│   hr_attendance: 1,847                  │
│                                         │
│ Result: BASELINE CAPTURED               │
╰─────────────────────────────────────────╯

... migration runs ...

╭──────────── Post-Validation ────────────╮
│ ✓ mac-odoo-dist.mandiriagro.com   303   │
│ ✓ mac-odoo-hrms.mandiriagro.com   303   │
│ ✓ mandiriagro.com                 200   │
│ ✓ mac-sfa.mandiriagro.com         200   │
│ ✓ mac-wms.mandiriagro.com         200   │
│ ✓ mac-hrm.mandiriagro.com         200   │
│ ✓ mac-bia.mandiriagro.com         200   │
│ ✓ mac-careers.mandiriagro.com     200   │
│                                         │
│ DB: mac_odoo_dist (target)              │
│   res_partner: 13 ✓ (matches pre)      │
│   sale_order: 45 ✓ (matches pre)       │
│   stock_picking: 128 ✓ (matches pre)   │
│ DB: mac_odoo_hrms (target)              │
│   hr_employee: 20 ✓ (matches pre)      │
│   hr_attendance: 1,847 ✓ (matches pre) │
│                                         │
│ Env sync: 10/10 services match          │
│                                         │
│ Result: MIGRATION VERIFIED ✓            │
╰─────────────────────────────────────────╯
```

## Out of Scope

- Odoo init script password bug (separate issue in kodemeio-odoo repo)
- PgBouncer configuration on target server
- Staging environment migrations (same system, just different manifests)
- Multi-server load balancing

## Success Criteria

Running `kctl-dokploy deploy migrate --tenant tpp --from kod-prod-01 --to tpp-prod-01` should:
1. Complete in under 30 minutes (including database dump/restore)
2. Zero manual intervention
3. Zero downtime errors that weren't caught by preflight
4. Automatic rollback if any step fails after services are stopped
5. All URLs verified healthy before declaring success
