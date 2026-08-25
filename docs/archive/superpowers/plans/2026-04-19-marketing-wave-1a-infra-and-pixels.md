# Marketing Wave 1a — Infra & Pixels Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up self-hosted Plausible CE at `plausible.kodeme.io` and self-hosted Shlink at `s.kodeme.io`, both on `kod-prod-01`. Install Meta Pixel + Google Tag snippets into the five Next.js marketing apps so the pixels fire on day 1 (for Wave 2 Meta Ads warm-audience build-up).

**Architecture:** Two new service repos (`kodemeio-plausible`, `kodemeio-shlink`) following the existing `kodemeio-<service>` convention. Both use the shared Postgres instance via private-IP on the kodemeio Hetzner account. Plausible adds a co-located ClickHouse for event storage. Deployed via existing `kctl-dokploy deploy apply` pipeline with YAML manifests in `kodemeio-platform/deploys/`. Pixel snippets installed as a shared `<SiteAnalytics>` Next.js Client Component wired into each `app/layout.tsx`.

**Tech Stack:** Docker Compose, Plausible CE v2.1.5 (Elixir), ClickHouse 24.12, Shlink 4.4 (PHP), shared Postgres 16, Traefik (Dokploy), Let's Encrypt, Cloudflare DNS, Hetzner Object Storage (ClickHouse backups), Next.js 15 `<Script>` + React Client Components for pixel installation.

**Spec:** `docs/superpowers/specs/2026-04-19-kctl-marketing-wave-1-design.md` (§3, §5)

**Working directories:**
- `/home/tgunawan/project/00-new-projects/kodemeio-workspace/kodemeio-platform` (deploys + this plan)
- `/home/tgunawan/project/00-new-projects/kodemeio-workspace/kodemeio-plausible` (NEW — created in Task 1)
- `/home/tgunawan/project/00-new-projects/kodemeio-workspace/kodemeio-shlink` (NEW — created in Task 8)
- `/home/tgunawan/project/00-new-projects/kodemeio-workspace/kodemeio-react` (pixel installs)

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Create repo | `kodemeio-plausible/` | Plausible service repo (Dokploy source) |
| Create | `kodemeio-plausible/docker-compose.prod.yml` | Production compose — Plausible + ClickHouse |
| Create | `kodemeio-plausible/docker-compose.yml` | Local dev compose (optional convenience) |
| Create | `kodemeio-plausible/clickhouse/config.xml` | ClickHouse logging + compression overrides |
| Create | `kodemeio-plausible/clickhouse/users.xml` | ClickHouse profile/quota config |
| Create | `kodemeio-plausible/scripts/backup-clickhouse.sh` | Nightly ClickHouse → S3 dump |
| Create | `kodemeio-plausible/.env.example` | Documented env reference (no secrets) |
| Create | `kodemeio-plausible/.gitignore` | Exclude `.env`, local volumes |
| Create | `kodemeio-plausible/README.md` | Service runbook |
| Create | `kodemeio-plausible/CHANGELOG.md` | v0.1.0 first release |
| Create | `kodemeio-plausible/Makefile` | `make up / down / logs / shell` |
| Create repo | `kodemeio-shlink/` | Shlink service repo |
| Create | `kodemeio-shlink/docker-compose.prod.yml` | Production compose — Shlink |
| Create | `kodemeio-shlink/docker-compose.yml` | Local dev compose |
| Create | `kodemeio-shlink/.env.example` | Documented env reference |
| Create | `kodemeio-shlink/.gitignore` | |
| Create | `kodemeio-shlink/README.md` | Service runbook |
| Create | `kodemeio-shlink/CHANGELOG.md` | v0.1.0 first release |
| Create | `kodemeio-shlink/Makefile` | |
| Create | `kodemeio-platform/deploys/bases/plausible.yaml` | Base template for Plausible deploys |
| Create | `kodemeio-platform/deploys/bases/shlink.yaml` | Base template for Shlink deploys |
| Create | `kodemeio-platform/deploys/instances/production/kod-infra-plausible.yaml` | Production Plausible instance |
| Create | `kodemeio-platform/deploys/instances/production/kod-infra-shlink.yaml` | Production Shlink instance |
| Create | `kodemeio-platform/deploys/env/production/.env.kod-infra-plausible` | Secrets (gitignored) |
| Create | `kodemeio-platform/deploys/env/production/.env.kod-infra-shlink` | Secrets (gitignored) |
| Modify | `kodemeio-react/apps/web/kodemeio/app/layout.tsx` | Add `<SiteAnalytics>` |
| Modify | `kodemeio-react/apps/web/corporate/app/layout.tsx` | Add `<SiteAnalytics>` |
| Modify | `kodemeio-react/apps/web/provetics/app/layout.tsx` | Add `<SiteAnalytics>` |
| Modify | `kodemeio-react/apps/web/terakidz/src/app/layout.tsx` | Add `<SiteAnalytics>` |
| Modify | `kodemeio-react/apps/web/careers/src/app/layout.tsx` | Add `<SiteAnalytics>` |
| Create | `kodemeio-react/packages/analytics/src/SiteAnalytics.tsx` | Shared pixel + Plausible Client Component |
| Create | `kodemeio-react/packages/analytics/src/index.ts` | Public exports |
| Create | `kodemeio-react/packages/analytics/package.json` | `@kodemeio/analytics` workspace pkg |
| Create | `kodemeio-react/packages/analytics/tsconfig.json` | |

---

## Prerequisites (verify before starting)

- [ ] `kctl-hz`, `kctl-pg`, `kctl-cf`, `kctl-dokploy`, `kctl-op` installed and with `kodemeio` profile configured
- [ ] You can `kctl-hz -p kodemeio servers list` and see `kod-prod-01`, `kod-prod-02`
- [ ] You can `kctl-pg -p kodemeio databases list` against the shared Postgres instance
- [ ] You have GitHub org write access to create new `kodemeio-plausible` and `kodemeio-shlink` repos
- [ ] 1Password vault `kodemeio-production` is unlocked (`op signin kodemeio`)
- [ ] Cloudflare zone `kodeme.io` is managed by `kctl-cf` profile `kodemeio`

Resolve **before Task 11** (deploy):

- [ ] Record the kodemeio-account shared Postgres private-IP endpoint: `kctl-hz -p kodemeio servers show kod-prod-01 --json | jq '.private_net[0].ip'` — document the IP in this plan's header comment before proceeding

---

## Task 1: Create `kodemeio-plausible` repo skeleton

**Files:**
- Create: `~/project/00-new-projects/kodemeio-workspace/kodemeio-plausible/` (new directory)
- Create: `kodemeio-plausible/.gitignore`
- Create: `kodemeio-plausible/README.md`
- Create: `kodemeio-plausible/CHANGELOG.md`
- Create: `kodemeio-plausible/Makefile`
- Create: `kodemeio-plausible/.env.example`

- [ ] **Step 1: Create directory and initialize git**

```bash
cd ~/project/00-new-projects/kodemeio-workspace
mkdir kodemeio-plausible
cd kodemeio-plausible
git init -b main
```

- [ ] **Step 2: Create `.gitignore`**

```gitignore
# .gitignore
.env
.env.*
!.env.example
*.log
node_modules/
data/
backups/
clickhouse-data/
```

- [ ] **Step 3: Create `.env.example`**

```dotenv
# kodemeio-plausible — .env.example
# Copy to .env and fill. Never commit .env.

DOMAIN=plausible.kodeme.io

# Plausible core
SECRET_KEY_BASE=<generate: openssl rand -base64 48>
TOTP_VAULT_KEY=<generate: openssl rand -base64 32>

# Postgres (shared kodemeio instance, private IP)
PG_HOST=<kodemeio private IP>
PG_PORT=5432
PG_USER=plausible
PG_PASSWORD=<from 1Password: kodemeio-production/plausible#pg_password>
PG_DATABASE=plausible

# SMTP (kodeme.io Mailcow)
MAILER_EMAIL=noreply@kodeme.io
SMTP_HOST_ADDR=mail.kodeme.io
SMTP_HOST_PORT=587
SMTP_USER_NAME=plausible@kodeme.io
SMTP_USER_PWD=<from 1Password: kodemeio-production/plausible#smtp_password>

# ClickHouse backup (Hetzner Object Storage)
CLICKHOUSE_BACKUP_S3_ENDPOINT=https://nbg1.your-objectstorage.com
CLICKHOUSE_BACKUP_S3_BUCKET=kodemeio-backups
CLICKHOUSE_BACKUP_S3_ACCESS_KEY=<from 1Password: kodemeio-production/hetzner-object-storage#access_key>
CLICKHOUSE_BACKUP_S3_SECRET_KEY=<from 1Password: kodemeio-production/hetzner-object-storage#secret_key>
```

- [ ] **Step 4: Create `Makefile`**

