# Deploy All React PWA Apps to KOD Tenant (Staging) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy all 13 React PWA apps (bia, dms, eam, hrm, lfa, mrp, saas, sfa, shop, tms, tms-parent, tpm, wms) to the `kod` tenant on `kod-prod-02` server as staging instances.

**Architecture:** Create a `kod.yaml` tenant definition, generate staging manifests via `generate.py`, create missing docker-compose files for the 9 apps that lack them, and create `.env` files for each app. All apps point to `kod-odoo-full.kodeme.io` as backend API. DNS pattern: `stg-kod-{app}.kodeme.io`.

**Tech Stack:** YAML manifests, Docker Compose, Vite React PWA, kctl-dokploy deploy pipeline

---

## Pre-Requisites

- `kod-prod-02` server is accessible and has Dokploy agent running
- `kod-odoo-full.kodeme.io` Odoo backend is deployed (confirmed: exists at `deploys/instances/production/kod-odoo-full.yaml`)
- Cloudflare zone `kodeme.io` is configured in kctl-cf

## File Structure

### Files to Create

| File | Responsibility |
|------|---------------|
| `deploys/tenants/kod.yaml` | KOD tenant definition with all 13 React apps |
| `kodemeio-react/compose/docker-compose.dms.yml` | DMS compose file |
| `kodemeio-react/compose/docker-compose.eam.yml` | EAM compose file |
| `kodemeio-react/compose/docker-compose.lfa.yml` | LFA compose file |
| `kodemeio-react/compose/docker-compose.mrp.yml` | MRP compose file |
| `kodemeio-react/compose/docker-compose.saas.yml` | SaaS compose file |
| `kodemeio-react/compose/docker-compose.shop.yml` | Shop compose file |
| `kodemeio-react/compose/docker-compose.tms.yml` | TMS compose file |
| `kodemeio-react/compose/docker-compose.tms-parent.yml` | TMS Parent (Terakidz Home) compose file |
| `kodemeio-react/compose/docker-compose.tpm.yml` | TPM compose file |
| 13x `deploys/instances/staging/kod-react-{app}.yaml` | Staging manifests (generated) |
| 13x `deploys/env/staging/.env.kod-react-{app}` | Staging env files (generated) |

### Existing Files (no modifications needed)

| File | Notes |
|------|-------|
| `kodemeio-react/compose/docker-compose.bia.yml` | Already exists |
| `kodemeio-react/compose/docker-compose.hrm.yml` | Already exists |
| `kodemeio-react/compose/docker-compose.sfa.yml` | Already exists |
| `kodemeio-react/compose/docker-compose.wms.yml` | Already exists |
| `deploys/bases/react-pwa.yaml` | Base template, no changes |
| `deploys/generate.py` | Generator script, no changes |

---

### Task 1: Create Missing Docker Compose Files (kodemeio-react repo)

**Files (all in `/home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-react/compose/`):**
- Create: `docker-compose.dms.yml`
- Create: `docker-compose.eam.yml`
- Create: `docker-compose.lfa.yml`
- Create: `docker-compose.mrp.yml`
- Create: `docker-compose.saas.yml`
- Create: `docker-compose.shop.yml`
- Create: `docker-compose.tms.yml`
- Create: `docker-compose.tms-parent.yml`
- Create: `docker-compose.tpm.yml`

All compose files follow the identical pattern as existing ones (e.g., `docker-compose.sfa.yml`). The only differences are `APP_NAME`, service name, and env var prefix (`VITE_{APP}_*`).

- [ ] **Step 1: Create docker-compose.dms.yml**

```yaml
# =============================================================================
# Kodemeio DMS — Distribution Management System
# =============================================================================
services:
  dms:
    build:
      context: ..
      dockerfile: Dockerfile
      args:
        APP_NAME: dms
        NGINX_CONF: ${NGINX_CONF:-nginx.conf}
        VITE_APP_NAME: ${VITE_DMS_APP_NAME}
        VITE_API_BASE_URL: ${VITE_DMS_API_BASE_URL}
        VITE_APP_THEME: ${VITE_DMS_THEME}
        VITE_AUTH_MODE: ${VITE_AUTH_MODE:-oidc}
        VITE_OIDC_AUTHORITY: ${VITE_OIDC_AUTHORITY}
        VITE_OIDC_CLIENT_ID: ${VITE_DMS_OIDC_CLIENT_ID}
        VITE_OIDC_REDIRECT_URI: ${VITE_DMS_OIDC_REDIRECT_URI}
        VITE_SENTRY_DSN: ${VITE_DMS_SENTRY_DSN:-}
        VITE_NOTIFY_SSE_URL: ${VITE_NOTIFY_SSE_URL:-}
        VITE_FCM_VAPID_KEY: ${VITE_FCM_VAPID_KEY:-}
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: '${SPA_CPU_LIMIT:-0.5}'
          memory: ${SPA_MEMORY_LIMIT:-256M}
        reservations:
          cpus: '0.1'
          memory: 64M
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://127.0.0.1/health"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s
```

