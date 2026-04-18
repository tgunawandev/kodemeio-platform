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

`kctl-lib` is a shared Python package (PyPI: kctl-lib v0.4.0) used by **23 CLI tools**, all consolidated into this single workspace.

### Workspace Members (23 packages)

#### Shared Library
- **kctl-lib** — Shared CLI infrastructure (v0.4.0, published to PyPI)

#### Infrastructure & Ops
- **kctl-dokploy** — Dokploy deployment platform (37 groups)
- **kctl-hz** — Hetzner Cloud infrastructure (24 groups)
- **kctl-pg** — PostgreSQL administration (24 groups)
- **kctl-redis** — Redis cache & message broker (16 groups)
- **kctl-cf** — Cloudflare DNS/CDN/WAF (27 groups)
- **kctl-ak** — Authentik SSO/identity (24 groups)
- **kctl-grafana** — Grafana monitoring platform (11 groups)
- **kctl-rustdesk** — RustDesk server management (9 groups)
- **kctl-waha** — WhatsApp HTTP API (8 groups)
- **kctl-mailcow** — Mailcow mail server management (31 groups)
- **kctl-mm** — Mattermost Team Edition management (24 groups)

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
- **kctl-zulip** — Zulip team chat administration (22 groups)

Each CLI uses thin re-export modules in `core/` that import from `kctl_lib`, keeping domain-specific code local. CLIs with HTTP APIs subclass `APIClient` from kctl-lib; exceptions are kctl-pg (psycopg/SSH), kctl-redis (redis-py/SSH), kctl-odoo (JSON-RPC), kctl-op (subprocess), kctl-linear (GraphQL), kctl-mdm (custom auth).

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
| `packages/kctl-github/` | GitHub cross-repo management CLI |
| `packages/kctl-grafana/` | Grafana monitoring CLI |
| `packages/kctl-hz/` | Hetzner Cloud infrastructure CLI |
| `packages/kctl-linear/` | Linear project tracking CLI |
| `packages/kctl-mailcow/` | Mailcow mail server CLI |
| `packages/kctl-mm/` | Mattermost Team Edition CLI |
| `packages/kctl-notion/` | Notion wiki management CLI |
| `packages/kctl-odoo/` | Odoo 18 ERP management CLI |
| `packages/kctl-op/` | 1Password secret management CLI |
| `packages/kctl-pg/` | PostgreSQL administration CLI |
| `packages/kctl-redis/` | Redis cache & message broker CLI |
| `packages/kctl-react/` | React PWA monorepo CLI |
| `packages/kctl-rustdesk/` | RustDesk server management CLI |
| `packages/kctl-sentry/` | Sentry error tracking CLI |
| `packages/kctl-telegram/` | Telegram bot platform CLI |
| `packages/kctl-waha/` | WhatsApp HTTP API CLI |
| `packages/kctl-zulip/` | Zulip team chat CLI |
| `deploys/bases/` | Deployment base templates (odoo, react-pwa, nextjs, fastapi, infra) |
| `deploys/instances/production/` | Production instance manifests (35 services) |
| `deploys/instances/staging/` | Staging instance manifests (17 services — mac + tpp) |
| `deploys/env/production/` | Production .env files (gitignored) |
| `deploys/env/staging/` | Staging .env files (gitignored) |
| `deploys/tenants/` | Tenant definitions with environment config |
| `templates/kctl-cli/` | Copier template for new CLIs |
| `docs/cli-standards.md` | CLI naming and option standards |
| `docs/architecture.md` | Platform architecture |
| `docs/migration-sop.md` | Server migration runbook |
| `deploys/migrations/` | Migration manifest YAML files |
| `.github/workflows/ci.yml` | CI: test + lint on push/PR |
| `.github/workflows/publish.yml` | Auto-publish to PyPI on v* tag |

## Deployment System

Declarative YAML-based deployment via `kctl-dokploy deploy`. Manifests live in `deploys/`.

### Structure

```
deploys/
├── bases/                          # Reusable base templates
│   ├── odoo.yaml                   # Odoo 18 base (compose, env, healthcheck, backup)
│   ├── react-pwa.yaml              # React PWA base (GitHub source, nginx)
│   ├── nextjs.yaml                 # Next.js base (GitHub source, port 3000)
│   ├── fastapi.yaml                # FastAPI base (port 8000)
│   └── infra.yaml                  # Infrastructure services base
├── env/
│   ├── production/                 # Production .env files (gitignored)
│   └── staging/                    # Staging .env files (gitignored)
├── instances/
│   ├── production/                 # Production manifests (34 services)
│   └── staging/                    # Staging manifests (17 services)
├── tenants/                        # Tenant definitions (mac.yaml, tpp.yaml)
├── setup/                          # Company setup scripts
└── generate.py                     # Generate instances from tenant config
```

### Multi-Environment Support

