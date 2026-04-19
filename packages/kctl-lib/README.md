# kctl-lib

Shared core library for all kctl-* CLI tools. Published to PyPI as `kctl-lib`.

## Installation

```bash
# As a dependency (in pyproject.toml)
dependencies = ["kctl-lib>=0.4.0"]

# For development
cd packages/kctl-lib
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

## Profile Resolution (Stage B)

Two-tier taxonomy: 4 fixed platform profiles (`abcfood`, `kodemeio`, `idtpp`, `local`) plus app profiles with the form `<platform>-<tenant>-<stack>-<app>[-<env>]`.

### API

```python
resolve_inheritance_chain(profile_name: str) -> list[str]
# idtpp-tpp-odoo-erp → [idtpp-tpp-odoo-erp, idtpp-tpp-odoo, idtpp-tpp, idtpp]
# Non-existent ancestors in the chain are skipped automatically.
```

```python
get_service_config(profile_name: str, service_key: str, valid_fields: list[str] | None = None) -> dict
# Walks inheritance chain; first profile that defines service_key wins.
# Raises ConfigError if service_key not found anywhere in chain.
# Explicit leaf profile is always required — no implicit default.
```

```python
resolve_active_profile_name(profile_name: str | None, env_prefix: str) -> str
# Returns profile from --profile flag or KCTL_{env_prefix}_PROFILE env var.
# Raises ValueError (listing available profiles) if neither source is set.
```

```python
AppContextBase.emit_banner(app: str, inheritance_chain: list[str], service_summary: str) -> None
# Prints profile banner to stderr once per invocation.
# Suppressed when output.quiet or output.json is True.
```

```python
profile_banner(app: str, profile: str, inheritance_chain: list[str], service_summary: str) -> str
# Returns the formatted banner string (multiline).
# Example output:
#   ▶ kctl-dokploy
#     profile : idtpp-tpp-odoo-erp  ←  idtpp
#     target  : https://dokploy.idtpp.com
```

### Secret masking

`SECRET_FIELDS` frozenset defines field names masked in `kctl-profiles show` output as `first4****last4`. Use `--reveal` to expose plaintext values.

### kctl-profiles meta-CLI

Entry point installed with kctl-lib (no separate package). Commands: `list`, `show <profile> [--reveal]`, `current [-p <profile>]`, `migrate [--config <path>] [--yes]`.

### Test isolation

Autouse fixture in `tests/conftest.py` monkeypatches `CONFIG_FILE` → `tmp_path` for every test. Opt out with `@pytest.mark.real_config`.

## Development

```bash
uv run pytest tests/ -v          # 247 tests
uv run ruff check src/           # Lint
uv run mypy src/                 # Type check
uv build                         # Build package
```
