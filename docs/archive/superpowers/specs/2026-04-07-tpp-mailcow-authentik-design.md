# TPP Mailcow & Authentik Setup — Design Spec

> **Date:** 2026-04-07
> **Server:** tpp-prod-01 (178.104.127.104, cpx42, 8 vCPU / 16GB RAM)
> **Dokploy:** dokploy.idtpp.com (profile: idtpp)
> **Tenant:** tpp (domain: idtpp.com)

## Goal

Deploy two infrastructure services on `tpp-prod-01`:

1. **Authentik** — SSO/Identity Provider at `auth.idtpp.com`
2. **Mailcow** — Mail server at `mail.idtpp.com` for `idtpp.com` domain

Both are independent instances (not federated with kodemeio). Both reuse existing repos (`kodemeio-authentik`, `kodemeio-mailcow`) with separate environment files.

## Approach

Sequential deploy via Dokploy manifests on the existing `tpp-prod-01` server. Follows the same pattern as `kod-infra-authentik` and `kod-infra-mailcow` on the kodemeio infrastructure.

## DNS Records

Zone: `idtpp.com` (Cloudflare)

| Type | Name | Content | Proxied | Purpose |
|------|------|---------|---------|---------|
| A | `auth` | 178.104.127.104 | Yes | Authentik web UI |
| A | `mail` | 178.104.127.104 | **No** | Mailcow web UI + MX target |
| MX | `@` | `mail.idtpp.com` (priority 10) | — | Mail delivery |
| TXT | `@` | `v=spf1 a mx ip4:178.104.127.104 ~all` | — | SPF |
| TXT | `_dmarc` | `v=DMARC1; p=quarantine; rua=mailto:postmaster@idtpp.com` | — | DMARC |
| CNAME | `autodiscover` | `mail.idtpp.com` | No | Outlook autodiscovery |
| CNAME | `autoconfig` | `mail.idtpp.com` | No | Thunderbird autoconfig |
| TXT | `dkim._domainkey` | *(added after Mailcow generates key)* | — | DKIM |

**Reverse DNS** (Hetzner): PTR for `178.104.127.104` → `mail.idtpp.com`

Note: `mail` A record must NOT be Cloudflare-proxied (breaks SMTP).

## Firewall

Hetzner firewall `tpp-firewall-prod-01` already has all required ports open:

| Port | Protocol | Purpose |
|------|----------|---------|
| 22 | TCP | SSH |
| 443 | TCP | HTTPS (Traefik) |
| 25 | TCP | SMTP |
| 465 | TCP | SMTPS |
| 587 | TCP | Submission |
| 993 | TCP | IMAPS |
| 4190 | TCP | Sieve |

**Blocker:** Hetzner network-level SMTP block must be lifted before Mailcow can send/receive email. Support request submitted 2026-04-07.

## Authentik Instance

**Manifest:** `deploys/instances/production/tpp-infra-authentik.yaml`

```yaml
kind: instance
extends: ../../bases/infra.yaml

instance:
  name: tpp-infra-authentik
  description: "TPP Authentik SSO/Identity Provider"

project: tpp
environment: production
server: tpp-prod-01

source_overrides:
  repo: kodemeio-authentik
  compose_path: ./docker-compose.prod.yml

dns:
  zone: idtpp.com
  name: auth

domain:
  host: auth.idtpp.com
  port: 9000
  service: server
  https: true
  cert: letsencrypt

env_file: ../../env/production/.env.tpp-infra-authentik

env_overrides:
  AUTHENTIK_POSTGRESQL__HOST: postgresql
  AUTHENTIK_POSTGRESQL__NAME: authentik
  AUTHENTIK_POSTGRESQL__USER: authentik
  COMPOSE_PROJECT_NAME: tpp-infra-authentik
  TZ: Asia/Jakarta
```

### Architecture

- PostgreSQL + Redis bundled inside the compose (self-contained, not using tpp-infra-postgres)
- Web UI at `https://auth.idtpp.com` (Traefik reverse proxy, port 9000)
- Initial admin bootstrap via `akadmin` on first run

### Environment File

