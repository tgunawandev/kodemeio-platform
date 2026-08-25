# TPP Mailcow & Authentik Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy Authentik SSO (auth.idtpp.com) and Mailcow mail server (mail.idtpp.com) on tpp-prod-01 via Dokploy manifests.

**Architecture:** Sequential deploy using existing repos (kodemeio-authentik, kodemeio-mailcow) with TPP-specific env files. Authentik deploys first (no external blockers), Mailcow deploys after Hetzner lifts SMTP block.

**Tech Stack:** Dokploy, Cloudflare DNS, Hetzner Cloud, Authentik 2026.2.1, Mailcow

**Spec:** `docs/superpowers/specs/2026-04-07-tpp-mailcow-authentik-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `deploys/instances/production/tpp-infra-authentik.yaml` | Create | Authentik deploy manifest |
| `deploys/instances/production/tpp-infra-mailcow.yaml` | Create | Mailcow deploy manifest |
| `deploys/env/production/.env.tpp-infra-authentik` | Create | Authentik env vars (gitignored) |
| `deploys/env/production/.env.tpp-infra-mailcow` | Create | Mailcow env vars (gitignored) |

---

## Task 1: Create DNS Records

**Files:** None (Cloudflare API only)

- [ ] **Step 1: Create A record for auth.idtpp.com (proxied)**

```bash
kctl-cf records create --type A --name auth --content "178.104.127.104" --zone idtpp.com --proxied
```

Expected: `OK DNS record created: <id>`

- [ ] **Step 2: Create A record for mail.idtpp.com (NOT proxied)**

```bash
kctl-cf records create --type A --name mail --content "178.104.127.104" --zone idtpp.com --no-proxied
```

Expected: `OK DNS record created: <id>`

- [ ] **Step 3: Create MX record**

```bash
kctl-cf records create --type MX --name "@" --content "mail.idtpp.com" --zone idtpp.com
```

Note: If MX requires priority, check `kctl-cf records create --help` for a `--priority` flag. Default priority 10.

- [ ] **Step 4: Create SPF TXT record**

```bash
kctl-cf records create --type TXT --name "@" --content "v=spf1 a mx ip4:178.104.127.104 ~all" --zone idtpp.com
```

- [ ] **Step 5: Create DMARC TXT record**

```bash
kctl-cf records create --type TXT --name "_dmarc" --content "v=DMARC1; p=quarantine; rua=mailto:postmaster@idtpp.com" --zone idtpp.com
```

- [ ] **Step 6: Create autodiscover CNAME**

```bash
kctl-cf records create --type CNAME --name "autodiscover" --content "mail.idtpp.com" --zone idtpp.com --no-proxied
```

- [ ] **Step 7: Create autoconfig CNAME**

```bash
kctl-cf records create --type CNAME --name "autoconfig" --content "mail.idtpp.com" --zone idtpp.com --no-proxied
```

- [ ] **Step 8: Verify all records**

```bash
kctl-cf records list --zone idtpp.com
```

Expected: All 7 new records visible (A auth, A mail, MX @, TXT @, TXT _dmarc, CNAME autodiscover, CNAME autoconfig) plus the existing `dokploy` A record.

---

## Task 2: Set Reverse DNS (PTR)

**Files:** None (Hetzner API only)

- [ ] **Step 1: Set PTR record on tpp-prod-01**

```bash
kctl-hz config use idtpp
kctl-hz rdns set server 126000539 "178.104.127.104" "mail.idtpp.com"
```

Server ID `126000539` = tpp-prod-01. Expected: PTR record set.

- [ ] **Step 2: Verify PTR**

```bash
kctl-hz rdns get server 126000539
```

Expected: `178.104.127.104 → mail.idtpp.com`

- [ ] **Step 3: Switch back to kodemeio profile**

```bash
kctl-hz config use kodemeio
```

---

## Task 3: Create Authentik Deploy Manifest

**Files:**
- Create: `deploys/instances/production/tpp-infra-authentik.yaml`

- [ ] **Step 1: Create the manifest file**

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

- [ ] **Step 2: Validate manifest**

```bash
kctl-dokploy config use idtpp
kctl-dokploy deploy validate -f deploys/instances/production/tpp-infra-authentik.yaml
```

Expected: Validation passes.

---

## Task 4: Create Authentik Environment File

**Files:**
- Create: `deploys/env/production/.env.tpp-infra-authentik` (gitignored)

- [ ] **Step 1: Generate secrets**

```bash
# Generate AUTHENTIK_SECRET_KEY (50+ chars)
openssl rand -hex 32

