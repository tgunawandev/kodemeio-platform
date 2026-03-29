# CLAUDE.md - kodemeio-platform

Shared CLI infrastructure: `kctl-common` Python package + copier template.

## Quick Commands

```bash
# Development
cd packages/kctl-common
uv sync --all-extras
uv run pytest tests/ -v           # 238 tests
uv run ruff check src/ tests/     # Lint
uv run ruff format src/ tests/    # Format
uv run mypy src/                  # Type check
uv build                          # Build wheel + sdist

# Scaffold new CLI
copier copy templates/kctl-cli/ /path/to/new-cli/
```

## Architecture

`kctl-common` is a shared Python package (PyPI: kctl-common v0.3.1) used by **21 CLI tools** across 3 repo groups.

### kodemeio-app (5 CLIs)
- **kctl-next** (kodemeio-next) — Next.js monorepo management (35 groups)
- **kctl-odoo** (kodemeio-odoo) — Odoo 18 ERP management (70+ groups)
- **kctl-react** (kodemeio-react) — React PWA monorepo management (31 groups)
- **kctl-api** (kodemeio-fastapi) — FastAPI platform management (46 groups)
- **kctl-claw** (kodemeio-openclaw) — AI agent gateway management (29 groups)

### kodemeio-core (9 CLIs)
- **kctl-dokploy** (kodemeio-dokploy) — Dokploy deployment platform (37 groups)
- **kctl-hetzner** (kodemeio-hetzner) — Hetzner Cloud infrastructure (24 groups)
- **kctl-pg** (kodemeio-postgres) — PostgreSQL administration (24 groups)
- **kctl-cloudflare** (kodemeio-cloudflare) — Cloudflare DNS/CDN/WAF (27 groups)
- **kctl-ak** (kodemeio-authentik) — Authentik SSO/identity (24 groups)
- **kctl-gatus** (kodemeio-gatus) — Gatus health monitoring (8 groups)
- **kctl-mdm** (kodemeio-headwind) — Headwind MDM device management (12 groups)
- **kctl-waha** (kodemeio-waha) — WhatsApp HTTP API (8 groups)
- **kctl-grafana** (kodemeio-grafana) — Grafana monitoring platform (11 groups)

### kodemeio-saas (7 CLIs)
- **kctl-telegram** (kodemeio-telegram) — Telegram bot platform (7 groups)
- **kctl-1password** (kodemeio-1password) — 1Password secret management (9 groups)
- **kctl-claude** (kodemeio-claude) — Claude Code environment management (8 groups)
- **kctl-github** (kodemeio-github) — Cross-repo GitHub management (10 groups)
- **kctl-linear** (kodemeio-linear) — Linear project/sprint tracking (9 groups)
- **kctl-notion** (kodemeio-notion) — Notion wiki/database management (7 groups)
- **kctl-sentry** (kodemeio-sentry) — Sentry error tracking (10 groups)

Each CLI uses thin re-export modules in `core/` that import from `kctl_common`, keeping domain-specific code local. CLIs with HTTP APIs subclass `APIClient` from kctl-common; exceptions are kctl-pg (psycopg/SSH), kctl-odoo (JSON-RPC), kctl-1password (subprocess), kctl-linear (GraphQL), kctl-gatus and kctl-mdm (custom auth).

## Key Paths

| Path | Description |
|------|-------------|
| `packages/kctl-common/src/kctl_common/` | Shared library source |
| `packages/kctl-common/tests/` | 238 tests |
| `templates/kctl-cli/` | Copier template for new CLIs |
| `docs/cli-standards.md` | CLI naming and option standards |
| `docs/architecture.md` | Platform architecture |
| `.github/workflows/ci.yml` | CI: test + lint on push/PR |
| `.github/workflows/publish.yml` | Auto-publish to PyPI on v* tag |

## kctl-common Modules

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
