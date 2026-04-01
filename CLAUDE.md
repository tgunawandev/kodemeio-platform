# CLAUDE.md - kodemeio-platform

Shared CLI infrastructure: `kctl-lib` Python package + copier template.

## Quick Commands

```bash
# Development (full workspace)
uv sync --all-extras --all-packages   # Install all packages + dev deps
uv run pytest packages/kctl-lib/tests/ -v  # kctl-lib: 247 tests
uv run pytest packages/kctl-op/tests/ -v      # kctl-op: 115 tests
uv run ruff check packages/*/src/             # Lint all packages

# Single package
cd packages/kctl-lib
uv sync --all-extras
uv run pytest tests/ -v
uv run mypy src/
uv build

# Scaffold new CLI
copier copy templates/kctl-cli/ /path/to/new-cli/
```

## Architecture

`kctl-lib` is a shared Python package (PyPI: kctl-lib v0.4.0) used by **21 CLI tools**, all consolidated into this single workspace.

### Workspace Members (21 packages)

#### Shared Library
- **kctl-lib** — Shared CLI infrastructure (v0.4.0, published to PyPI)

#### Infrastructure & Ops
- **kctl-dokploy** — Dokploy deployment platform (37 groups)
- **kctl-hz** — Hetzner Cloud infrastructure (24 groups)
- **kctl-pg** — PostgreSQL administration (24 groups)
- **kctl-cf** — Cloudflare DNS/CDN/WAF (27 groups)
- **kctl-ak** — Authentik SSO/identity (24 groups)
- **kctl-grafana** — Grafana monitoring platform (11 groups)
- **kctl-gatus** — Gatus health monitoring (8 groups)
- **kctl-rustdesk** — RustDesk server management (9 groups)
- **kctl-waha** — WhatsApp HTTP API (8 groups)

#### Application Management
- **kctl-odoo** — Odoo 18 ERP management (70+ groups)
- **kctl-api** — FastAPI platform management (46 groups)
- **kctl-react** — React PWA monorepo management (31 groups)
- **kctl-claw** — AI agent gateway management (29 groups)

#### Developer & SaaS Tools
- **kctl-op** — 1Password secret management (9 groups) — *renamed from kctl-1password*
- **kctl-github** — Cross-repo GitHub management (10 groups)
- **kctl-sentry** — Sentry error tracking (10 groups)
- **kctl-linear** — Linear project/sprint tracking (9 groups)
- **kctl-claude** — Claude Code environment management (8 groups)
- **kctl-telegram** — Telegram bot platform (7 groups)
- **kctl-notion** — Notion wiki/database management (7 groups)

Each CLI uses thin re-export modules in `core/` that import from `kctl_lib`, keeping domain-specific code local. CLIs with HTTP APIs subclass `APIClient` from kctl-lib; exceptions are kctl-pg (psycopg/SSH), kctl-odoo (JSON-RPC), kctl-op (subprocess), kctl-linear (GraphQL), kctl-gatus and kctl-mdm (custom auth).

## Key Paths

