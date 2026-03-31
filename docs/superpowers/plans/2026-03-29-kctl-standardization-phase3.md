# Phase 3: kodemeio-saas — Migrate 3 CLIs to kctl-lib

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace duplicated core/ modules in kodemeio-saas CLIs with kctl-lib v0.3.0 imports. Standardize structure and add tests.

**Architecture:** Same re-export pattern as Phase 2. kctl-claude requires extra structural work due to divergent module naming.

**Tech Stack:** Python 3.12+, kctl-lib>=0.3.0, Typer, httpx, Rich, Pydantic 2

**Prerequisite:** Phase 1 complete (kctl-lib v0.3.0 published to PyPI)

**Spec:** `docs/superpowers/specs/2026-03-29-kctl-standardization-design.md`

**Working directory:** `/home/tgunawan/project/00-new-projects/kodemeio-saas`

---

## Migration Order

| # | CLI | Location | Tests | Special Notes |
|---|-----|----------|-------|---------------|
| 1 | kctl-telegram | kodemeio-telegram/cli | 9 files | Extraction markers already in code |
| 2 | kctl-1password | kodemeio-1password/cli | 0 CLI tests | Uses `op` CLI subprocess, not httpx for some ops |
| 3 | kctl-claude | kodemeio-claude/cli | 0 tests | Most divergent — needs structural alignment |

---

## Task 1.*: kctl-telegram

Follow the **Phase 2 Per-CLI Migration Template** (Tasks N.1 through N.8) with these specifics:

| Setting | Value |
|---------|-------|
| Service directory | `kodemeio-telegram/cli` |
| Package name | `kctl_telegram` |
| SERVICE_KEY | `"telegram"` |
| AUTH_HEADER | `X-Api-Key` |
| AUTH_PREFIX | `""` |
| API_PREFIX | `/api/v1` |
| retry_enabled | `False` |
| Entry point fix | Change `cli:app` → `cli:_run` |
| Version fix | Already uses `__version__` |

**Additional kctl-telegram specifics:**
- Remove `# KCTL-COMMON: extractable` comments from all core modules after migration
- Has `get_all()` pagination method on client — keep as service-specific method on subclass
- Has `check_health()` and `check_ready()` — keep as service-specific
- Has 9 existing test files — run them all after each migration step

---

## Task 2.*: kctl-1password

Follow the **Phase 2 Per-CLI Migration Template** (Tasks N.1 through N.9) with these specifics:

| Setting | Value |
|---------|-------|
| Service directory | `kodemeio-1password/cli` |
| Package name | `kctl_1password` |
| SERVICE_KEY | `"1password"` |
| Entry point fix | Change `cli:app` → `cli:_run` |
| Version fix | Change `VERSION = "0.1.0"` → `__version__ = "0.1.0"` |

**kctl-1password special handling:**

The client uses the `op` CLI subprocess (1Password CLI) rather than a direct HTTP API. The `core/client.py` wraps shell commands, not httpx.

- [ ] **Do NOT subclass APIClient.** Keep `core/client.py` as-is — it's a subprocess wrapper, not an HTTP client.
- [ ] Still migrate: exceptions.py, output.py, callbacks.py, config.py
- [ ] Preserve service-specific exceptions: `VaultError`, `OpCliError`
- [ ] Add smoke tests (Task N.9)

**Exception migration for kctl-1password:**

```python
"""Exception hierarchy for kctl-1password."""

from kctl_lib.exceptions import (
    AuthenticationError,
    ConfigError,
    ConnectionError,
    KctlError,
    NotFoundError,
)

__all__ = [
    "AuthenticationError",
    "ConfigError",
    "ConnectionError",
    "KctlError",
    "NotFoundError",
    "OpCliError",
    "VaultError",
]


class VaultError(KctlError):
    """1Password vault operation error."""


class OpCliError(KctlError):
    """1Password CLI (op) execution error."""

    def __init__(self, command: str, returncode: int, stderr: str = ""):
        self.command = command
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(f"op CLI failed (exit {returncode}): {command}\n{stderr}".strip())
```

