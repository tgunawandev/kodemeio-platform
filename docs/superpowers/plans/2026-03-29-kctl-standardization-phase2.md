# Phase 2: kodemeio-core — Migrate 8 CLIs to kctl-lib

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace duplicated core/ modules in all 8 kodemeio-core CLIs with kctl-lib v0.3.0 imports. Standardize CI/CD, code style, and add minimum tests.

**Architecture:** Each CLI's `core/` directory keeps thin re-export files that import from kctl-lib and add service-specific customizations (ServiceConfig, client subclass). Command modules update their imports to use the new core paths. No command behavior changes.

**Tech Stack:** Python 3.12+, kctl-lib>=0.3.0, Typer, httpx, Rich, Pydantic 2

**Prerequisite:** Phase 1 complete (kctl-lib v0.3.0 published to PyPI)

**Spec:** `docs/superpowers/specs/2026-03-29-kctl-standardization-design.md`

**Working directory:** `/home/tgunawan/project/00-new-projects/kodemeio-core`

---

## Migration Order

Ordered by existing test coverage (most tested first = easiest to validate):

| # | CLI | Location | Tests | Client Auth Pattern |
|---|-----|----------|-------|---------------------|
| 1 | kctl-dokploy | kodemeio-dokploy/cli | 33 files | `x-api-key` raw, retry enabled |
| 2 | kctl-hz | kodemeio-hetzner/cli | 6 files | `Authorization: Bearer`, + DNS: `Auth-API-Token` raw |
| 3 | kctl-pg | kodemeio-postgres/cli | 5 files | No httpx client (psycopg + SSH) |
| 4 | kctl-cf | kodemeio-cloudflare/cli | 3 files | `Authorization: Bearer`, response envelope unwrap |
| 5 | kctl-ak | kodemeio-authentik/cli | 0 files | `Authorization: Bearer` |
| 6 | kctl-gatus | kodemeio-gatus/cli | 0 files | `Authorization: Bearer` |
| 7 | kctl-mdm | kodemeio-headwind/cli | 0 files | `Authorization: Bearer` |
| 8 | kctl-waha | kodemeio-waha/cli | 0 files | `X-Api-Key` raw |

---

## Per-CLI Migration Template

Each CLI follows identical steps. The template below uses `{SERVICE}` as placeholder — substitute for each CLI.

### Task N.1: Add kctl-lib dependency and standardize pyproject.toml

**Files:**
- Modify: `kodemeio-{service}/cli/pyproject.toml`

- [ ] **Step 1: Add kctl-lib to dependencies**

Add `"kctl-lib>=0.3.0"` to the `[project] dependencies` list.

- [ ] **Step 2: Standardize ruff and mypy config**

Ensure these sections exist:

```toml
[tool.ruff]
target-version = "py312"
line-length = 120

[tool.ruff.lint]
select = ["E", "F", "I", "W", "UP", "B", "SIM", "N"]

[tool.mypy]
python_version = "3.12"
strict = true
```

- [ ] **Step 3: Standardize dev dependencies**

Ensure dev deps include:

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-httpx>=0.35.0",
    "pytest-cov>=6.0.0",
    "ruff>=0.9.0",
    "mypy>=1.14.0",
    "types-PyYAML>=6.0.0",
]
```

- [ ] **Step 4: Sync and verify**

```bash
cd kodemeio-{service}/cli && uv sync --all-extras
```

- [ ] **Step 5: Commit**

```bash
git add kodemeio-{service}/cli/pyproject.toml kodemeio-{service}/cli/uv.lock
git commit -m "chore(kctl-{name}): add kctl-lib>=0.3.0, standardize tooling"
```

---

### Task N.2: Replace core/exceptions.py

**Files:**
- Modify: `kodemeio-{service}/cli/src/kctl_{name}/core/exceptions.py`

- [ ] **Step 1: Replace with re-exports + service-specific exceptions**

```python
"""Exception hierarchy for kctl-{name}.

Base exceptions re-exported from kctl-lib.
Service-specific exceptions defined below.
"""

from kctl_lib.exceptions import (
    APIError,
    AuthenticationError,
    ConfigError,
    ConnectionError,
    KctlError,
    NotFoundError,
    ValidationError,
)

__all__ = [
    "APIError",
    "AuthenticationError",
    "ConfigError",
    "ConnectionError",
    "KctlError",
    "NotFoundError",
    "ValidationError",
]

