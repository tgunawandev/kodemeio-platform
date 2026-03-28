# CLAUDE.md - kodemeio-platform

Shared CLI infrastructure: `kctl-common` Python package + copier template.

## Quick Commands

```bash
# Development
cd packages/kctl-common
uv sync --all-extras
uv run pytest tests/ -v           # 80 tests
uv run ruff check src/ tests/     # Lint
uv run ruff format src/ tests/    # Format
uv run mypy src/                  # Type check
uv build                          # Build wheel + sdist

# Scaffold new CLI
copier copy templates/kctl-cli/ /path/to/new-cli/
```

## Architecture

`kctl-common` is a shared Python package (PyPI: kctl-common) used by 5 CLI tools:

- **kctl-next** (kodemeio-next) — Next.js monorepo management
- **kctl-odoo** (kodemeio-odoo) — Odoo 18 ERP management
- **kctl-react** (kodemeio-react) — React PWA monorepo management
- **kctl-api** (kodemeio-fastapi) — FastAPI platform management
- **kctl-claw** (kodemeio-openclaw) — AI agent gateway management

Each CLI uses thin re-export modules in `core/` that import from `kctl_common`, keeping domain-specific code local.

## Key Paths

| Path | Description |
|------|-------------|
| `packages/kctl-common/src/kctl_common/` | Shared library source |
| `packages/kctl-common/tests/` | 80 tests |
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