---

## Task 3.*: kctl-claude

Follow the **Phase 2 Per-CLI Migration Template** with these specifics plus extra structural alignment steps:

| Setting | Value |
|---------|-------|
| Service directory | `kodemeio-claude/cli` |
| Package name | `kctl_claude` |
| SERVICE_KEY | `"claude"` |
| Entry point fix | Already uses `cli:_run` |
| Version fix | Already uses `__version__` |

**kctl-claude structural issues to fix:**

### Task 3.0: Structural alignment (before template migration)

- [ ] **Step 1: Create core/exceptions.py**

kctl-claude has no exceptions module. Create one:

```python
"""Exception hierarchy for kctl-claude."""

from kctl_lib.exceptions import (
    CommandError,
    ConfigError,
    ConnectionError,
    KctlError,
    ValidationError,
)

__all__ = [
    "CommandError",
    "ConfigError",
    "ConnectionError",
    "KctlError",
    "ValidationError",
]
```

- [ ] **Step 2: Rename core/context.py → core/callbacks.py**

```bash
cd kodemeio-claude/cli
git mv src/kctl_claude/core/context.py src/kctl_claude/core/callbacks.py
```

Update all imports in command files:
```python
# Before
from kctl_claude.core.context import AppContext
# After
from kctl_claude.core.callbacks import AppContext
```

- [ ] **Step 3: Create core/config.py**

kctl-claude has no config.py (profile support). Create one:

```python
"""Configuration for kctl-claude."""

from __future__ import annotations

from pydantic import BaseModel

from kctl_lib.config import ConfigFile

SERVICE_KEY = "claude"


class ServiceConfig(BaseModel):
    """Claude service configuration."""

    config_dir: str = ""
    backup_dir: str = ""


def load_config(profile: str = "") -> ServiceConfig:
    """Load service config from shared config file."""
    cfg = ConfigFile.load()
    profile_name = profile or cfg.default_profile
    profile_data = cfg.get_profile(profile_name)
    service_data = profile_data.get(SERVICE_KEY, {})
    return ServiceConfig(**service_data)
```

- [ ] **Step 4: Keep core/checks.py and core/paths.py**

These are service-specific modules — keep unchanged.

- [ ] **Step 5: Commit structural changes**

```bash
git add -A
git commit -m "refactor(kctl-claude): align module structure with kctl-* standard"
```

- [ ] **Step 6: Add config subcommands**

kctl-claude lacks the standard 9 config subcommands. Create `commands/config_cmd.py` following the copier template pattern from kodemeio-platform:

```python
"""Config subcommands for kctl-claude."""

from __future__ import annotations

import typer

from kctl_lib.config import ConfigFile

app = typer.Typer(help="Manage configuration profiles.")

SERVICE_KEY = "claude"


@app.command()
def init() -> None:
    """Initialize configuration with defaults."""
    cfg = ConfigFile.load_or_create()
    cfg.ensure_profile("default", {SERVICE_KEY: {}})
    cfg.save()
    typer.echo("Configuration initialized.")


@app.command()
def show(profile: str = "") -> None:
    """Show current configuration."""
    cfg = ConfigFile.load()
    profile_name = profile or cfg.default_profile
    data = cfg.get_profile(profile_name)
    service = data.get(SERVICE_KEY, {})
    for k, v in service.items():
        typer.echo(f"  {k}: {v}")


@app.command()
def profiles() -> None:
    """List all profiles."""
    cfg = ConfigFile.load()
    for name in cfg.profile_names():
        marker = " (active)" if name == cfg.default_profile else ""
        typer.echo(f"  {name}{marker}")


@app.command()
def current() -> None:
    """Show active profile name."""
    cfg = ConfigFile.load()
    typer.echo(cfg.default_profile)


@app.command()
def use(name: str = typer.Argument(..., help="Profile to activate")) -> None:
    """Switch active profile."""
    cfg = ConfigFile.load()
    cfg.set_default(name)
    cfg.save()
    typer.echo(f"Switched to profile: {name}")
```

