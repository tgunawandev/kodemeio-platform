# Move & Refactor kctl-mailcow to kodemeio-platform

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move kctl-mailcow from `kodemeio-core/kodemeio-mailcow/cli` into the `kodemeio-platform/packages/kctl-mailcow` monorepo, refactoring core/ to use kctl-lib base classes (matching kctl-ak patterns).

**Architecture:** Replace custom exceptions, output, config, callbacks, and client with kctl-lib re-exports and subclasses. The MailcowClient subclasses APIClient, overriding AUTH_HEADER/AUTH_PREFIX/API_PREFIX for Mailcow's `X-API-Key` auth and `/api/v1` prefix. All 16 command files are copied with minimal import-path updates. Config switches from custom YAML handling to kctl-lib's config framework.

**Tech Stack:** Python 3.12+, Typer, kctl-lib 0.4.0, httpx, Pydantic 2, Rich, hatchling

---

## File Structure

### New files to create (under `packages/kctl-mailcow/`)

| File | Responsibility |
|------|---------------|
| `pyproject.toml` | Package metadata with kctl-lib workspace dep |
| `src/kctl_mailcow/__init__.py` | Version string |
| `src/kctl_mailcow/__main__.py` | `python -m` entry point |
| `src/kctl_mailcow/cli.py` | Typer app, command registration, `_run()` |
| `src/kctl_mailcow/core/__init__.py` | Empty |
| `src/kctl_mailcow/core/exceptions.py` | Re-export from kctl-lib |
| `src/kctl_mailcow/core/output.py` | Re-export from kctl-lib |
| `src/kctl_mailcow/core/config.py` | Mailcow-specific config wrapping kctl-lib |
| `src/kctl_mailcow/core/callbacks.py` | AppContext subclassing AppContextBase |
| `src/kctl_mailcow/core/client.py` | MailcowClient subclassing APIClient |
| `src/kctl_mailcow/commands/__init__.py` | Empty |
| `src/kctl_mailcow/commands/domains.py` | Copy from old, update imports |
| `src/kctl_mailcow/commands/mailboxes.py` | Copy from old, update imports |
| `src/kctl_mailcow/commands/aliases.py` | Copy from old, update imports |
| `src/kctl_mailcow/commands/dkim.py` | Copy from old, update imports |
| `src/kctl_mailcow/commands/queue.py` | Copy from old, update imports |
| `src/kctl_mailcow/commands/logs.py` | Copy from old, update imports |
| `src/kctl_mailcow/commands/ratelimits.py` | Copy from old, update imports |
| `src/kctl_mailcow/commands/quarantine.py` | Copy from old, update imports |
| `src/kctl_mailcow/commands/status.py` | Copy from old, update imports |
| `src/kctl_mailcow/commands/health.py` | Copy from old, update imports |
| `src/kctl_mailcow/commands/dashboard.py` | Copy from old, update imports |
| `src/kctl_mailcow/commands/sync_jobs.py` | Copy from old, update imports |
| `src/kctl_mailcow/commands/fwdhost.py` | Copy from old, update imports |
| `src/kctl_mailcow/commands/config_cmd.py` | Rewrite to match kctl-ak pattern |
| `src/kctl_mailcow/commands/tls.py` | Copy from old, update imports |
| `src/kctl_mailcow/commands/resources.py` | Copy from old, update imports |
| `tests/__init__.py` | Empty |
| `tests/test_client.py` | Client construction & auth tests |
| `tests/test_config.py` | Config resolution tests |
| `tests/test_exceptions.py` | Exception re-export tests |
| `tests/test_smoke.py` | CLI help/version smoke tests |

---

### Task 1: Create package skeleton and pyproject.toml