`.env.tpp-infra-authentik` requires:
- `AUTHENTIK_SECRET_KEY` — random 50+ char secret
- `AUTHENTIK_POSTGRESQL__PASSWORD` — database password
- `AUTHENTIK_ERROR_REPORTING__ENABLED` — `false`
- `PG_PASS` — same as AUTHENTIK_POSTGRESQL__PASSWORD (for bundled postgres)

## Mailcow Instance

**Manifest:** `deploys/instances/production/tpp-infra-mailcow.yaml`

```yaml
kind: instance
extends: ../../bases/infra.yaml

instance:
  name: tpp-infra-mailcow
  description: "TPP Mailcow mail server"

project: tpp
environment: production
server: tpp-prod-01

source_overrides:
  repo: kodemeio-mailcow
  branch: "master"

dns:
  zone: idtpp.com
  name: mail

domain:
  host: mail.idtpp.com
  port: 8080
  service: nginx-mailcow
  https: true
  cert: letsencrypt

env_file: ../../env/production/.env.tpp-infra-mailcow

env_overrides:
  MAILCOW_HOSTNAME: mail.idtpp.com
  COMPOSE_PROJECT_NAME: tpp-infra-mailcow
  TZ: Asia/Jakarta
```

### Architecture

- Reuses `kodemeio-mailcow` repo (same compose as kod-infra-mailcow)
- Traefik handles HTTPS for web UI (port 8080)
- Mail ports (25, 465, 587, 993, 4190) exposed directly via Docker, bypassing Traefik
- Fully self-contained: bundles MariaDB, Redis, Solr, ClamAV, Rspamd
- Mail domain: `idtpp.com`

### Environment File

`.env.tpp-infra-mailcow` requires:
- `MAILCOW_HOSTNAME` — `mail.idtpp.com`
- `DBNAME` — mailcow database name
- `DBUSER` — mailcow database user
- `DBPASS` — mailcow database password
- `DBROOT` — MariaDB root password

### Post-Deploy Manual Steps

1. Log in to `https://mail.idtpp.com` (default: admin / moohoo)
2. Change admin password immediately
3. Add `idtpp.com` as mail domain
4. Copy generated DKIM key → add as TXT record in Cloudflare
5. Create mailboxes as needed

## Deployment Order

| Step | Action | Tool | Depends On |
|------|--------|------|------------|
| 1 | Create DNS records (auth, mail, MX, SPF, DMARC, autodiscover, autoconfig) | kctl-cf | — |
| 2 | Set PTR record 178.104.127.104 → mail.idtpp.com | kctl-hz | — |
| 3 | Create .env.tpp-infra-authentik | manual | — |
| 4 | Deploy Authentik | kctl-dokploy deploy apply | Steps 1, 3 |
| 5 | Verify Authentik at https://auth.idtpp.com | healthcheck | Step 4 |
| 6 | Create .env.tpp-infra-mailcow | manual | — |
| 7 | Deploy Mailcow (after Hetzner unblocks SMTP) | kctl-dokploy deploy apply | Steps 1, 2, 6, Hetzner approval |
| 8 | Verify Mailcow web UI at https://mail.idtpp.com | healthcheck | Step 7 |
| 9 | Add idtpp.com domain in Mailcow admin | manual | Step 8 |
| 10 | Copy DKIM TXT record to Cloudflare | kctl-cf | Step 9 |
| 11 | Test email send/receive | manual | Step 10 |

## Resource Estimate

| Service | RAM (approx) | Notes |
|---------|-------------|-------|
| Authentik (server + worker + postgres + redis) | ~1.5 GB | |
| Mailcow (postfix + dovecot + mariadb + redis + solr + clamav + rspamd + nginx) | ~3-4 GB | ClamAV is the heaviest |
| Existing TPP services | ~4-5 GB | Odoo, React apps, PostgreSQL, etc. |
| **Total estimated** | **~9-10.5 GB** | cpx42 has 16 GB |

Sufficient headroom on the cpx42 instance.

## Files Created/Modified

| File | Action |
|------|--------|
| `deploys/instances/production/tpp-infra-authentik.yaml` | Create |
| `deploys/instances/production/tpp-infra-mailcow.yaml` | Create |
| `deploys/env/production/.env.tpp-infra-authentik` | Create (gitignored) |
| `deploys/env/production/.env.tpp-infra-mailcow` | Create (gitignored) |