```makefile
.PHONY: help up down logs shell restart pull ps

help:
	@echo "kodemeio-plausible targets:"
	@echo "  up       Start (prod compose)"
	@echo "  down     Stop and remove containers"
	@echo "  logs     Tail logs"
	@echo "  shell    Shell into plausible container"
	@echo "  restart  Restart services"
	@echo "  pull     Pull latest images"
	@echo "  ps       List running services"

up:
	docker compose -f docker-compose.prod.yml --env-file .env up -d

down:
	docker compose -f docker-compose.prod.yml --env-file .env down

logs:
	docker compose -f docker-compose.prod.yml logs -f --tail=100

shell:
	docker compose -f docker-compose.prod.yml exec plausible sh

restart:
	docker compose -f docker-compose.prod.yml --env-file .env restart

pull:
	docker compose -f docker-compose.prod.yml pull

ps:
	docker compose -f docker-compose.prod.yml ps
```

- [ ] **Step 5: Create `CHANGELOG.md`**

```markdown
# Changelog — kodemeio-plausible

All notable changes documented here. Format: Keep a Changelog.

## [0.1.0] — 2026-04-19

### Added
- Initial Plausible CE v2.1.5 production compose
- Co-located ClickHouse 24.12 for event storage
- Shared-Postgres wiring for config metadata
- Hetzner Object Storage backup for ClickHouse
- SMTP wiring via Mailcow
```

- [ ] **Step 6: Create README.md (minimum 60 lines)**

```markdown
# kodemeio-plausible

Self-hosted Plausible Community Edition for Kodemeio's six tracked properties. Deployed via Dokploy on `kod-prod-01`, fronted by Traefik at `plausible.kodeme.io`.

## What this is

- **Plausible CE v2.1.5** — privacy-friendly, cookie-less web analytics
- **ClickHouse 24.12** — event store (co-located on same host)
- **Shared Postgres** — Plausible config metadata (sites, goals, users)
- Single shared instance for all six Kodemeio marketing properties: `kodemeio.com`, `corporate.kodemeio.com`, `careers.kodemeio.com`, `bas.kodeme.io`, `hrm.kodeme.io`, `provetics.com`, `terakidz.com`

## Managed by

`kctl-plausible` (see `packages/kctl-plausible` in `kodemeio-platform`). All CRUD — sites, goals, funnels, shared links, guests, and queries — goes through the CLI. Direct UI access at `https://plausible.kodeme.io` is available for exploration but not the source of truth.

## Deploy

This repo is the Dokploy source. Deploy flow:

```bash
cd ~/project/00-new-projects/kodemeio-workspace/kodemeio-platform
kctl-dokploy -p kodemeio deploy apply -f deploys/instances/production/kod-infra-plausible.yaml
```

The pipeline runs DNS → DB → Compose → Env → Domain → Deploy → Verify → Backup → Schedules. Env file lives at `kodemeio-platform/deploys/env/production/.env.kod-infra-plausible`.

## Local development

```bash
cp .env.example .env
# Edit .env
make up
# Plausible at http://localhost:8000
make logs
make down
```

## Backups

- **Postgres**: Dokploy native — nightly 03:00, rolled to Hetzner Object Storage, 14-day retention. Inherited from `deploys/bases/infra.yaml`.
- **ClickHouse**: custom via `scripts/backup-clickhouse.sh` — runs nightly 03:30 as a scheduled container command. Dumps `plausible_events` database to `s3://kodemeio-backups/clickhouse/plausible-<date>.zip`.

## Architecture

```
┌─────────────────────── kod-prod-01 ─────────────────────────┐
│ Traefik (Dokploy)                                           │
│   └── plausible.kodeme.io → plausible-app:8000 (Elixir)     │
│                                                              │
│ plausible-app ──── clickhouse:8123 (events DB)              │
│        │                                                     │
│        └── <shared Postgres>:5432 (config DB)               │
└──────────────────────────────────────────────────────────────┘
```

## Restart / upgrade

1. Bump `default_tag` in `kodemeio-platform/deploys/bases/plausible.yaml`.
2. `kctl-dokploy -p kodemeio deploy apply -f deploys/instances/production/kod-infra-plausible.yaml`.
3. Verify via `kctl-plausible doctor`.

## Healthcheck

Docker-compose healthcheck: `wget -qO- http://localhost:8000/api/health | grep -q ok`.
Deploy pipeline waits up to 2 min after deploy before marking healthy.

## Troubleshooting

- **"plausible_events database not found"**: ClickHouse didn't init. Shell in (`make shell`, then `clickhouse-client`) and check `SHOW DATABASES;`.
- **"Postgres connection refused"**: Check `PG_HOST` in `.env` matches current private-IP of shared Postgres node (`kctl-hz -p kodemeio servers show kod-prod-01`).
- **Stuck email verification**: SMTP failure. Test with `kctl-mailcow -p kodemeio doctor` on the `plausible@kodeme.io` account.
```

- [ ] **Step 7: Commit**

```bash
git add .
git commit -m "chore: initial kodemeio-plausible skeleton

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: ClickHouse configuration files

**Files:**
- Create: `kodemeio-plausible/clickhouse/config.xml`
- Create: `kodemeio-plausible/clickhouse/users.xml`

- [ ] **Step 1: Create `clickhouse/config.xml`**

```xml
<!-- clickhouse/config.xml — logging + compression overrides -->
<clickhouse>
    <logger>
        <level>warning</level>
        <log>/var/log/clickhouse-server/clickhouse-server.log</log>
        <errorlog>/var/log/clickhouse-server/clickhouse-server.err.log</errorlog>
        <size>100M</size>
        <count>3</count>
    </logger>

    <compression>
        <case>
            <min_part_size>10000000000</min_part_size>
            <min_part_size_ratio>0.01</min_part_size_ratio>
            <method>lz4</method>
        </case>
    </compression>

    <query_log replace="true">
        <database>system</database>
        <table>query_log</table>
        <engine>ENGINE = MergeTree ORDER BY (event_date, event_time) TTL event_date + interval 7 day</engine>
        <partition_by>toYYYYMM(event_date)</partition_by>
        <flush_interval_milliseconds>7500</flush_interval_milliseconds>
    </query_log>
</clickhouse>
```

- [ ] **Step 2: Create `clickhouse/users.xml`**

```xml
<!-- clickhouse/users.xml — profile + quota for Plausible workload -->
<clickhouse>
    <profiles>
        <default>
            <max_memory_usage>1000000000</max_memory_usage>
            <max_execution_time>30</max_execution_time>
            <log_queries>0</log_queries>
        </default>
    </profiles>

    <quotas>
        <default>
            <interval>
                <duration>3600</duration>
                <queries>0</queries>
                <errors>0</errors>
                <result_rows>0</result_rows>
                <read_rows>0</read_rows>
                <execution_time>0</execution_time>
            </interval>
        </default>
    </quotas>
</clickhouse>
```

- [ ] **Step 3: Commit**

```bash
git add clickhouse/
git commit -m "chore(clickhouse): add logging + profile configs

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: ClickHouse backup script

**Files:**
- Create: `kodemeio-plausible/scripts/backup-clickhouse.sh`

- [ ] **Step 1: Create `scripts/backup-clickhouse.sh`**

```bash
#!/usr/bin/env bash
# scripts/backup-clickhouse.sh
# Dump plausible_events to Hetzner Object Storage. Runs via scheduled exec
# command on the clickhouse container at 03:30 daily.

set -euo pipefail

: "${CLICKHOUSE_BACKUP_S3_ENDPOINT:?env missing}"
: "${CLICKHOUSE_BACKUP_S3_BUCKET:?env missing}"
: "${CLICKHOUSE_BACKUP_S3_ACCESS_KEY:?env missing}"
: "${CLICKHOUSE_BACKUP_S3_SECRET_KEY:?env missing}"

DATE="$(date -u +%Y%m%d_%H%M%S)"
BACKUP_NAME="plausible-events-${DATE}.zip"
S3_URL="${CLICKHOUSE_BACKUP_S3_ENDPOINT}/${CLICKHOUSE_BACKUP_S3_BUCKET}/clickhouse/${BACKUP_NAME}"

echo "[$(date -u)] backup start: ${BACKUP_NAME}"

clickhouse-client --query="
  BACKUP DATABASE plausible_events
  TO S3('${S3_URL}', '${CLICKHOUSE_BACKUP_S3_ACCESS_KEY}', '${CLICKHOUSE_BACKUP_S3_SECRET_KEY}')
  SETTINGS compression_method = 'zstd', compression_level = 3
"

echo "[$(date -u)] backup complete: ${BACKUP_NAME}"

# Retention: keep 14 newest; list + delete older via S3 lifecycle rule.
# (Lifecycle rule configured on bucket via kctl-hz storage, not here.)
```

- [ ] **Step 2: Make executable**

```bash
chmod +x scripts/backup-clickhouse.sh
```

- [ ] **Step 3: Commit**

```bash
git add scripts/
git commit -m "feat(backup): add ClickHouse S3 backup script

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Plausible production compose

**Files:**
- Create: `kodemeio-plausible/docker-compose.prod.yml`

- [ ] **Step 1: Create `docker-compose.prod.yml`**

