# Multi-Environment Deploys Design

**Date:** 2026-04-05  
**Status:** Draft  
**Scope:** `deploys/` structure refactor + `kctl-dokploy` environment support

---

## Problem

All 34 deploy manifests target a single environment (production). There is no way to deploy a staging copy of a service with different server, domain, database, and env vars using the existing manifest system.

Dokploy already supports environments per project (e.g., `production` + `staging`), but `kctl-dokploy deploy` always creates services in the default environment and has no manifest field to control which environment a service belongs to.

## Goal

- Deploy any service to either `production` or `staging` using the same manifest pipeline
- Staging services run on separate servers with separate databases and subdomains
- The generator (`generate.py`) produces manifests for both environments from a single tenant definition
- `kctl-dokploy` natively supports the `environment` field in manifests

## Server Layout

| Tenant | Production Server | Staging Server |
|--------|------------------|----------------|
| mac | `mac-prod-01` | `mac-stg-01` |
| kod, tpp, tkz, pro, tgw, kid | `kod-prod-01` | `kod-prod-02` |

Future tenants will get dedicated server pairs. Until then, they share `kod-*` servers.

## Branch Strategy

Same branch for both environments. No staging branch.

| Stack | Branch | Both Environments |
|-------|--------|-------------------|
| React PWA | `main` | yes |
| Next.js | `main` | yes |
| Hono | `main` | yes |
| FastAPI | `18.0` | yes |
| Odoo | `18.0` | yes |

## Naming Convention

Services keep the same `{tenant}-{stack}-{app}` name in both environments. The Dokploy **environment** (production vs staging) provides the separation — not the service name.

| Attribute | Production | Staging |
|-----------|-----------|---------|
| Service name | `mac-react-sfa` | `mac-react-sfa` |
| Dokploy environment | `production` | `staging` |
| Server | `mac-prod-01` | `mac-stg-01` |
| DNS subdomain | `mac-sfa.mandiriagro.com` | `stg-mac-sfa.mandiriagro.com` |
| Database | `mac_odoo_dist` | `stg_mac_odoo_dist` |
| Env file | `env/production/.env.mac-react-sfa` | `env/staging/.env.mac-react-sfa` |
| Auto-deploy | `false` (manual) | `true` (on push) |

## Directory Structure

### Current (flat)

```
deploys/
├── bases/
├── env/                    ← flat, no environment separation
│   ├── .env.mac-react-sfa
│   └── ...
├── instances/              ← flat, production only
│   ├── mac-react-sfa.yaml
│   └── ...
├── tenants/
├── setup/
└── generate.py
```

### Proposed (environment-scoped)

```
deploys/
├── bases/                          ← unchanged
│   ├── react-pwa.yaml
│   ├── nextjs.yaml
│   ├── odoo.yaml
│   ├── fastapi.yaml
│   └── infra.yaml
├── env/
│   ├── production/                 ← current .env files move here
│   │   ├── .env.mac-react-sfa
│   │   ├── .env.tpp-odoo-trad
│   │   └── ...
│   └── staging/                    ← staging env files (different URLs, test keys)
│       ├── .env.mac-react-sfa
│       ├── .env.tpp-odoo-trad
│       └── ...
├── instances/
│   ├── production/                 ← current manifests move here
│   │   ├── mac-react-sfa.yaml
│   │   ├── tpp-odoo-trad.yaml
│   │   ├── kod-infra-gatus.yaml
│   │   └── ...
│   └── staging/                    ← staging manifests (different server/domain/db)
│       ├── mac-react-sfa.yaml
│       ├── tpp-odoo-trad.yaml
│       └── ...  (no infra services — production only)
├── tenants/
│   ├── mac.yaml                    ← add environments block
│   └── tpp.yaml
├── setup/
│   └── mac-distribution.yaml       ← unchanged
├── generate.py                     ← updated: generates both environments
└── .gitignore                      ← updated patterns
```

## Manifest Changes

### New field: `environment`

Add an `environment` field to `DeployManifest`. The deployer uses this to find (or create) the service in the correct Dokploy environment.

