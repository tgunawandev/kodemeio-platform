# Monitoring-as-Code

Declarative monitoring configuration for the Kodemeio platform. All configs are version-controlled and applied via `kctl-*` CLIs.

## Stack

| Tool | Purpose | CLI | URL |
|------|---------|-----|-----|
| Grafana | Dashboards, visualization & uptime | `kctl-grafana` | grafana.kodeme.io |
| GlitchTip | Error tracking & DSN keys | `kctl-glitchtip` | glitchtip.kodeme.io |
| Prometheus | Metrics collection & alerting | (via Grafana) | prometheus.kodeme.io |

> **Note:** Uptime and health check monitoring is handled by Grafana (via `kctl-grafana`). Gatus has been removed.

## Directory Structure

```
monitoring/
├── README.md                              # This file
├── grafana/
│   ├── dashboards/
│   │   └── platform-overview.json         # Main platform dashboard
│   └── datasources/
│       └── prometheus.yaml                # Prometheus datasource provisioning
├── alerts/
│   └── rules.yaml                         # Prometheus alerting rules
└── scripts/
    └── apply-monitoring.sh                # Apply all configs via kctl-* CLIs
```

## Quick Start

Apply all monitoring configs in one shot:

```bash
./ops/monitoring/scripts/apply-monitoring.sh
```

Or apply individual components:

```bash
# Grafana dashboards
kctl-grafana dashboard import ops/monitoring/grafana/dashboards/platform-overview.json

# Grafana datasources
kctl-grafana datasource list

# Grafana alert rules
kctl-grafana alert list
```

## Service Inventory

### Odoo Instances (6)

| Service | URL | Health Endpoint |
|---------|-----|-----------------|
| Odoo Production (kodeme.io) | odoo.kodeme.io | /web/health |
| Odoo HRMS (kodeme.io) | odoo-hrms.kodeme.io | /web/health |
| Odoo Trading (mandiriagro.com) | odoo.mandiriagro.com | /web/health |
| Odoo HRMS (mandiriagro.com) | odoo-hrms.mandiriagro.com | /web/health |
| Odoo Trading (pakerti.com) | odoo.pakerti.com | /web/health |
| Odoo HRMS (pakerti.com) | odoo-hrms.pakerti.com | /web/health |

### Next.js Websites (5)

| Service | URL | Health Endpoint |
|---------|-----|-----------------|
| kodeme.io | kodeme.io | / |
| mandiriagro.com | mandiriagro.com | / |
| pakerti.com | pakerti.com | / |
| terakidz.com | terakidz.com | / |
| trigunawan.com | trigunawan.com | / |

### Infrastructure Services (8)

| Service | URL | Health Endpoint |
|---------|-----|-----------------|
| Authentik SSO | auth.kodeme.io | /-/health/ready/ |
| Grafana | grafana.kodeme.io | /api/health |
| GlitchTip | glitchtip.kodeme.io | /_health/ |
| Mailcow | mail.kodeme.io | / |
| WAHA | waha.kodeme.io | /api/health |
| Tactical RMM | rmm.kodeme.io | / |
| RustDesk | rustdesk.kodeme.io | / |

### Database

| Service | Host | Port | Check |
|---------|------|------|-------|
| PostgreSQL 16 | 10.0.0.3 | 5432 | TCP |

### DNS

All 6 domains are verified via DNS resolution checks.

## Alert Channels

| Channel | Target | Used For |
|---------|--------|----------|
| Telegram | @kodemeio_alerts | Critical: PostgreSQL, Authentik, Traefik |
| Webhook | Slack-compatible | Non-critical: websites, Odoo instances |

## Alert Thresholds

- **Trigger**: 3 consecutive failures
- **Resolve**: 2 consecutive successes
- **Check intervals**: 60s (critical), 120s (standard), 300s (DNS)

## Adding a New Service

1. Add a panel to the Grafana dashboard if needed
2. Add alert rules in `alerts/rules.yaml` if the service has Prometheus metrics
3. Run `./ops/monitoring/scripts/apply-monitoring.sh`

## Maintenance

- Review alert noise monthly: tune thresholds or mute flapping endpoints
- Rotate Telegram bot token and webhook URLs via 1Password (`kctl-op`)
- Dashboard JSON should be exported after manual edits: `kctl-grafana dashboard export <uid> -o ops/monitoring/grafana/dashboards/platform-overview.json`
