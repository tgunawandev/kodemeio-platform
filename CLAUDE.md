# CLAUDE.md - kodemeio-platform

Infrastructure-only repository: deployment manifests, environment configs, and operational tooling.

## CLI Tools

All kctl-* CLI tools have moved to [kodemeio-cli](https://github.com/tgunawandev/kodemeio-cli).

## Key Paths

| Path | Description |
|------|-------------|
| `deploys/bases/` | Deployment base templates (odoo, react-pwa, nextjs, fastapi, infra) |
| `deploys/instances/production/` | Production instance manifests (35 services) |
| `deploys/instances/staging/` | Staging instance manifests (17 services — mac + tpp) |
| `deploys/env/production/` | Production .env files (gitignored) |
| `deploys/env/staging/` | Staging .env files (gitignored) |
| `deploys/tenants/` | Tenant definitions with environment config |
| `deploys/migrations/` | Migration manifest YAML files |
| `deploys/generate.py` | Generate instances from tenant config |
| `docs/architecture.md` | Platform architecture |
| `docs/migration-sop.md` | Server migration runbook |
| `runbooks/` | Operational runbooks (postgres-restore, etc.) |
| `.github/workflows/deploy.yml` | Deploy: detect changed manifests on push to main |
| `.github/workflows/secret-scan.yml` | Gitleaks secret scanning on push/PR |

## Deployment System

Declarative YAML-based deployment via `kctl-dokploy deploy`. Manifests live in `deploys/`.

### Structure

```
deploys/
├── bases/                          # Reusable base templates
│   ├── odoo.yaml                   # Odoo 18 base (compose, env, healthcheck, backup)
│   ├── react-pwa.yaml              # React PWA base (GitHub source, nginx)
│   ├── nextjs.yaml                 # Next.js base (GitHub source, port 3000)
│   ├── fastapi.yaml                # FastAPI base (port 8000)
│   └── infra.yaml                  # Infrastructure services base
├── env/
│   ├── production/                 # Production .env files (gitignored)
│   └── staging/                    # Staging .env files (gitignored)
├── instances/
│   ├── production/                 # Production manifests (34 services)
│   └── staging/                    # Staging manifests (17 services)
├── tenants/                        # Tenant definitions (mac.yaml, tpp.yaml)
├── setup/                          # Company setup scripts
└── generate.py                     # Generate instances from tenant config
```

### Multi-Environment Support

Each tenant can define production + staging environments. The deployer targets the correct Dokploy environment automatically.

| Environment | Branch | DNS Prefix | DB Prefix | Auto-deploy |
|-------------|--------|------------|-----------|-------------|
| production | main / 18.0 | (none) | (none) | false (manual) |
| staging | main / 18.0 | stg- | stg_ | true (on push) |

Server mapping (Hetzner):
- **idtpp account** (`trigunawan.note@gmail.com`, nbg1-dc3, private net `10.0.0.0/24`):
  - `tpp-prod-01` (`178.104.127.104` / `10.0.0.2`) — shared postgres, authentik, mailcow
  - `tpp-prod-02` (`46.224.93.123` / `10.0.0.3`) — **MAC production** (compose-embedded postgres)
  - `tpp-prod-03` (`46.225.215.106` / `10.0.0.4`)
  - `tpp-prod-04` (`178.104.169.250` / `10.0.0.6`) — mattermost
  - `tpp-prod-05` (`178.104.171.122` / `10.0.0.5`)
  - Hosts both `tpp` and `mac` tenants.
- **kodemeio account** (`tri.gunawan@live.com`, fsn1-dc14, private net `10.0.0.0/24`):
  - `kod-prod-01` (`49.13.116.191` / `10.0.0.2`)
  - `kod-prod-02` (`49.13.14.79` / `10.0.0.3`)
  - Hosts `kod`, `tkz`, `pro`, `tgw`, `kid` tenants.

> Historical note: a separate MAC-only Hetzner account once ran `mac-prod-01` at
> `91.98.80.207` (fsn1-dc14). It was merged into the `idtpp` account; MAC now
> runs on `tpp-prod-02`.

### Deploy Commands

```bash
# Production deploy
kctl-dokploy deploy apply -f deploys/instances/production/mac-react-sfa.yaml

# Staging deploy
kctl-dokploy deploy apply -f deploys/instances/staging/mac-react-sfa.yaml

# Batch deploy all production
kctl-dokploy deploy apply-all -d deploys/instances/production/

# Batch deploy all staging
kctl-dokploy deploy apply-all -d deploys/instances/staging/

# Troubleshoot failed deployment
kctl-dokploy deploy troubleshoot -f <manifest>
kctl-dokploy deploy troubleshoot --compose <id>

# Staged deployment (for troubleshooting)
kctl-dokploy deploy setup -f <manifest>   # Stage 1: DNS + DB + Compose + Env + Domain
kctl-dokploy deploy run -f <manifest>     # Stage 2: Deploy + Verify healthcheck
kctl-dokploy deploy post -f <manifest>    # Stage 3: Backup + Schedules + Post-deploy

# Preflight checks (pre-deploy validation)
kctl-dokploy deploy preflight -f <manifest>
kctl-dokploy deploy preflight-all -d deploys/instances/production/
kctl-dokploy deploy preflight-all -d deploys/instances/production/ --server tpp-prod-02

# Server migration
kctl-dokploy deploy migrate validate -f deploys/migrations/mac-to-dedicated.yaml
kctl-dokploy deploy migrate plan -f deploys/migrations/mac-to-dedicated.yaml
kctl-dokploy deploy migrate apply -f deploys/migrations/mac-to-dedicated.yaml
kctl-dokploy deploy migrate rollback -f deploys/migrations/mac-to-dedicated.yaml
kctl-dokploy deploy migrate cleanup -f deploys/migrations/mac-to-dedicated.yaml

# Preview / status
kctl-dokploy deploy status -f <manifest>

# Generate manifests from tenant config
cd deploys && python generate.py            # Generate all
cd deploys && python generate.py -t mac     # Generate single tenant
cd deploys && python generate.py --dry-run  # Preview
```

### 13-Phase Pipeline

| # | Phase | CLI Used | Description |
|---|-------|----------|-------------|
| 0 | Preflight | kctl-dokploy | 10 gates: server, firewall, DNS, image pull, DB, compose, env sync (OIDC), source, network, SSL |
| 1 | DNS | kctl-cf | Create/verify DNS record |
| 2 | Database | kctl-pg | Create database + user |
| 3 | Registry | kctl-dokploy | Ensure container registry access |
| 4 | Compose | kctl-dokploy | Create/update compose service |
| 5 | Environment | kctl-dokploy | Push env vars from manifest |
| 6 | Domain | kctl-dokploy | Configure Traefik domain routing |
| 7 | Deploy | kctl-dokploy | Trigger redeploy |
| 8 | Verify | kctl-dokploy | Wait for healthcheck pass |
| 9 | Backup | kctl-dokploy | Configure backup destination + schedule |
| 10 | Schedules | kctl-dokploy | Setup cron jobs (vacuum, session cleanup) |
| 11 | Post-deploy | kctl-odoo | Install Odoo bundles/profiles |

### Odoo Prod Compose

Source: `kodemeio-odoo` repo → `compose/odoo.prod.yml` (4 containers: init → web + cron + gevent)

### Compose Postgres Backup → S3 → Local Restore

`kctl-dokploy backups restore` streams Dokploy's native SSE restore endpoint.

```bash
# One-shot restore — latest S3 key for a database (prod → local)
kctl-dokploy -p local backups restore \
    --compose <local-compose-id> \
    --destination <local-dest-id> \
    --database-name <db-name> \
    --service-name postgres \
    --database-user odoo \
    --latest <db-name>
```

See `runbooks/postgres-restore.md` for the full reference.

## Deploy Manifest Naming

Convention: `{tenant}-{stack}-{app}.yaml`

Stacks: `react`, `nextjs`, `odoo`, `hono`, `fastapi`, `infra`

Examples:
- `mac-react-sfa.yaml` — MAC SFA PWA
- `tpp-odoo-trad.yaml` — Pakerti Trading Odoo
- `kod-infra-grafana.yaml` — Kodemeio Grafana monitoring

Dokploy projects use tenant codes: `mac`, `tpp`, `kod`, `tgw`, `tkz`, `pro`, `kid`

Each Dokploy project has environments (production + staging). Services keep the same name across environments — the Dokploy environment provides separation.

## Env File Conventions

- Production: `deploys/env/production/.env.<service-name>` (gitignored)
- Staging: `deploys/env/staging/.env.<service-name>` (gitignored)
- Every `.env` file must have a corresponding `.env.example` (sanitized, committed)
- Never commit secrets — use environment variables or 1Password
