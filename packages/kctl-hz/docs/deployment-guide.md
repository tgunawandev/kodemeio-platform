# Kodemeio Hetzner Deployment Guide

Complete guide for deploying the Kodemeio platform on Hetzner Cloud using Terraform.

## Architecture Overview

```
                                 ┌─────────────────────────────┐
                                 │       Hetzner Cloud         │
                                 │        (fsn1 / EU)          │
                                 │                             │
  Internet ──► Firewall(web) ──► │  ┌───────────────────────┐  │
                                 │  │  dokploy (cx42)       │  │
                                 │  │  8 vCPU / 16 GB RAM   │  │
                                 │  │                       │  │
                                 │  │  Traefik (reverse     │  │
                                 │  │    proxy + TLS)       │  │
                                 │  │  Dokploy (orchestr.)  │  │
                                 │  │                       │  │
                                 │  │  ┌─── kodemeio-app ─┐ │  │
                                 │  │  │ React SPAs (8)   │ │  │
                                 │  │  │ Next.js Web (3)  │ │  │
                                 │  │  │ FastAPI (13)     │ │  │
                                 │  │  │ Odoo 18          │ │  │
                                 │  │  └──────────────────┘ │  │
                                 │  │                       │  │
                                 │  │  ┌─── kodemeio-core ┐ │  │
                                 │  │  │ Authentik (SSO)  │ │  │
                                 │  │  │ Plane (PM)       │ │  │
                                 │  │  │ Grafana stack    │ │  │
                                 │  │  │ Mailcow (email)  │ │  │
                                 │  │  │ Gatus (uptime)   │ │  │
                                 │  │  │ Outline (wiki)   │ │  │
                                 │  │  │ OpenClaw (AI)    │ │  │
                                 │  │  │ RustDesk/RMM     │ │  │
                                 │  │  └──────────────────┘ │  │
                                 │  └──────────┬────────────┘  │
                                 │             │ private net   │
                                 │             │ 10.0.1.0/24   │
                                 │  ┌──────────▼────────────┐  │
                                 │  │  db (cx32)            │  │
  Firewall(database) ──────────► │  │  4 vCPU / 8 GB RAM    │  │
  (private network only)         │  │                       │  │
                                 │  │  PostgreSQL 16        │  │
                                 │  │  PgBouncer (pool)     │  │
                                 │  │  Redis 7 (cache/queue)│  │
                                 │  │  postgres-exporter    │  │
                                 │  └───────────────────────┘  │
                                 │                             │
                                 │  S3 Object Storage ────────►│
                                 │  fsn1.your-objectstorage    │
                                 └─────────────────────────────┘
```

## Server Sizing Guide

### Option A: Single Server (Simplest)

| Server | Type | Specs | Monthly Cost |
|--------|------|-------|-------------|
| dokploy | cx52 | 16 vCPU, 32 GB RAM, 320 GB | ~€65 |
| **Total** | | | **~€75** (+ volumes, IPs) |

Best for: development, staging, or <50 concurrent users.

### Option B: 2-Server Split (Recommended)

| Server | Type | Specs | Role | Monthly Cost |
|--------|------|-------|------|-------------|
| dokploy | cx42 | 8 vCPU, 16 GB RAM, 160 GB | All apps via Dokploy | ~€35 |
| db | cx32 | 4 vCPU, 8 GB RAM, 80 GB | PostgreSQL + Redis | ~€18 |
| **Total** | | | | **~€63** (+ volumes, IPs, backups) |

Best for: production with up to ~500 concurrent users.

### Option C: 3-Server Split (Scale-Ready)

| Server | Type | Specs | Role | Monthly Cost |
|--------|------|-------|------|-------------|
| web | cx32 | 4 vCPU, 8 GB RAM | Frontend SPAs + Next.js | ~€18 |
| api | cx42 | 8 vCPU, 16 GB RAM | Backend APIs + workers | ~€35 |
| db | cx42 | 8 vCPU, 16 GB RAM | PostgreSQL + Redis | ~€35 |
| **Total** | | | | **~€98** (+ volumes, IPs, backups) |

Best for: production with 500+ concurrent users.

### ARM Alternative (30% cheaper)

Use `cax` series instead of `cx` for non-x86 workloads:

| x86 Type | ARM Equivalent | Savings |
|----------|---------------|---------|
| cx32 | cax21 | ~30% |
| cx42 | cax31 | ~30% |
| cx52 | cax41 | ~30% |

