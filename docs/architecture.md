# Kodemeio Platform Architecture

Single monorepo workspace: `kctl-lib` shared library + 21 CLI tools.

## CLI Ecosystem

22 packages total, all sharing `kctl-lib` as their foundation.

### Shared Library

| Package | Version | PyPI | Tests |
|---------|---------|------|-------|
| kctl-lib | v0.4.0 | Published | 247 |

### Infrastructure & Ops (9 CLIs)

| CLI | Target | Groups |
|-----|--------|--------|
| kctl-dokploy | Dokploy deployment platform | 37 |
| kctl-hz | Hetzner Cloud infrastructure | 24 |
| kctl-pg | PostgreSQL administration | 24 |
| kctl-cf | Cloudflare DNS/CDN/WAF | 27 |
| kctl-ak | Authentik SSO/identity | 24 |
| kctl-grafana | Grafana monitoring platform | 11 |
| kctl-gatus | Gatus health monitoring | 8 |
| kctl-rustdesk | RustDesk server management | 9 |
| kctl-waha | WhatsApp HTTP API | 8 |

### Application Management (4 CLIs)

| CLI | Target | Groups |
|-----|--------|--------|
| kctl-odoo | Odoo 18 ERP management | 70+ |
| kctl-api | FastAPI platform management | 46 |
| kctl-react | React PWA monorepo management | 31 |
| kctl-claw | AI agent gateway management | 29 |

### Developer & SaaS Tools (8 CLIs)

| CLI | Target | Groups |
|-----|--------|--------|
| kctl-op | 1Password secret management | 9 |
| kctl-github | Cross-repo GitHub management | 10 |
| kctl-sentry | Sentry error tracking | 10 |
| kctl-linear | Linear project/sprint tracking | 9 |
| kctl-claude | Claude Code environment management | 8 |
| kctl-telegram | Telegram bot platform | 7 |
| kctl-notion | Notion wiki/database management | 7 |
| kctl-glitchtip | GlitchTip error monitoring | — |

### Remote Management (1 CLI)

| CLI | Target | Groups |
|-----|--------|--------|
| kctl-rmm | Remote device management | — |

## Dependency Flow

```
kctl-lib v0.4.0 (PyPI)
  │
  ├── Infrastructure & Ops
  │   ├── kctl-dokploy
  │   ├── kctl-hz
  │   ├── kctl-pg
  │   ├── kctl-cf
  │   ├── kctl-ak
  │   ├── kctl-grafana
  │   ├── kctl-gatus
  │   ├── kctl-rustdesk
  │   └── kctl-waha
  │
  ├── Application Management
  │   ├── kctl-odoo
  │   ├── kctl-api
  │   ├── kctl-react
  │   └── kctl-claw
  │
  ├── Developer & SaaS Tools
  │   ├── kctl-op
  │   ├── kctl-github
  │   ├── kctl-sentry
  │   ├── kctl-linear
  │   ├── kctl-claude
  │   ├── kctl-telegram
  │   ├── kctl-notion
  │   └── kctl-glitchtip
  │
  └── Remote Management
      └── kctl-rmm
```

## Shared Config

All CLIs share `~/.config/kodemeio/config.yaml` with service-scoped profiles and env var expansion:

```yaml
default_profile: default
profiles:
  default:
    dokploy:  { url: https://dokploy.kodeme.io, api_key: ${DOKPLOY_API_KEY} }
    hz:       { api_key: ${HETZNER_API_KEY} }
    pg:       { host: db.kodeme.io, port: 5432, user: postgres, password: ${PG_PASSWORD} }
    cf:       { api_key: ${CF_API_KEY}, zone_id: ${CF_ZONE_ID} }
    ak:       { url: https://auth.kodeme.io, api_key: ${AUTHENTIK_API_KEY} }
    grafana:  { url: https://grafana.kodeme.io, api_key: ${GRAFANA_API_KEY} }
    odoo:     { url: https://erp.kodeme.io, database: kodemeio, api_key: ${ODOO_API_KEY} }
    api:      { url: https://api.kodeme.io, api_key: ${API_KEY} }
    op:       { vault: kodemeio }
    linear:   { api_key: ${LINEAR_API_KEY} }
  staging:
    odoo:     { url: https://erp-staging.kodeme.io, database: kodemeio_staging }
```

