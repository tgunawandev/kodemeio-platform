# Developer Onboarding Guide

> Time to complete: ~30 minutes

## Prerequisites

| Tool | Install | Verify |
|------|---------|--------|
| Python 3.12+ | `brew install python@3.12` | `python3 --version` |
| uv | `curl -LsSf https://astral.sh/uv/install.sh \| sh` | `uv --version` |
| just | `brew install just` or `cargo install just` | `just --version` |
| git | Pre-installed | `git --version` |
| Docker | [docs.docker.com](https://docs.docker.com/get-docker/) | `docker --version` |

## Step 1: Clone and Install

```bash
git clone https://github.com/tgunawandev/kodemeio-dokploy.git
cd kodemeio-dokploy

# Install all packages + dev dependencies
just install
# or: uv sync --all-extras --all-packages
```

This installs kctl-lib + all 22 CLI tools in development mode.

## Step 2: Verify Installation

```bash
# Run the full quality gate
just check

# Or individually:
just test           # kctl-lib tests (247 tests)
just test-integration   # Cross-package tests (108 tests)
just lint           # Lint all packages
```

## Step 3: Configure CLI Profiles

All 22 kctl-* CLIs share one config file: `~/.config/kodemeio/config.yaml`.

```bash
# Initialize config for key services (interactive)
kctl-dokploy config init    # Deployment platform
kctl-pg config init         # PostgreSQL
kctl-cf config init         # Cloudflare
kctl-ak config init         # Authentik SSO
kctl-odoo config init       # Odoo ERP

# Verify config
kctl-dokploy config validate
```

### Minimal Config Example

```yaml
default_profile: default
profiles:
  default:
    dokploy:
      url: https://dokploy.kodeme.io
      api_key: ${DOKPLOY_API_KEY}
    postgres:
      host: 10.0.0.3
      port: 5432
      user: postgres
      password: ${PG_PASSWORD}
    cloudflare:
      api_token: ${CF_API_TOKEN}
    authentik:
      url: https://auth.kodeme.io
      api_key: ${AK_API_KEY}
    odoo:
      url: https://odoo.kodeme.io
      database: kodemeio_prod
      api_key: ${ODOO_API_KEY}
```

Secrets use `${VAR}` syntax — set them in your shell profile or 1Password:

```bash
# Pull secrets from 1Password (if configured)
kctl-op env pull --vault kodemeio --env .env.local
source .env.local
```

## Step 4: Verify Service Access

```bash
# Check connectivity to all services
kctl-dokploy health          # Deployment platform
kctl-pg health               # PostgreSQL
kctl-ak health               # Authentik SSO
kctl-odoo health             # Odoo ERP
kctl-grafana status          # Grafana dashboards & health monitoring
```

## Step 5: Understand the Architecture

Read these docs in order:

1. **[Service Map](service-map.md)** — What depends on what, blast radius analysis
2. **[Architecture](architecture.md)** — 22 CLI packages, API client patterns, deployment system
3. **[CLI Standards](cli-standards.md)** — Naming conventions, global options, command patterns
4. **[CLAUDE.md](../CLAUDE.md)** — Quick command reference, key paths, conventions

## Common Tasks

### Run tests for a specific package

```bash
just test-pkg kctl-dokploy
```

### Validate a deploy manifest

```bash
just deploy-validate deploys/instances/kodeme.io-odoo-full.yaml
```

### Check backup health

```bash
just verify-backups
```

### Check environment drift

```bash
just check-env
```

### Scaffold a new CLI

```bash
just new-cli kctl-myservice
# Follow the interactive prompts
```

### Regenerate CLI docs

```bash
just docs
```

## Key Directories

```
kodemeio-dokploy/
├── packages/kctl-lib/     # Shared library (edit here for cross-cutting changes)
├── packages/kctl-*/       # 21 CLI packages
├── deploys/               # Deployment manifests (bases + instances + env)
├── monitoring/            # Gatus endpoints, Grafana dashboards, alert rules
├── runbooks/              # Incident response procedures
├── scripts/               # Operational scripts
├── templates/             # Copier templates for new CLIs
├── tests/                 # Cross-package integration tests
├── docs/                  # Architecture, standards, CLI reference
├── infra/                 # Terraform modules (Cloudflare, Hetzner)
└── justfile               # Common commands: just --list
```

## Environment Access

| Service | URL | Auth |
|---------|-----|------|
| Dokploy | dokploy.kodeme.io | API key |
| Authentik | auth.kodeme.io | OIDC / API key |
| Grafana | grafana.kodeme.io | Authentik SSO |
| GlitchTip | glitchtip.kodeme.io | Authentik SSO |
| Odoo | odoo.kodeme.io | Authentik SSO / API key |
| PostgreSQL | 10.0.0.3:5432 | Private network only |

## Troubleshooting

### "ConfigError: No URL configured"

You haven't initialized the CLI profile:
```bash
kctl-<service> config init
```

### "AuthenticationError: 401"

Your API key is expired or wrong. Check:
```bash
kctl-<service> config show   # Verify config (secrets masked)
```

### Tests fail with import errors

Re-install the workspace:
```bash
just install
```

### Can't reach services

You need VPN or SSH access to the Hetzner private network (10.0.0.0/8) for PostgreSQL. Other services are public via HTTPS.