Each tenant can define production + staging environments. The deployer targets the correct Dokploy environment automatically.

| Environment | Branch | DNS Prefix | DB Prefix | Auto-deploy |
|-------------|--------|------------|-----------|-------------|
| production | main / 18.0 | (none) | (none) | false (manual) |
| staging | main / 18.0 | stg- | stg_ | true (on push) |

Server mapping:
- **mac**: `mac-prod-01` / `mac-stg-01` (dedicated)
- **kod, tpp, tkz, pro, tgw, kid**: `kod-prod-01` / `kod-prod-02` (shared)

### Deploy Commands

```bash
# Production deploy
kctl-dokploy deploy apply -f deploys/instances/production/mac-react-sfa.yaml

# Staging deploy
kctl-dokploy deploy apply -f deploys/instances/staging/mac-react-sfa.yaml

# Batch deploy all production
kctl-dokploy deploy apply-all -d deploys/instances/production/

# Batch deploy all staging
kctl-dokploy deploy apply-all -d deploys/instances/staging/

# Troubleshoot failed deployment (auto-runs on deploy failure too)
kctl-dokploy deploy troubleshoot -f <manifest>         # Diagnose by manifest
kctl-dokploy deploy troubleshoot --compose <id>        # Diagnose by compose ID

# Staged deployment (for troubleshooting)
kctl-dokploy deploy setup -f <manifest>   # Stage 1: DNS + DB + Compose + Env + Domain
kctl-dokploy deploy run -f <manifest>     # Stage 2: Deploy + Verify healthcheck
kctl-dokploy deploy post -f <manifest>    # Stage 3: Backup + Schedules + Post-deploy

# Preflight checks (pre-deploy validation)
kctl-dokploy deploy preflight -f <manifest>                   # Single manifest
kctl-dokploy deploy preflight-all -d deploys/instances/production/  # All production
kctl-dokploy deploy preflight-all -d deploys/instances/production/ --server mac-prod-01  # Filter by server

# Preflight with specific gates
kctl-dokploy deploy preflight -f <manifest> --gates dns,database,env_sync

# Server migration
kctl-dokploy deploy migrate validate -f deploys/migrations/mac-to-dedicated.yaml
kctl-dokploy deploy migrate plan -f deploys/migrations/mac-to-dedicated.yaml
kctl-dokploy deploy migrate apply -f deploys/migrations/mac-to-dedicated.yaml
kctl-dokploy deploy migrate apply -f deploys/migrations/mac-to-dedicated.yaml --resume
kctl-dokploy deploy migrate rollback -f deploys/migrations/mac-to-dedicated.yaml
kctl-dokploy deploy migrate cleanup -f deploys/migrations/mac-to-dedicated.yaml

# Preview / status
kctl-dokploy deploy status -f <manifest>  # Dry-run all phases

# Generate manifests from tenant config
cd deploys && python generate.py            # Generate all
cd deploys && python generate.py -t mac     # Generate single tenant
cd deploys && python generate.py --dry-run  # Preview
```

### 13-Phase Pipeline

| # | Phase | CLI Used | Description |
|---|-------|----------|-------------|
| 0 | Preflight | kctl-dokploy | 10 gates: server, firewall, DNS, image pull, DB, compose, env sync (OIDC), source, network, SSL |
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

### Compose Postgres Backup → S3 → Local Restore

Dokploy's `/backup.manualBackupCompose` endpoint is unreliable for compose-embedded
postgres. `kctl-dokploy backups` ships a reliable alternative that streams `pg_dump`
straight to S3 via SSH + docker exec, then restores into a local compose's postgres
container.

```bash
# One-shot refresh (prod → local)
kctl-dokploy --profile local backups refresh \
    --source-profile idtpp \
    --source-compose <prod-compose-id> \
    --source-destination <idtpp-dest-id> \
    --target-compose <local-compose-id> \
    --database authentik \
    --force

# Or step-by-step: dump-compose → download → restore-local
kctl-dokploy --profile idtpp backups dump-compose --compose <id> --destination <id> --database <db>
kctl-dokploy --profile local  backups download <s3-key> --destination <id> --output /tmp/dump
kctl-dokploy --profile local  backups restore-local /tmp/dump --compose <id> --force
```

Uses custom-format `pg_dump -F c` with `pg_restore --exit-on-error` (or `psql -v
ON_ERROR_STOP=1` for plain SQL). S3 creds live in the Dokploy destination record —
no additional credential setup needed. Works with Hetzner Object Storage or any
S3-compatible endpoint. See `packages/kctl-dokploy/README.md` for full details.

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
| `ssh.py` | `ssh_run()`, `scp_download()`, `scp_upload()` — standardized SSH command execution with `SSHResult` |
| `ssh_tunnel.py` | `SSHTunnel` — context manager wrapping `SSHTunnelForwarder` for database CLIs |
| `api_client.py` | `APIClient` — sync HTTP base client with retry, auth header, error mapping |
| `async_api_client.py` | `AsyncAPIClient` — async HTTP base client with retry, auth header, error mapping |
| `skill_generator.py` | `SkillGenerator` — Typer app introspection → SKILL.md auto-generation (`skill generate`) |