Config is managed via the `config` subcommand present on every CLI:

```bash
kctl-dokploy config init          # Interactive setup
kctl-dokploy config show          # Display current profile (secrets masked)
kctl-dokploy config add staging   # Add new profile
kctl-dokploy config use staging   # Switch active profile
```

## API Client Base Classes

CLIs with HTTP APIs subclass `APIClient` (sync) or `AsyncAPIClient` (async) from `kctl-lib`. These base classes provide authentication, retry with exponential backoff, error mapping, and debug logging.

### Class Attributes

| Attribute | Default | Purpose |
|-----------|---------|---------|
| `AUTH_HEADER` | `"Authorization"` | HTTP header name for credentials |
| `AUTH_PREFIX` | `"Bearer"` | Prefix before the credential value (empty for raw tokens) |
| `API_PREFIX` | `""` | URL path prefix appended to base URL (e.g., `/v1`) |
| `BASE_URL` | `""` | Default base URL if not passed at init |

### Override Hooks

| Method | Purpose |
|--------|---------|
| `_unwrap_response(response)` | Parse/unwrap response body. Override for envelope APIs (e.g., Cloudflare wraps results in `{"result": ...}`) |
| `_map_error(response)` | Extract human-readable error detail from error responses |
| `_is_retryable(response)` | Determine if a failed response should be retried (beyond the default 5xx check) |
| `_build_auth_header()` | Override for non-standard authentication schemes |

### Example Subclass

```python
from kctl_lib.api_client import APIClient

class CloudflareClient(APIClient):
    BASE_URL = "https://api.cloudflare.com"
    AUTH_HEADER = "Authorization"
    AUTH_PREFIX = "Bearer"
    API_PREFIX = "/client/v4"

    def _unwrap_response(self, response):
        data = response.json()
        return data.get("result", data)
```

### Transport per CLI

| CLI | Transport | Reason |
|-----|-----------|--------|
| kctl-dokploy | APIClient | REST API |
| kctl-hz | APIClient | REST API |
| kctl-cf | APIClient | REST API (envelope unwrap) |
| kctl-ak | APIClient | REST API |
| kctl-grafana | APIClient | REST API |
| kctl-rustdesk | APIClient | REST API |
| kctl-waha | APIClient | REST API |
| kctl-api | APIClient | REST API |
| kctl-react | APIClient | REST API |
| kctl-claw | APIClient | REST API |
| kctl-github | APIClient | REST API |
| kctl-sentry | APIClient | REST API |
| kctl-telegram | APIClient | REST API |
| kctl-notion | APIClient | REST API |
| kctl-claude | APIClient | REST API |
| kctl-glitchtip | APIClient | REST API |
| kctl-pg | psycopg / SSH | Direct DB connection, no HTTP |
| kctl-odoo | JSON-RPC | Odoo XML-RPC/JSON-RPC protocol |
| kctl-op | subprocess | Delegates to `op` CLI binary |
| kctl-linear | GraphQL | GraphQL over HTTP (not REST) |
| kctl-gatus | Custom auth | Non-standard auth scheme |
| kctl-rmm | Custom auth | Non-standard auth scheme |

## kctl-lib Modules

| Module | Purpose |
|--------|---------|
| `exceptions.py` | 9 exception classes: `KctlError` → `ConfigError`, `AuthenticationError`, `NotFoundError`, `AppNotFoundError`, `CommandError`, `APIError`, `ConnectionError`, `DockerError`, `ValidationError` |
| `output.py` | `Output` class — pretty (Rich), json, csv, yaml. Methods: `table()`, `detail()`, `tree()`, `success/error/warn/info()`, `raw_json()` |
| `config.py` | Profile framework — `~/.config/kodemeio/config.yaml`, service-scoped, env var expansion (`${VAR}`) |
| `callbacks.py` | `AppContextBase` dataclass — lazy Output init. Each CLI subclasses. |
| `runner.py` | `run()`, `run_quiet()`, `get_git_sha()`, `get_git_branch()` |
| `plugins.py` | `KctlPlugin` protocol + `discover_and_load_plugins(app, group)` |
| `history.py` | `HistoryStore` — SQLite at `~/.local/share/kodemeio/{app}/history.db` |
| `testing.py` | `mock_output()`, `mock_app_context()`, `temp_config()` |
| `docker.py` | `DockerManager` — Docker Compose wrapper (up/down/ps/logs/restart/image_size/prune/exec) |
| `validate.py` | YAML/JSON/env/Dockerfile linting with `Issue` dataclass |
| `git_ops.py` | Git workflow helpers — branch_status, pr_create, changelog_generate, diff_summary |
| `completions.py` | Shell completion generation + install (zsh/bash/fish) |
| `self_update.py` | PyPI version check + uv tool upgrade |
| `doctor_base.py` | `DoctorCheck` protocol + `run_doctor()` + 4 built-in checks (Python, uv, git, Docker) |
| `monitor_base.py` | `health_check_url()`, `ssl_check()`, `dns_check()` |
| `api_client.py` | `APIClient` — sync HTTP base client with retry, auth header, error mapping |
| `async_api_client.py` | `AsyncAPIClient` — async HTTP base client with retry, auth header, error mapping |
| `skill_generator.py` | `SkillGenerator` — Typer app introspection → SKILL.md auto-generation (`skill generate`) |