```yaml
# kodemeio-plausible/docker-compose.prod.yml
# Production compose — deployed via Dokploy, env from .env.kod-infra-plausible.

x-logging: &default-logging
  driver: "json-file"
  options:
    max-size: "50m"
    max-file: "5"

volumes:
  clickhouse-data:
  clickhouse-logs:

networks:
  dokploy-network:
    external: true

services:
  plausible:
    image: ghcr.io/plausible/community-edition:v2.1.5
    restart: unless-stopped
    depends_on:
      clickhouse:
        condition: service_healthy
    environment:
      BASE_URL: "https://${DOMAIN}"
      SECRET_KEY_BASE: "${SECRET_KEY_BASE}"
      TOTP_VAULT_KEY: "${TOTP_VAULT_KEY}"
      DATABASE_URL: "postgres://${PG_USER}:${PG_PASSWORD}@${PG_HOST}:${PG_PORT}/${PG_DATABASE}"
      CLICKHOUSE_DATABASE_URL: "http://default:@clickhouse:8123/plausible_events"
      MAILER_EMAIL: "${MAILER_EMAIL}"
      SMTP_HOST_ADDR: "${SMTP_HOST_ADDR}"
      SMTP_HOST_PORT: "${SMTP_HOST_PORT}"
      SMTP_USER_NAME: "${SMTP_USER_NAME}"
      SMTP_USER_PWD: "${SMTP_USER_PWD}"
      DISABLE_REGISTRATION: "true"
      LISTEN_IP: "0.0.0.0"
      TZ: "Asia/Jakarta"
    healthcheck:
      test: ["CMD-SHELL", "wget -qO- http://localhost:8000/api/health 2>&1 | grep -q ok || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 60s
    deploy:
      resources:
        limits:
          cpus: "1.0"
          memory: 1G
        reservations:
          cpus: "0.25"
          memory: 256M
    logging: *default-logging
    networks:
      - dokploy-network
    labels:
      - traefik.enable=true
      - traefik.http.routers.plausible.rule=Host(`${DOMAIN}`)
      - traefik.http.routers.plausible.entrypoints=websecure
      - traefik.http.routers.plausible.tls.certresolver=letsencrypt
      - traefik.http.services.plausible.loadbalancer.server.port=8000
      - traefik.docker.network=dokploy-network

  clickhouse:
    image: clickhouse/clickhouse-server:24.12-alpine
    restart: unless-stopped
    volumes:
      - clickhouse-data:/var/lib/clickhouse
      - clickhouse-logs:/var/log/clickhouse-server
      - ./clickhouse/config.xml:/etc/clickhouse-server/config.d/logging.xml:ro
      - ./clickhouse/users.xml:/etc/clickhouse-server/users.d/logging.xml:ro
      - ./scripts/backup-clickhouse.sh:/usr/local/bin/backup-clickhouse.sh:ro
    environment:
      CLICKHOUSE_BACKUP_S3_ENDPOINT: "${CLICKHOUSE_BACKUP_S3_ENDPOINT}"
      CLICKHOUSE_BACKUP_S3_BUCKET: "${CLICKHOUSE_BACKUP_S3_BUCKET}"
      CLICKHOUSE_BACKUP_S3_ACCESS_KEY: "${CLICKHOUSE_BACKUP_S3_ACCESS_KEY}"
      CLICKHOUSE_BACKUP_S3_SECRET_KEY: "${CLICKHOUSE_BACKUP_S3_SECRET_KEY}"
      TZ: "Asia/Jakarta"
    healthcheck:
      test: ["CMD", "wget", "--spider", "-q", "http://localhost:8123/ping"]
      interval: 30s
      timeout: 5s
      retries: 5
      start_period: 30s
    deploy:
      resources:
        limits:
          cpus: "1.0"
          memory: 2G
        reservations:
          cpus: "0.25"
          memory: 512M
    ulimits:
      nofile:
        soft: 262144
        hard: 262144
    logging: *default-logging
    networks:
      - dokploy-network
```

- [ ] **Step 2: Validate compose locally (no deploy)**

```bash
cd ~/project/00-new-projects/kodemeio-workspace/kodemeio-plausible
cp .env.example .env
# Fill in dummy values just to pass validation
docker compose -f docker-compose.prod.yml --env-file .env config > /dev/null
```

Expected: no errors, silent success.

- [ ] **Step 3: Commit**

```bash
git add docker-compose.prod.yml
git commit -m "feat(compose): add Plausible CE + ClickHouse production compose

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Plausible local dev compose

**Files:**
- Create: `kodemeio-plausible/docker-compose.yml`

- [ ] **Step 1: Create local dev compose (embedded Postgres, no external deps)**

```yaml
# kodemeio-plausible/docker-compose.yml — local dev only
# Uses embedded Postgres + ClickHouse, no Traefik, exposes Plausible on :8000.

volumes:
  postgres-data:
  clickhouse-data:

services:
  postgres:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_DB: plausible_dev
      POSTGRES_USER: plausible
      POSTGRES_PASSWORD: plausible_dev_password
    volumes:
      - postgres-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "plausible"]
      interval: 10s
      timeout: 5s
      retries: 5

  clickhouse:
    image: clickhouse/clickhouse-server:24.12-alpine
    restart: unless-stopped
    volumes:
      - clickhouse-data:/var/lib/clickhouse
      - ./clickhouse/config.xml:/etc/clickhouse-server/config.d/logging.xml:ro
      - ./clickhouse/users.xml:/etc/clickhouse-server/users.d/logging.xml:ro
    ulimits:
      nofile:
        soft: 262144
        hard: 262144

  plausible:
    image: ghcr.io/plausible/community-edition:v2.1.5
    restart: unless-stopped
    depends_on:
      postgres:
        condition: service_healthy
      clickhouse:
        condition: service_started
    environment:
      BASE_URL: "http://localhost:8000"
      SECRET_KEY_BASE: "dev_key_64_chars_padding_padding_padding_padding_padding_padding"
      TOTP_VAULT_KEY: "dev_totp_vault_key_32_chars_pad"
      DATABASE_URL: "postgres://plausible:plausible_dev_password@postgres:5432/plausible_dev"
      CLICKHOUSE_DATABASE_URL: "http://default:@clickhouse:8123/plausible_events"
      DISABLE_REGISTRATION: "false"
    ports:
      - "8000:8000"
```

- [ ] **Step 2: Smoke-test local startup**

```bash
make up
# Wait ~45s
curl -sS http://localhost:8000/api/health
```

Expected: `{"status":"ok"}` (may take up to 60s while migrations run).

- [ ] **Step 3: Tear down local**

```bash
make down
docker volume rm kodemeio-plausible_postgres-data kodemeio-plausible_clickhouse-data
```

- [ ] **Step 4: Commit**

```bash
git add docker-compose.yml
git commit -m "feat(compose): add local dev compose with embedded Postgres

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Push `kodemeio-plausible` to GitHub

**Files:** (remote-only)

- [ ] **Step 1: Create remote repo via `gh`**

```bash
cd ~/project/00-new-projects/kodemeio-workspace/kodemeio-plausible
gh repo create kodemeio/kodemeio-plausible --private --source=. --remote=origin --description "Self-hosted Plausible CE for Kodemeio marketing analytics"
```

Expected: repo URL printed.

- [ ] **Step 2: Push**

```bash
git push -u origin main
```

Expected: branch `main` → `origin/main` tracking set.

- [ ] **Step 3: Verify**

```bash
gh repo view kodemeio/kodemeio-plausible --json name,visibility,defaultBranchRef
```

Expected: JSON shows `private`, `main` default.

---

## Task 7: Create `kodemeio-shlink` repo skeleton

**Files:**
- Create: `kodemeio-shlink/` (new directory)
- Create: `kodemeio-shlink/.gitignore`
- Create: `kodemeio-shlink/.env.example`
- Create: `kodemeio-shlink/Makefile`
- Create: `kodemeio-shlink/CHANGELOG.md`
- Create: `kodemeio-shlink/README.md`

- [ ] **Step 1: Create directory + git init**

```bash
cd ~/project/00-new-projects/kodemeio-workspace
mkdir kodemeio-shlink
cd kodemeio-shlink
git init -b main
```

- [ ] **Step 2: Create `.gitignore`**

```gitignore
.env
.env.*
!.env.example
*.log
data/
```

- [ ] **Step 3: Create `.env.example`**

```dotenv
# kodemeio-shlink — .env.example
# Copy to .env and fill. Never commit .env.

DOMAIN=s.kodeme.io

# Postgres (shared kodemeio instance, private IP)
PG_HOST=<kodemeio private IP>
PG_PORT=5432
PG_USER=shlink
PG_PASSWORD=<from 1Password: kodemeio-production/shlink#pg_password>
PG_DATABASE=shlink

# Shlink runtime
INITIAL_API_KEY=<generate: openssl rand -hex 32>
GEOLITE_LICENSE_KEY=<from 1Password: kodemeio-production/shlink#geolite_license>
IS_HTTPS_ENABLED=true
DISABLE_TRACK_PARAM=no-track
REDIRECT_STATUS_CODE=302
DEFAULT_SHORT_CODES_LENGTH=6
ENABLE_PERIODIC_VISIT_LOCATE=true
TIMEZONE=Asia/Jakarta
```

- [ ] **Step 4: Create `Makefile`**