```yaml
# instances/staging/mac-react-sfa.yaml
kind: instance
extends: ../../bases/react-pwa.yaml

instance:
  name: mac-react-sfa
  description: "Mandiri Agro — SFA PWA"

environment: staging              # NEW — targets Dokploy staging environment
server: mac-stg-01                # Different server
project: mac

dns:
  zone: mandiriagro.com
  name: stg-mac-sfa               # stg- prefix

domain:
  host: stg-mac-sfa.mandiriagro.com
  port: 80
  service: sfa
  https: true

env_file: ../../env/staging/.env.mac-react-sfa
```

Production manifests get `environment: production` (or omit it — production is the default).

### Staging Odoo example

```yaml
# instances/staging/mac-odoo-dist.yaml
kind: instance
extends: ../../bases/odoo.yaml

instance:
  name: mac-odoo-dist
  description: "Mandiri Agro — Distribution (staging)"

environment: staging
server: mac-stg-01
project: mac

dns:
  zone: mandiriagro.com
  name: stg-mac-odoo-dist

domain:
  host: stg-mac-odoo-dist.mandiriagro.com
  port: 8069
  service: odoo-web
  https: true
  cert: letsencrypt

database:
  name: stg_mac_odoo_dist          # stg_ prefix
  user: odoo

env_file: ../../env/staging/.env.mac-odoo-dist
env_overrides:
  COMPOSE_PROJECT_NAME: mac-odoo-dist
  PGDATABASE: stg_mac_odoo_dist
  ODOO_DB_FILTER: "^stg_mac_odoo_dist$"
  DOMAIN: stg-mac-odoo-dist.mandiriagro.com
```

### Infrastructure services

Infrastructure services (`kod-infra-*`) are **production only** — they are not generated for staging. Staging apps on `kod-prod-02` share production infrastructure (authentik, postgres, gatus, etc.) running on `kod-prod-01`.

Exception: if a staging server needs its own PostgreSQL, it gets a `kod-infra-postgres` instance in the staging manifests.

## Tenant Config Changes

```yaml
# tenants/mac.yaml
tenant:
  code: mac
  name: "Mandiri Agro"
  short_name: "MAC"
  domain: mandiriagro.com

environments:
  production:
    server: mac-prod-01
    dns_prefix: ""
    db_prefix: ""
    auto_deploy: false
  staging:
    server: mac-stg-01
    dns_prefix: "stg-"
    db_prefix: "stg_"
    auto_deploy: true

odoo:
  - profile: distribution
    short: dist
    ...
```

For tenants without the `environments` block, the generator produces only production manifests (backward compatible).

## Generator Changes (`generate.py`)

The generator loops over `environments` and produces manifests in `instances/{env}/` and env files in `env/{env}/`:

```python
for env_name, env_config in tenant.get("environments", {"production": {}}).items():
    server = env_config.get("server", base_server)
    dns_prefix = env_config.get("dns_prefix", "")
    db_prefix = env_config.get("db_prefix", "")
    
    # Generate into instances/{env_name}/ and env/{env_name}/
    for odoo_entry in raw.get("odoo", []):
        gen_odoo(tenant, odoo_entry, env_name, server, dns_prefix, db_prefix)
        for app in odoo_entry.get("apps", []):
            gen_react_pwa(tenant, odoo_entry, app, env_name, server, dns_prefix, db_prefix)
    # ... nextjs, notify, etc.
```

Key differences in staging output:
- `extends:` path uses `../../bases/` (one level deeper)
- `environment: staging` field added
- `server:` uses staging server name
- `dns.name:` gets `stg-` prefix
- `domain.host:` gets `stg-` prefix
- `database.name:` gets `stg_` prefix
- `env_file:` points to `../../env/staging/.env.{name}`
- Odoo `env_overrides` reflect staging database names and domains

## kctl-dokploy Changes

### 1. Manifest model (`core/manifest.py`)

Add `environment` field to `DeployManifest`:

```python
class DeployManifest(BaseModel):
    environment: str = "production"   # NEW
    # ... rest unchanged
```

