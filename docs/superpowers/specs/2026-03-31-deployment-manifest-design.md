# Deployment Manifest System — Design Spec

**Date:** 2026-03-31
**Status:** Approved
**Scope:** `kctl-dokploy deploy` command + YAML manifest format

## Problem

Deploying services to Dokploy requires 12+ manual steps across 4 CLIs (cloudflare, pg, dokploy, odoo). Steps are error-prone, not reproducible, and not version-controlled. We need to support:

- Multiple Odoo instances (same image, different databases/profiles/domains)
- 18+ React PWA apps (same monorepo, different compose files/domains)
- 14+ infrastructure services (postgres, gatus, waha, etc.)
- Both new deployments and updates (idempotent)

## Approach: Base Template + Instance Overrides

Two-layer YAML manifests: **base templates** define shared patterns per service type, **instance manifests** inherit and override with instance-specific config.

```
deploys/
  bases/
    odoo.yaml           # Shared Odoo config (image, healthcheck, schedules)
    react-pwa.yaml      # Shared React PWA config (stateless, no DB)
    infra.yaml          # Shared infra config (compose + DB + backup)
  instances/
    odoo-prod.yaml      # extends: bases/odoo.yaml
    odoo-hrms.yaml      # extends: bases/odoo.yaml
    react-sfa.yaml      # extends: bases/react-pwa.yaml
    waha.yaml           # extends: bases/infra.yaml
```

## Base Template Format

```yaml
kind: base
type: odoo                        # odoo | react-pwa | infrastructure

source:
  type: github
  owner: tgunawandev
  repo: kodemeio-odoo
  branch: "18.0"
  compose_path: ./docker-compose.prod.yml

server: kodeme-service            # Dokploy server name
project: kodemeio-service         # Dokploy project name

healthcheck:
  path: /web/health
  port: 8069
  expected_status: 200
  timeout: 120

env_defaults:                     # Shared env vars
  RUNNING_ENV: production
  TZ: "Asia/Jakarta"

backup:                           # null for stateless services
  destination: kodemeio-s3-backups
  type: postgres
  schedule: "0 2 * * *"
  prefix_template: "odoo-{instance_name}"
  keep_latest: 30

schedules:                        # Supports {instance_name}, {db_name}, {db_user} interpolation
  - name: "{instance_name}-vacuum"
    cron: "0 4 * * 0"
    command: "vacuumdb -U {db_user} -d {db_name} --analyze"
    service: odoo

post_deploy:                      # Service-type-specific hooks
  odoo_profile: null
  odoo_init_db: true
```

## Instance Manifest Format

```yaml
kind: instance
extends: bases/odoo.yaml          # Path to base template

instance:
  name: kodemeio-odoo-prod        # Unique service name in Dokploy
  description: "Kodemeio Production ERP"

dns:
  zone: kodeme.io
  name: odoo                      # → odoo.kodeme.io
  content: 49.13.14.79

domain:
  host: odoo.kodeme.io
  port: 8069
  service: odoo                   # Docker Compose service name
  https: true

database:                         # Omit for stateless services
  name: kodemeio_prod
  user: odoo

env_overrides:                    # Merged on top of base env_defaults
  PGDATABASE: kodemeio_prod
  ODOO_DB_FILTER: "^kodemeio_prod$"
  DOMAIN: odoo.kodeme.io

source_overrides:                 # Override base source fields (e.g. compose_path for React)
  compose_path: ./docker-compose.sfa.yml

post_deploy:
  odoo_profile: profile-distribution
```

## Execution Flow: `kctl-dokploy deploy apply`

12 phases, fully automated, idempotent (check-before-create):

| Phase | Tool | Action | Idempotent |
|-------|------|--------|-----------|
| 1. Resolve | — | Read YAML, merge base+instance, interpolate variables | — |
| 2. DNS | kctl-cf | Create A record if not exists | Skip if exists |
| 3. Database | kctl-pg | Create role + database if not exists | Skip if exists |
| 4. Registry | kctl-dokploy | Create GHCR registry if not exists | Skip if exists |
| 5. Compose | kctl-dokploy | Create compose service + link GitHub repo | Update if changed |
| 6. Environment | kctl-dokploy | Push merged env vars | Always push (overwrite) |
| 7. Domain | kctl-dokploy | Create domain with service name | Skip if exists, update if changed |
| 8. Deploy | kctl-dokploy | Redeploy from GitHub | Always run |
| 9. Verify | curl/httpx | Poll healthcheck URL until healthy or timeout | — |
| 10. Backup | kctl-dokploy | Create backup config if not exists | Skip if exists |
| 11. Schedules | kctl-dokploy | Create/update schedules from manifest | Create if missing, update if changed |
| 12. Post-deploy | kctl-odoo | Install bundle/profile modules (Odoo only) | Skipped if modules already installed |

### Idempotency Rules

- Every phase checks existence before creating
- Updates only when values differ from current state
- Never deletes resources (DNS, schedules, backups)
- Re-running same manifest = no changes = all "skipped"
- Exit codes: 0 = success, 1 = deploy failed, 2 = post-deploy failed

## CLI Interface

```bash
# Deploy (create or update)
kctl-dokploy deploy apply --file deploys/instances/odoo-prod.yaml
kctl-dokploy deploy apply --file deploys/instances/odoo-prod.yaml --dry-run

# Check current state vs manifest
kctl-dokploy deploy status --file deploys/instances/odoo-prod.yaml

# Deploy all instances
kctl-dokploy deploy apply-all --dir deploys/instances/

# Show what's deployed
kctl-dokploy deploy list
```

## Base Template Coverage

| Base | Services | Database | Backup | Post-deploy |
|------|----------|----------|--------|-------------|
| `odoo.yaml` | Odoo ERP instances | Yes (per-instance) | Daily pg_dump to S3 | kctl-odoo bundles install |
| `react-pwa.yaml` | 18 React PWA apps | No | No (stateless) | None |
| `infra.yaml` | postgres, waha, gatus, etc. | Yes | Daily to S3 | None |

## Variable Interpolation

Templates support `{variable}` placeholders resolved from instance fields:

| Variable | Source |
|----------|--------|
| `{instance_name}` | `instance.name` |
| `{db_name}` | `database.name` |
| `{db_user}` | `database.user` |
| `{domain}` | `domain.host` |

`${OP_*}` references are resolved via kctl-op (1Password) at deploy time.

## Implementation Location

New command group in kctl-dokploy:
- `packages/kctl-dokploy/src/kctl_dokploy/commands/deploy.py`
- `packages/kctl-dokploy/src/kctl_dokploy/core/manifest.py` (YAML parser + merger)
- `packages/kctl-dokploy/src/kctl_dokploy/core/deployer.py` (12-phase executor)

## Out of Scope

- Auto-rollback on failure (manual via `kctl-dokploy pipeline rollback`)
- Secret rotation
- Multi-server orchestration (all services target one server per manifest)
- Terraform integration