## Deployment System

Declarative YAML-based deployment via `kctl-dokploy deploy`. Instance manifests extend reusable base templates.

```
deploys/
├── bases/              # Reusable base templates
│   ├── odoo.yaml       # Odoo 18 (compose, env, healthcheck, backup, schedules)
│   ├── react-pwa.yaml  # React PWA (GitHub source, Authentik OIDC)
│   └── infra.yaml      # Infrastructure services
└── instances/          # Per-instance manifests (extend a base)
    ├── odoo-prod.yaml       # kodemeio_prod → odoo.kodeme.io
    ├── odoo-mac.yaml        # odoo_full_mac → odoo-mac.kodeme.io
    └── react-*-mac.yaml     # 11 React PWA apps for MAC customer
```

### 12-Phase Pipeline

Triggered by `kctl-dokploy deploy apply -f <manifest>`:

| # | Phase | CLI Used | Description |
|---|-------|----------|-------------|
| 1 | DNS | kctl-cf | Create/verify DNS record |
| 2 | Database | kctl-pg | Create database + user |
| 3 | Registry | kctl-dokploy | Ensure container registry access |
| 4 | Compose | kctl-dokploy | Create/update compose service |
| 5 | Environment | kctl-dokploy | Push env vars from manifest |
| 6 | Domain | kctl-dokploy | Configure Traefik domain routing |
| 7 | Deploy | kctl-dokploy | Trigger redeploy |
| 8 | Verify | kctl-dokploy | Wait for healthcheck pass |
| 9 | Backup | kctl-dokploy | Configure backup destination + schedule |
| 10 | Schedules | kctl-dokploy | Setup cron jobs (vacuum, session cleanup) |
| 11 | Post-deploy | kctl-odoo | Install Odoo bundles/profiles |

Staged execution: `deploy setup` (phases 1–6) → `deploy run` (phases 7–8) → `deploy post` (phases 9–11).

Manifest naming convention: `{domain}-{type}-{name}.yaml` (e.g., `mandiriagro.com-react-sfa.yaml`).

## CI/CD

Five GitHub Actions workflows:

| Workflow | File | Trigger | Purpose |
|----------|------|---------|---------|
| CI | `ci.yml` | push, pull_request | Lint (ruff) + test (pytest) all packages |
| Publish | `publish.yml` | push `v*` tag | Auto-publish kctl-lib to PyPI |
| Deploy | `deploy.yml` | push to main | Deploy updated instances via kctl-dokploy |
| E2E Tests | `e2e.yml` | schedule, workflow_dispatch | Playwright E2E tests for kctl-odoo + kctl-react |
| Secret Scanning | `secret-scan.yml` | push, pull_request | Detect leaked credentials before merge |

Publishing kctl-lib:

```bash
# 1. Bump version in packages/kctl-lib/pyproject.toml and __init__.py
# 2. Commit, tag, and push
git tag v0.4.1
git push origin main --tags
# CI tests pass → publish.yml auto-publishes to PyPI
```

## Related Documentation

- [docs/cli-standards.md](cli-standards.md) — Global options, config subcommands, naming conventions, APIClient subclassing pattern
- [CLAUDE.md](../CLAUDE.md) — Quick commands, full module reference, E2E testing guide, deploy manifest reference
