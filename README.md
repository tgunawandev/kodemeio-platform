# kodemeio-platform

Infrastructure repository for the Kodemeio ecosystem: deployment manifests, environment configs, server mapping, and operational tooling.

## CLI Tools

All 33 kctl-* CLI tools (kctl-lib, kctl-dokploy, kctl-odoo, etc.) have moved to [kodemeio-cli](https://github.com/tgunawandev/kodemeio-cli).

## What's Here

```
deploys/
├── bases/                      # Reusable base templates (odoo, react-pwa, nextjs, fastapi, infra)
├── instances/
│   ├── production/             # Production manifests (35 services)
│   └── staging/                # Staging manifests (17 services)
├── env/
│   ├── production/             # Production .env files (gitignored)
│   └── staging/                # Staging .env files (gitignored)
├── tenants/                    # Tenant definitions with environment config
├── migrations/                 # Server migration manifests
└── generate.py                 # Generate instances from tenant config

docs/                           # Architecture and standards documentation
runbooks/                       # Operational runbooks (postgres-restore, etc.)
monitoring/                     # Monitoring configurations
infra/                          # Infrastructure definitions
templates/                      # Service templates
```

## Deployment

Declarative YAML-based deployment via `kctl-dokploy deploy`. Instance manifests extend base templates and support production + staging environments.

```bash
# Deploy a single service
kctl-dokploy deploy apply -f deploys/instances/production/mac-react-sfa.yaml

# Batch deploy all production
kctl-dokploy deploy apply-all -d deploys/instances/production/

# Pre-deploy validation
kctl-dokploy deploy preflight -f <manifest>

# Generate manifests from tenant config
cd deploys && python generate.py
```

### 13-Phase Pipeline

Preflight → DNS → Database → Registry → Compose → Environment → Domain → Deploy → Verify → Backup → Schedules → Post-deploy

Uses: kctl-cf (DNS), kctl-pg (DB), kctl-dokploy (compose/env/domain/deploy/preflight), kctl-odoo (post-deploy bundles)

### Manifest Naming

`{tenant}-{stack}-{app}` — e.g., `mac-react-sfa`, `tpp-odoo-trad`, `kod-infra-grafana`

Tenant codes: `mac`, `tpp`, `kod`, `tgw`, `tkz`, `pro`, `kid`

## CI/CD

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `deploy.yml` | Push to main (deploys/instances/**) | Detect changed manifests |
| `secret-scan.yml` | Push/PR to main | Gitleaks secret scanning |

## Documentation

- [Architecture](docs/architecture.md) — Platform architecture overview
- [Migration SOP](docs/migration-sop.md) — Server migration runbook
- [Postgres Restore](runbooks/postgres-restore.md) — Backup restore procedures