**Files:**
- Create: `packages/kctl-mailcow/pyproject.toml`
- Create: `packages/kctl-mailcow/src/kctl_mailcow/__init__.py`
- Create: `packages/kctl-mailcow/src/kctl_mailcow/__main__.py`
- Create: `packages/kctl-mailcow/src/kctl_mailcow/core/__init__.py`
- Create: `packages/kctl-mailcow/src/kctl_mailcow/commands/__init__.py`
- Create: `packages/kctl-mailcow/tests/__init__.py`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p packages/kctl-mailcow/src/kctl_mailcow/core
mkdir -p packages/kctl-mailcow/src/kctl_mailcow/commands
mkdir -p packages/kctl-mailcow/tests
```

- [ ] **Step 2: Write pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "kctl-mailcow"
version = "0.1.0"
description = "Kodemeio Mailcow CLI — manage your Mailcow mail server"
requires-python = ">=3.12"
dependencies = [
    "kctl-lib>=0.4.0",
    "typer>=0.15.0",
    "rich>=13.9.0",
    "pydantic>=2.10.0",
    "pyyaml>=6.0.2",
    "httpx>=0.28.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-httpx>=0.35.0",
    "ruff>=0.9.0",
    "mypy>=1.14.0",
    "types-PyYAML>=6.0.0",
]

[project.scripts]
kctl-mailcow = "kctl_mailcow.cli:_run"

[tool.uv.sources]
kctl-lib = { workspace = true }

[project.entry-points."kctl_mailcow.plugins"]

[tool.hatch.build.targets.wheel]
packages = ["src/kctl_mailcow"]

[tool.ruff]
target-version = "py312"
line-length = 120

[tool.mypy]
python_version = "3.12"
strict = true
```

- [ ] **Step 3: Write __init__.py**

```python
"""kctl-mailcow: Kodemeio Mailcow CLI."""

__version__ = "0.1.0"
```

- [ ] **Step 4: Write __main__.py**

```python
"""Allow running as: python -m kctl_mailcow."""

from kctl_mailcow.cli import app

app()
```

- [ ] **Step 5: Write empty __init__.py files**

Create empty files for `core/__init__.py`, `commands/__init__.py`, `tests/__init__.py`.

- [ ] **Step 6: Verify package is discovered by workspace**

```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform
uv sync --package kctl-mailcow --all-extras 2>&1 | tail -5
```

Expected: uv recognizes kctl-mailcow as a workspace member (may fail on imports since cli.py doesn't exist yet — that's fine).

- [ ] **Step 7: Commit**

```bash
git add packages/kctl-mailcow/
git commit -m "chore(kctl-mailcow): scaffold package skeleton in monorepo"
```

---

### Task 2: Create core/ modules (exceptions, output, config, callbacks, client)

**Files:**
- Create: `packages/kctl-mailcow/src/kctl_mailcow/core/exceptions.py`
- Create: `packages/kctl-mailcow/src/kctl_mailcow/core/output.py`
- Create: `packages/kctl-mailcow/src/kctl_mailcow/core/config.py`
- Create: `packages/kctl-mailcow/src/kctl_mailcow/core/callbacks.py`
- Create: `packages/kctl-mailcow/src/kctl_mailcow/core/client.py`

- [ ] **Step 1: Write core/exceptions.py (re-export from kctl-lib)**

```python
"""Exception hierarchy for kctl-mailcow — re-exports from kctl-lib."""

from __future__ import annotations

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
```

- [ ] **Step 2: Write core/output.py (re-export from kctl-lib)**

```python
"""Output handler for kctl-mailcow — re-exports from kctl-lib."""

from __future__ import annotations

from kctl_lib.output import Output

__all__ = ["Output"]
```

- [ ] **Step 3: Write core/config.py**