# Add any service-specific exceptions below, inheriting from KctlError.
# Example:
# class VaultError(KctlError):
#     """Vault-specific operation error."""
```

Preserve any existing service-specific exception classes (e.g., `TimeoutError` in kctl-dokploy, `VaultError` in kctl-1password) — just make them inherit from the kctl-lib base classes.

- [ ] **Step 2: Update imports in all command files**

Search all `commands/*.py` for `from kctl_{name}.core.exceptions import` — these should continue to work since core/exceptions.py re-exports everything.

- [ ] **Step 3: Run existing tests**

```bash
cd kodemeio-{service}/cli && uv run pytest tests/ -v --tb=short
```

- [ ] **Step 4: Commit**

```bash
git commit -am "refactor(kctl-{name}): use kctl-lib exceptions"
```

---

### Task N.3: Replace core/output.py

**Files:**
- Modify: `kodemeio-{service}/cli/src/kctl_{name}/core/output.py`

- [ ] **Step 1: Replace with re-export**

```python
"""Output utilities for kctl-{name}.

Re-exported from kctl-lib.
"""

from kctl_lib.output import Output

__all__ = ["Output"]
```

- [ ] **Step 2: Verify imports still work**

All command files import `from kctl_{name}.core.output import Output` — this path still works.

- [ ] **Step 3: Run tests, commit**

```bash
cd kodemeio-{service}/cli && uv run pytest tests/ -v --tb=short
git commit -am "refactor(kctl-{name}): use kctl-lib Output"
```

---

### Task N.4: Replace core/callbacks.py

**Files:**
- Modify: `kodemeio-{service}/cli/src/kctl_{name}/core/callbacks.py`

- [ ] **Step 1: Replace with subclass of AppContextBase**

```python
"""App context for kctl-{name}.

Subclasses AppContextBase from kctl-lib.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from kctl_lib.callbacks import AppContextBase

from kctl_{name}.core.config import get_service_config, ServiceConfig


@dataclass
class AppContext(AppContextBase):
    """CLI context for kctl-{name}."""

    # Service-specific fields
    url: str = ""
    api_key: str = ""

    # Populated from config on init
    config: ServiceConfig = field(default_factory=ServiceConfig)
```

Adapt fields to match what the existing AppContext/callbacks.py provides for this specific CLI. The key change is inheriting from `AppContextBase` instead of defining output/json_mode/quiet/format/profile from scratch.

- [ ] **Step 2: Update cli.py callback to use AppContextBase patterns**

Verify the main CLI callback populates AppContext correctly and that `ctx.obj` is set.

- [ ] **Step 3: Run tests, commit**

```bash
cd kodemeio-{service}/cli && uv run pytest tests/ -v --tb=short
git commit -am "refactor(kctl-{name}): subclass AppContextBase for callbacks"
```

---

### Task N.5: Replace core/config.py

**Files:**
- Modify: `kodemeio-{service}/cli/src/kctl_{name}/core/config.py`

- [ ] **Step 1: Replace with kctl-lib ConfigFile + service-specific ServiceConfig**

```python
"""Configuration for kctl-{name}.

Uses kctl-lib's ConfigFile for profile management.
Defines service-specific ServiceConfig model.
"""

from __future__ import annotations

from pydantic import BaseModel

from kctl_lib.config import ConfigFile, is_service_scoped

SERVICE_KEY = "{service_key}"  # e.g. "dokploy", "hetzner", "cloudflare"


class ServiceConfig(BaseModel):
    """Service-specific configuration fields."""

    url: str = ""
    api_key: str = ""
    # Add other service-specific fields


def load_config(profile: str = "") -> ServiceConfig:
    """Load service config from the shared config file."""
    cfg = ConfigFile.load()
    profile_name = profile or cfg.default_profile
    profile_data = cfg.get_profile(profile_name)
    service_data = profile_data.get(SERVICE_KEY, {})
    return ServiceConfig(**service_data)
```

Adapt `ServiceConfig` fields to match what the existing config.py defines for this CLI (url, api_key, token, container_name, etc.).

- [ ] **Step 2: Update all usages of config loading in commands**

Search for existing config loading patterns and update to use the new `load_config()`.

- [ ] **Step 3: Run tests, commit**

```bash
cd kodemeio-{service}/cli && uv run pytest tests/ -v --tb=short
git commit -am "refactor(kctl-{name}): use kctl-lib ConfigFile for config"
```

---

### Task N.6: Replace core/client.py (skip for kctl-pg)

**Files:**
- Modify: `kodemeio-{service}/cli/src/kctl_{name}/core/client.py`

- [ ] **Step 1: Replace with APIClient subclass**

```python
"""API client for kctl-{name}.

Subclasses APIClient from kctl-lib.
"""

from __future__ import annotations

from typing import Any

from kctl_lib.api_client import APIClient


class {Service}Client(APIClient):
    """Synchronous {Service} API client."""

    AUTH_HEADER = "{auth_header}"   # e.g. "x-api-key", "Authorization"
    AUTH_PREFIX = "{auth_prefix}"   # e.g. "", "Bearer"
    API_PREFIX = "{api_prefix}"     # e.g. "/api", "/api/v1", ""
    # BASE_URL = ""                 # Set if hard-coded (e.g. Cloudflare)

    def __init__(self, base_url: str = "", credential: str = "", **kwargs: Any) -> None:
        super().__init__(
            base_url=base_url,
            credential=credential,
            # retry_enabled=True,   # Enable for services that need it (e.g. Dokploy)
            **kwargs,
        )

    # Service-specific methods below
    # Move existing methods (list_projects, deploy, etc.) here unchanged
```

**Per-CLI auth mapping:**

| CLI | AUTH_HEADER | AUTH_PREFIX | API_PREFIX | BASE_URL | retry_enabled |
|-----|-------------|-------------|------------|----------|---------------|
| kctl-dokploy | `x-api-key` | `""` | `/api` | — | `True` |
| kctl-hz (cloud) | `Authorization` | `Bearer` | `""` | `https://api.hetzner.cloud/v1` | `False` |
| kctl-hz (dns) | `Auth-API-Token` | `""` | `""` | `https://dns.hetzner.com/api/v1` | `False` |
| kctl-cf | `Authorization` | `Bearer` | `""` | `https://api.cloudflare.com/client/v4` | `False` |
| kctl-ak | `Authorization` | `Bearer` | `""` | — | `False` |
| kctl-gatus | `Authorization` | `Bearer` | `""` | — | `False` |
| kctl-mdm | `Authorization` | `Bearer` | `""` | — | `False` |
| kctl-waha | `X-Api-Key` | `""` | `/api/v1` | — | `False` |

For **kctl-cf**, also override `_unwrap_response()` to extract from `{success, result}` envelope.

For **kctl-hz**, create two separate client classes: `HetznerCloudClient(APIClient)` and `HetznerDnsClient(APIClient)`.

- [ ] **Step 2: Move service-specific methods**

Copy existing service-specific methods (e.g., `list_projects()`, `deploy()`, `check_health()`) into the new subclass. Remove the duplicated CRUD/auth/error-mapping code that's now in the base class.

- [ ] **Step 3: Update command imports**

All `commands/*.py` files that import from `core.client` should continue to work — the class name stays the same.

- [ ] **Step 4: Run tests, commit**

```bash
cd kodemeio-{service}/cli && uv run pytest tests/ -v --tb=short
git commit -am "refactor(kctl-{name}): subclass kctl-lib APIClient"
```

---

### Task N.7: Standardize entry point and version

**Files:**
- Modify: `kodemeio-{service}/cli/src/kctl_{name}/__init__.py`
- Modify: `kodemeio-{service}/cli/src/kctl_{name}/cli.py`
- Modify: `kodemeio-{service}/cli/pyproject.toml` (entry point)

- [ ] **Step 1: Ensure __init__.py uses `__version__`**

```python
"""kctl-{name}: {description}."""

__version__ = "X.Y.Z"
```

- [ ] **Step 2: Ensure cli.py has `_run()` wrapper with error handling**

```python
from kctl_lib import handle_cli_error, KctlError

def _run() -> None:
    """Entry point with error handling."""
    try:
        app()
    except KctlError as e:
        handle_cli_error(e)
```

- [ ] **Step 3: Update pyproject.toml entry point**

```toml
[project.scripts]
kctl-{name} = "kctl_{name}.cli:_run"
```

- [ ] **Step 4: Run full test suite, commit**

```bash
cd kodemeio-{service}/cli && uv run pytest tests/ -v --tb=short
git commit -am "refactor(kctl-{name}): standardize entry point and version"
```

---

### Task N.8: Add/update CI workflow

**Files:**
- Create or Modify: `kodemeio-{service}/.github/workflows/validate.yml`

- [ ] **Step 1: Create standardized validate.yml**

```yaml
name: Validate kctl-{name}

on:
  push:
    branches: [main]
    paths: ["cli/**"]
  pull_request:
    branches: [main]
    paths: ["cli/**"]

jobs:
  validate:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.12", "3.13"]
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4

      - name: Set up Python ${{ matrix.python-version }}
        run: uv python install ${{ matrix.python-version }}

      - name: Install dependencies
        working-directory: cli
        run: uv sync --all-extras

      - name: Lint
        working-directory: cli
        run: uv run ruff check src/ tests/

      - name: Format check
        working-directory: cli
        run: uv run ruff format --check src/ tests/

      - name: Tests
        working-directory: cli
        run: uv run pytest tests/ -v --tb=short

      - name: Secret detection
        run: |
          if grep -rn "PRIVATE_KEY\|sk-\|op_service" cli/src/ --include="*.py" | grep -v "\.example\|test_\|mock"; then
            echo "::error::Potential secret found in source code"
            exit 1
          fi
```

- [ ] **Step 2: Commit**

```bash
git add kodemeio-{service}/.github/workflows/validate.yml
git commit -m "ci(kctl-{name}): add standardized validation workflow"
```

---

### Task N.9: Add smoke tests (for CLIs with 0 tests)

**Files:**
- Create: `kodemeio-{service}/cli/tests/test_smoke.py`
- Create: `kodemeio-{service}/cli/tests/conftest.py`

Only needed for: kctl-ak, kctl-gatus, kctl-mdm, kctl-waha.

- [ ] **Step 1: Create conftest.py**

```python
"""Shared test configuration for kctl-{name}."""

from kctl_lib.testing import mock_app_context, mock_output, temp_config  # noqa: F401
```

- [ ] **Step 2: Create smoke test**

```python
"""Smoke tests for kctl-{name} CLI."""

from typer.testing import CliRunner

from kctl_{name}.cli import app

runner = CliRunner()


class TestCLISmoke:
    def test_help_exits_zero(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "kctl-{name}" in result.output.lower() or "usage" in result.output.lower()

    def test_version_flag(self):
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0

    def test_config_help(self):
        result = runner.invoke(app, ["config", "--help"])
        assert result.exit_code == 0
```

- [ ] **Step 3: Run tests, commit**

```bash
cd kodemeio-{service}/cli && uv run pytest tests/ -v --tb=short
git commit -am "test(kctl-{name}): add smoke tests"
```

---

## CLI-Specific Notes

### kctl-dokploy (Task 1.*)
- Largest CLI (11K lines, 37 commands, 33 test files)
- Has retry logic → set `retry_enabled=True` in client subclass
- Has `deploy_ops.py`, `health_ops.py`, `notify_ops.py` in core — keep as-is (service-specific)
- Has `aliases.py` command module — keep as-is
- Entry point already uses `cli:_run` pattern

### kctl-hz (Task 2.*)
- Two API clients: `HetznerCloudClient` + `HetznerDnsClient` — create two subclasses
- Has `resolve.py` and `utils.py` in core — keep as-is
- Has plugin system — already compatible with kctl-lib plugins

### kctl-pg (Task 3.*)
- Uses psycopg + SSH tunnel, NOT httpx — **skip Task N.6 (client.py replacement)**
- Still migrate exceptions, output, callbacks, config
- Keep `core/client.py` as-is (psycopg-based)

### kctl-cf (Task 4.*)
- Override `_unwrap_response()` for `{success, result}` envelope
- Hard-coded `BASE_URL = "https://api.cloudflare.com/client/v4"`
- Has `utils.py` in core — keep as-is

### kctl-ak (Task 5.*)
- Has `models/` and `roles/` directories — keep as-is
- Has `core/mailer.py` and `core/resolve.py` — keep as-is
- Entry point uses `cli:app` → change to `cli:_run`

### kctl-gatus (Task 6.*)
- Smallest API surface (8 commands)
- Has `core/resolve.py` — keep as-is

### kctl-mdm (Task 7.*)
- kodemeio-headwind directory but package is kctl-mdm
- No CLAUDE.md at service level — consider adding one

### kctl-waha (Task 8.*)
- Uses `X-Api-Key` header (not Authorization)
- API_PREFIX = `/api/v1`

---

## Verification Checklist (after all 8 CLIs migrated)

For each CLI:
- [ ] `uv run pytest tests/ -v` passes
- [ ] `uv run ruff check src/ tests/` passes
- [ ] `uv run ruff format --check src/ tests/` passes
- [ ] `kctl-{name} --help` works
- [ ] `kctl-{name} --version` works
- [ ] `kctl-{name} config --help` works
- [ ] validate.yml CI workflow exists
- [ ] core/exceptions.py imports from kctl-lib
- [ ] core/output.py imports from kctl-lib
- [ ] core/callbacks.py subclasses AppContextBase
- [ ] core/config.py uses ConfigFile from kctl-lib
- [ ] core/client.py subclasses APIClient (except kctl-pg)
- [ ] pyproject.toml has `kctl-lib>=0.3.0` in dependencies
