# Incident Response

> Last verified: 2026-04-03 | Owner: Platform team

A general template for handling incidents on the Kodemeio platform. Use this when you don't yet know the root cause and need a structured triage process.

Severity levels:
- **P1** — Production down for paying customers. Drop everything.
- **P2** — Degraded service or partial outage. Resolve within 2 hours.
- **P3** — Non-critical service down or performance issue. Resolve within 24 hours.

## Detection

Common alert sources:

- **Gatus** — Health check failure notifications
- **GlitchTip** — Error spike beyond baseline (`kctl-dokploy services logs -s kodemeio-glitchtip --tail 20`)
- **Telegram ops channel** — Alert forwarded from monitoring
- **User report** — Customer contacts support directly

When you receive an alert:

```bash
# First: establish what is currently failing
kctl-grafana dashboard list

# Check overall service health
kctl-dokploy services list
```

## Triage

### Step 1: Identify the root service

Most outages originate from Layer 0 or Layer 1. Check the [service dependency map](../../docs/service-map.md) — walk the graph backward from the failing service.

```bash
# Is PostgreSQL up? (Layer 0 — causes cascade failures if down)
kctl-pg health

# Is Authentik up? (Layer 0 — all SSO logins fail if down)
kctl-ak health

# Is Traefik routing traffic? (Layer 0 — all HTTPS fails if down)
kctl-dokploy services status -s traefik

# Check the specific failing service logs
kctl-dokploy services logs -s <service-name> --tail 100
```

### Step 2: Assess blast radius

```bash
# List all services and their status
kctl-dokploy services list

# Check error rates
kctl-sentry projects list
kctl-sentry issues list --project <project> --unresolved --limit 20
```

Blast radius guide:
- PostgreSQL down → Odoo (all 6), Authentik, GlitchTip, Grafana, Mailcow all fail
- Authentik down → All OIDC logins fail; apps with native auth still work
- Traefik down → All public HTTPS access fails; Dokploy may still be reachable on port 3000
- Single Odoo instance down → Isolated to that customer's domain

### Step 3: Classify and route

| Root cause | Runbook |
|------------|---------|
| PostgreSQL | [db-recovery.md](db-recovery.md) |
| Authentik / SSO | [authentik-recovery.md](authentik-recovery.md) |
| TLS / SSL cert | [ssl-renewal.md](ssl-renewal.md) |
| Odoo deployment | [odoo-upgrade.md](odoo-upgrade.md) |
| Full server / hardware | [server-migration.md](server-migration.md) |

## Communication

Notify the ops channel immediately when you have a P1 or P2:

```bash
# Initial notification (send within 5 minutes of detection)
kctl-telegram send --chat ops "INCIDENT P1: <one-line description>. Investigating. ETA unknown."

# Update every 15 minutes while working
kctl-telegram send --chat ops "UPDATE: Root cause identified as <X>. Applying fix. ETA <time>."

# Resolution notification
kctl-telegram send --chat ops "RESOLVED: <short description of fix>. All services verified healthy. Duration: <X> minutes."
```

For P1 incidents affecting paying customers, also notify via email or the appropriate support channel.

Template for customer-facing communication (neutral language, no technical details):

```
Subject: Service disruption — [service name]

We are aware of an issue affecting [service] and are actively working to resolve it.
All other services are unaffected.
We will provide an update at [time].
```

## Resolution

Once you have identified the root cause, follow the appropriate runbook. Common quick wins:

```bash
# Service crashed: restart it
kctl-dokploy services restart -s <service-name>

# Container in bad state: full redeploy
kctl-dokploy deploy run -f deploys/instances/<manifest>.yaml

# Config drift: re-apply manifest
kctl-dokploy deploy apply -f deploys/instances/<manifest>.yaml

# Check if a recent deploy caused the issue
git log --oneline deploys/instances/<manifest>.yaml
```

## Post-Mortem

Every P1 and P2 incident requires a post-mortem document. Create it within 24 hours of resolution.

```bash
# Create incident document
# File naming: YYYY-MM-DD-short-description.md
touch ops/runbooks/incidents/$(date +%Y-%m-%d)-<short-description>.md
```

Post-mortem template:

```markdown
# Incident: <title>

**Date:** YYYY-MM-DD
**Severity:** P1 / P2
**Duration:** X minutes
**Services affected:** <list>

## Timeline

| Time (UTC) | Event |
|------------|-------|
| HH:MM | Alert triggered |
| HH:MM | Investigation started |
| HH:MM | Root cause identified |
| HH:MM | Fix applied |
| HH:MM | Services restored |

## Root Cause

<Technical description of what failed and why>

## Impact

- Services affected: <list>
- Customers affected: <count or description>
- Data loss: None / <description>

## Resolution

<What was done to fix it>

## Action Items

- [ ] <Preventive measure 1>
- [ ] <Monitoring improvement>
- [ ] <Runbook update>
```

## Verification

After any incident, confirm recovery is complete:

```bash
# All services healthy
kctl-grafana dashboard list

# No elevated error rates
kctl-sentry issues list --project <project> --unresolved --limit 10

# PostgreSQL connections normal
kctl-pg stats connections

# Authentik logins working
kctl-ak audit logins --limit 5

# Spot check the most critical service (Odoo production)
kctl-odoo health
```

Send resolution notification to ops channel (see Communication section above).

## Escalation

- If root cause is unclear after 30 minutes of investigation: engage a second person
- If data loss is suspected: stop the service immediately and do not attempt fix alone — get a second opinion before proceeding
- If Hetzner infrastructure is involved (hardware failure, network issue): open a Hetzner support ticket at console.hetzner.cloud
- Hetzner status: https://www.hetzner.com/status
- Let's Encrypt status: https://letsencrypt.status.io/
- Cloudflare status: https://www.cloudflarestatus.com/