- [ ] **Step 2: Create docker-compose.eam.yml**

Same pattern, replace `dms`→`eam`, `DMS`→`EAM`. Service name: `eam`. Comment: `Kodemeio EAM — Enterprise Asset Management`.

- [ ] **Step 3: Create docker-compose.lfa.yml**

Same pattern, replace with `lfa`/`LFA`. Comment: `Kodemeio LFA — Logistics & Fleet Automation`.

- [ ] **Step 4: Create docker-compose.mrp.yml**

Same pattern, replace with `mrp`/`MRP`. Comment: `Kodemeio MRP — Manufacturing Resource Planning`.

- [ ] **Step 5: Create docker-compose.saas.yml**

Same pattern, replace with `saas`/`SAAS`. Comment: `Kodemeio SaaS — Multi-tenant SaaS Portal`.

- [ ] **Step 6: Create docker-compose.shop.yml**

Same pattern, replace with `shop`/`SHOP`. Comment: `Kodemeio Shop — E-Commerce Storefront`.

- [ ] **Step 7: Create docker-compose.tms.yml**

Same pattern, replace with `tms`/`TMS`. Comment: `Kodemeio TMS — Transportation Management System`.

- [ ] **Step 8: Create docker-compose.tms-parent.yml**

Same pattern but service name is `tms-parent`, env prefix is `TMS_PARENT`, APP_NAME is `tms-parent`. Comment: `Kodemeio TMS Parent — Terakidz Home`.

- [ ] **Step 9: Create docker-compose.tpm.yml**

Same pattern, replace with `tpm`/`TPM`. Comment: `Kodemeio TPM — Total Productive Maintenance`.

- [ ] **Step 10: Commit compose files**

```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-react
git add compose/docker-compose.dms.yml compose/docker-compose.eam.yml compose/docker-compose.lfa.yml compose/docker-compose.mrp.yml compose/docker-compose.saas.yml compose/docker-compose.shop.yml compose/docker-compose.tms.yml compose/docker-compose.tms-parent.yml compose/docker-compose.tpm.yml
git commit -m "feat: add docker-compose files for 9 new React PWA apps (dms, eam, lfa, mrp, saas, shop, tms, tms-parent, tpm)"
```

---

### Task 2: Create KOD Tenant Definition

**Files:**
- Create: `deploys/tenants/kod.yaml`

The KOD tenant uses `kodeme.io` domain and maps all 13 React apps to a single `kod-odoo-full` Odoo backend.

- [ ] **Step 1: Create kod.yaml tenant file**

```yaml
tenant:
  code: kod
  name: "Kodemeio"
  short_name: "KOD"
  domain: kodeme.io

environments:
  staging:
    server: kod-prod-02
    dns_prefix: "stg-"
    db_prefix: "stg_"
    auto_deploy: true

odoo:
  - profile: full
    short: full
    description: "Full Odoo (all modules, all PWA apps)"
    workers: 6
    apps: [bia, dms, eam, hrm, lfa, mrp, saas, sfa, shop, tms, tms-parent, tpm, wms]
```

Note: Only `staging` environment is defined — production `kod-odoo-full` and `kod-infra-*` already exist as hand-crafted manifests.

- [ ] **Step 2: Validate YAML syntax**

Run: `python3 -c "import yaml; yaml.safe_load(open('deploys/tenants/kod.yaml'))"`

Expected: No output (valid YAML)

- [ ] **Step 3: Commit**

```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform
git add deploys/tenants/kod.yaml
git commit -m "feat(deploy): add kod tenant definition for staging React PWA deployment"
```

---

### Task 3: Generate Staging Manifests and Env Files