```python
"""Profile management and configuration for kctl-mailcow.

Wraps kctl-lib config framework with Mailcow-specific service logic.
"""

from __future__ import annotations

import os

from kctl_lib.config import (
    CONFIG_DIR,
    CONFIG_FILE,
    ConfigFile,
    expand_env,
    get_all_services_in_profile,
    get_default_profile,
    get_profile_names,
    is_service_scoped,
    load_config,
    load_raw_config,
    remove_profile,
    save_raw_config,
    set_default_profile,
)
from kctl_lib.config import get_service_config as _get_service_config
from kctl_lib.config import resolve_active_profile_name as _resolve_active_profile_name
from kctl_lib.config import set_service_config as _set_service_config
from pydantic import BaseModel

# This CLI's service key
SERVICE_KEY = "mailcow"


class ServiceConfig(BaseModel):
    """Service-specific config within a profile."""

    url: str = ""
    api_key: str = ""


def get_service_config(profile_name: str) -> ServiceConfig:
    """Get Mailcow service config from a profile."""
    raw = _get_service_config(
        profile_name,
        SERVICE_KEY,
        valid_fields=list(ServiceConfig.model_fields.keys()),
    )
    if not raw:
        return ServiceConfig()
    return ServiceConfig(**raw)


def set_service_config(profile_name: str, svc_config: ServiceConfig) -> None:
    """Write Mailcow service config into a profile."""
    svc_data = svc_config.model_dump(exclude_defaults=False)
    _set_service_config(profile_name, SERVICE_KEY, svc_data)


def resolve_active_profile_name(profile_name: str | None = None) -> str:
    """Resolve the active profile name."""
    return _resolve_active_profile_name(profile_name, env_prefix="KCTL_MAILCOW")


def resolve_connection(
    profile_name: str | None = None,
    url_override: str | None = None,
    api_key_override: str | None = None,
) -> tuple[str, str]:
    """Resolve API URL and API key from all sources.

    Priority:
    1. CLI flags (url_override, api_key_override)
    2. KCTL_MAILCOW_URL / KCTL_MAILCOW_API_KEY env vars
    3. Profile's mailcow service config
    """
    url = ""
    api_key = ""

    # 3. Config file profile (service-scoped)
    pname = resolve_active_profile_name(profile_name)
    svc = get_service_config(pname)
    if svc.url:
        url = svc.url
    if svc.api_key:
        api_key = expand_env(svc.api_key)

    # 2. KCTL env vars
    if env_url := os.environ.get("KCTL_MAILCOW_URL"):
        url = env_url
    if env_key := os.environ.get("KCTL_MAILCOW_API_KEY"):
        api_key = env_key

    # 1. CLI flags
    if url_override:
        url = url_override
    if api_key_override:
        api_key = api_key_override

    return url, api_key


# Re-export everything that config_cmd.py needs
__all__ = [
    "CONFIG_DIR",
    "CONFIG_FILE",
    "ConfigFile",
    "SERVICE_KEY",
    "ServiceConfig",
    "get_all_services_in_profile",
    "get_default_profile",
    "get_profile_names",
    "get_service_config",
    "is_service_scoped",
    "load_config",
    "load_raw_config",
    "remove_profile",
    "resolve_active_profile_name",
    "resolve_connection",
    "save_raw_config",
    "set_default_profile",
    "set_service_config",
]
```

- [ ] **Step 4: Write core/callbacks.py**

```python
"""Typer global callback and shared context for kctl-mailcow.

Subclasses AppContextBase from kctl-lib, adding Mailcow-specific
client resolution.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from kctl_lib.callbacks import AppContextBase

from kctl_mailcow.core.client import MailcowClient
from kctl_mailcow.core.config import resolve_connection


@dataclass
class AppContext(AppContextBase):
    """Mailcow-specific application context."""

    url_override: str | None = None
    api_key_override: str | None = None
    _client: MailcowClient | None = field(default=None, repr=False)

    @property
    def client(self) -> MailcowClient:
        if self._client is None:
            url, api_key = resolve_connection(
                profile_name=self.profile,
                url_override=self.url_override,
                api_key_override=self.api_key_override,
            )
            self._client = MailcowClient(base_url=url, credential=api_key)
        return self._client
```

- [ ] **Step 5: Write core/client.py**

The Mailcow API uses non-standard REST:
- Auth: `X-API-Key` header (no prefix)
- Base path: `/api/v1`
- GET `/api/v1/get/{resource}/{id}`, POST `/api/v1/add/{resource}`, POST `/api/v1/edit/{resource}`, POST `/api/v1/delete/{resource}`

