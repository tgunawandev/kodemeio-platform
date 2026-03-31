# kodemeio-platform

Shared infrastructure for the Kodemeio CLI ecosystem.

## Packages

### kctl-common

Shared core library for all `kctl-*` CLI tools.

[![PyPI](https://img.shields.io/pypi/v/kctl-common)](https://pypi.org/project/kctl-common/)
[![Python](https://img.shields.io/pypi/pyversions/kctl-common)](https://pypi.org/project/kctl-common/)

**Install:** `pip install kctl-common` or `uv add kctl-common`

**Modules (17 total):**

| Module | Purpose |
|--------|---------|
| `kctl_common.exceptions` | 9-class exception hierarchy (KctlError, ConfigError, APIError, etc.) |
| `kctl_common.output` | Multi-format output handler (pretty/json/csv/yaml) |
| `kctl_common.config` | Profile management (`~/.config/kodemeio/config.yaml`) |
| `kctl_common.callbacks` | `AppContextBase` — abstract Typer context with lazy Output |
| `kctl_common.api_client` | `APIClient` — sync HTTP base client with retry, auth header, error mapping |
| `kctl_common.async_api_client` | `AsyncAPIClient` — async HTTP base client (mirror of APIClient) |
| `kctl_common.runner` | Shell command runner + git helpers |
| `kctl_common.plugins` | Plugin discovery via Python entry points |
| `kctl_common.history` | SQLite-based history tracking |
| `kctl_common.testing` | Shared test fixtures (mock_output, temp_config) |
| `kctl_common.docker` | `DockerManager` — Docker Compose wrapper (up/down/ps/logs/restart/exec) |
| `kctl_common.validate` | YAML/JSON/env/Dockerfile linting with `Issue` dataclass |
| `kctl_common.git_ops` | Git workflow helpers — branch_status, pr_create, changelog_generate |
| `kctl_common.completions` | Shell completion generation + install (zsh/bash/fish) |
| `kctl_common.self_update` | PyPI version check + uv tool upgrade |
| `kctl_common.doctor_base` | `DoctorCheck` protocol + `run_doctor()` + 4 built-in checks |
| `kctl_common.monitor_base` | `health_check_url()`, `ssl_check()`, `dns_check()` |
| `kctl_common.skill_generator` | Typer app introspection → SKILL.md auto-generation |

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

CLIs with HTTP APIs subclass `APIClient` from kctl-common:

```python
from kctl_common.api_client import APIClient

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
- AppContext subclass from kctl-common
- kctl-common >= 0.3.1 dependency

## Development

```bash
uv sync --all-extras
uv run pytest packages/kctl-common/tests/ -v    # 238 tests
uv run ruff check packages/kctl-common/src/
uv run mypy packages/kctl-common/src/
```

## Publishing

Automatic via GitHub Actions on version tag push:

```bash
# 1. Bump version in packages/kctl-common/pyproject.toml + __init__.py
# 2. Commit and tag
git tag v0.3.1
git push origin main --tags
# → CI tests → auto-publish to PyPI
```

## Standards

See [docs/cli-standards.md](docs/cli-standards.md) for naming conventions, global options, config subcommand requirements, and the APIClient subclassing pattern.

See [docs/architecture.md](docs/architecture.md) for platform architecture and module details.