**Files (auto-generated by `generate.py`):**
- Create: `deploys/instances/staging/kod-react-bia.yaml`
- Create: `deploys/instances/staging/kod-react-dms.yaml`
- Create: `deploys/instances/staging/kod-react-eam.yaml`
- Create: `deploys/instances/staging/kod-react-hrm.yaml`
- Create: `deploys/instances/staging/kod-react-lfa.yaml`
- Create: `deploys/instances/staging/kod-react-mrp.yaml`
- Create: `deploys/instances/staging/kod-react-saas.yaml`
- Create: `deploys/instances/staging/kod-react-sfa.yaml`
- Create: `deploys/instances/staging/kod-react-shop.yaml`
- Create: `deploys/instances/staging/kod-react-tms.yaml`
- Create: `deploys/instances/staging/kod-react-tms-parent.yaml`
- Create: `deploys/instances/staging/kod-react-tpm.yaml`
- Create: `deploys/instances/staging/kod-react-wms.yaml`
- Create: 13x `deploys/env/staging/.env.kod-react-{app}`

- [ ] **Step 1: Dry-run the generator to preview output**

```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform/deploys
python generate.py --tenant kod --dry-run
```

Expected: List of 13 staging manifest files + 13 env files + 1 odoo manifest (kod-odoo-full staging) to be generated. Verify filenames follow `kod-react-{app}.yaml` pattern.

- [ ] **Step 2: Check diff before generating**

```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform/deploys
python generate.py --tenant kod --diff
```

Expected: Shows all new files since none exist yet.

- [ ] **Step 3: Generate the manifests**

```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform/deploys
python generate.py --tenant kod
```

Expected: Creates files under `deploys/instances/staging/` and `deploys/env/staging/`.

- [ ] **Step 4: Verify generated manifests**

```bash
ls deploys/instances/staging/kod-react-*.yaml | wc -l
```

Expected: `13`

- [ ] **Step 5: Verify a sample manifest (kod-react-sfa.yaml)**

```bash
cat deploys/instances/staging/kod-react-sfa.yaml
```

Expected structure:
```yaml
kind: instance
extends: ../../bases/react-pwa.yaml
instance:
  name: kod-react-sfa
  description: KOD — SFA PWA
project: kod
environment: staging
server: kod-prod-02
source_overrides:
  compose_path: compose/docker-compose.sfa.yml
dns:
  zone: kodeme.io
  name: stg-kod-sfa
domain:
  host: stg-kod-sfa.kodeme.io
  port: 80
  service: sfa
  https: true
env_file: ../../env/staging/.env.kod-react-sfa
env_overrides:
  VITE_SFA_APP_NAME: KOD SFA
  VITE_SFA_API_BASE_URL: https://stg-kod-odoo-full.kodeme.io/sfa/api
  VITE_AUTH_MODE: native
  VITE_SFA_OIDC_CLIENT_ID: ''
  VITE_SFA_OIDC_REDIRECT_URI: ''
```

- [ ] **Step 6: Handle tms-parent special case**

Check `kod-react-tms-parent.yaml` — the compose_path should be `compose/docker-compose.tms-parent.yml` and env prefix should use `TMS_PARENT`. If the generator doesn't handle hyphens in app names properly, manually fix.

```bash
cat deploys/instances/staging/kod-react-tms-parent.yaml
```

If env var prefix is `VITE_TMS-PARENT_*` (invalid), manually fix to `VITE_TMS_PARENT_*` or adjust the generator.

- [ ] **Step 7: Verify env files exist**

```bash
ls deploys/env/staging/.env.kod-react-* | wc -l
```

Expected: `13`

- [ ] **Step 8: Remove the auto-generated staging Odoo manifest (if created)**

The generator may also create `kod-odoo-full` staging manifest. If it does, check if it conflicts with the existing production `kod-odoo-full.yaml` and decide whether to keep it.

```bash
ls deploys/instances/staging/kod-odoo-*.yaml 2>/dev/null
```

If a staging Odoo manifest was created and is not wanted, remove it.

- [ ] **Step 9: Commit generated files**

```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform
git add deploys/instances/staging/kod-react-*.yaml
git add deploys/env/staging/.env.kod-react-*
git commit -m "feat(deploy): add 13 kod-react staging manifests for kod-prod-02"
```

---

### Task 4: Deploy All React Apps via kctl-dokploy

**No files to create/modify — this is an operational deployment task.**

- [ ] **Step 1: Run preflight checks on all manifests**