```python
"""Mailcow API client — subclasses kctl-lib APIClient.

Mailcow API uses non-standard REST patterns:
- GET /api/v1/get/{resource}/{id_or_all}  — read
- POST /api/v1/add/{resource}             — create
- POST /api/v1/edit/{resource}            — update
- POST /api/v1/delete/{resource}          — delete

Auth: X-API-Key header (no prefix).
"""

from __future__ import annotations

from typing import Any

import httpx
from kctl_lib.api_client import APIClient
from kctl_lib.exceptions import ConfigError
from kctl_lib.exceptions import ConnectionError as KctlConnectionError


class MailcowClient(APIClient):
    """Synchronous httpx client for Mailcow API v1."""

    AUTH_HEADER = "X-API-Key"
    AUTH_PREFIX = ""  # Mailcow uses plain key, no "Bearer" prefix
    API_PREFIX = "/api/v1"

    def __init__(self, base_url: str, credential: str, timeout: float = 30.0) -> None:
        if not base_url:
            raise ConfigError("No API URL configured. Run: kctl-mailcow config init")
        super().__init__(base_url=base_url, credential=credential, timeout=timeout)
        # Store root URL for health checks
        self._root_url = base_url.rstrip("/")

    # -- Mailcow-specific CRUD wrappers --

    def mc_get(self, resource: str, identifier: str = "all") -> Any:
        """Mailcow-style GET: /api/v1/get/{resource}/{identifier}."""
        return self.get(f"get/{resource}/{identifier}")

    def mc_add(self, resource: str, data: dict[str, Any]) -> Any:
        """Mailcow-style ADD: POST /api/v1/add/{resource}."""
        return self.post(f"add/{resource}", json=data)

    def mc_edit(self, resource: str, data: dict[str, Any]) -> Any:
        """Mailcow-style EDIT: POST /api/v1/edit/{resource}."""
        return self.post(f"edit/{resource}", json=data)

    def mc_delete(self, resource: str, items: list[str]) -> Any:
        """Mailcow-style DELETE: POST /api/v1/delete/{resource} with items array."""
        return self.post(f"delete/{resource}", json=items)

    def check_health(self) -> tuple[bool, str]:
        """Check Mailcow API health by fetching container status."""
        try:
            self.mc_get("status/containers")
            return True, "ok"
        except Exception as e:
            return False, str(e)
```

- [ ] **Step 6: Commit**

```bash
git add packages/kctl-mailcow/src/kctl_mailcow/core/
git commit -m "feat(kctl-mailcow): add core modules using kctl-lib base classes"
```

---

### Task 3: Write tests for core modules

**Files:**
- Create: `packages/kctl-mailcow/tests/test_exceptions.py`
- Create: `packages/kctl-mailcow/tests/test_client.py`
- Create: `packages/kctl-mailcow/tests/test_config.py`

- [ ] **Step 1: Write test_exceptions.py**

```python
"""Test that exceptions are properly re-exported from kctl-lib."""

from kctl_mailcow.core.exceptions import (
    APIError,
    AuthenticationError,
    ConfigError,
    ConnectionError,
    KctlError,
    NotFoundError,
    ValidationError,
)


class TestExceptionHierarchy:
    def test_all_inherit_from_kctl_error(self) -> None:
        for exc_cls in [ConfigError, AuthenticationError, NotFoundError, APIError, ConnectionError, ValidationError]:
            assert issubclass(exc_cls, KctlError)

    def test_kctl_error_is_exception(self) -> None:
        assert issubclass(KctlError, Exception)
```

- [ ] **Step 2: Write test_client.py**

```python
"""Test MailcowClient construction and auth header."""

import pytest
from kctl_lib.exceptions import ConfigError

from kctl_mailcow.core.client import MailcowClient


class TestClientConstruction:
    def test_requires_base_url(self) -> None:
        with pytest.raises(ConfigError, match="No API URL configured"):
            MailcowClient(base_url="", credential="test-key")

    def test_requires_credential(self) -> None:
        with pytest.raises(ConfigError, match="credential is required"):
            MailcowClient(base_url="https://mail.example.com", credential="")

    def test_auth_header_uses_x_api_key(self) -> None:
        client = MailcowClient(base_url="https://mail.example.com", credential="my-key")
        headers = client._build_auth_header()
        assert headers == {"X-API-Key": "my-key"}
        client.close()

    def test_api_prefix_appended(self) -> None:
        client = MailcowClient(base_url="https://mail.example.com", credential="my-key")
        assert client._base_url.endswith("/api/v1")
        client.close()

    def test_api_prefix_not_doubled(self) -> None:
        client = MailcowClient(base_url="https://mail.example.com/api/v1", credential="my-key")
        assert client._base_url.endswith("/api/v1")
        assert "/api/v1/api/v1" not in client._base_url
        client.close()

    def test_context_manager(self) -> None:
        with MailcowClient(base_url="https://mail.example.com", credential="key") as client:
            assert client._base_url.endswith("/api/v1")
```