Register in cli.py:
```python
from kctl_claude.commands import config_cmd
app.add_typer(config_cmd.app, name="config")
```

- [ ] **Step 7: Add validate.yml CI workflow**

kctl-claude only has notify.yml. Add validate.yml using the standard template from Phase 2 Task N.8.

- [ ] **Step 8: Add smoke tests**

Follow Phase 2 Task N.9 template.

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat(kctl-claude): add config subcommands, CI, and smoke tests"
```

Then proceed with the standard Phase 2 template tasks (N.2 through N.7) for the remaining core module replacements.

---

## Task 4: Scaffold placeholder CLIs

**Files:**
- Create: `kodemeio-github/cli/` (full scaffold)
- Create: `kodemeio-linear/cli/` (full scaffold)
- Create: `kodemeio-notion/cli/` (full scaffold)
- Create: `kodemeio-sentry/cli/` (full scaffold)

- [ ] **Step 1: Run copier for each placeholder**

```bash
TEMPLATE=/home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform/templates/kctl-cli

copier copy "$TEMPLATE" kodemeio-github/cli/ \
  --data project_name=kctl-github \
  --data service_key=github \
  --data package_name=kctl_github \
  --data description="GitHub integration management" \
  --data cli_type=server \
  --data env_prefix=KCTL_GITHUB

copier copy "$TEMPLATE" kodemeio-linear/cli/ \
  --data project_name=kctl-linear \
  --data service_key=linear \
  --data package_name=kctl_linear \
  --data description="Linear project management" \
  --data cli_type=server \
  --data env_prefix=KCTL_LINEAR

copier copy "$TEMPLATE" kodemeio-notion/cli/ \
  --data project_name=kctl-notion \
  --data service_key=notion \
  --data package_name=kctl_notion \
  --data description="Notion workspace management" \
  --data cli_type=server \
  --data env_prefix=KCTL_NOTION

copier copy "$TEMPLATE" kodemeio-sentry/cli/ \
  --data project_name=kctl-sentry \
  --data service_key=sentry \
  --data package_name=kctl_sentry \
  --data description="Sentry error tracking management" \
  --data cli_type=server \
  --data env_prefix=KCTL_SENTRY
```

- [ ] **Step 2: Verify each scaffold builds**

```bash
for dir in kodemeio-github kodemeio-linear kodemeio-notion kodemeio-sentry; do
  echo "=== $dir ==="
  cd "$dir/cli" && uv sync --all-extras && uv run pytest tests/ -v --tb=short
  cd ../..
done
```

- [ ] **Step 3: Add validate.yml to each**

Use standard CI template from Phase 2 Task N.8.

- [ ] **Step 4: Commit all scaffolds**

```bash
git add kodemeio-github/ kodemeio-linear/ kodemeio-notion/ kodemeio-sentry/
git commit -m "feat: scaffold kctl-github, kctl-linear, kctl-notion, kctl-sentry from copier template"
```

---

## Verification Checklist (after all kodemeio-saas CLIs migrated)

For each of kctl-telegram, kctl-1password, kctl-claude:
- [ ] `uv run pytest tests/ -v` passes
- [ ] `uv run ruff check src/ tests/` passes
- [ ] `kctl-{name} --help` works
- [ ] `kctl-{name} --version` works
- [ ] `kctl-{name} config --help` works
- [ ] validate.yml CI workflow exists
- [ ] core/ modules import from kctl-lib
- [ ] pyproject.toml has `kctl-lib>=0.3.0`
- [ ] Entry point is `cli:_run`
- [ ] Version uses `__version__`

For each placeholder (kctl-github, kctl-linear, kctl-notion, kctl-sentry):
- [ ] Scaffold builds and tests pass
- [ ] validate.yml exists
- [ ] `kctl-{name} --help` works