> Note: Ensure all Docker images support `linux/arm64`.

## Prerequisites

1. **Hetzner Cloud account** with API token
2. **Terraform** >= 1.0 installed
3. **SSH key pair** for server access
4. **Domain** configured (kodeme.io)
5. **Hetzner S3** bucket for Terraform state (optional)

## Step-by-Step Deployment

### 1. Clone and Configure

```bash
cd infra/hetzner
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` with your actual values:
- `hcloud_token` - from Hetzner Cloud Console > API Tokens
- `ssh_keys` - your actual SSH public keys
- Server sizes based on your chosen architecture option

### 2. Enable Remote State (Recommended)

Uncomment the S3 backend in `main.tf` and create the bucket:

```bash
# Create state bucket via hcloud-mgr or Hetzner Console
# Then uncomment backend "s3" block in main.tf
```

### 3. Initialize Terraform

```bash
terraform init
```

### 4. Plan and Review

```bash
terraform plan -out=plan.tfplan
```

Review the plan carefully. Expected resources for Option B:
- 2 servers (dokploy + db)
- 1 private network + 1 subnet
- 2 firewalls (web + database)
- 2 SSH keys
- 3 volumes (dokploy-data, pg-data, pg-backup)
- 1 placement group
- 2 reverse DNS entries

### 5. Apply

```bash
terraform apply plan.tfplan
```

### 6. Post-Deploy: Dokploy Server Setup

SSH into the dokploy server and verify:

```bash
ssh root@<dokploy-ip>

# Check Dokploy is running
docker ps | grep dokploy

# Access Dokploy UI at https://dokploy.kodeme.io:3000
# Set up admin account on first visit
```

### 7. Post-Deploy: Database Server Setup

SSH into the db server:

```bash
ssh root@<db-ip>

# Mount the data volume
lsblk  # Find the volume device
mkdir -p /mnt/pg-data /mnt/pg-backup

# Clone and deploy kodemeio-postgres-16
git clone https://github.com/tgunawandev/kodemeio-postgres-16.git
cd kodemeio-postgres-16
cp .env.example .env.prod
# Edit .env.prod with database credentials
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d
```

### 8. Deploy Application Stacks via Dokploy

In Dokploy UI, add each service from GitHub:

**kodemeio-core services:**
1. `kodemeio-authentik` - SSO/Identity (deploy first)
2. `kodemeio-grafana` - Monitoring stack
3. `kodemeio-gatus` - Uptime monitoring
4. `kodemeio-plane` - Project management
5. `kodemeio-mailcow` - Email server
6. `kodemeio-outline` - Wiki
7. `kodemeio-telegram` - Telegram bots
8. `kodemeio-glitchtip` - Error tracking
9. `kodemeio-zulip` - Team chat
10. `kodemeio-rustdesk` - Remote access
11. `kodemeio-rmm` - Device management

**kodemeio-app services:**
1. `kodemeio-python` - FastAPI backend (api-main, worker, webhooks)
2. `kodemeio-react-spa` - React business apps (SFA, WMS, HRM, etc.)
3. `kodemeio-next-web` - Next.js websites (corporate, portfolio, careers)
4. `kodemeio-odoo-18` - ERP system
5. `kodemeio-openclaw` - AI agent gateway

### 9. DNS Configuration

Point your domains to the dokploy server IP:

```
*.kodeme.io          → A    → <dokploy-ipv4>
kodeme.io            → A    → <dokploy-ipv4>
mail.kodeme.io       → A    → <dokploy-ipv4>
```

Required DNS records for Mailcow:
```
mail.kodeme.io       → A     → <dokploy-ipv4>
kodeme.io            → MX 10 → mail.kodeme.io
kodeme.io            → TXT   → "v=spf1 ip4:<dokploy-ipv4> -all"
dkim._domainkey      → TXT   → <from-mailcow-ui>
_dmarc.kodeme.io     → TXT   → "v=DMARC1; p=quarantine; rua=mailto:dmarc@kodeme.io"
```

## Container Inventory

### kodemeio-app (~30 containers)