## CLI Standards

### Global Options (all CLIs)
`--json`, `--quiet/-q`, `--format/-f` (pretty/json/csv/yaml), `--no-header`, `--profile/-p`, `--version/-V`

### Config Subcommands (all CLIs)
init, add, use, show, validate, remove, set, profiles, current

### Standard Commands (all 23 CLIs, since Quality Sweep 2026-04-06)
| Command | Purpose |
|---------|---------|
| `config init` | Interactive profile setup |
| `doctor` | Diagnostic checks (API/SSH connectivity, auth, config) |
| `self-update` | Check PyPI for updates and upgrade via `uv tool` |
| `completions [zsh\|bash\|fish] [--install]` | Generate/install shell completions |
| `skill generate` | Auto-generate SKILL.md from Typer introspection |

### Command Naming
| Concern | Name |
|---------|------|
| Code generation | `scaffold` |
| Diagnostics | `doctor` |
| Cleanup | `clean` |

### Quality Baseline (all CLIs)
- README.md ≥ 40 lines (proportional to CLI size)
- SKILL.md present in `skills/<name>-admin/`
- conftest.py with standard fixtures (runner, mock_client, mock_config, mock_output, mock_context)
- E2E scaffolding for 5 critical CLIs: odoo, dokploy, react, pg, ak

## Deploy Manifest Naming

Convention: `{tenant}-{stack}-{app}.yaml`

Stacks: `react`, `nextjs`, `odoo`, `hono`, `fastapi`, `infra`

Examples:
- `mac-react-sfa.yaml` — MAC SFA PWA
- `tpp-odoo-trad.yaml` — Pakerti Trading Odoo
- `kod-infra-grafana.yaml` — Kodemeio Grafana monitoring

Dokploy projects use tenant codes: `mac`, `tpp`, `kod`, `tgw`, `tkz`, `pro`, `kid`

Each Dokploy project has environments (production + staging). Services keep the same name across environments — the Dokploy environment provides separation.

## E2E Testing (Playwright)

kctl-odoo and kctl-react both support Playwright-based E2E browser testing.

### kctl-odoo E2E (`packages/kctl-odoo/e2e/`)

```bash
kctl-odoo e2e install                     # Install Playwright + browsers
kctl-odoo e2e test                        # Run all E2E tests
kctl-odoo e2e test login                  # Run login scenario only
kctl-odoo e2e test --smoke                # Smoke test: visit all menus
kctl-odoo e2e test --module sale --headed # Sales tests, visible browser
kctl-odoo e2e test --mobile               # Mobile viewport
kctl-odoo e2e test --screenshots --video  # Capture evidence
kctl-odoo e2e test --grep "Invoice"       # Filter by pattern
kctl-odoo e2e test --ui                   # Playwright UI mode
kctl-odoo e2e list                        # List all tests
kctl-odoo e2e report                      # Open HTML report
kctl-odoo e2e screenshots                 # Screenshot all menus
kctl-odoo e2e discover                    # Generate menu registry from live Odoo
```

Structure:
```
packages/kctl-odoo/e2e/
├── playwright.config.ts    # Multi-project: setup → desktop/mobile
├── fixtures/
│   ├── odoo-auth.ts        # Login helpers (form + RPC)
│   ├── odoo-helpers.ts     # Navigation, form fields, wait helpers
│   └── odoo-test.ts        # Extended test fixture with odoo helpers
├── tests/
│   ├── global-setup.ts     # Authenticate once, save session
│   ├── scenarios/          # Business flow tests (login, sales-order, etc.)
│   ├── smoke/              # All-menus smoke test
│   └── shared/             # Common UI tests (navbar, settings)
└── odoo-menu-registry.json # Auto-generated by `e2e discover`
```

Connection uses the active kctl-odoo profile (ODOO_URL, ODOO_DATABASE, ODOO_API_KEY).

### kctl-react E2E (`packages/kctl-react/ → e2e/`)

```bash
kctl-react e2e test [app]     # Run per-app Playwright tests
kctl-react e2e test --mobile  # Mobile viewport
kctl-react e2e discover       # Auto-discover app configs → app-registry.ts
kctl-react e2e screenshots    # Capture all app pages
```

## Conventions

- Python 3.12+, Typer + Rich + Pydantic 2 + PyYAML
- Hatchling build system, uv for package management
- Ruff for linting, mypy strict for type checking
- Conventional commits with commitizen
- Tests with pytest
- E2E tests with Playwright (TypeScript, `@playwright/test`)
