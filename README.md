# kodemeio-platform

Shared infrastructure for the Kodemeio CLI ecosystem.

## Packages

### kctl-common

Shared core library for all `kctl-*` CLI tools.

[![PyPI](https://img.shields.io/pypi/v/kctl-common)](https://pypi.org/project/kctl-common/)
[![Python](https://img.shields.io/pypi/pyversions/kctl-common)](https://pypi.org/project/kctl-common/)

**Install:** `pip install kctl-common` or `uv add kctl-common`

**Modules (15 total):**

| Module | Purpose |
|--------|---------|
| `kctl_common.exceptions` | 9-class exception hierarchy (KctlError, ConfigError, APIError, etc.) |
| `kctl_common.output` | Multi-format output handler (pretty/json/csv/yaml) |
| `kctl_common.config` | Profile management (`~/.config/kodemeio/config.yaml`) |
| `kctl_common.callbacks` | `AppContextBase` — abstract Typer context with lazy Output |
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

**Used by:** kctl-next, kctl-odoo, kctl-react, kctl-api, kctl-claw

## CLI Ecosystem

| CLI | Repo | Target | Command Groups |
|-----|------|--------|---------------|
| kctl-next | kodemeio-next | Next.js monorepo (4 apps) | 35 |
| kctl-odoo | kodemeio-odoo | Odoo 18 ERP (96 modules) | 70 |
| kctl-react | kodemeio-react | React PWA monorepo (11 apps) | 31 |
| kctl-api | kodemeio-fastapi | FastAPI platform | 46 |
| kctl-claw | kodemeio-openclaw | AI agent gateway | 29 |

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

## Development

```bash
uv sync --all-extras
uv run pytest packages/kctl-common/tests/ -v
uv run ruff check packages/kctl-common/src/
uv run mypy packages/kctl-common/src/
```

## Publishing

Automatic via GitHub Actions on version tag push:

```bash
# 1. Bump version in packages/kctl-common/pyproject.toml + __init__.py
# 2. Commit and tag
git tag v0.2.0
git push origin main --tags
# → CI tests → auto-publish to PyPI
```

## Standards

See [docs/cli-standards.md](docs/cli-standards.md) for naming conventions, global options, and config subcommand requirements.
