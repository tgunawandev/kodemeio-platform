# Infrastructure Reference

## Hetzner Cloud Resources

### Server Types

| Type | vCPU | RAM | Disk | Architecture | ~EUR/month |
|------|------|-----|------|-------------|------------|
| cx22 | 2 | 4 GB | 40 GB | x86 (shared) | 3.99 |
| cx32 | 4 | 8 GB | 80 GB | x86 (shared) | 7.49 |
| cx42 | 8 | 16 GB | 160 GB | x86 (shared) | 14.49 |
| cx52 | 16 | 32 GB | 320 GB | x86 (shared) | 28.49 |
| cax11 | 2 | 4 GB | 40 GB | ARM (shared) | 3.49 |
| cax21 | 4 | 8 GB | 80 GB | ARM (shared) | 5.49 |
| cax31 | 8 | 16 GB | 160 GB | ARM (shared) | 8.49 |
| cax41 | 16 | 32 GB | 320 GB | ARM (shared) | 14.49 |
| ccx13 | 2 | 8 GB | 80 GB | x86 (dedicated) | 12.49 |
| ccx23 | 4 | 16 GB | 160 GB | x86 (dedicated) | 22.49 |
| ccx33 | 8 | 32 GB | 240 GB | x86 (dedicated) | 42.49 |
| ccx43 | 16 | 64 GB | 360 GB | x86 (dedicated) | 82.49 |

### Locations

| Code | City | Country |
|------|------|---------|
| fsn1 | Falkenstein | Germany |
| nbg1 | Nuremberg | Germany |
| hel1 | Helsinki | Finland |
| ash | Ashburn | USA |
| hil | Hillsboro | USA |
| sin | Singapore | Singapore |

### Additional Costs

| Resource | Price |
|----------|-------|
| Primary IPv4 | 0.50/month (included in server) |
| Floating IPv4 | 4.63/month |
| Floating IPv6 | Free |
| Volume storage | 0.0524/GB/month |
| Snapshot storage | 0.0119/GB/month |
| Load Balancer (lb11) | 6.45/month |
| Load Balancer (lb21) | 14.49/month |
| Load Balancer (lb31) | 28.49/month |

All prices in EUR, excluding VAT. Traffic included (20-60 TB depending on server type).

### API Rate Limits

- Cloud API: 3,600 requests/hour
- DNS API: Separate rate limit
- Rate limit headers: `X-Ratelimit-Limit`, `X-Ratelimit-Remaining`, `X-Ratelimit-Reset`

### API Endpoints

| API | Base URL | Authentication |
|-----|----------|---------------|
| Cloud | `https://api.hetzner.cloud/v1` | `Authorization: Bearer TOKEN` |
| DNS | `https://dns.hetzner.com/api/v1` | `Auth-API-Token: TOKEN` |

## Kodemeio Platform Architecture

### Technology Stack

| Layer | Technology | Source |
|-------|-----------|--------|
| Frontend (Business) | React 19 + Vite + Tailwind (8 SPAs) | kodemeio-app |
| Frontend (Web) | Next.js 16 + React 19 (3 sites) | kodemeio-app |
| Backend API | FastAPI + SQLAlchemy 2.0 async (13 services) | kodemeio-app |
| ERP | Odoo 18 | kodemeio-app |
| AI Gateway | OpenClaw (Claude Sonnet 4) | kodemeio-app |
| Identity/SSO | Authentik (OIDC/LDAP) | kodemeio-core |
| Project Management | Plane | kodemeio-core |
| Monitoring | Prometheus + Grafana + Loki + AlertManager | kodemeio-core |
| Uptime | Gatus | kodemeio-core |
| Error Tracking | GlitchTip (Sentry-compatible) | kodemeio-core |
| Email | Mailcow | kodemeio-core |
| Wiki | Outline | kodemeio-core |
| Team Chat | Zulip | kodemeio-core |
| Remote Access | RustDesk + Tactical RMM | kodemeio-core |
| Database | PostgreSQL 16 + PgBouncer | kodemeio-core |
| Cache/Queue | Redis 7 + ARQ | kodemeio-app |
| Object Storage | Hetzner S3 (fsn1) | Hetzner |
| Orchestration | Dokploy + Docker Compose | - |
| Reverse Proxy | Traefik + Let's Encrypt | Dokploy |

### Subdomains

