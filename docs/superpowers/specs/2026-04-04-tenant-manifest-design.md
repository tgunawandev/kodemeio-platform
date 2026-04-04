# Tenant Manifest System

**Date:** 2026-04-04
**Status:** Approved
**Goal:** Single-file tenant definitions that generate all deploy instance YAMLs + env files, enabling easy onboarding of new companies.

## Problem

Onboarding a new company (e.g., MAC, TPP) requires creating ~8-10 instance YAML files + matching .env files in `deploys/`. Each file follows a mechanical pattern where only domain, tenant code, app name, and Odoo URL differ. This is error-prone and tedious.

## Solution

Add a `tenants/` directory with one YAML per company + a Python generator script that produces all instance/env files.

### Directory Structure

```
deploys/
  bases/          # UNCHANGED (5 files)
  tenants/        # NEW — 1 file per company (source of truth)
    mac.yaml
    tpp.yaml
  instances/      # NOW GENERATED for tenant instances, hand-written for bespoke
  env/            # NOW GENERATED for safe envs, hand-written for secrets
  generate.py     # NEW — reads tenants/ + bases/, writes instances/ + env/
```

### Tenant Schema

```yaml
tenant:
  code: mac                    # short code, used in instance names
  name: "Mandiri Agro"        # display name
  domain: mandiriagro.com     # primary domain

odoo:
  - profile: distribution     # full profile name
    short: dist               # used in instance/DB names
    description: "Supply chain, warehouse, logistics"
    workers: 4
    apps: [bia, wms]          # React PWAs connecting to this Odoo
  - profile: hrms
    short: hrms
    description: "HR, attendance, payroll"
    workers: 2
    apps: [hrm]

web:
  corporate:
    compose_brand: mandiriagro  # → compose/docker-compose.mandiriagro.yml
  careers: true                 # → compose/docker-compose.prod.careers.yml

services:
  notify: true
```

### Derivation Rules

**React PWA** (per app in `odoo[].apps`):

| Field | Template |
|---|---|
| File | `{domain}-react-{app}.yaml` |
| instance.name | `react-{app}-{code}` |
| description | `"{name} — {APP} PWA"` |
| dns.zone | `{domain}` |
| dns.name | `{app}-{code}` |
| domain.host | `{app}-{code}.{domain}` |
| domain.port | `80` |
| domain.service | `{app}` |
| compose_path | `compose/docker-compose.{app}.yml` |
| VITE_{APP}_APP_NAME | `"{name} {APP}"` |
| VITE_{APP}_API_BASE_URL | `"https://odoo-{short}-{code}.{domain}/{app}/api"` |
| VITE_AUTH_MODE | `"native"` |
| VITE_{APP}_OIDC_CLIENT_ID | `""` |
| VITE_{APP}_OIDC_REDIRECT_URI | `""` |

**Odoo** (per entry in `odoo[]`):

| Field | Template |
|---|---|
| File | `{domain}-odoo-{short}.yaml` |
| instance.name | `odoo-{short}-{code}` |
| description | `"{name} — {description}"` |
| dns.zone | `{domain}` |
| dns.name | `odoo-{short}-{code}` |
| domain.host | `odoo-{short}-{code}.{domain}` |
| domain.port | `8069` |
| domain.service | `odoo-web` |
| database.name | `odoo_{short}_{code}` |
| database.user | `odoo` |
| COMPOSE_PROJECT_NAME | `odoo-{short}-{code}` |
| TENANT | `{code}` |
| PGDATABASE | `odoo_{short}_{code}` |
| ODOO_DB_FILTER | `"^odoo_{short}_{code}$"` |
| DOMAIN | `odoo-{short}-{code}.{domain}` |
| ODOO_WORKERS | `"{workers}"` |
| post_deploy.odoo_profile | `profile-{profile}` |

**Next.js corporate** (from `web.corporate`):

| Field | Template |
|---|---|
| File | `{domain}-nextjs-web.yaml` |
| instance.name | `web-{code}` |
| description | `"{name} company website"` |
| dns.zone | `{domain}` |
| dns.name | `"@"` |
| domain.host | `{domain}` |
| domain.port | `3000` |
| domain.service | `{compose_brand}-web` |
| compose_path | `compose/docker-compose.{compose_brand}.yml` |

**Next.js careers** (from `web.careers`):

| Field | Template |
|---|---|
| File | `{domain}-nextjs-careers.yaml` |
| instance.name | `careers-{code}` |
| description | `"{name} — Careers Portal (recruitment)"` |
| dns.zone | `{domain}` |
| dns.name | `careers-{code}` |
| domain.host | `careers-{code}.{domain}` |
| domain.port | `4002` |
| domain.service | `careers` |
| compose_path | `compose/docker-compose.prod.careers.yml` |
| NEXT_PUBLIC_SITE_URL | `"https://careers-{code}.{domain}"` |
| API_URL | `"https://odoo-hrms-{code}.{domain}"` |

**Notify** (from `services.notify`):

| Field | Template |
|---|---|
| File | `{domain}-hono-notify.yaml` |
| instance.name | `notify-{code}` |
| description | `"Notification dispatch service (FCM push + SSE real-time + Telegram)"` |
| dns.zone | `{domain}` |
| dns.name | `notify-{code}` |
| domain.host | `notify-{code}.{domain}` |
| domain.port | `3020` |
| domain.service | `notify` |
| source | kodemeio-react, `apps/api/notify/docker-compose.yml` |

### Env File Handling

| Type | Secrets? | Generated? |
|---|---|---|
| React PWA `.env` | No | Fully generated |
| Next.js `.env` | No | Fully generated |
| Odoo `.env` | Yes (PGPASSWORD, ODOO_ADMIN_PASSWD, SMTP_PASSWORD) | `.env.example` only |
| Notify `.env` | Yes (DB_PASSWORD, JWT_SECRET) | `.env.example` only |

### Generator CLI

```bash
python generate.py                    # Generate all tenants
python generate.py --tenant mac       # Generate single tenant
python generate.py --dry-run          # Preview without writing
python generate.py --diff             # Show diff vs existing files
```

### Safety

- Generated files get `# GENERATED FROM tenants/{code}.yaml — DO NOT EDIT` header
- Never overwrites `.env` files containing secrets — only `.env.example`
- `--dry-run` flag for preview
- Bespoke instances (kodeme.io infra, terakidz, provetics, trigunawan, kidneuro) are never touched

### Bespoke Instances (Not Managed by Generator)

These stay hand-written in `instances/`:
- `kodeme.io-infra-*` (authentik, postgres, gatus, glitchtip, mailcow, rmm, rustdesk, waha)
- `kodeme.io-odoo-*` (full, hrms)
- `kodeme.io-nextjs-web`
- `terakidz.com-*` (nextjs-web, fastapi-api-tms)
- `provetics.com-nextjs-web`
- `trigunawan.com-nextjs-web`
- `kidneuro.io-infra-immich`

### Implementation

Single file: `deploys/generate.py` — pure Python, no dependencies beyond PyYAML (already available). Reads tenant YAML, applies templates, writes output. ~200-300 lines.