| Path | Description |
|------|-------------|
| `packages/kctl-lib/` | Shared library (v0.4.0, PyPI, 247 tests) |
| `packages/kctl-ak/` | Authentik SSO/identity CLI |
| `packages/kctl-api/` | FastAPI platform CLI |
| `packages/kctl-claude/` | Claude Code environment CLI |
| `packages/kctl-claw/` | AI agent gateway CLI |
| `packages/kctl-cf/` | Cloudflare DNS/CDN/WAF CLI |
| `packages/kctl-dokploy/` | Dokploy deployment CLI |
| `packages/kctl-gatus/` | Gatus health monitoring CLI |
| `packages/kctl-github/` | GitHub cross-repo management CLI |
| `packages/kctl-grafana/` | Grafana monitoring CLI |
| `packages/kctl-hz/` | Hetzner Cloud infrastructure CLI |
| `packages/kctl-linear/` | Linear project tracking CLI |
| `packages/kctl-notion/` | Notion wiki management CLI |
| `packages/kctl-odoo/` | Odoo 18 ERP management CLI |
| `packages/kctl-op/` | 1Password secret management CLI |
| `packages/kctl-pg/` | PostgreSQL administration CLI |
| `packages/kctl-react/` | React PWA monorepo CLI |
| `packages/kctl-rustdesk/` | RustDesk server management CLI |
| `packages/kctl-sentry/` | Sentry error tracking CLI |
| `packages/kctl-telegram/` | Telegram bot platform CLI |
| `packages/kctl-waha/` | WhatsApp HTTP API CLI |
| `deploys/bases/` | Deployment base templates (odoo, react-pwa, infra) |
| `deploys/instances/` | Instance manifests (odoo-prod, odoo-mac, react-*-mac) |
| `templates/kctl-cli/` | Copier template for new CLIs |
| `docs/cli-standards.md` | CLI naming and option standards |
| `docs/architecture.md` | Platform architecture |
| `.github/workflows/ci.yml` | CI: test + lint on push/PR |
| `.github/workflows/publish.yml` | Auto-publish to PyPI on v* tag |

## Deployment System

Declarative YAML-based deployment via `kctl-dokploy deploy`. Manifests live in `deploys/`.

### Structure

```
deploys/
├── bases/           # Reusable base templates
│   ├── odoo.yaml    # Odoo 18 base (compose, env, healthcheck, backup, schedules)
│   ├── react-pwa.yaml  # React PWA base (GitHub source, Authentik OIDC)
│   └── infra.yaml   # Infrastructure services base
└── instances/       # Per-instance manifests (extend a base)
    ├── odoo-prod.yaml       # kodemeio_prod → odoo.kodeme.io
    ├── odoo-mac.yaml        # odoo_full_mac → odoo-mac.kodeme.io
    └── react-*-mac.yaml     # 11 React PWA apps for MAC customer
```

### Deploy Commands

```bash
# Full pipeline: DNS → DB → Compose → Env → Domain → Deploy → Verify → Backup → Post
kctl-dokploy deploy apply -f deploys/instances/odoo-mac.yaml

# Staged deployment (for troubleshooting)
kctl-dokploy deploy setup -f <manifest>   # Stage 1: DNS + DB + Compose + Env + Domain
kctl-dokploy deploy run -f <manifest>     # Stage 2: Deploy + Verify healthcheck
kctl-dokploy deploy post -f <manifest>    # Stage 3: Backup + Schedules + Post-deploy

# Preview / status
kctl-dokploy deploy status -f <manifest>  # Dry-run all phases
kctl-dokploy deploy apply -f <manifest> --dry-run

# Batch deploy all instances
kctl-dokploy deploy apply-all -d deploys/instances/
```

### 12-Phase Pipeline

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

### Odoo Prod Compose

Source: `kodemeio-odoo` repo → `compose/odoo.prod.yml` (4 containers: init → web + cron + gevent)

## kctl-lib Modules

| Module | Purpose |
|--------|---------|
| `exceptions.py` | 9 exception classes: KctlError → ConfigError, AuthenticationError, NotFoundError, AppNotFoundError, CommandError, APIError, ConnectionError, DockerError, ValidationError |
| `output.py` | `Output` class — pretty (Rich), json, csv, yaml. Methods: table(), detail(), tree(), success/error/warn/info(), raw_json() |
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

## CLI Standards

### Global Options (all CLIs)
`--json`, `--quiet/-q`, `--format/-f` (pretty/json/csv/yaml), `--no-header`, `--profile/-p`, `--version/-V`

### Config Subcommands (all CLIs)
init, add, use, show, validate, remove, set, profiles, current

### Command Naming
| Concern | Name |
|---------|------|
| Code generation | `scaffold` |
| Diagnostics | `doctor` |
| Cleanup | `clean` |

## Conventions

- Python 3.12+, Typer + Rich + Pydantic 2 + PyYAML
- Hatchling build system, uv for package management
- Ruff for linting, mypy strict for type checking
- Conventional commits with commitizen
- Tests with pytest
