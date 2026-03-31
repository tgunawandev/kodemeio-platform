# kctl-common

Shared core library for all kctl-* CLI tools. Published to PyPI as `kctl-common`.

## Installation

```bash
# As a dependency (in pyproject.toml)
dependencies = ["kctl-common>=0.3.1"]

# For development
cd packages/kctl-common
uv sync --all-extras
```

## Modules

| Module | Purpose |
|--------|---------|
| `api_client.py` | `APIClient` — sync HTTP base client with retry, auth, error mapping |
| `async_api_client.py` | `AsyncAPIClient` — async HTTP base client with retry, auth, error mapping |
| `callbacks.py` | `AppContextBase` dataclass — lazy Output init, subclassed by each CLI |
| `completions.py` | Shell completion generation + install (zsh/bash/fish) |
| `config.py` | Profile framework — `~/.config/kodemeio/config.yaml`, service-scoped, env var expansion |
| `docker.py` | `DockerManager` — Docker Compose wrapper (up/down/ps/logs/restart/exec) |
| `doctor_base.py` | `DoctorCheck` protocol + `run_doctor()` + built-in checks |
| `exceptions.py` | 9 exception classes: KctlError hierarchy |
| `git_ops.py` | Git workflow helpers — branch_status, pr_create, changelog_generate |
| `history.py` | `HistoryStore` — SQLite at `~/.local/share/kodemeio/{app}/history.db` |
| `monitor_base.py` | `health_check_url()`, `ssl_check()`, `dns_check()` |
| `output.py` | `Output` class — pretty (Rich), json, csv, yaml formatting |
| `plugins.py` | `KctlPlugin` protocol + plugin discovery |
| `runner.py` | `run()`, `run_quiet()`, `get_git_sha()`, `get_git_branch()` |
| `self_update.py` | PyPI version check + uv tool upgrade |
| `skill_generator.py` | `SkillGenerator` — Typer app introspection for SKILL.md generation |
| `testing.py` | `mock_output()`, `mock_app_context()`, `temp_config()` |
| `validate.py` | YAML/JSON/env/Dockerfile linting with `Issue` dataclass |

## Development

```bash
uv run pytest tests/ -v          # 247 tests
uv run ruff check src/           # Lint
uv run mypy src/                 # Type check
uv build                         # Build package
```
