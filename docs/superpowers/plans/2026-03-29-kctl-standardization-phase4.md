# Phase 4: kodemeio-app — Update 5 Existing CLIs

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update the 5 kodemeio-app CLIs that already use kctl-lib to leverage the new APIClient/AsyncAPIClient base classes. Bump dependency to >=0.3.0.

**Architecture:** kctl-api and kctl-odoo have client.py and async_client.py marked for extraction — migrate these to subclass the new base classes. kctl-next, kctl-react, and kctl-claw only need a version bump.

**Tech Stack:** Python 3.12+, kctl-lib>=0.3.0

**Prerequisite:** Phase 1 complete (kctl-lib v0.3.0 published to PyPI)

**Spec:** `docs/superpowers/specs/2026-03-29-kctl-standardization-design.md`

**Working directories:**
- `/home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-next/cli`
- `/home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-react/cli`
- `/home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-fastapi/cli`
- `/home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-odoo/cli`
- `/home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-openclaw/cli`

---

## Task 1: Bump kctl-lib in kctl-next, kctl-react, kctl-claw

These 3 CLIs don't have httpx API clients — they only need a version bump.

**Files (per CLI):**
- Modify: `cli/pyproject.toml`

- [ ] **Step 1: Update dependency version in each pyproject.toml**

Change `kctl-lib>=0.2.1` → `kctl-lib>=0.3.0` in:
- `kodemeio-next/cli/pyproject.toml`
- `kodemeio-react/cli/pyproject.toml`
- `kodemeio-openclaw/cli/pyproject.toml`

- [ ] **Step 2: Sync and test each**

```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-next/cli && uv sync --all-extras && uv run pytest tests/ -v --tb=short
cd /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-react/cli && uv sync --all-extras && uv run pytest tests/ -v --tb=short
cd /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-openclaw/cli && uv sync --all-extras && uv run pytest tests/ -v --tb=short
```

Expected: All tests pass — kctl-lib v0.3.0 is backward compatible.

- [ ] **Step 3: Commit in each repo**

```bash
# In each repo:
git add cli/pyproject.toml cli/uv.lock
git commit -m "chore: bump kctl-lib to >=0.3.0"
```

---

## Task 2: Migrate kctl-api client to APIClient subclass

**Files:**
- Modify: `kodemeio-fastapi/cli/src/kctl_api/core/client.py`
- Modify: `kodemeio-fastapi/cli/src/kctl_api/core/async_client.py`
- Modify: `kodemeio-fastapi/cli/pyproject.toml`

- [ ] **Step 1: Bump kctl-lib version**

In `kodemeio-fastapi/cli/pyproject.toml`, change `kctl-lib>=0.2.1` → `kctl-lib>=0.3.0`.

- [ ] **Step 2: Read current client.py and async_client.py**

Read both files fully. Identify:
- Service-specific methods to keep
- Auth pattern (JWT Bearer + API key)
- Any custom error handling beyond the base class

- [ ] **Step 3: Refactor client.py to subclass APIClient**

```python
"""FastAPI platform API client.

Subclasses APIClient from kctl-lib.
"""

from __future__ import annotations

from typing import Any

from kctl_lib.api_client import APIClient


class ApiClient(APIClient):
    """Synchronous FastAPI platform client."""

    AUTH_HEADER = "Authorization"
    AUTH_PREFIX = "Bearer"
    API_PREFIX = "/api/v1"

    def __init__(self, base_url: str = "", credential: str = "", **kwargs: Any) -> None:
        super().__init__(base_url=base_url, credential=credential, **kwargs)

    # Keep all service-specific methods from the existing client.py
    # (list_apps, deploy, health_check, etc.)
    # Remove: __init__ boilerplate, get/post/put/patch/delete, error mapping,
    #          auth header construction — all handled by base class
```

- [ ] **Step 4: Refactor async_client.py to subclass AsyncAPIClient**

Same pattern but using `AsyncAPIClient`:

```python
"""FastAPI platform async API client."""

from __future__ import annotations

from typing import Any

from kctl_lib.async_api_client import AsyncAPIClient


class AsyncApiClient(AsyncAPIClient):
    """Async FastAPI platform client."""

    AUTH_HEADER = "Authorization"
    AUTH_PREFIX = "Bearer"
    API_PREFIX = "/api/v1"

    def __init__(self, base_url: str = "", credential: str = "", **kwargs: Any) -> None:
        super().__init__(base_url=base_url, credential=credential, **kwargs)

    # Keep all service-specific async methods
```

- [ ] **Step 5: Remove `# KCTL-COMMON: extractable` comments**

- [ ] **Step 6: Run tests**

```bash
cd kodemeio-fastapi/cli && uv sync --all-extras && uv run pytest tests/ -v --tb=short
```

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor(kctl-api): subclass kctl-lib APIClient/AsyncAPIClient"
```

---

## Task 3: Migrate kctl-odoo client to APIClient subclass

**Files:**
- Modify: `kodemeio-odoo/cli/src/kctl_odoo/core/client.py`
- Modify: `kodemeio-odoo/cli/src/kctl_odoo/core/async_client.py`
- Modify: `kodemeio-odoo/cli/pyproject.toml`

- [ ] **Step 1: Bump kctl-lib version**

Change `kctl-lib>=0.2.1` → `kctl-lib>=0.3.0`.

- [ ] **Step 2: Read current client.py and async_client.py**

Read both files fully. Note: Odoo uses JSON-RPC, which may require custom `_request()` or `_unwrap_response()` override.

- [ ] **Step 3: Refactor client.py**

```python
"""Odoo JSON-RPC API client.

Subclasses APIClient from kctl-lib.
"""

from __future__ import annotations

from typing import Any

from kctl_lib.api_client import APIClient


class OdooClient(APIClient):
    """Synchronous Odoo client."""

    AUTH_HEADER = "Authorization"
    AUTH_PREFIX = "Bearer"
    API_PREFIX = ""

    def __init__(self, base_url: str = "", credential: str = "", **kwargs: Any) -> None:
        super().__init__(base_url=base_url, credential=credential, **kwargs)

    # Override _unwrap_response if Odoo uses JSON-RPC envelope
    # Keep all Odoo-specific methods (authenticate, execute_kw, search_read, etc.)
```

Note: If Odoo's client uses JSON-RPC protocol (not REST), the migration may require overriding `_request()` to handle `jsonrpc` payload format. Read the actual file first to determine the right approach. If the protocol divergence is too large, keep client.py as-is and only bump the version.

- [ ] **Step 4: Refactor async_client.py (same approach)**

- [ ] **Step 5: Remove extraction markers**

- [ ] **Step 6: Run tests**

```bash
cd kodemeio-odoo/cli && uv sync --all-extras && uv run pytest tests/ -v --tb=short
```

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor(kctl-odoo): subclass kctl-lib APIClient/AsyncAPIClient"
```

---

## Verification Checklist

- [ ] All 5 CLIs depend on `kctl-lib>=0.3.0`
- [ ] kctl-next, kctl-react, kctl-claw: tests pass after version bump
- [ ] kctl-api: client.py and async_client.py subclass base classes
- [ ] kctl-odoo: client.py and async_client.py subclass base classes (or documented exception)
- [ ] No `# KCTL-COMMON: extractable` markers remain
- [ ] All lock files updated