### 2. Deployer (`core/deployer.py`) — `phase_compose()`

Currently the deployer searches all environments for a matching compose service name and creates new services in the default environment. Change to:

1. Find the Dokploy environment matching `manifest.environment` (by name, not ID)
2. Search only that environment for existing compose services
3. If creating a new service, create it in that specific environment's ID

```python
# Find target environment by name
target_env_name = self.manifest.environment or "production"
target_env_id = ""
for env in (project_data or {}).get("environments", []):
    if env.get("name", "").lower() == target_env_name.lower():
        target_env_id = env.get("environmentId", "")
        break

# Search only target environment for existing compose
for comp in target_env.get("compose", []):
    if comp.get("name") == instance_name:
        self._compose_id = comp["composeId"]
        ...

# Create in target environment
create_args = ["kctl-dokploy", "compose", "create", target_env_id, ...]
```

### 3. Auto-deploy setting

After creating or updating a compose service, set `autoDeploy` based on the environment:

- `production`: `auto_deploy: false` (manual deploy via CLI)
- `staging`: `auto_deploy: true` (auto-deploy on push to branch)

This can be controlled via the tenant config's `auto_deploy` field, passed through the manifest, or defaulted by the deployer based on environment name.

### 4. Deploy commands — environment filtering

```bash
# Deploy all production instances
kctl-dokploy deploy apply-all -d deploys/instances/production/

# Deploy all staging instances
kctl-dokploy deploy apply-all -d deploys/instances/staging/

# Deploy single service to staging
kctl-dokploy deploy apply -f deploys/instances/staging/mac-react-sfa.yaml

# Check status across environments
kctl-dokploy deploy list -d deploys/instances/production/
kctl-dokploy deploy list -d deploys/instances/staging/
```

No new CLI flags needed — the directory structure handles environment selection. The `environment` field in each manifest tells the deployer which Dokploy environment to target.

### 5. Ensure staging environments exist

The deployer should auto-create the `staging` Dokploy environment if it doesn't exist in the project. Add to `phase_compose()`:

```python
if not target_env_id:
    # Create the environment
    result = client.post("/environment.create", json={
        "projectId": project_id,
        "name": target_env_name,
        "description": f"{target_env_name} environment",
    })
    target_env_id = result.get("environmentId", "")
```

## .gitignore Update

```gitignore
# Deploy env files (.env.{tenant}-{stack}-{app})
deploys/env/production/.env.*
deploys/env/staging/.env.*
```

## Migration Plan

1. Create `instances/production/` and `instances/staging/` directories
2. Move all 34 current manifests from `instances/` to `instances/production/`
3. Update `extends:` paths in production manifests (`../bases/` → `../../bases/`)
4. Create `env/production/` and `env/staging/` directories
5. Move all current env files from `env/` to `env/production/`
6. Update `env_file:` paths in production manifests (`../env/.env.X` → `../../env/production/.env.X`)
7. Update `generate.py` with environment loop
8. Update tenant YAML files with `environments` block
9. Add `environment` field to `DeployManifest` in `core/manifest.py`
10. Update deployer `phase_compose()` to target correct environment
11. Update `.gitignore` patterns
12. Run `generate.py` to produce staging manifests
13. Create staging env files (copy from production, update URLs/keys)
14. Deploy staging services: `kctl-dokploy deploy apply-all -d deploys/instances/staging/`

## What Does NOT Change

- Base templates (`deploys/bases/`) — unchanged
- Service naming convention (`{tenant}-{stack}-{app}`) — unchanged  
- Port standards (80, 3000, 8069) — unchanged
- Branch strategy (`main` / `18.0`) — unchanged
- Setup files — unchanged
- Existing production deployments — unchanged (just moved to subdirectory)

## Risks

- **Path changes break CI** — CI workflow references `deploys/instances/` must be updated to `deploys/instances/production/`
- **Staging env files need real values** — copying from production and changing URLs is manual work per service; secrets must be rotated for staging
- **Shared infrastructure** — staging services on `kod-prod-02` need network access to production postgres on `kod-prod-01` (or their own postgres instance)