| Subdomain | Service | Source |
|-----------|---------|--------|
| dokploy.kodeme.io | Dokploy orchestrator | kodemeio-core |
| auth.kodeme.io | Authentik SSO | kodemeio-core |
| mm.kodeme.io | Mattermost | kodemeio-core |
| mail.kodeme.io | Mailcow | kodemeio-core |
| plane.kodeme.io | Plane PM | kodemeio-core |
| grafana.kodeme.io | Grafana | kodemeio-core |
| status.kodeme.io | Gatus | kodemeio-core |
| wiki.kodeme.io | Outline | kodemeio-core |
| glitchtip.kodeme.io | GlitchTip | kodemeio-core |
| zulip.kodeme.io | Zulip | kodemeio-core |
| rustdesk.kodeme.io | RustDesk | kodemeio-core |
| rmm.kodeme.io | Tactical RMM | kodemeio-core |
| api.kodeme.io | FastAPI main | kodemeio-app |
| sfa.kodeme.io | Sales Force App | kodemeio-app |
| shop.kodeme.io | B2B Shop | kodemeio-app |
| wms.kodeme.io | Warehouse Mgmt | kodemeio-app |
| hrm.kodeme.io | HR Management | kodemeio-app |
| erp.kodeme.io | Odoo 18 | kodemeio-app |
| kodeme.io | Corporate site | kodemeio-app |

### Current Infrastructure

| Name | IP | Type | Location | Role |
|------|----|------|----------|------|
| dokploy.kodeme.io | 168.119.233.161 | - | fsn1 | Container orchestration |

### Recommended Architecture (2-Server)

```
Internet
  │
  └── Hetzner Cloud (fsn1)
        │
        ├── dokploy (cx42 - 8 vCPU, 16 GB RAM)
        │     ├── Traefik (reverse proxy + TLS)
        │     ├── Dokploy (orchestrator UI)
        │     │
        │     ├── kodemeio-app containers (~30)
        │     │   ├── React SPAs (8 nginx containers)
        │     │   ├── Next.js sites (3 node containers)
        │     │   ├── FastAPI services (13 uvicorn)
        │     │   ├── Odoo 18 (+ internal postgres)
        │     │   ├── OpenClaw AI gateway
        │     │   └── Redis 7 (app cache/queue)
        │     │
        │     └── kodemeio-core containers (~25)
        │         ├── Authentik (server + worker + LDAP)
        │         ├── Plane (api + worker + web + proxy)
        │         ├── Grafana stack (6 containers)
        │         ├── Gatus + discovery
        │         ├── Mailcow (8+ containers)
        │         ├── Outline + redis
        │         ├── GlitchTip + celery
        │         ├── Zulip (+ internal services)
        │         ├── Telegram bot
        │         ├── RustDesk (hbbs + hbbr)
        │         └── Tactical RMM + MeshCentral
        │
        ├── Private Network (10.0.1.0/24)
        │
        ├── db (cx32 - 4 vCPU, 8 GB RAM)
        │     ├── PostgreSQL 16 (shared)
        │     │   └── Databases: plane, authentik, glitchtip,
        │     │       outline, telegram, zulip, gatus, kodemeio_python
        │     ├── PgBouncer (connection pooling)
        │     ├── Redis 7 (central, optional)
        │     └── postgres-exporter (metrics)
        │
        └── Object Storage (S3)
              └── fsn1.your-objectstorage.com
                  ├── kodemeio-authentik-data
                  ├── kodemeio-glitchtip
                  ├── kodemeio-zulip-uploads
                  ├── kodemeio-zulip-avatars
                  ├── kodemeio-rustdesk-data
                  ├── kodemeio-dokploy (db backups)
                  ├── kodemeio-terraform-state
                  └── hz-kodemeio-gatus
```

### Best Practices

1. **Always use private networks** for inter-service communication
2. **Apply firewalls** to all servers - restrict SSH to known IPs
3. **Enable backups** for critical servers
4. **Use snapshots** before major changes (rebuild, resize)
5. **Monitor costs** with `hcloud-mgr costs` regularly
6. **Rotate API tokens** periodically
7. **Use labels** consistently for resource organization
8. **Store Terraform state remotely** (S3 backend) for team collaboration
9. **Separate database** from app server for isolation and independent scaling
10. **Use PgBouncer** to handle connection pooling across 8+ databases