- [ ] **Step 3: Write test_config.py**

```python
"""Test config resolution logic."""

import os

from kctl_mailcow.core.config import SERVICE_KEY, resolve_active_profile_name, resolve_connection


class TestServiceKey:
    def test_service_key_is_mailcow(self) -> None:
        assert SERVICE_KEY == "mailcow"


class TestResolveActiveProfile:
    def test_explicit_profile_wins(self) -> None:
        assert resolve_active_profile_name("staging") == "staging"

    def test_env_var_used(self, monkeypatch: object) -> None:
        import pytest

        mp = pytest.MonkeyPatch()
        mp.setenv("KCTL_MAILCOW_PROFILE", "from-env")
        try:
            assert resolve_active_profile_name() == "from-env"
        finally:
            mp.undo()


class TestResolveConnection:
    def test_cli_flags_override_env(self, monkeypatch: object) -> None:
        import pytest

        mp = pytest.MonkeyPatch()
        mp.setenv("KCTL_MAILCOW_URL", "https://env.example.com")
        mp.setenv("KCTL_MAILCOW_API_KEY", "env-key")
        try:
            url, key = resolve_connection(
                url_override="https://flag.example.com",
                api_key_override="flag-key",
            )
            assert url == "https://flag.example.com"
            assert key == "flag-key"
        finally:
            mp.undo()

    def test_env_vars_used(self, monkeypatch: object) -> None:
        import pytest

        mp = pytest.MonkeyPatch()
        mp.setenv("KCTL_MAILCOW_URL", "https://env.example.com")
        mp.setenv("KCTL_MAILCOW_API_KEY", "env-key")
        try:
            url, key = resolve_connection()
            assert url == "https://env.example.com"
            assert key == "env-key"
        finally:
            mp.undo()
```

- [ ] **Step 4: Run tests**

```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform
uv run pytest packages/kctl-mailcow/tests/ -v
```

Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add packages/kctl-mailcow/tests/
git commit -m "test(kctl-mailcow): add core module tests (client, config, exceptions)"
```

---

### Task 4: Create cli.py and copy all command files

**Files:**
- Create: `packages/kctl-mailcow/src/kctl_mailcow/cli.py`
- Create: all 16 command files in `packages/kctl-mailcow/src/kctl_mailcow/commands/`

- [ ] **Step 1: Write cli.py**

```python
"""Main CLI entry point for kctl-mailcow."""

from __future__ import annotations

from typing import Annotated

import typer
from kctl_lib import KctlError, handle_cli_error

from kctl_mailcow import __version__
from kctl_mailcow.commands.aliases import app as aliases_app
from kctl_mailcow.commands.config_cmd import app as config_app
from kctl_mailcow.commands.dashboard import app as dashboard_app
from kctl_mailcow.commands.dkim import app as dkim_app
from kctl_mailcow.commands.domains import app as domains_app
from kctl_mailcow.commands.fwdhost import app as fwdhost_app
from kctl_mailcow.commands.health import app as health_app
from kctl_mailcow.commands.logs import app as logs_app
from kctl_mailcow.commands.mailboxes import app as mailboxes_app
from kctl_mailcow.commands.quarantine import app as quarantine_app
from kctl_mailcow.commands.queue import app as queue_app
from kctl_mailcow.commands.ratelimits import app as ratelimits_app
from kctl_mailcow.commands.resources import app as resources_app
from kctl_mailcow.commands.status import app as status_app
from kctl_mailcow.commands.sync_jobs import app as sync_jobs_app
from kctl_mailcow.commands.tls import app as tls_app
from kctl_mailcow.core.callbacks import AppContext


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"kctl-mailcow {__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="kctl-mailcow",
    help="Kodemeio Mailcow CLI - manage your Mailcow mail server.",
    no_args_is_help=True,
    rich_markup_mode="rich",
    pretty_exceptions_enable=False,
)