```makefile
.PHONY: help up down logs shell restart pull ps

help:
	@echo "kodemeio-shlink targets:"
	@echo "  up       Start (prod compose)"
	@echo "  down     Stop and remove containers"
	@echo "  logs     Tail logs"
	@echo "  shell    Shell into shlink container"
	@echo "  restart  Restart services"
	@echo "  pull     Pull latest images"
	@echo "  ps       List running services"

up:
	docker compose -f docker-compose.prod.yml --env-file .env up -d

down:
	docker compose -f docker-compose.prod.yml --env-file .env down

logs:
	docker compose -f docker-compose.prod.yml logs -f --tail=100

shell:
	docker compose -f docker-compose.prod.yml exec shlink sh

restart:
	docker compose -f docker-compose.prod.yml --env-file .env restart

pull:
	docker compose -f docker-compose.prod.yml pull

ps:
	docker compose -f docker-compose.prod.yml ps
```

- [ ] **Step 5: Create CHANGELOG.md**

```markdown
# Changelog — kodemeio-shlink

Format: Keep a Changelog.

## [0.1.0] — 2026-04-19

### Added
- Initial Shlink 4.4 production compose
- Shared-Postgres wiring for URLs + visits
- MaxMind GeoLite2 integration for visit geolocation
```

- [ ] **Step 6: Create README.md (minimum 60 lines)**

```markdown
# kodemeio-shlink

Self-hosted [Shlink](https://shlink.io) — the URL shortener serving `s.kodeme.io`. Deployed via Dokploy on `kod-prod-01`, fronted by Traefik + Cloudflare.

## What this is

- **Shlink 4.4** — multi-domain REST-API-driven URL shortener
- **Shared Postgres** for URLs, tags, visits
- Single short domain `s.kodeme.io` serving all Kodemeio marketing campaigns across four product audiences (BAS, HRM, TPM, TMS) plus agency and careers surfaces
- QR code generation built into the API (used by `kctl-shlink qr generate` for print collateral)

## Managed by

`kctl-shlink` (see `packages/kctl-shlink` in `kodemeio-platform`). All short URL CRUD, campaign applies, tags, visits, QR codes, and reports go through the CLI. Direct API access possible but not the day-to-day path.

## Deploy

This repo is the Dokploy source. Deploy flow:

```bash
cd ~/project/00-new-projects/kodemeio-workspace/kodemeio-platform
kctl-dokploy -p kodemeio deploy apply -f deploys/instances/production/kod-infra-shlink.yaml
```

Env file lives at `kodemeio-platform/deploys/env/production/.env.kod-infra-shlink`.

## Local development

```bash
cp .env.example .env
# Edit .env
make up
# Shlink API at http://localhost:8080
# Health: curl http://localhost:8080/rest/health
make logs
make down
```

## Backups

- **Postgres**: Dokploy native — nightly 03:00, rolled to Hetzner Object Storage, 14-day retention (inherited from `deploys/bases/infra.yaml`).
- No ClickHouse — Shlink uses only Postgres. Visit history lives in `public.visit` table.

## Architecture

```
┌──────── kod-prod-01 ────────┐
│ Traefik (Dokploy)           │
│   └── s.kodeme.io → shlink  │
│                             │
│ shlink → shared Postgres    │
└─────────────────────────────┘
```

Cloudflare proxy: **enabled** (`proxied: true` in DNS manifest) — short-link redirects benefit from CF edge caching.

## Slug taxonomy

See `docs/marketing/taxonomy.md` in `kodemeio-platform`. Format: `{product}-{channel}-{campaign_tag}[-{variant}]`. Enforced by `kctl-shlink campaigns apply`.

## Restart / upgrade

1. Bump `default_tag` in `kodemeio-platform/deploys/bases/shlink.yaml`.
2. `kctl-dokploy -p kodemeio deploy apply -f deploys/instances/production/kod-infra-shlink.yaml`.
3. Verify via `kctl-shlink doctor`.

## Healthcheck

`curl http://localhost:8080/rest/health` returns `{"status":"pass"}`.

## Troubleshooting

- **GeoIP lookups returning null**: MaxMind license key invalid. Renew at maxmind.com (free tier OK), rotate `GEOLITE_LICENSE_KEY` in .env, restart.
- **404 on redirect**: short URL deleted. Check `kctl-shlink urls list --deleted`.
- **Cloudflare caching stale redirects**: purge the short URL path (`s.kodeme.io/<slug>`) in Cloudflare UI or via `kctl-cf cache purge`.
```

- [ ] **Step 7: Commit**

```bash
git add .
git commit -m "chore: initial kodemeio-shlink skeleton

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: Shlink production + dev compose

**Files:**
- Create: `kodemeio-shlink/docker-compose.prod.yml`
- Create: `kodemeio-shlink/docker-compose.yml`

- [ ] **Step 1: Create `docker-compose.prod.yml`**

```yaml
# kodemeio-shlink/docker-compose.prod.yml
# Production compose — deployed via Dokploy, env from .env.kod-infra-shlink.

x-logging: &default-logging
  driver: "json-file"
  options:
    max-size: "50m"
    max-file: "5"

networks:
  dokploy-network:
    external: true

services:
  shlink:
    image: shlinkio/shlink:4.4
    restart: unless-stopped
    environment:
      DEFAULT_DOMAIN: "${DOMAIN}"
      IS_HTTPS_ENABLED: "${IS_HTTPS_ENABLED:-true}"
      GEOLITE_LICENSE_KEY: "${GEOLITE_LICENSE_KEY}"
      DB_DRIVER: postgres
      DB_HOST: "${PG_HOST}"
      DB_PORT: "${PG_PORT}"
      DB_NAME: "${PG_DATABASE}"
      DB_USER: "${PG_USER}"
      DB_PASSWORD: "${PG_PASSWORD}"
      INITIAL_API_KEY: "${INITIAL_API_KEY}"
      DISABLE_TRACK_PARAM: "${DISABLE_TRACK_PARAM:-no-track}"
      REDIRECT_STATUS_CODE: "${REDIRECT_STATUS_CODE:-302}"
      DEFAULT_SHORT_CODES_LENGTH: "${DEFAULT_SHORT_CODES_LENGTH:-6}"
      ENABLE_PERIODIC_VISIT_LOCATE: "${ENABLE_PERIODIC_VISIT_LOCATE:-true}"
      TIMEZONE: "${TIMEZONE:-Asia/Jakarta}"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/rest/health"]
      interval: 30s
      timeout: 5s
      retries: 5
      start_period: 30s
    deploy:
      resources:
        limits:
          cpus: "0.5"
          memory: 512M
        reservations:
          cpus: "0.1"
          memory: 128M
    logging: *default-logging
    networks:
      - dokploy-network
    labels:
      - traefik.enable=true
      - traefik.http.routers.shlink.rule=Host(`${DOMAIN}`)
      - traefik.http.routers.shlink.entrypoints=websecure
      - traefik.http.routers.shlink.tls.certresolver=letsencrypt
      - traefik.http.services.shlink.loadbalancer.server.port=8080
      - traefik.docker.network=dokploy-network
```

- [ ] **Step 2: Create `docker-compose.yml` (local dev)**

```yaml
# kodemeio-shlink/docker-compose.yml — local dev only
volumes:
  postgres-data:

services:
  postgres:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_DB: shlink_dev
      POSTGRES_USER: shlink
      POSTGRES_PASSWORD: shlink_dev_password
    volumes:
      - postgres-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "shlink"]
      interval: 10s

  shlink:
    image: shlinkio/shlink:4.4
    restart: unless-stopped
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      DEFAULT_DOMAIN: "localhost:8080"
      IS_HTTPS_ENABLED: "false"
      DB_DRIVER: postgres
      DB_HOST: postgres
      DB_NAME: shlink_dev
      DB_USER: shlink
      DB_PASSWORD: shlink_dev_password
      INITIAL_API_KEY: dev_api_key_32_chars_padding_pad
      GEOLITE_LICENSE_KEY: ""
    ports:
      - "8080:8080"
```

- [ ] **Step 3: Validate compose**

```bash
cp .env.example .env
docker compose -f docker-compose.prod.yml --env-file .env config > /dev/null
```

Expected: silent success.

- [ ] **Step 4: Commit**

```bash
git add docker-compose.prod.yml docker-compose.yml
git commit -m "feat(compose): add Shlink production + dev compose files

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: Push `kodemeio-shlink` to GitHub

- [ ] **Step 1: Create remote repo**

```bash
cd ~/project/00-new-projects/kodemeio-workspace/kodemeio-shlink
gh repo create kodemeio/kodemeio-shlink --private --source=. --remote=origin --description "Self-hosted Shlink URL shortener for Kodemeio marketing campaigns"
```

- [ ] **Step 2: Push**

```bash
git push -u origin main
```

- [ ] **Step 3: Verify**

```bash
gh repo view kodemeio/kodemeio-shlink --json name,visibility,defaultBranchRef
```

Expected: private, main default.

---

## Task 10: Deploy bases in kodemeio-platform

**Files:**
- Create: `kodemeio-platform/deploys/bases/plausible.yaml`
- Create: `kodemeio-platform/deploys/bases/shlink.yaml`

- [ ] **Step 1: Create `deploys/bases/plausible.yaml`**

```yaml
# kodemeio-platform/deploys/bases/plausible.yaml
kind: base
type: infrastructure

