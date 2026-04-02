# Kodemeio Platform Runbooks

> Last verified: 2026-04-03 | Owner: Platform team

Operational runbooks for the Kodemeio platform. All services run on **kodeme-service** (49.13.14.79, 16GB RAM) via Dokploy + Docker Compose + Traefik. PostgreSQL 16 is on the private network at **10.0.0.3:5432**.

All management uses `kctl-*` CLI tools. Never use raw curl or direct API calls — see [infrastructure rules](../CLAUDE.md).

## Service Layers

| Layer | Services |
|-------|----------|
| 0 - Foundation | PostgreSQL 16, Authentik SSO, Traefik, Dokploy |
| 1 - Core | Gatus, GlitchTip, Grafana, Mailcow |
| 2 - Business Apps | Odoo (6 instances), FastAPI |
| 3 - Websites | 5 Next.js sites (kodeme.io, mandiriagro.com, pakerti.com, terakidz.com, trigunawan.com) |
| 4 - Utilities | WAHA, RustDesk, Tactical RMM, Immich |

For full dependency graph see [docs/service-map.md](../docs/service-map.md). When a service fails, walk the graph backward to find the root cause — most outages trace to PostgreSQL or Authentik.

## Runbooks

| Runbook | When to use |
|---------|-------------|
| [db-recovery.md](db-recovery.md) | Services returning 500s, DB connection refused, PostgreSQL container down |
| [authentik-recovery.md](authentik-recovery.md) | OIDC logins failing, 502 on auth.kodeme.io, all apps showing auth errors |
| [ssl-renewal.md](ssl-renewal.md) | Browser SSL warnings, HTTPS connection refused, Let's Encrypt failures |
| [odoo-upgrade.md](odoo-upgrade.md) | Deploying a new Odoo image, module updates, post-deploy verification |
| [server-migration.md](server-migration.md) | Moving to a new Hetzner server, hardware replacement, datacenter migration |
| [incident-response.md](incident-response.md) | General incident triage, blast-radius assessment, communication template |

## Incidents Archive

Past incidents are documented in [incidents/](incidents/). Filename convention: `YYYY-MM-DD-short-description.md`.

## Quick Reference

```bash
# Are services healthy?
kctl-gatus dashboard

# Check a specific service
kctl-dokploy services logs -s <service-name> --tail 50

# PostgreSQL health
kctl-pg health
kctl-pg stats connections

# Authentik status
kctl-ak health
kctl-ak audit logins --failed --limit 20

# SSL check
kctl-cf ssl check --domain kodeme.io

# Send incident notification
kctl-telegram send --chat ops "Incident: <description>"
```