| Service | Type | Port | Memory |
|---------|------|------|--------|
| api-main | FastAPI | 8000 | 512MB |
| worker | ARQ | - | 256MB |
| odoo-mm (webhook) | FastAPI | 8003 | 256MB |
| odoo-mm (events) | Worker | - | 256MB |
| plane-mm (webhook) | FastAPI | 8004 | 256MB |
| plane-mm (events) | Worker | - | 256MB |
| webhook-github | FastAPI | 8005 | 128MB |
| webhook-chatwoot | FastAPI | 8006 | 128MB |
| events-sync | Worker | - | 256MB |
| agent-main | Worker | - | 512MB |
| etl-main | Worker | - | 256MB |
| mcp-main | Worker | - | 256MB |
| scheduler-main | Worker | - | 128MB |
| stream-main | FastAPI | 8002 | 256MB |
| sfa | React SPA | 4004 | 64MB |
| lfa | React SPA | - | 64MB |
| shop | React SPA | 4006 | 64MB |
| wms | React SPA | - | 64MB |
| hrm | React SPA | - | 64MB |
| mrp | React SPA | - | 64MB |
| bia | React SPA | - | 64MB |
| eam | React SPA | - | 64MB |
| corporate | Next.js | - | 256MB |
| portfolio | Next.js | - | 256MB |
| careers | Next.js | - | 256MB |
| odoo-18 | Odoo | 8069 | 2GB |
| openclaw | AI Gateway | 18789 | 512MB |
| redis | Redis 7 | 6379 | 256MB |

### kodemeio-core (~25 containers)

| Service | Type | Memory |
|---------|------|--------|
| authentik-server | Django | 1GB |
| authentik-worker | Celery | 512MB |
| authentik-ldap | LDAP | 128MB |
| plane-api | Django | 2GB |
| plane-worker | Celery | 512MB |
| plane-web | Next.js | 512MB |
| plane-proxy | Nginx | 64MB |
| plane-mattermost | Node.js | 128MB |
| grafana | Go | 512MB |
| prometheus | Go | 512MB |
| loki | Go | 512MB |
| alertmanager | Go | 128MB |
| promtail | Go | 128MB |
| node-exporter | Go | 64MB |
| cadvisor | Go | 128MB |
| gatus | Go | 128MB |
| outline | Node.js | 512MB |
| glitchtip | Django | 512MB |
| mailcow (stack) | Multi | 2GB |
| zulip | Django | 4GB |
| telegram-bot | FastAPI | 256MB |
| rustdesk-hbbs | Rust | 64MB |
| rustdesk-hbbr | Rust | 64MB |
| rmm-api | Go | 512MB |
| meshcentral | Node.js | 512MB |

**Total estimated memory: ~22 GB** (justifies cx42 for app server)

## Cost Estimation (Option B)

| Resource | Monthly Cost |
|----------|-------------|
| cx42 (dokploy) | €34.49 |
| cx32 (db) | €17.49 |
| Volume 80GB (dokploy-data) | €3.84 |
| Volume 100GB (pg-data) | €4.80 |
| Volume 50GB (pg-backup) | €2.40 |
| 2x Server backups | ~€5.20 |
| S3 Object Storage | ~€5-10 |
| IPv4 addresses (2) | included |
| **Total** | **~€73-78/mo** |

## Scaling Path

When you outgrow Option B:

1. **Vertical**: Upgrade cx42 → cx52 (16 vCPU, 32 GB) via Terraform
2. **Split**: Move heavy services (Odoo, Zulip, Mailcow) to a 3rd server
3. **Add Load Balancer**: For web tier HA (lb11 = €5.39/mo)
4. **Database Replica**: Add read replica for PostgreSQL
5. **ARM migration**: Switch to cax series for 30% cost savings

## Backup Strategy

1. **Server backups**: Enabled via Terraform (`backups = true`)
2. **PostgreSQL**: Automated S3 backups via pgBackRest/pg_dump
3. **Volumes**: Hetzner volume snapshots (via hcloud-mgr)
4. **Terraform state**: S3 remote backend with versioning
5. **Application data**: Docker volume backups to S3

## Security Checklist

- [x] Firewall rules: web server only exposes 22, 80, 443, 3000
- [x] Firewall rules: database only accessible from private network
- [x] SSH: key-only auth, no password login
- [x] Private network: database traffic never hits public internet
- [x] Cloud-init: fail2ban, UFW, SSH hardening applied automatically
- [x] Delete protection: enabled on production servers
- [x] Backups: automated daily backups
- [ ] SSH port: consider changing from 22 (set `ssh_port` variable)
- [ ] Hetzner API token: rotate regularly
- [ ] S3 credentials: separate per-service access keys