server: kodeme-service
project: kod

source:
  type: github
  repo: kodemeio-plausible
  branch: main

healthcheck:
  path: /api/health
  port: 8000
  service: plausible
  expected_status: 200
  timeout: 120
  interval: 10

env_defaults:
  TZ: "Asia/Jakarta"
  PG_PORT: "5432"
  PG_USER: plausible
  PG_DATABASE: plausible
  SMTP_HOST_ADDR: "mail.kodeme.io"
  SMTP_HOST_PORT: "587"
  MAILER_EMAIL: "noreply@kodeme.io"
  DISABLE_REGISTRATION: "true"

backup:
  destination: kodemeio-s3-backups
  type: postgres
  schedule: "0 3 * * *"
  prefix_template: "{instance_name}"
  keep_latest: 14

schedules:
  - name: clickhouse-backup
    cron: "30 3 * * *"
    service: clickhouse
    command: "/usr/local/bin/backup-clickhouse.sh"
```

- [ ] **Step 2: Create `deploys/bases/shlink.yaml`**

```yaml
# kodemeio-platform/deploys/bases/shlink.yaml
kind: base
type: infrastructure

server: kodeme-service
project: kod

source:
  type: github
  repo: kodemeio-shlink
  branch: main

healthcheck:
  path: /rest/health
  port: 8080
  service: shlink
  expected_status: 200
  timeout: 60
  interval: 10

env_defaults:
  TZ: "Asia/Jakarta"
  TIMEZONE: "Asia/Jakarta"
  PG_PORT: "5432"
  PG_USER: shlink
  PG_DATABASE: shlink
  IS_HTTPS_ENABLED: "true"
  DISABLE_TRACK_PARAM: "no-track"
  REDIRECT_STATUS_CODE: "302"
  DEFAULT_SHORT_CODES_LENGTH: "6"
  ENABLE_PERIODIC_VISIT_LOCATE: "true"

backup:
  destination: kodemeio-s3-backups
  type: postgres
  schedule: "0 3 * * *"
  prefix_template: "{instance_name}"
  keep_latest: 14
```

- [ ] **Step 3: Validate manifests**

```bash
cd ~/project/00-new-projects/kodemeio-workspace/kodemeio-platform
uv run python -c "
import yaml
for f in ['deploys/bases/plausible.yaml', 'deploys/bases/shlink.yaml']:
    with open(f) as fh:
        doc = yaml.safe_load(fh)
    assert doc['kind'] == 'base'
    assert doc['type'] == 'infrastructure'
    print(f'{f}: ok')
"
```

Expected:
```
deploys/bases/plausible.yaml: ok
deploys/bases/shlink.yaml: ok
```

- [ ] **Step 4: Commit**

```bash
git add deploys/bases/plausible.yaml deploys/bases/shlink.yaml
git commit -m "feat(deploys): add Plausible + Shlink base templates

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 11: Resolve kodemeio-account shared Postgres IP and create production instance manifests

**Files:**
- Create: `kodemeio-platform/deploys/instances/production/kod-infra-plausible.yaml`
- Create: `kodemeio-platform/deploys/instances/production/kod-infra-shlink.yaml`

- [ ] **Step 1: Query shared Postgres private IP**

```bash
kctl-hz -p kodemeio servers list --json | jq -r '.[] | select(.name=="kod-prod-01") | .private_net[0].ip'
```

Expected: a `10.0.0.x` IP. Record it — you'll use it below. Call this `$KOD_PG_IP`.

If shared Postgres lives on a different node (e.g., `kod-prod-02`), substitute that server's private IP.

- [ ] **Step 2: Create `kod-infra-plausible.yaml`** (substitute the recorded IP)

```yaml
# kodemeio-platform/deploys/instances/production/kod-infra-plausible.yaml
kind: instance
extends: ../../bases/plausible.yaml

instance:
  name: kod-infra-plausible
  description: "Plausible CE — self-hosted privacy analytics"

project: kod
server: kod-prod-01

source_overrides:
  repo: kodemeio-plausible
  compose_path: ./docker-compose.prod.yml

domain:
  host: plausible.kodeme.io
  port: 8000
  service: plausible
  https: true
  cert: letsencrypt
  cloudflare_proxied: false   # Plausible WS / LiveView — keep direct

dns:
  provider: cloudflare
  zone: kodeme.io
  record: plausible
  type: A
  target: $PUBLIC_IP_KOD_PROD_01
  proxied: false

env_file: ../../env/production/.env.kod-infra-plausible
```

- [ ] **Step 3: Create `kod-infra-shlink.yaml`**

```yaml
# kodemeio-platform/deploys/instances/production/kod-infra-shlink.yaml
kind: instance
extends: ../../bases/shlink.yaml

instance:
  name: kod-infra-shlink
  description: "Shlink — self-hosted URL shortener"

project: kod
server: kod-prod-01

source_overrides:
  repo: kodemeio-shlink
  compose_path: ./docker-compose.prod.yml

domain:
  host: s.kodeme.io
  port: 8080
  service: shlink
  https: true
  cert: letsencrypt
  cloudflare_proxied: true   # Cloudflare caching fine for redirects

dns:
  provider: cloudflare
  zone: kodeme.io
  record: s
  type: A
  target: $PUBLIC_IP_KOD_PROD_01
  proxied: true

env_file: ../../env/production/.env.kod-infra-shlink
```

- [ ] **Step 4: Commit**

```bash
git add deploys/instances/production/kod-infra-plausible.yaml \
        deploys/instances/production/kod-infra-shlink.yaml
git commit -m "feat(deploys): add Plausible + Shlink production instance manifests

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 12: Provision Postgres databases via kctl-pg

- [ ] **Step 1: Create `plausible` database and user**

```bash
# Generate password
PLAUSIBLE_PG_PW="$(openssl rand -base64 32)"

kctl-pg -p kodemeio databases create plausible \
    --owner plausible \
    --create-user \
    --password "$PLAUSIBLE_PG_PW"

# Record the password — needed for 1Password in next task
echo "plausible pg password: $PLAUSIBLE_PG_PW"
```

Expected: database `plausible` created, user `plausible` created with OWNER on database.

- [ ] **Step 2: Create `shlink` database and user**

```bash
SHLINK_PG_PW="$(openssl rand -base64 32)"

kctl-pg -p kodemeio databases create shlink \
    --owner shlink \
    --create-user \
    --password "$SHLINK_PG_PW"

echo "shlink pg password: $SHLINK_PG_PW"
```

- [ ] **Step 3: Verify both databases exist**

```bash
kctl-pg -p kodemeio databases list | grep -E '^(plausible|shlink)\s'
```

Expected: both names appear.

---

## Task 13: Store secrets in 1Password

- [ ] **Step 1: Create 1Password items via CLI**

```bash
# Plausible
SECRET_KEY_BASE="$(openssl rand -base64 48)"
TOTP_VAULT_KEY="$(openssl rand -base64 32)"
# SMTP password for plausible@kodeme.io — get from mailcow
PLAUSIBLE_SMTP_PW="$(kctl-mailcow -p kodemeio mailboxes create-or-reset-password plausible@kodeme.io --json | jq -r '.password')"

op item create \
    --category=login \
    --title='plausible' \
    --vault='kodemeio-production' \
    --url='https://plausible.kodeme.io' \
    'username=admin' \
    "password=$SECRET_KEY_BASE" \
    "pg_password[password]=$PLAUSIBLE_PG_PW" \
    "smtp_password[password]=$PLAUSIBLE_SMTP_PW" \
    "totp_vault_key[password]=$TOTP_VAULT_KEY"
```

- [ ] **Step 2: Create Shlink 1Password item**

```bash
INITIAL_API_KEY="$(openssl rand -hex 32)"
# GeoLite2 key — fetch from MaxMind dashboard (manual); substitute literal here
GEOLITE_LICENSE_KEY="<paste from MaxMind dashboard>"

op item create \
    --category=login \
    --title='shlink' \
    --vault='kodemeio-production' \
    --url='https://s.kodeme.io' \
    'username=admin' \
    "password=$INITIAL_API_KEY" \
    "pg_password[password]=$SHLINK_PG_PW" \
    "geolite_license[password]=$GEOLITE_LICENSE_KEY"