# Generate PG_PASS
openssl rand -hex 16

# Generate AUTHENTIK_BOOTSTRAP_PASSWORD
openssl rand -hex 16

# Generate AUTHENTIK_BOOTSTRAP_TOKEN
openssl rand -hex 32
```

Record all generated values.

- [ ] **Step 2: Create the env file**

Create `deploys/env/production/.env.tpp-infra-authentik` using the pattern from `kod-infra-authentik`, adapted for TPP:

```env
# =============================================================================
# Authentik Identity Provider - TPP PRODUCTION
# =============================================================================
# Authentik 2026.2.1 — Bundled PostgreSQL + Redis (self-contained)

# =============================================================================
# Compose Project
# =============================================================================
COMPOSE_PROJECT_NAME=tpp-infra-authentik
TENANT=tpp

# =============================================================================
# Domain Configuration
# =============================================================================
DOMAIN=auth.idtpp.com

# =============================================================================
# Authentik Version
# =============================================================================
AUTHENTIK_TAG=2026.2.1
AUTHENTIK_DEBUG=false

# =============================================================================
# Bootstrap (First Run Only)
# =============================================================================
AUTHENTIK_BOOTSTRAP_EMAIL=tri.gunawan@live.com
AUTHENTIK_BOOTSTRAP_PASSWORD=<GENERATED_BOOTSTRAP_PASSWORD>
AUTHENTIK_BOOTSTRAP_TOKEN=<GENERATED_BOOTSTRAP_TOKEN>

# =============================================================================
# Security (REQUIRED)
# =============================================================================
AUTHENTIK_SECRET_KEY=<GENERATED_SECRET_KEY>
ERROR_REPORTING=false

# =============================================================================
# PostgreSQL (Bundled)
# =============================================================================
AUTHENTIK_POSTGRESQL__HOST=postgresql
AUTHENTIK_POSTGRESQL__PORT=5432
AUTHENTIK_POSTGRESQL__USER=authentik
AUTHENTIK_POSTGRESQL__NAME=authentik
AUTHENTIK_POSTGRESQL__PASSWORD=<GENERATED_PG_PASS>
PG_PASS=<GENERATED_PG_PASS>

# =============================================================================
# Resource Limits
# =============================================================================
SERVER_CPU_LIMIT=1.5
SERVER_MEMORY_LIMIT=2G
WORKER_CPU_LIMIT=1.5
WORKER_MEMORY_LIMIT=2G

# =============================================================================
# Timezone
# =============================================================================
TZ=Asia/Jakarta
```

Replace all `<GENERATED_*>` placeholders with values from Step 1.

- [ ] **Step 3: Verify file exists and is gitignored**

```bash
ls -la deploys/env/production/.env.tpp-infra-authentik
git status deploys/env/production/.env.tpp-infra-authentik
```

Expected: File exists, not tracked by git.

---

## Task 5: Deploy Authentik

**Files:** None (CLI deploy)

- [ ] **Step 1: Deploy via manifest**

```bash
kctl-dokploy config use idtpp
kctl-dokploy deploy apply -f deploys/instances/production/tpp-infra-authentik.yaml
```

Expected: 13-phase pipeline runs — DNS verified, compose created, env pushed, domain configured, deploy triggered.

- [ ] **Step 2: Verify healthcheck**

```bash
curl -sk https://auth.idtpp.com/ | head -20
```

Expected: Authentik login page HTML or redirect.

- [ ] **Step 3: Log in to verify bootstrap**

Open `https://auth.idtpp.com` in browser. Log in with `akadmin` / `<AUTHENTIK_BOOTSTRAP_PASSWORD>`.

Expected: Authentik admin dashboard loads.

- [ ] **Step 4: Switch Dokploy back to kodemeio**

```bash
kctl-dokploy config use kodemeio
```

- [ ] **Step 5: Commit manifest**

```bash
git add deploys/instances/production/tpp-infra-authentik.yaml
git commit -m "feat(deploys): add TPP Authentik SSO instance (auth.idtpp.com)"
```

---

## Task 6: Create Mailcow Deploy Manifest

**Files:**
- Create: `deploys/instances/production/tpp-infra-mailcow.yaml`

**Prerequisite:** Hetzner has unblocked SMTP ports on tpp-prod-01.

- [ ] **Step 1: Create the manifest file**

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

- [ ] **Step 2: Validate manifest**

```bash
kctl-dokploy config use idtpp
kctl-dokploy deploy validate -f deploys/instances/production/tpp-infra-mailcow.yaml
```

Expected: Validation passes.

---

## Task 7: Create Mailcow Environment File