@app.callback()
def main(
    ctx: typer.Context,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress info messages")] = False,
    profile: Annotated[str | None, typer.Option("--profile", "-p", help="Config profile name")] = None,
    url: Annotated[str | None, typer.Option("--url", help="API URL override")] = None,
    api_key: Annotated[str | None, typer.Option("--api-key", help="API key override")] = None,
    version: Annotated[
        bool, typer.Option("--version", "-V", callback=version_callback, is_eager=True, help="Show version")
    ] = False,
) -> None:
    """Kodemeio Mailcow CLI."""
    ctx.ensure_object(dict)
    ctx.obj = AppContext(
        json_mode=json_output,
        quiet=quiet,
        profile=profile,
        url_override=url,
        api_key_override=api_key,
    )


# Register all command groups
app.add_typer(domains_app, name="domains")
app.add_typer(mailboxes_app, name="mailboxes")
app.add_typer(aliases_app, name="aliases")
app.add_typer(dkim_app, name="dkim")
app.add_typer(queue_app, name="queue")
app.add_typer(logs_app, name="logs")
app.add_typer(ratelimits_app, name="ratelimits")
app.add_typer(quarantine_app, name="quarantine")
app.add_typer(status_app, name="status")
app.add_typer(health_app, name="health")
app.add_typer(dashboard_app, name="dashboard")
app.add_typer(sync_jobs_app, name="sync-jobs")
app.add_typer(fwdhost_app, name="fwdhost")
app.add_typer(config_app, name="config")
app.add_typer(tls_app, name="tls")
app.add_typer(resources_app, name="resources")


def _run() -> None:
    """Entry point with error handling."""
    try:
        app()
    except KctlError as e:
        handle_cli_error(e)


if __name__ == "__main__":
    _run()
```

- [ ] **Step 2: Copy all command files from old location**

For each of the 16 command files, copy from old location and apply these changes:
1. Remove `from typing import Optional` (use `str | None` instead)
2. Change imports from `kctl_mailcow.core.exceptions` to `kctl_mailcow.core.exceptions`  (path stays same)
3. Change imports from `kctl_mailcow.core.callbacks` to `kctl_mailcow.core.callbacks` (path stays same)
4. In `domains.py` and any file using `_handle_result`: change `c.output.json_mode` to `c.json_mode`

The import paths (`kctl_mailcow.core.callbacks`, `kctl_mailcow.core.config`) remain the same since the package name doesn't change. The key changes are:

**For all command files (except config_cmd.py):**
- Replace `Optional[str]` with `str | None`, `Optional[int]` with `int | None`, `Optional[bool]` with `bool | None`
- Remove `from typing import Optional` if no longer needed
- Imports from `kctl_mailcow.core.callbacks` stay the same

**For domains.py `_handle_result`:**
- Change `c.output.json_mode` to `c.json_mode` (AppContextBase exposes json_mode directly)

```bash
# Copy all command files
SRC=/home/tgunawan/project/00-new-projects/kodemeio-core/kodemeio-mailcow/cli/src/kctl_mailcow/commands
DST=packages/kctl-mailcow/src/kctl_mailcow/commands

for f in aliases.py dashboard.py dkim.py domains.py fwdhost.py health.py logs.py \
         mailboxes.py quarantine.py queue.py ratelimits.py resources.py status.py \
         sync_jobs.py tls.py; do
    cp "$SRC/$f" "$DST/$f"