```bash
kctl-dokploy deploy preflight-all -d deploys/instances/staging/ --server kod-prod-02
```

Expected: All 13 kod-react manifests pass preflight gates. Fix any failures before proceeding.

- [ ] **Step 2: Deploy all staging apps in batch**

```bash
kctl-dokploy deploy apply-all -d deploys/instances/staging/ --filter "kod-react-*"
```

If `--filter` is not supported, deploy individually in this order (smallest first for quick validation):

```bash
kctl-dokploy deploy apply -f deploys/instances/staging/kod-react-sfa.yaml
```

Verify the first one works before batch deploying the rest.

- [ ] **Step 3: Deploy remaining apps**

```bash
for app in bia dms eam hrm lfa mrp saas shop tms tms-parent tpm wms; do
  echo "=== Deploying kod-react-$app ==="
  kctl-dokploy deploy apply -f deploys/instances/staging/kod-react-$app.yaml
done
```

- [ ] **Step 4: Verify all apps are healthy**

```bash
for app in bia dms eam hrm lfa mrp saas sfa shop tms tms-parent tpm wms; do
  echo "=== $app ==="
  curl -s -o /dev/null -w "%{http_code}" https://stg-kod-$app.kodeme.io/
done
```

Expected: All return `200`.

- [ ] **Step 5: Commit any env file updates (if deployer modified them)**

Check for unstaged changes and commit if needed.

---

## Summary Table

| App | Compose File | Manifest | DNS (staging) | Backend API |
|-----|-------------|----------|---------------|-------------|
| bia | EXISTS | kod-react-bia.yaml | stg-kod-bia.kodeme.io | stg-kod-odoo-full.kodeme.io/bia/api |
| dms | CREATE | kod-react-dms.yaml | stg-kod-dms.kodeme.io | stg-kod-odoo-full.kodeme.io/dms/api |
| eam | CREATE | kod-react-eam.yaml | stg-kod-eam.kodeme.io | stg-kod-odoo-full.kodeme.io/eam/api |
| hrm | EXISTS | kod-react-hrm.yaml | stg-kod-hrm.kodeme.io | stg-kod-odoo-full.kodeme.io/hrm/api |
| lfa | CREATE | kod-react-lfa.yaml | stg-kod-lfa.kodeme.io | stg-kod-odoo-full.kodeme.io/lfa/api |
| mrp | CREATE | kod-react-mrp.yaml | stg-kod-mrp.kodeme.io | stg-kod-odoo-full.kodeme.io/mrp/api |
| saas | CREATE | kod-react-saas.yaml | stg-kod-saas.kodeme.io | stg-kod-odoo-full.kodeme.io/saas/api |
| sfa | EXISTS | kod-react-sfa.yaml | stg-kod-sfa.kodeme.io | stg-kod-odoo-full.kodeme.io/sfa/api |
| shop | CREATE | kod-react-shop.yaml | stg-kod-shop.kodeme.io | stg-kod-odoo-full.kodeme.io/shop/api |
| tms | CREATE | kod-react-tms.yaml | stg-kod-tms.kodeme.io | stg-kod-odoo-full.kodeme.io/tms/api |
| tms-parent | CREATE | kod-react-tms-parent.yaml | stg-kod-tms-parent.kodeme.io | stg-kod-odoo-full.kodeme.io/tms-parent/api |
| tpm | CREATE | kod-react-tpm.yaml | stg-kod-tpm.kodeme.io | stg-kod-odoo-full.kodeme.io/tpm/api |
| wms | EXISTS | kod-react-wms.yaml | stg-kod-wms.kodeme.io | stg-kod-odoo-full.kodeme.io/wms/api |

## Risks & Notes

1. **tms-parent hyphen in app name** — The generator uses `app.upper()` for env var prefix. `tms-parent` → `TMS-PARENT` which is invalid in env vars. May need to handle this edge case in `generate.py` or override manually.
2. **Backend API readiness** — All apps point to `stg-kod-odoo-full.kodeme.io` which doesn't exist yet (only production `kod-odoo-full.kodeme.io` exists). The generator will create a staging Odoo manifest too, but it would need to be deployed first for the React apps to work.
3. **9 new compose files** — Need to be committed to `kodemeio-react` repo and pushed before Dokploy can build from GitHub source.
4. **Resource limits** — 13 apps x 256MB = ~3.3GB RAM on kod-prod-02. Verify server has capacity.