**Files:**
- Create: `deploys/env/production/.env.tpp-infra-mailcow` (gitignored)

- [ ] **Step 1: Generate secrets**

```bash
# Generate DBPASS
openssl rand -base64 21

# Generate DBROOT
openssl rand -base64 21

# Generate REDISPASS
openssl rand -base64 21

# Generate API_KEY
openssl rand -hex 32

# Generate API_KEY_READ_ONLY
openssl rand -hex 32

# Generate SOGO_URL_ENCRYPTION_KEY
openssl rand -base64 12
```

Record all generated values.

- [ ] **Step 2: Create the env file**

Create `deploys/env/production/.env.tpp-infra-mailcow` using the pattern from `kod-infra-mailcow`, adapted for TPP:

```env
# =============================================================================
# Mailcow - TPP PRODUCTION
# =============================================================================

DEPLOY_ENV=production
DOKPLOY_PROJECT_NAME=tpp-infra-mailcow

# =============================================================================
# Dokploy Domain Configuration
# =============================================================================
SERVICE_DOMAIN=mail.idtpp.com
SERVICE_PORT=8080
SERVICE_HTTPS=true
SERVICE_CERT_TYPE=letsencrypt
SERVICE_NAME_IN_COMPOSE=nginx-mailcow

# =============================================================================
# Core Mailcow Settings
# =============================================================================
COMPOSE_PROJECT_NAME=tpp-mailcow
MAILCOW_HOSTNAME=mail.idtpp.com
MAILCOW_PASS_SCHEME=BLF-CRYPT
TZ=Asia/Jakarta
DOCKER_COMPOSE_VERSION=native

# =============================================================================
# Database (MariaDB)
# =============================================================================
DBNAME=mailcow
DBUSER=mailcow
DBPASS=<GENERATED_DBPASS>
DBROOT=<GENERATED_DBROOT>
SQL_PORT=127.0.0.1:13306

# =============================================================================
# Redis
# =============================================================================
REDISPASS=<GENERATED_REDISPASS>
REDIS_PORT=127.0.0.1:7654

# =============================================================================
# HTTP/HTTPS Bindings (behind Traefik)
# =============================================================================
HTTP_PORT=8080
HTTP_BIND=127.0.0.1
HTTPS_PORT=8443
HTTPS_BIND=127.0.0.1
HTTP_REDIRECT=n

# =============================================================================
# SSL / Let's Encrypt
# =============================================================================
SKIP_LETS_ENCRYPT=n
ENABLE_SSL_SNI=n
SKIP_IP_CHECK=n
SKIP_HTTP_VERIFICATION=y
ADDITIONAL_SAN=autodiscover.idtpp.com,autoconfig.idtpp.com
AUTODISCOVER_SAN=y
ADDITIONAL_SERVER_NAMES=

# ACME DNS challenge via Cloudflare
ACME_DNS_CHALLENGE=y
ACME_DNS_PROVIDER=dns_cf
ACME_ACCOUNT_EMAIL=tri.gunawan@live.com

# =============================================================================
# Mail Service Ports (direct, not proxied)
# =============================================================================
SMTP_PORT=25
SMTPS_PORT=465
SUBMISSION_PORT=587
IMAP_PORT=143
IMAPS_PORT=993
POP_PORT=110
POPS_PORT=995
SIEVE_PORT=4190
DOVEADM_PORT=127.0.0.1:19991

# =============================================================================
# Optional Services
# =============================================================================
SKIP_CLAMD=n
SKIP_OLEFY=n
SKIP_SOGO=n
SKIP_FTS=n
FTS_HEAP=128
FTS_PROCS=1

# =============================================================================
# Unbound & Watchdog
# =============================================================================
SKIP_UNBOUND_HEALTHCHECK=n
USE_WATCHDOG=y
WATCHDOG_NOTIFY_EMAIL=tri.gunawan@live.com
WATCHDOG_NOTIFY_BAN=y
WATCHDOG_NOTIFY_START=y
WATCHDOG_EXTERNAL_CHECKS=n
WATCHDOG_VERBOSE=n

# =============================================================================
# Access Control & Security
# =============================================================================
ACL_ANYONE=disallow
ALLOW_ADMIN_EMAIL_LOGIN=n
API_KEY=<GENERATED_API_KEY>
API_KEY_READ_ONLY=<GENERATED_API_KEY_READ_ONLY>
API_ALLOW_FROM=0.0.0.0/0

# =============================================================================
# Mail & SOGo Settings
# =============================================================================
MAILDIR_SUB=Maildir
MAILDIR_GC_TIME=7200
SOGO_EXPIRE_SESSION=480
SOGO_URL_ENCRYPTION_KEY=<GENERATED_SOGO_KEY>
LOG_LINES=9999

# =============================================================================
# Networking
# =============================================================================
IPV4_NETWORK=172.22.2
IPV6_NETWORK=fd4d:6169:6c63:6f78::/64
SNAT_TO_SOURCE=
SNAT6_TO_SOURCE=
ENABLE_IPV6=false
DISABLE_NETFILTER_ISOLATION_RULE=n

# =============================================================================
# Cloudflare DNS API (for ACME DNS challenge)
# =============================================================================
CF_API_TOKEN=<YOUR_CLOUDFLARE_API_TOKEN_FOR_IDTPP>
CF_ACCOUNT_EMAIL=Trigun.bsns@gmail.com

# =============================================================================
# Timezone
# =============================================================================
TZ=Asia/Jakarta
```