```

- [ ] **Step 3: Verify retrievable**

```bash
op item get plausible --vault=kodemeio-production --fields pg_password --reveal
op item get shlink --vault=kodemeio-production --fields pg_password --reveal
```

Expected: each prints the password (should match what you generated).

---

## Task 14: Create production env files

**Files:**
- Create: `kodemeio-platform/deploys/env/production/.env.kod-infra-plausible`
- Create: `kodemeio-platform/deploys/env/production/.env.kod-infra-shlink`

- [ ] **Step 1: Create Plausible env file**

```bash
# Substitute $KOD_PG_IP with the private IP recorded in Task 11.
cat > ~/project/00-new-projects/kodemeio-workspace/kodemeio-platform/deploys/env/production/.env.kod-infra-plausible <<EOF
DOMAIN=plausible.kodeme.io
SECRET_KEY_BASE=$(op item get plausible --vault=kodemeio-production --fields password --reveal)
TOTP_VAULT_KEY=$(op item get plausible --vault=kodemeio-production --fields totp_vault_key --reveal)
PG_HOST=$KOD_PG_IP
PG_PORT=5432
PG_USER=plausible
PG_PASSWORD=$(op item get plausible --vault=kodemeio-production --fields pg_password --reveal)
PG_DATABASE=plausible
MAILER_EMAIL=noreply@kodeme.io
SMTP_HOST_ADDR=mail.kodeme.io
SMTP_HOST_PORT=587
SMTP_USER_NAME=plausible@kodeme.io
SMTP_USER_PWD=$(op item get plausible --vault=kodemeio-production --fields smtp_password --reveal)
CLICKHOUSE_BACKUP_S3_ENDPOINT=https://nbg1.your-objectstorage.com
CLICKHOUSE_BACKUP_S3_BUCKET=kodemeio-backups
CLICKHOUSE_BACKUP_S3_ACCESS_KEY=$(op item get hetzner-object-storage --vault=kodemeio-production --fields access_key --reveal)
CLICKHOUSE_BACKUP_S3_SECRET_KEY=$(op item get hetzner-object-storage --vault=kodemeio-production --fields secret_key --reveal)
EOF
chmod 600 ~/project/00-new-projects/kodemeio-workspace/kodemeio-platform/deploys/env/production/.env.kod-infra-plausible
```

- [ ] **Step 2: Create Shlink env file**

```bash
cat > ~/project/00-new-projects/kodemeio-workspace/kodemeio-platform/deploys/env/production/.env.kod-infra-shlink <<EOF
DOMAIN=s.kodeme.io
PG_HOST=$KOD_PG_IP
PG_PORT=5432
PG_USER=shlink
PG_PASSWORD=$(op item get shlink --vault=kodemeio-production --fields pg_password --reveal)
PG_DATABASE=shlink
INITIAL_API_KEY=$(op item get shlink --vault=kodemeio-production --fields password --reveal)
GEOLITE_LICENSE_KEY=$(op item get shlink --vault=kodemeio-production --fields geolite_license --reveal)
IS_HTTPS_ENABLED=true
DISABLE_TRACK_PARAM=no-track
REDIRECT_STATUS_CODE=302
DEFAULT_SHORT_CODES_LENGTH=6
ENABLE_PERIODIC_VISIT_LOCATE=true
TIMEZONE=Asia/Jakarta
EOF
chmod 600 ~/project/00-new-projects/kodemeio-workspace/kodemeio-platform/deploys/env/production/.env.kod-infra-shlink
```

- [ ] **Step 3: Verify files are gitignored**

```bash
cd ~/project/00-new-projects/kodemeio-workspace/kodemeio-platform
git check-ignore deploys/env/production/.env.kod-infra-plausible
git check-ignore deploys/env/production/.env.kod-infra-shlink
```

Expected: both paths printed (confirming they are ignored).

- [ ] **Step 4: Validate env file shape**

```bash
for f in deploys/env/production/.env.kod-infra-plausible deploys/env/production/.env.kod-infra-shlink; do
  echo "=== $f ==="
  grep -c '=' "$f"
  grep -c '^$' "$f"
  grep '^$' "$f" || true
  # Ensure no unresolved substitution artifacts
  grep '^\$\|<.*>' "$f" && echo "UNRESOLVED TOKENS in $f" && exit 1
  echo ok
done
```

Expected: no errors, no unresolved tokens.

---

## Task 15: Preflight check

- [ ] **Step 1: Run preflight for Plausible manifest**

```bash
cd ~/project/00-new-projects/kodemeio-workspace/kodemeio-platform
kctl-dokploy -p kodemeio deploy preflight \
    -f deploys/instances/production/kod-infra-plausible.yaml
```

Expected: all 10 gates PASS. If any fail, fix before proceeding (e.g., DNS not yet created is fine — that's Phase 1 of apply; but "server unreachable" or "env sync missing" are blockers).

- [ ] **Step 2: Run preflight for Shlink manifest**

```bash
kctl-dokploy -p kodemeio deploy preflight \
    -f deploys/instances/production/kod-infra-shlink.yaml
```

Expected: all 10 gates PASS.

---

## Task 16: Deploy Plausible

- [ ] **Step 1: Apply the manifest**

```bash
kctl-dokploy -p kodemeio deploy apply \
    -f deploys/instances/production/kod-infra-plausible.yaml
```

Expected: 13-phase pipeline runs through Phase 8 (Verify). Healthcheck passes.

- [ ] **Step 2: Verify live service**

```bash
curl -sS https://plausible.kodeme.io/api/health | jq .
```

Expected: `{"status":"ok"}`.

- [ ] **Step 3: Create admin user**

```bash
# First-time only — register via /register once, then flip DISABLE_REGISTRATION to true.
# DISABLE_REGISTRATION is already true in our env; so bootstrap admin via direct container call.
kctl-dokploy -p kodemeio compose exec \
    --compose-id "$(kctl-dokploy -p kodemeio deploy show -f deploys/instances/production/kod-infra-plausible.yaml --json | jq -r .compose_id)" \
    --service plausible \
    -- "bin/plausible remote" \
    <<'EOS'
:mnesia.start()
Plausible.Auth.User.new!(%{
  name: "Kodemeio Admin",
  email: "admin@kodeme.io",
  password: System.get_env("ADMIN_PASSWORD") || "rotate_me_now"
}) |> Plausible.Repo.insert!()
EOS
```

Alternative if the remote console approach is blocked: temporarily set `DISABLE_REGISTRATION=false`, register via UI, set back to `true`.

Expected: admin user created; can log in at https://plausible.kodeme.io/login.

- [ ] **Step 4: Generate and store admin API key**

```bash
# Log in via UI: https://plausible.kodeme.io → Settings → API Keys → New API Key
# Name: "kctl-plausible admin"
# Copy key, store in 1Password:

PLAUSIBLE_API_KEY="<paste>"
op item edit plausible --vault=kodemeio-production \
    "api_key[password]=$PLAUSIBLE_API_KEY"
```

---

## Task 17: Deploy Shlink

- [ ] **Step 1: Apply the manifest**

```bash
kctl-dokploy -p kodemeio deploy apply \
    -f deploys/instances/production/kod-infra-shlink.yaml
```

Expected: 13-phase pipeline green through Verify.

- [ ] **Step 2: Verify live service**

```bash
curl -sS https://s.kodeme.io/rest/health | jq .
```

Expected: `{"status":"pass"}` (Shlink uses `pass` not `ok`).

- [ ] **Step 3: Verify API key works**

```bash
curl -sS -H "X-Api-Key: $(op item get shlink --vault=kodemeio-production --fields password --reveal)" \
    https://s.kodeme.io/rest/v3/short-urls | jq .
```

Expected: `{"shortUrls":{"data":[],"pagination":{...}}}` (empty list is correct — no URLs yet).

---

## Task 18: Create shared `@kodemeio/analytics` package in kodemeio-react

**Files:**
- Create: `kodemeio-react/packages/analytics/package.json`
- Create: `kodemeio-react/packages/analytics/tsconfig.json`
- Create: `kodemeio-react/packages/analytics/src/SiteAnalytics.tsx`
- Create: `kodemeio-react/packages/analytics/src/index.ts`

- [ ] **Step 1: Create directory + package.json**

```bash
cd ~/project/00-new-projects/kodemeio-workspace/kodemeio-react
mkdir -p packages/analytics/src
```

```json
{
  "name": "@kodemeio/analytics",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "main": "./src/index.ts",
  "types": "./src/index.ts",
  "exports": {
    ".": "./src/index.ts"
  },
  "peerDependencies": {
    "next": "^15.0.0",
    "react": "^19.0.0"
  }
}
```

Save to `packages/analytics/package.json`.

- [ ] **Step 2: Create tsconfig.json**

```json
{
  "extends": "../../tsconfig.base.json",
  "compilerOptions": {
    "outDir": "./dist",
    "rootDir": "./src"
  },
  "include": ["src/**/*"]
}
```

Save to `packages/analytics/tsconfig.json`.

- [ ] **Step 3: Create `src/SiteAnalytics.tsx` (the shared pixel component)**

```tsx
// packages/analytics/src/SiteAnalytics.tsx
"use client";

import Script from "next/script";

export interface SiteAnalyticsProps {
  /** Plausible domain name (matches the site-id in Plausible), e.g. "bas.kodeme.io". */
  plausibleDomain: string;
  /** Plausible script host (defaults to plausible.kodeme.io for this infra). */
  plausibleScriptHost?: string;
  /** Meta (Facebook) Pixel ID. Pass falsy to skip. */
  metaPixelId?: string;
  /** Google Tag (GA4 / Google Ads) measurement ID, e.g. "G-XXXXXXX". Pass falsy to skip. */
  googleTagId?: string;
}