done
```

Then for each file, update `Optional[X]` to `X | None` and clean up imports.

- [ ] **Step 3: Rewrite config_cmd.py to match kctl-ak pattern**

The config_cmd.py needs a full rewrite because:
- Old version imports from its own `kctl_mailcow.core.config` (custom)
- New version imports from the new kctl-lib-backed `kctl_mailcow.core.config`
- Old `MailcowClient(base_url=url, api_key=key)` becomes `MailcowClient(base_url=url, credential=key)`
- Old `_test_connection` uses old client constructor
- `_mask_key` stays the same pattern

Copy the old `config_cmd.py` and apply these changes:
1. Import `MailcowClient` from `kctl_mailcow.core.client`
2. Import exceptions from `kctl_mailcow.core.exceptions`
3. In `_test_connection`: `MailcowClient(base_url=url, credential=api_key)`
4. Replace `Optional[str]` with `str | None`
5. Import `KctlError` from `kctl_mailcow.core.exceptions`

- [ ] **Step 4: Fix _handle_result in domains.py**

In `domains.py`, the `_handle_result` function uses `c.output.json_mode`. Since `AppContextBase` has `json_mode` directly, change to `c.json_mode`:

```python
# In _handle_result, change:
#   if c.output.json_mode:
# to:
#   if c.json_mode:
```

Also check all other command files for `c.output.json_mode` usage and fix similarly.

- [ ] **Step 5: Commit**

```bash
git add packages/kctl-mailcow/src/kctl_mailcow/cli.py
git add packages/kctl-mailcow/src/kctl_mailcow/commands/
git commit -m "feat(kctl-mailcow): add cli.py and all 16 command groups"
```

---

### Task 5: Write smoke tests and verify full CLI works

**Files:**
- Create: `packages/kctl-mailcow/tests/test_smoke.py`

- [ ] **Step 1: Write test_smoke.py**

```python
"""Smoke tests — verify CLI loads and help works."""

from typer.testing import CliRunner

from kctl_mailcow.cli import app

runner = CliRunner()


class TestCLIHelp:
    def test_main_help(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "kctl-mailcow" in result.output.lower() or "mailcow" in result.output.lower()

    def test_version(self) -> None:
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output


class TestCommandGroupsRegistered:
    """Verify all 16 command groups appear in help."""

    GROUPS = [
        "domains", "mailboxes", "aliases", "dkim", "queue", "logs",
        "ratelimits", "quarantine", "status", "health", "dashboard",
        "sync-jobs", "fwdhost", "config", "tls", "resources",
    ]

    def test_all_groups_in_help(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        for group in self.GROUPS:
            assert group in result.output, f"Command group '{group}' not found in help output"


class TestSubcommandHelp:
    """Spot-check a few subcommands load without error."""

    def test_domains_list_help(self) -> None:
        result = runner.invoke(app, ["domains", "list", "--help"])
        assert result.exit_code == 0

    def test_config_init_help(self) -> None:
        result = runner.invoke(app, ["config", "init", "--help"])
        assert result.exit_code == 0

    def test_mailboxes_list_help(self) -> None:
        result = runner.invoke(app, ["mailboxes", "list", "--help"])
        assert result.exit_code == 0

    def test_health_help(self) -> None:
        result = runner.invoke(app, ["health", "--help"])
        assert result.exit_code == 0
```

- [ ] **Step 2: Run all tests**

```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform
uv run pytest packages/kctl-mailcow/tests/ -v
```

Expected: All tests pass.

- [ ] **Step 3: Run ruff lint**

```bash
uv run ruff check packages/kctl-mailcow/src/ --fix
```

Expected: No errors (or auto-fixable ones).

- [ ] **Step 4: Commit**

```bash
git add packages/kctl-mailcow/tests/test_smoke.py
git commit -m "test(kctl-mailcow): add smoke tests for CLI and all command groups"
```

---

### Task 6: Final validation and cleanup

- [ ] **Step 1: Verify package installs and CLI runs**

```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform
uv sync --package kctl-mailcow --all-extras
uv run kctl-mailcow --help
uv run kctl-mailcow --version
```

Expected: Help shows all 16 command groups, version shows 0.1.0.

- [ ] **Step 2: Run full test suite**

```bash
uv run pytest packages/kctl-mailcow/tests/ -v --tb=short
```

Expected: All tests pass.

- [ ] **Step 3: Run ruff and mypy**

```bash
uv run ruff check packages/kctl-mailcow/src/
uv run mypy packages/kctl-mailcow/src/ --ignore-missing-imports
```

Expected: Clean or minimal warnings.

- [ ] **Step 4: Final commit if any fixups needed**

```bash
git add -A packages/kctl-mailcow/
git commit -m "chore(kctl-mailcow): final cleanup after monorepo migration"
```
