# kodemeio-platform

Shared infrastructure for the Kodemeio CLI ecosystem.

## Packages

### kctl-lib

Shared core library for all `kctl-*` CLI tools.

[![PyPI](https://img.shields.io/pypi/v/kctl-lib)](https://pypi.org/project/kctl-lib/)
[![Python](https://img.shields.io/pypi/pyversions/kctl-lib)](https://pypi.org/project/kctl-lib/)

**Install:** `pip install kctl-lib` or `uv add kctl-lib`

**Modules (17 total):**

| Module | Purpose |
|--------|---------|
| `kctl_lib.exceptions` | 9-class exception hierarchy (KctlError, ConfigError, APIError, etc.) |
| `kctl_lib.output` | Multi-format output handler (pretty/json/csv/yaml) |
| `kctl_lib.config` | Profile management (`~/.config/kodemeio/config.yaml`) |
| `kctl_lib.callbacks` | `AppContextBase` — abstract Typer context with lazy Output |
| `kctl_lib.api_client` | `APIClient` — sync HTTP base client with retry, auth header, error mapping |
| `kctl_lib.async_api_client` | `AsyncAPIClient` — async HTTP base client (mirror of APIClient) |
| `kctl_lib.runner` | Shell command runner + git helpers |
| `kctl_lib.plugins` | Plugin discovery via Python entry points |
| `kctl_lib.history` | SQLite-based history tracking |
| `kctl_lib.testing` | Shared test fixtures (mock_output, temp_config) |
| `kctl_lib.docker` | `DockerManager` — Docker Compose wrapper (up/down/ps/logs/restart/exec) |
| `kctl_lib.validate` | YAML/JSON/env/Dockerfile linting with `Issue` dataclass |
| `kctl_lib.git_ops` | Git workflow helpers — branch_status, pr_create, changelog_generate |
| `kctl_lib.completions` | Shell completion generation + install (zsh/bash/fish) |
| `kctl_lib.self_update` | PyPI version check + uv tool upgrade |
| `kctl_lib.doctor_base` | `DoctorCheck` protocol + `run_doctor()` + 4 built-in checks |
| `kctl_lib.monitor_base` | `health_check_url()`, `ssl_check()`, `dns_check()` |
| `kctl_lib.skill_generator` | Typer app introspection → SKILL.md auto-generation |

**Used by:** 21 kctl-* CLI tools across kodemeio-app, kodemeio-core, and kodemeio-saas

## CLI Ecosystem

### kodemeio-app (Application Management)

| CLI | Repo | Target | Command Groups |
|-----|------|--------|---------------|
| kctl-next | kodemeio-next | Next.js monorepo (4 apps) | 35 |
| kctl-odoo | kodemeio-odoo | Odoo 18 ERP (96 modules) | 70+ |
| kctl-react | kodemeio-react | React PWA monorepo (11 apps) | 31 |
| kctl-api | kodemeio-fastapi | FastAPI platform | 46 |
| kctl-claw | kodemeio-openclaw | AI agent gateway | 29 |

### kodemeio-core (Infrastructure Management)

| CLI | Repo | Target | Command Groups |
|-----|------|--------|---------------|
| kctl-dokploy | kodemeio-dokploy | Dokploy deployment platform | 37 |
| kctl-hz | kodemeio-hetzner | Hetzner Cloud infrastructure | 24 |
| kctl-pg | kodemeio-postgres | PostgreSQL administration | 24 |
| kctl-cf | kodemeio-cloudflare | Cloudflare DNS/CDN/WAF | 27 |
| kctl-ak | kodemeio-authentik | Authentik SSO/identity | 24 |
| kctl-gatus | kodemeio-gatus | Gatus health monitoring | 8 |
| kctl-mdm | kodemeio-headwind | Headwind MDM device management | 12 |
| kctl-waha | kodemeio-waha | WhatsApp HTTP API | 8 |
| kctl-grafana | kodemeio-grafana | Grafana monitoring platform | 11 |

### kodemeio-saas (SaaS Integration)

| CLI | Repo | Target | Command Groups |
|-----|------|--------|---------------|
| kctl-telegram | kodemeio-telegram | Telegram bot platform | 7 |
| kctl-1password | kodemeio-1password | 1Password secret management | 9 |
| kctl-claude | kodemeio-claude | Claude Code environments | 8 |
| kctl-github | kodemeio-github | Cross-repo GitHub management | 10 |
| kctl-linear | kodemeio-linear | Linear project/sprint tracking | 9 |
| kctl-notion | kodemeio-notion | Notion wiki/database management | 7 |
| kctl-sentry | kodemeio-sentry | Sentry error tracking | 10 |

## APIClient Base Class

CLIs with HTTP APIs subclass `APIClient` from kctl-lib:

```python
from kctl_lib.api_client import APIClient

class MyServiceClient(APIClient):
    AUTH_HEADER = "Authorization"   # or "X-Api-Key", "Auth-API-Token"
    AUTH_PREFIX = "Bearer"          # or "" for raw token
    API_PREFIX = "/api/v1"          # auto-appended to base URL
    BASE_URL = ""                   # hard-coded or from config

    def __init__(self, base_url="", credential="", **kwargs):
        super().__init__(base_url=base_url, credential=credential, **kwargs)
```

Override hooks: `_unwrap_response()`, `_map_error()`, `_is_retryable()`, `_build_auth_header()`

**Exceptions:** kctl-pg (psycopg/SSH), kctl-odoo (JSON-RPC), kctl-1password (subprocess), kctl-linear (GraphQL), kctl-gatus/kctl-mdm (custom auth)

## Templates

### Scaffold a new kctl-* CLI

```bash
pip install copier
copier copy templates/kctl-cli/ /path/to/new-cli/
```

Generates a fully functional CLI with:
- All 6 standard global options (`--json`, `--quiet`, `--format`, `--no-header`, `--profile`, `--version`)
- All 9 standard config subcommands
- Plugin system via entry points
- AppContext subclass from kctl-lib
- kctl-lib >= 0.4.0 dependency

## Deployment System

Declarative YAML-based deployment via `kctl-dokploy deploy`. Instance manifests extend base templates. Supports production + staging environments.

```
deploys/
├── bases/                      # Reusable base templates (odoo, react-pwa, nextjs, fastapi, infra)
├── instances/
│   ├── production/             # Production manifests (34 services)
│   └── staging/                # Staging manifests (17 services)
├── env/
│   ├── production/             # Production .env files (gitignored)
│   └── staging/                # Staging .env files (gitignored)
├── tenants/                    # Tenant definitions with environment config
└── generate.py                 # Generate instances from tenant config
```

### Deploy Commands

```bash
kctl-dokploy deploy apply -f deploys/instances/production/mac-react-sfa.yaml  # Production
kctl-dokploy deploy apply -f deploys/instances/staging/mac-react-sfa.yaml     # Staging
kctl-dokploy deploy apply-all -d deploys/instances/production/                # All production
kctl-dokploy deploy apply-all -d deploys/instances/staging/                   # All staging
kctl-dokploy deploy preflight -f <manifest>                                   # Pre-deploy validation
kctl-dokploy deploy preflight -f <manifest> --gates dns,database              # Specific gates
kctl-dokploy deploy preflight-all -d deploys/instances/production/            # Batch preflight
kctl-dokploy deploy migrate plan -f deploys/migrations/mac-to-dedicated.yaml  # Migration dry-run
kctl-dokploy deploy migrate apply -f deploys/migrations/mac-to-dedicated.yaml # Execute migration
kctl-dokploy deploy status -f <manifest>                                      # Dry-run preview
```

### 13-Phase Pipeline

Preflight → DNS → Database → Registry → Compose → Environment → Domain → Deploy → Verify → Backup → Schedules → Post-deploy

Uses: kctl-cf (DNS), kctl-pg (DB), kctl-dokploy (compose/env/domain/deploy/preflight), kctl-odoo (post-deploy bundles)

### Naming Convention

`{tenant}-{stack}-{app}` — e.g., `mac-react-sfa`, `tpp-odoo-trad`, `kod-infra-gatus`

## Development

```bash
uv sync --all-extras
uv run pytest packages/kctl-lib/tests/ -v    # 238 tests
uv run ruff check packages/kctl-lib/src/
uv run mypy packages/kctl-lib/src/
```

## Publishing

Automatic via GitHub Actions on version tag push:

```bash
# 1. Bump version in packages/kctl-lib/pyproject.toml + __init__.py
# 2. Commit and tag
git tag v0.4.0
git push origin main --tags
# → CI tests → auto-publish to PyPI
```

## Standards

See [docs/cli-standards.md](docs/cli-standards.md) for naming conventions, global options, config subcommand requirements, and the APIClient subclassing pattern.

See [docs/architecture.md](docs/architecture.md) for platform architecture and module details.