/**
 * Installs Plausible + Meta Pixel + Google Tag on the current page.
 *
 * Drop into the root `app/layout.tsx` of any Next.js App Router site.
 * Uses `next/script` with `strategy="afterInteractive"` — no impact on LCP.
 */
export function SiteAnalytics({
  plausibleDomain,
  plausibleScriptHost = "https://plausible.kodeme.io",
  metaPixelId,
  googleTagId,
}: SiteAnalyticsProps) {
  const plausibleSrc = `${plausibleScriptHost}/js/script.tagged-events.outbound-links.js`;

  return (
    <>
      {/* Plausible — privacy-friendly, cookie-less */}
      <Script
        defer
        data-domain={plausibleDomain}
        src={plausibleSrc}
        strategy="afterInteractive"
      />
      <Script id="plausible-queue" strategy="afterInteractive">
        {`window.plausible = window.plausible || function() { (window.plausible.q = window.plausible.q || []).push(arguments) }`}
      </Script>

      {/* Meta (Facebook) Pixel */}
      {metaPixelId ? (
        <>
          <Script id="meta-pixel" strategy="afterInteractive">
            {`
              !function(f,b,e,v,n,t,s){if(f.fbq)return;n=f.fbq=function(){n.callMethod?n.callMethod.apply(n,arguments):n.queue.push(arguments)};if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';n.queue=[];t=b.createElement(e);t.async=!0;t.src=v;s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)}(window,document,'script','https://connect.facebook.net/en_US/fbevents.js');
              fbq('init', '${metaPixelId}');
              fbq('track', 'PageView');
            `}
          </Script>
          <noscript>
            <img
              height="1"
              width="1"
              style={{ display: "none" }}
              alt=""
              src={`https://www.facebook.com/tr?id=${metaPixelId}&ev=PageView&noscript=1`}
            />
          </noscript>
        </>
      ) : null}

      {/* Google Tag (GA4 + Google Ads) */}
      {googleTagId ? (
        <>
          <Script
            src={`https://www.googletagmanager.com/gtag/js?id=${googleTagId}`}
            strategy="afterInteractive"
          />
          <Script id="google-tag" strategy="afterInteractive">
            {`
              window.dataLayer = window.dataLayer || [];
              function gtag(){dataLayer.push(arguments);}
              gtag('js', new Date());
              gtag('config', '${googleTagId}', { anonymize_ip: true });
            `}
          </Script>
        </>
      ) : null}
    </>
  );
}
```

Save to `packages/analytics/src/SiteAnalytics.tsx`.

- [ ] **Step 4: Create `src/index.ts`**

```ts
// packages/analytics/src/index.ts
export { SiteAnalytics } from "./SiteAnalytics";
export type { SiteAnalyticsProps } from "./SiteAnalytics";
```

Save to `packages/analytics/src/index.ts`.

- [ ] **Step 5: Register in workspace — add to `kodemeio-react/pnpm-workspace.yaml`** (only if not already covered by `packages/*`)

```bash
cd ~/project/00-new-projects/kodemeio-workspace/kodemeio-react
cat pnpm-workspace.yaml
```

If `packages/*` is already listed, no edit needed. Otherwise add:

```yaml
packages:
  - "apps/**"
  - "packages/*"
```

- [ ] **Step 6: Install workspace**

```bash
cd ~/project/00-new-projects/kodemeio-workspace/kodemeio-react
pnpm install
```

Expected: `@kodemeio/analytics` registered as workspace package (verify `pnpm why @kodemeio/analytics` lists no consumers yet — expected, Tasks 19–23 add consumers).

- [ ] **Step 7: Commit**

```bash
git add packages/analytics/
git commit -m "feat(analytics): add shared SiteAnalytics component (Plausible + Meta Pixel + Google Tag)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 19: Wire `<SiteAnalytics>` into `apps/web/kodemeio` (agency site)

**Files:**
- Modify: `kodemeio-react/apps/web/kodemeio/package.json` (add dependency)
- Modify: `kodemeio-react/apps/web/kodemeio/app/layout.tsx`
- Modify: `kodemeio-react/apps/web/kodemeio/.env.example`

- [ ] **Step 1: Add dependency**

```bash
cd ~/project/00-new-projects/kodemeio-workspace/kodemeio-react/apps/web/kodemeio
pnpm add @kodemeio/analytics@workspace:*
```

- [ ] **Step 2: Read current layout.tsx to understand structure**

```bash
head -60 app/layout.tsx
```

- [ ] **Step 3: Modify `app/layout.tsx` — add `<SiteAnalytics>` inside `<body>`**

Insert the import at the top of the file:

```tsx
import { SiteAnalytics } from "@kodemeio/analytics";
```

Inside `RootLayout`'s returned JSX, at the top of `<body>` (before `{children}`):

```tsx
<SiteAnalytics
  plausibleDomain="kodemeio.com"
  metaPixelId={process.env.NEXT_PUBLIC_META_PIXEL_ID}
  googleTagId={process.env.NEXT_PUBLIC_GOOGLE_TAG_ID}
/>
```

- [ ] **Step 4: Update `.env.example`**

Append:

```dotenv
NEXT_PUBLIC_META_PIXEL_ID=
NEXT_PUBLIC_GOOGLE_TAG_ID=
```

- [ ] **Step 5: Local build smoke test**

```bash
cd ~/project/00-new-projects/kodemeio-workspace/kodemeio-react
pnpm --filter kodemeio build
```

Expected: build completes with no TypeScript errors.

- [ ] **Step 6: Commit**

```bash
git add apps/web/kodemeio/ packages/analytics/
git commit -m "feat(kodemeio): install Plausible + pixel tracking

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 20: Wire `<SiteAnalytics>` into `apps/web/corporate`

**Files:**
- Modify: `kodemeio-react/apps/web/corporate/package.json`
- Modify: `kodemeio-react/apps/web/corporate/app/layout.tsx`
- Modify: `kodemeio-react/apps/web/corporate/.env.example`

- [ ] **Step 1: Add dependency**

```bash
cd ~/project/00-new-projects/kodemeio-workspace/kodemeio-react/apps/web/corporate
pnpm add @kodemeio/analytics@workspace:*
```

- [ ] **Step 2: Read current layout.tsx**

```bash
head -60 app/layout.tsx
```

- [ ] **Step 3: Modify `app/layout.tsx`**

Add import:

```tsx
import { SiteAnalytics } from "@kodemeio/analytics";
```

Inside `<body>`, at the top, before `{children}`:

```tsx
<SiteAnalytics
  plausibleDomain="corporate.kodemeio.com"
  metaPixelId={process.env.NEXT_PUBLIC_META_PIXEL_ID}
  googleTagId={process.env.NEXT_PUBLIC_GOOGLE_TAG_ID}
/>
```

Note: `corporate.kodemeio.com` is the Plausible site-id — exactly matches the domain the app is served at in production.

- [ ] **Step 4: Update `.env.example`**

Append:

```dotenv
NEXT_PUBLIC_META_PIXEL_ID=
NEXT_PUBLIC_GOOGLE_TAG_ID=
```

- [ ] **Step 5: Smoke build**

```bash
cd ~/project/00-new-projects/kodemeio-workspace/kodemeio-react
pnpm --filter corporate build
```

Expected: build clean.

- [ ] **Step 6: Commit**

```bash
git add apps/web/corporate/
git commit -m "feat(corporate): install Plausible + pixel tracking

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 21: Wire `<SiteAnalytics>` into `apps/web/provetics` (TPM)

**Files:**
- Modify: `kodemeio-react/apps/web/provetics/package.json`
- Modify: `kodemeio-react/apps/web/provetics/app/layout.tsx`
- Modify: `kodemeio-react/apps/web/provetics/.env.example`

- [ ] **Step 1: Add dependency**

```bash
cd ~/project/00-new-projects/kodemeio-workspace/kodemeio-react/apps/web/provetics
pnpm add @kodemeio/analytics@workspace:*
```

- [ ] **Step 2: Modify `app/layout.tsx`**

Add import:

```tsx
import { SiteAnalytics } from "@kodemeio/analytics";
```

Inside `<body>`, before `{children}`:

```tsx
<SiteAnalytics
  plausibleDomain="provetics.com"
  metaPixelId={process.env.NEXT_PUBLIC_META_PIXEL_ID}
  googleTagId={process.env.NEXT_PUBLIC_GOOGLE_TAG_ID}
/>
```

- [ ] **Step 3: Update `.env.example`**

Append:

```dotenv
NEXT_PUBLIC_META_PIXEL_ID=
NEXT_PUBLIC_GOOGLE_TAG_ID=
```

- [ ] **Step 4: Smoke build**

```bash
cd ~/project/00-new-projects/kodemeio-workspace/kodemeio-react
pnpm --filter provetics build
```

Expected: build clean.

- [ ] **Step 5: Commit**

```bash
git add apps/web/provetics/
git commit -m "feat(provetics): install Plausible + pixel tracking (TPM funnel)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 22: Wire `<SiteAnalytics>` into `apps/web/terakidz` (TMS) — critical: Meta is primary channel

**Files:**
- Modify: `kodemeio-react/apps/web/terakidz/package.json`
- Modify: `kodemeio-react/apps/web/terakidz/src/app/layout.tsx` (note: this app uses `src/`)
- Modify: `kodemeio-react/apps/web/terakidz/.env.example`

- [ ] **Step 1: Add dependency**

```bash
cd ~/project/00-new-projects/kodemeio-workspace/kodemeio-react/apps/web/terakidz
pnpm add @kodemeio/analytics@workspace:*
```

- [ ] **Step 2: Modify `src/app/layout.tsx`**

Add import at top:

```tsx
import { SiteAnalytics } from "@kodemeio/analytics";
```

Inside `<body>`, before `{children}`:

```tsx
<SiteAnalytics
  plausibleDomain="terakidz.com"
  metaPixelId={process.env.NEXT_PUBLIC_META_PIXEL_ID}
  googleTagId={process.env.NEXT_PUBLIC_GOOGLE_TAG_ID}
/>
```

- [ ] **Step 3: Update `.env.example`**

Append:

```dotenv
NEXT_PUBLIC_META_PIXEL_ID=
NEXT_PUBLIC_GOOGLE_TAG_ID=
```

- [ ] **Step 4: Smoke build**

```bash
cd ~/project/00-new-projects/kodemeio-workspace/kodemeio-react
pnpm --filter terakidz build
```

Expected: build clean.

- [ ] **Step 5: Commit**

```bash
git add apps/web/terakidz/
git commit -m "feat(terakidz): install Plausible + pixel tracking (TMS funnel)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 23: Wire `<SiteAnalytics>` into `apps/web/careers`

**Files:**
- Modify: `kodemeio-react/apps/web/careers/package.json`
- Modify: `kodemeio-react/apps/web/careers/src/app/layout.tsx`
- Modify: `kodemeio-react/apps/web/careers/.env.example`

- [ ] **Step 1: Add dependency**

```bash
cd ~/project/00-new-projects/kodemeio-workspace/kodemeio-react/apps/web/careers
pnpm add @kodemeio/analytics@workspace:*
```

- [ ] **Step 2: Modify `src/app/layout.tsx`**

Add import:

```tsx
import { SiteAnalytics } from "@kodemeio/analytics";
```

Inside `<body>`, before `{children}`:

```tsx
<SiteAnalytics
  plausibleDomain="careers.kodemeio.com"
  metaPixelId={process.env.NEXT_PUBLIC_META_PIXEL_ID}
  googleTagId={process.env.NEXT_PUBLIC_GOOGLE_TAG_ID}
/>
```

- [ ] **Step 3: Update `.env.example`**

Append:

```dotenv
NEXT_PUBLIC_META_PIXEL_ID=
NEXT_PUBLIC_GOOGLE_TAG_ID=
```

- [ ] **Step 4: Smoke build**

```bash
pnpm --filter careers build
```

Expected: build clean.

- [ ] **Step 5: Commit**

```bash
git add apps/web/careers/
git commit -m "feat(careers): install Plausible + pixel tracking

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 24: Push kodemeio-react pixel installs

- [ ] **Step 1: Push to origin**

```bash
cd ~/project/00-new-projects/kodemeio-workspace/kodemeio-react
git push origin main
```

- [ ] **Step 2: Set `NEXT_PUBLIC_META_PIXEL_ID` + `NEXT_PUBLIC_GOOGLE_TAG_ID` in each site's Dokploy env**

For each of the five sites (`kodemeio`, `corporate`, `provetics`, `terakidz`, `careers`) that have production Dokploy compose services, pull the Meta Pixel ID + Google Tag ID from a marketing-ops 1Password entry (create if missing):

```bash
# Create item if missing
op item create --category=login --title='marketing-pixels' --vault='kodemeio-production' \
    'username=ops' \
    'password=placeholder' \
    'meta_pixel_id[text]=<paste from Meta Business Manager>' \
    'google_tag_id[text]=<paste from Google Ads / GA4>'

META_PIXEL_ID=$(op item get marketing-pixels --vault=kodemeio-production --fields meta_pixel_id --reveal)
GOOGLE_TAG_ID=$(op item get marketing-pixels --vault=kodemeio-production --fields google_tag_id --reveal)
```

For each site's Dokploy compose service, append to its env file:

```bash
cd ~/project/00-new-projects/kodemeio-workspace/kodemeio-platform
for site in kodemeio corporate provetics terakidz careers; do
  f="deploys/env/production/.env.kod-nextjs-${site}"
  if [ -f "$f" ]; then
    # Remove any prior lines, then append
    sed -i '/^NEXT_PUBLIC_META_PIXEL_ID=/d; /^NEXT_PUBLIC_GOOGLE_TAG_ID=/d' "$f"
    echo "NEXT_PUBLIC_META_PIXEL_ID=$META_PIXEL_ID" >> "$f"
    echo "NEXT_PUBLIC_GOOGLE_TAG_ID=$GOOGLE_TAG_ID" >> "$f"
    echo "updated: $f"
  else
    echo "WARN: $f missing — create Dokploy service for $site first"
  fi
done
```

- [ ] **Step 3: Redeploy each site**

```bash
for site in kodemeio corporate provetics terakidz careers; do
  m="deploys/instances/production/kod-nextjs-${site}.yaml"
  if [ -f "$m" ]; then
    kctl-dokploy -p kodemeio deploy apply -f "$m"
  fi
done
```

Expected: each site redeploys, pixel + Plausible scripts live.

---

## Task 25: Smoke test pixel installation

- [ ] **Step 1: curl each URL and verify scripts present**

```bash
for host in kodemeio.com corporate.kodemeio.com provetics.com terakidz.com careers.kodemeio.com; do
  echo "=== $host ==="
  body=$(curl -sS "https://$host" -H 'User-Agent: Mozilla/5.0 kctl-smoke')
  echo -n "  plausible: "; echo "$body" | grep -qo 'plausible.kodeme.io/js/script' && echo ok || echo MISSING
  echo -n "  meta:      "; echo "$body" | grep -qo "fbq('init'," && echo ok || echo MISSING
  echo -n "  gtag:      "; echo "$body" | grep -qo "gtag('config'," && echo ok || echo MISSING
done
```

Expected output (for each host): three `ok` lines.

- [ ] **Step 2: Open Plausible UI and confirm first events arrive**

1. Log in to https://plausible.kodeme.io
2. (Sites won't exist yet — created in Plan E's bootstrap step)
3. If you haven't yet created sites, visit the test URL below.

- [ ] **Step 3: Verify Meta Pixel in Meta Events Manager**

1. Open https://business.facebook.com/events_manager
2. Select the Pixel corresponding to `$META_PIXEL_ID`
3. "Test Events" tab → paste one of the URLs (e.g., `https://terakidz.com`) → open page → check that `PageView` arrives within 30 seconds

- [ ] **Step 4: Verify Google Tag in GA4 Realtime**

1. Open https://analytics.google.com
2. Select the property for `$GOOGLE_TAG_ID`
3. Reports → Realtime → visit one of the URLs → confirm count increments

---

## Task 26: Commit platform changes and tag

- [ ] **Step 1: Confirm platform git state**

```bash
cd ~/project/00-new-projects/kodemeio-workspace/kodemeio-platform
git status
```

Expected: clean working tree (all env files are gitignored; deploy manifests and bases are already committed).

- [ ] **Step 2: Push**

```bash
git push origin main
```

- [ ] **Step 3: Tag Wave 1a milestone**

```bash
git tag -a marketing-wave-1a -m "Marketing Wave 1a complete: Plausible + Shlink live; pixels installed"
git push origin marketing-wave-1a
```

---

## Exit criteria (Plan A done-done)

All of the following must hold before starting Plan B/C/D:

- [ ] `https://plausible.kodeme.io/api/health` returns `{"status":"ok"}`
- [ ] `https://s.kodeme.io/rest/health` returns `{"status":"pass"}`
- [ ] Admin API keys stored in 1Password vault `kodemeio-production` (`plausible.api_key`, `shlink.password` = `INITIAL_API_KEY`)
- [ ] All five Next.js marketing apps (`kodemeio`, `corporate`, `provetics`, `terakidz`, `careers`) have `@kodemeio/analytics` installed and `<SiteAnalytics>` in their root `layout.tsx`
- [ ] All five live URLs return HTML containing the three tracker snippets (Task 25 Step 1 green)
- [ ] ClickHouse backup script present and executable at `/usr/local/bin/backup-clickhouse.sh` inside the clickhouse container
- [ ] Git tag `marketing-wave-1a` pushed

Plan B (`kctl-plausible`) can now begin — the profile `kodemeio-kod-infra-plausible` will be populated from the API key in 1Password during its Task 1.

## Notes

- **bas.kodeme.io** and **hrm.kodeme.io** subdomains are not installed with pixels in Plan A because their frontends are served by `apps/web/corporate` (subdomain-routed). If either becomes a separately-deployed Next.js app later, repeat Task 19's pattern for that app.
- **mandiriagro**, **pakerti**, **trigunawan** are customer-owned tenant brand sites — out of scope for Kodemeio growth.
- Plan E will create Plausible sites (via `kctl-plausible sites bootstrap`), install goals, and run the final end-to-end pixel-firing verification via `kctl-plausible doctor`.