Replace all `<GENERATED_*>` placeholders with values from Step 1. Note `IPV4_NETWORK=172.22.2` to avoid conflict with kodemeio-mailcow (`172.22.1`).

- [ ] **Step 3: Verify file exists and is gitignored**

```bash
ls -la deploys/env/production/.env.tpp-infra-mailcow
git status deploys/env/production/.env.tpp-infra-mailcow
```

Expected: File exists, not tracked by git.

---

## Task 8: Deploy Mailcow

**Files:** None (CLI deploy)

**Prerequisite:** Hetzner SMTP block lifted (support request approved).

- [ ] **Step 1: Verify SMTP is unblocked**

```bash
# From tpp-prod-01 or locally via SSH
nc -zv smtp.gmail.com 25
```

Expected: Connection succeeds. If refused, Hetzner hasn't unblocked yet — wait.

- [ ] **Step 2: Deploy via manifest**

```bash
kctl-dokploy config use idtpp
kctl-dokploy deploy apply -f deploys/instances/production/tpp-infra-mailcow.yaml
```

Expected: Pipeline runs through all phases.

- [ ] **Step 3: Verify web UI**

```bash
curl -sk https://mail.idtpp.com/ | head -20
```

Expected: Mailcow login page HTML.

- [ ] **Step 4: Switch Dokploy back**

```bash
kctl-dokploy config use kodemeio
```

- [ ] **Step 5: Commit manifest**

```bash
git add deploys/instances/production/tpp-infra-mailcow.yaml
git commit -m "feat(deploys): add TPP Mailcow mail server instance (mail.idtpp.com)"
```

---

## Task 9: Post-Deploy Mailcow Configuration

**Files:** None (manual + CLI)

- [ ] **Step 1: Log in to Mailcow admin**

Open `https://mail.idtpp.com` in browser. Login: `admin` / `moohoo`.

- [ ] **Step 2: Change admin password**

Go to System > Admin accounts. Change password immediately.

- [ ] **Step 3: Add idtpp.com mail domain**

Go to Configuration > Mail setup > Domains > Add domain. Enter `idtpp.com`.

- [ ] **Step 4: Copy DKIM key**

Go to Configuration > ARC/DKIM Keys. Select `idtpp.com`, copy the DKIM public key TXT value.

- [ ] **Step 5: Add DKIM TXT record to Cloudflare**

```bash
kctl-cf records create --type TXT --name "dkim._domainkey" --content "<DKIM_KEY_VALUE>" --zone idtpp.com
```

Replace `<DKIM_KEY_VALUE>` with the DKIM public key from Step 4. The selector name may differ — check Mailcow UI for the exact `selector._domainkey` format.

- [ ] **Step 6: Test email delivery**

Create a test mailbox in Mailcow (e.g., `test@idtpp.com`). Send an email to an external address. Verify delivery and check headers for SPF/DKIM/DMARC pass.

```bash
# Quick DNS verification
dig MX idtpp.com +short
dig TXT idtpp.com +short
dig TXT _dmarc.idtpp.com +short
```

Expected:
- MX: `10 mail.idtpp.com.`
- TXT includes SPF record
- DMARC: `v=DMARC1; p=quarantine; ...`

---

## Task 10: Final Commit and Cleanup

- [ ] **Step 1: Verify git status**

```bash
git status
```

Expected: Only the two manifest YAML files should be uncommitted (env files are gitignored).

- [ ] **Step 2: Commit any remaining changes**

If both manifests were already committed in Tasks 5 and 8, verify:

```bash
git log --oneline -5
```

Expected: Two commits for the manifests visible.

- [ ] **Step 3: Push to remote**

```bash
git push origin main
```
