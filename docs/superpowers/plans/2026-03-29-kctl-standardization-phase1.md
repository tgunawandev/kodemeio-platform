# Phase 1: kctl-lib v0.3.0 — APIClient + AsyncAPIClient

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add base `APIClient` and `AsyncAPIClient` classes to kctl-lib so all kctl-* CLIs can subclass instead of duplicating httpx client code.

**Architecture:** Two new modules (`api_client.py`, `async_api_client.py`) added to kctl-lib alongside existing modules. Pure additions — no existing modules change. Each class provides configurable auth, CRUD methods, error mapping, optional retry with exponential backoff, and context manager support. CLIs subclass and override class attributes for service-specific behavior.

**Tech Stack:** Python 3.12+, httpx, kctl-lib exceptions

**Spec:** `docs/superpowers/specs/2026-03-29-kctl-standardization-design.md`

**Working directory:** `/home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform`

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `packages/kctl-lib/src/kctl_lib/api_client.py` | Base synchronous APIClient |
| Create | `packages/kctl-lib/src/kctl_lib/async_api_client.py` | Base async APIClient |
| Create | `packages/kctl-lib/tests/test_api_client.py` | Tests for APIClient |
| Create | `packages/kctl-lib/tests/test_async_api_client.py` | Tests for AsyncAPIClient |
| Modify | `packages/kctl-lib/src/kctl_lib/__init__.py` | Add exports |
| Modify | `packages/kctl-lib/pyproject.toml` | Add httpx to core deps, bump to 0.3.0 |

---

### Task 1: Add httpx to core dependencies and bump version

**Files:**
- Modify: `packages/kctl-lib/pyproject.toml`
- Modify: `packages/kctl-lib/src/kctl_lib/__init__.py`

- [ ] **Step 1: Update pyproject.toml — move httpx from optional to core, bump version**

In `packages/kctl-lib/pyproject.toml`, make these changes:

```toml
[project]
name = "kctl-lib"
version = "0.3.0"
description = "Shared core library for kctl-* CLI tools"
requires-python = ">=3.12"
dependencies = [
    "typer>=0.15.0",
    "rich>=13.9.0",
    "pydantic>=2.10.0",
    "pyyaml>=6.0.2",
    "httpx>=0.28.0",
]

[project.optional-dependencies]
testing = ["pytest>=8.3.0"]
monitor = []
dev = [
    "pytest>=8.3.0",
    "pytest-cov>=6.0.0",
    "pytest-httpx>=0.35.0",
    "ruff>=0.9.0",
    "mypy>=1.14.0",
    "types-PyYAML>=6.0.0",
]
```

Key changes:
- `version` → `"0.3.0"`
- `httpx>=0.28.0` moved from `monitor` optional to core `dependencies`
- `monitor` optional kept empty (backward compat for `pip install kctl-lib[monitor]`)
- `pytest-httpx>=0.35.0` added to dev deps for mocking httpx

- [ ] **Step 2: Update __version__ in __init__.py**

In `packages/kctl-lib/src/kctl_lib/__init__.py`, change:

```python
__version__ = "0.3.0"
```

- [ ] **Step 3: Sync and verify existing tests still pass**

Run:
```bash
cd packages/kctl-lib && uv sync --all-extras && uv run pytest tests/ -v --tb=short
```
Expected: All 187 tests pass. No regressions from dependency changes.

- [ ] **Step 4: Commit**

```bash
git add packages/kctl-lib/pyproject.toml packages/kctl-lib/src/kctl_lib/__init__.py
git commit -m "chore: bump kctl-lib to 0.3.0, move httpx to core deps"
```

---

### Task 2: Write failing tests for APIClient

**Files:**
- Create: `packages/kctl-lib/tests/test_api_client.py`

- [ ] **Step 1: Write the test file**

Create `packages/kctl-lib/tests/test_api_client.py`:

```python
"""Tests for base APIClient."""

from __future__ import annotations

import httpx
import pytest

from kctl_lib.api_client import APIClient
from kctl_lib.exceptions import (
    APIError,
    AuthenticationError,
    ConfigError,
    ConnectionError,
)


# --- Concrete subclass for testing ---

class TestClient(APIClient):
    """Minimal subclass for testing."""

    AUTH_HEADER = "X-Api-Key"
    AUTH_PREFIX = ""
    API_PREFIX = "/api/v1"


class CloudflareStyleClient(APIClient):
    """Subclass that unwraps response envelope."""

    BASE_URL = "https://api.example.com/v4"
    AUTH_HEADER = "Authorization"
    AUTH_PREFIX = "Bearer"

    def _unwrap_response(self, response: httpx.Response) -> dict | list:
        data = response.json()
        if isinstance(data, dict) and "result" in data:
            return data["result"]
        return data


class RetryClient(APIClient):
    """Subclass with retry enabled."""

    AUTH_HEADER = "x-api-key"
    AUTH_PREFIX = ""

    def __init__(self, **kwargs):
        super().__init__(retry_enabled=True, max_retries=2, retry_base_delay=0.01, **kwargs)


# --- Constructor tests ---

class TestConstructor:
    def test_requires_credential(self):
        with pytest.raises(ConfigError, match="No credential"):
            TestClient(base_url="https://example.com")

    def test_requires_base_url_when_no_class_base(self):
        with pytest.raises(ConfigError, match="No URL"):
            TestClient(credential="test-key")

    def test_uses_class_base_url(self):
        client = CloudflareStyleClient(credential="tok_123")
        assert client.base_url == "https://api.example.com/v4"
        client.close()

    def test_instance_base_url_overrides_class(self):
        client = CloudflareStyleClient(base_url="https://custom.example.com", credential="tok_123")
        assert client.base_url == "https://custom.example.com"
        client.close()

    def test_api_prefix_appended(self):
        client = TestClient(base_url="https://example.com", credential="key")
        assert client.base_url == "https://example.com/api/v1"
        client.close()

    def test_api_prefix_not_doubled(self):
        client = TestClient(base_url="https://example.com/api/v1", credential="key")
        assert client.base_url == "https://example.com/api/v1"
        client.close()

    def test_trailing_slash_cleaned(self):
        client = TestClient(base_url="https://example.com/", credential="key")
        assert client.base_url == "https://example.com/api/v1"
        client.close()

    def test_context_manager(self):
        with TestClient(base_url="https://example.com", credential="key") as client:
            assert client is not None


# --- Auth header tests ---

class TestAuthHeaders:
    def test_raw_key_header(self):
        client = TestClient(base_url="https://example.com", credential="my-key")
        headers = client._build_auth_header()
        assert headers == {"X-Api-Key": "my-key"}
        client.close()

    def test_bearer_token_header(self):
        client = CloudflareStyleClient(credential="tok_123")
        headers = client._build_auth_header()
        assert headers == {"Authorization": "Bearer tok_123"}
        client.close()


# --- HTTP method tests (using pytest-httpx) ---

class TestHTTPMethods:
    def test_get(self, httpx_mock):
        httpx_mock.add_response(json={"id": 1, "name": "test"})
        with TestClient(base_url="https://example.com", credential="key") as client:
            result = client.get("/items/1")
        assert result == {"id": 1, "name": "test"}

    def test_post(self, httpx_mock):
        httpx_mock.add_response(json={"id": 2}, status_code=201)
        with TestClient(base_url="https://example.com", credential="key") as client:
            result = client.post("/items", json={"name": "new"})
        assert result == {"id": 2}

    def test_put(self, httpx_mock):
        httpx_mock.add_response(json={"updated": True})
        with TestClient(base_url="https://example.com", credential="key") as client:
            result = client.put("/items/1", json={"name": "changed"})
        assert result == {"updated": True}

    def test_patch(self, httpx_mock):
        httpx_mock.add_response(json={"patched": True})
        with TestClient(base_url="https://example.com", credential="key") as client:
            result = client.patch("/items/1", json={"name": "patched"})
        assert result == {"patched": True}

    def test_delete(self, httpx_mock):
        httpx_mock.add_response(status_code=204, content=b"")
        with TestClient(base_url="https://example.com", credential="key") as client:
            result = client.delete("/items/1")
        assert result == {}

    def test_empty_response_body(self, httpx_mock):
        httpx_mock.add_response(status_code=200, content=b"")
        with TestClient(base_url="https://example.com", credential="key") as client:
            result = client.get("/empty")
        assert result == {}

    def test_params_passed(self, httpx_mock):
        httpx_mock.add_response(json=[])
        with TestClient(base_url="https://example.com", credential="key") as client:
            client.get("/items", params={"page": 1, "limit": 10})
        req = httpx_mock.get_request()
        assert "page=1" in str(req.url)
        assert "limit=10" in str(req.url)


# --- Error mapping tests ---

class TestErrorMapping:
    def test_401_raises_authentication_error(self, httpx_mock):
        httpx_mock.add_response(status_code=401, json={"error": "unauthorized"})
        with TestClient(base_url="https://example.com", credential="key") as client:
            with pytest.raises(AuthenticationError, match="invalid"):
                client.get("/protected")

    def test_403_raises_authentication_error(self, httpx_mock):
        httpx_mock.add_response(status_code=403, json={"error": "forbidden"})
        with TestClient(base_url="https://example.com", credential="key") as client:
            with pytest.raises(AuthenticationError, match="Permission denied"):
                client.get("/admin")

    def test_404_raises_api_error(self, httpx_mock):
        httpx_mock.add_response(status_code=404, json={"error": "not found"})
        with TestClient(base_url="https://example.com", credential="key") as client:
            with pytest.raises(APIError) as exc_info:
                client.get("/missing")
        assert exc_info.value.status_code == 404

    def test_500_raises_api_error(self, httpx_mock):
        httpx_mock.add_response(status_code=500, json={"error": "server error"})
        with TestClient(base_url="https://example.com", credential="key") as client:
            with pytest.raises(APIError) as exc_info:
                client.get("/broken")
        assert exc_info.value.status_code == 500

    def test_connect_error_raises_connection_error(self, httpx_mock):
        httpx_mock.add_exception(httpx.ConnectError("Connection refused"))
        with TestClient(base_url="https://example.com", credential="key") as client:
            with pytest.raises(ConnectionError, match="example.com"):
                client.get("/unreachable")

    def test_timeout_raises_connection_error(self, httpx_mock):
        httpx_mock.add_exception(httpx.ReadTimeout("Timed out"))
        with TestClient(base_url="https://example.com", credential="key") as client:
            with pytest.raises(ConnectionError):
                client.get("/slow")


# --- Response unwrapping tests ---

class TestResponseUnwrapping:
    def test_default_returns_json_as_is(self, httpx_mock):
        httpx_mock.add_response(json={"data": [1, 2, 3]})
        with TestClient(base_url="https://example.com", credential="key") as client:
            result = client.get("/data")
        assert result == {"data": [1, 2, 3]}

    def test_custom_unwrap(self, httpx_mock):
        httpx_mock.add_response(json={"success": True, "result": {"id": 1}})
        with CloudflareStyleClient(credential="tok_123") as client:
            result = client.get("/zones")
        assert result == {"id": 1}


# --- Retry tests ---

class TestRetry:
    def test_retries_on_5xx(self, httpx_mock):
        httpx_mock.add_response(status_code=500, json={"error": "fail"})
        httpx_mock.add_response(status_code=500, json={"error": "fail"})
        httpx_mock.add_response(json={"ok": True})
        with RetryClient(base_url="https://example.com", credential="key") as client:
            result = client.get("/flaky")
        assert result == {"ok": True}
        assert len(httpx_mock.get_requests()) == 3

    def test_no_retry_on_4xx(self, httpx_mock):
        httpx_mock.add_response(status_code=400, json={"error": "bad request"})
        with RetryClient(base_url="https://example.com", credential="key") as client:
            with pytest.raises(APIError):
                client.get("/bad")
        assert len(httpx_mock.get_requests()) == 1

    def test_retry_exhausted_raises(self, httpx_mock):
        httpx_mock.add_response(status_code=500, json={"error": "fail"})
        httpx_mock.add_response(status_code=500, json={"error": "fail"})
        httpx_mock.add_response(status_code=500, json={"error": "fail"})
        with RetryClient(base_url="https://example.com", credential="key") as client:
            with pytest.raises(APIError) as exc_info:
                client.get("/always-broken")
        assert exc_info.value.status_code == 500

    def test_retry_on_connect_error(self, httpx_mock):
        httpx_mock.add_exception(httpx.ConnectError("refused"))
        httpx_mock.add_response(json={"ok": True})
        with RetryClient(base_url="https://example.com", credential="key") as client:
            result = client.get("/recovers")
        assert result == {"ok": True}

    def test_retry_disabled_by_default(self, httpx_mock):
        httpx_mock.add_response(status_code=500, json={"error": "fail"})
        with TestClient(base_url="https://example.com", credential="key") as client:
            with pytest.raises(APIError):
                client.get("/no-retry")
        assert len(httpx_mock.get_requests()) == 1


# --- Debug logging test ---

class TestDebugLogging:
    def test_debug_logs_when_enabled(self, httpx_mock, monkeypatch, capsys):
        monkeypatch.setenv("KCTL_DEBUG", "1")
        httpx_mock.add_response(json={"ok": True})
        with TestClient(base_url="https://example.com", credential="key") as client:
            client.get("/debug-test")
        captured = capsys.readouterr()
        assert "[DEBUG]" in captured.err
        assert "GET" in captured.err

    def test_no_debug_by_default(self, httpx_mock, capsys):
        httpx_mock.add_response(json={"ok": True})
        with TestClient(base_url="https://example.com", credential="key") as client:
            client.get("/quiet-test")
        captured = capsys.readouterr()
        assert "[DEBUG]" not in captured.err
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
cd packages/kctl-lib && uv run pytest tests/test_api_client.py -v --tb=short 2>&1 | head -20
```
Expected: FAIL with `ModuleNotFoundError: No module named 'kctl_lib.api_client'`

- [ ] **Step 3: Commit test file**

```bash
git add packages/kctl-lib/tests/test_api_client.py
git commit -m "test: add failing tests for APIClient base class"
```

---

### Task 3: Implement APIClient

**Files:**
- Create: `packages/kctl-lib/src/kctl_lib/api_client.py`

- [ ] **Step 1: Write the implementation**

Create `packages/kctl-lib/src/kctl_lib/api_client.py`:

```python
"""Base synchronous HTTP API client for kctl-* CLIs.

Subclass and override class attributes for service-specific behavior:

    class DokployClient(APIClient):
        AUTH_HEADER = "x-api-key"
        AUTH_PREFIX = ""
        API_PREFIX = "/api"

        def __init__(self, base_url: str, api_key: str, **kwargs):
            super().__init__(base_url=base_url, credential=api_key,
                             retry_enabled=True, **kwargs)
"""

from __future__ import annotations

import os
import random
import sys
import time
from typing import Any, Self

import httpx

from kctl_lib.exceptions import (
    APIError,
    AuthenticationError,
    ConfigError,
    ConnectionError,
)


def _is_debug() -> bool:
    return os.environ.get("KCTL_DEBUG", "").strip() in ("1", "true", "yes")


class APIClient:
    """Base synchronous HTTP API client with configurable auth, retry, and error mapping."""

    # --- Subclass overrides ---
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer"
    API_PREFIX: str = ""
    BASE_URL: str = ""

    def __init__(
        self,
        base_url: str = "",
        credential: str = "",
        timeout: float = 30.0,
        retry_enabled: bool = False,
        max_retries: int = 3,
        retry_base_delay: float = 2.0,
        retry_max_delay: float = 60.0,
    ) -> None:
        if not credential:
            raise ConfigError("No credential configured. Check your profile or pass --api-key / --token.")

        # Resolve base URL: instance arg > class attribute
        resolved_url = base_url or self.BASE_URL
        if not resolved_url:
            raise ConfigError("No URL configured. Run: config init")

        # Clean and append API_PREFIX
        resolved_url = resolved_url.rstrip("/")
        if self.API_PREFIX and not resolved_url.endswith(self.API_PREFIX):
            resolved_url = f"{resolved_url}{self.API_PREFIX}"

        self._base_url = resolved_url
        self._credential = credential
        self._timeout = timeout
        self._retry_enabled = retry_enabled
        self._max_retries = max_retries if retry_enabled else 0
        self._retry_base_delay = retry_base_delay
        self._retry_max_delay = retry_max_delay
        self._debug = _is_debug()

        self._client = httpx.Client(
            base_url=self._base_url,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                **self._build_auth_header(),
            },
            timeout=timeout,
            follow_redirects=True,
        )

    @property
    def base_url(self) -> str:
        """The resolved base URL (with API prefix)."""
        return self._base_url

    def _build_auth_header(self) -> dict[str, str]:
        """Build auth header dict. Override for custom auth schemes."""
        value = f"{self.AUTH_PREFIX} {self._credential}" if self.AUTH_PREFIX else self._credential
        return {self.AUTH_HEADER: value}

    def _log_debug(self, msg: str) -> None:
        if self._debug:
            print(f"[DEBUG] {msg}", file=sys.stderr)

    def _is_retryable(self, status_code: int) -> bool:
        """Return True if request should be retried. Override for custom logic."""
        return status_code >= 500

    def _retry_delay(self, attempt: int) -> float:
        """Exponential backoff with full jitter."""
        delay = min(self._retry_base_delay * (2**attempt), self._retry_max_delay)
        return random.uniform(0, delay)  # noqa: S311

    def _unwrap_response(self, response: httpx.Response) -> dict | list:
        """Parse response body. Override for envelope unwrapping (e.g. Cloudflare)."""
        if not response.content:
            return {}
        return response.json()

    def _map_error(self, response: httpx.Response) -> APIError | AuthenticationError:
        """Map HTTP error status to exception. Override for custom error extraction."""
        if response.status_code == 401:
            return AuthenticationError("Credential invalid or expired.")
        if response.status_code == 403:
            return AuthenticationError("Permission denied.")
        detail = ""
        try:
            body = response.json()
            detail = body.get("detail", body.get("error", body.get("message", str(body))))
        except Exception:
            detail = response.text[:200] if response.text else ""
        return APIError(status_code=response.status_code, detail=detail)

    def _request(self, method: str, endpoint: str, **kwargs: Any) -> httpx.Response:
        """Execute HTTP request with optional retry on transient errors."""
        url = endpoint.lstrip("/")
        timeout = kwargs.pop("timeout", None)
        if timeout is not None:
            kwargs["timeout"] = timeout

        last_exc: Exception | None = None
        attempts = self._max_retries + 1

        for attempt in range(attempts):
            try:
                self._log_debug(f"{method} {self._base_url}/{url} (attempt {attempt + 1})")
                response = self._client.request(method, url, **kwargs)
                self._log_debug(f"  -> {response.status_code}")

                if response.status_code >= 400:
                    if self._retry_enabled and self._is_retryable(response.status_code) and attempt < self._max_retries:
                        delay = self._retry_delay(attempt)
                        self._log_debug(f"  Retryable {response.status_code}, sleeping {delay:.1f}s")
                        time.sleep(delay)
                        continue
                    raise self._map_error(response)

                return response

            except (AuthenticationError, APIError):
                raise
            except httpx.TimeoutException as e:
                last_exc = e
                if self._retry_enabled and attempt < self._max_retries:
                    delay = self._retry_delay(attempt)
                    self._log_debug(f"  Timeout, retrying in {delay:.1f}s")
                    time.sleep(delay)
                    continue
                raise ConnectionError(self._base_url, e) from e
            except httpx.ConnectError as e:
                last_exc = e
                if self._retry_enabled and attempt < self._max_retries:
                    delay = self._retry_delay(attempt)
                    self._log_debug(f"  Connection error, retrying in {delay:.1f}s")
                    time.sleep(delay)
                    continue
                raise ConnectionError(self._base_url, e) from e
            except httpx.HTTPError as e:
                last_exc = e
                raise ConnectionError(self._base_url, e) from e

        raise ConnectionError(self._base_url, last_exc)

    # --- Public CRUD methods ---

    def get(self, endpoint: str, params: dict | None = None, **kwargs: Any) -> dict | list:
        """GET request, returns parsed JSON."""
        return self._unwrap_response(self._request("GET", endpoint, params=params, **kwargs))

    def post(self, endpoint: str, json: dict | None = None, **kwargs: Any) -> dict | list:
        """POST request, returns parsed JSON."""
        return self._unwrap_response(self._request("POST", endpoint, json=json, **kwargs))

    def put(self, endpoint: str, json: dict | None = None, **kwargs: Any) -> dict | list:
        """PUT request, returns parsed JSON."""
        return self._unwrap_response(self._request("PUT", endpoint, json=json, **kwargs))

    def patch(self, endpoint: str, json: dict | None = None, **kwargs: Any) -> dict | list:
        """PATCH request, returns parsed JSON."""
        return self._unwrap_response(self._request("PATCH", endpoint, json=json, **kwargs))

    def delete(self, endpoint: str, **kwargs: Any) -> dict | list:
        """DELETE request, returns parsed JSON (or empty dict)."""
        return self._unwrap_response(self._request("DELETE", endpoint, **kwargs))

    # --- Lifecycle ---

    def close(self) -> None:
        """Close the underlying httpx client."""
        self._client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
```

- [ ] **Step 2: Run tests to verify they pass**

Run:
```bash
cd packages/kctl-lib && uv run pytest tests/test_api_client.py -v --tb=short
```
Expected: All tests PASS.

- [ ] **Step 3: Run linting and type check**

Run:
```bash
cd packages/kctl-lib && uv run ruff check src/kctl_lib/api_client.py && uv run ruff format --check src/kctl_lib/api_client.py && uv run mypy src/kctl_lib/api_client.py
```
Expected: No errors.

- [ ] **Step 4: Commit**

```bash
git add packages/kctl-lib/src/kctl_lib/api_client.py packages/kctl-lib/tests/test_api_client.py
git commit -m "feat: add base APIClient class with retry and error mapping"
```

---

### Task 4: Write failing tests for AsyncAPIClient

**Files:**
- Create: `packages/kctl-lib/tests/test_async_api_client.py`

- [ ] **Step 1: Write the test file**

Create `packages/kctl-lib/tests/test_async_api_client.py`:

```python
"""Tests for base AsyncAPIClient."""

from __future__ import annotations

import httpx
import pytest

from kctl_lib.async_api_client import AsyncAPIClient
from kctl_lib.exceptions import (
    APIError,
    AuthenticationError,
    ConfigError,
    ConnectionError,
)


class TestAsyncClient(AsyncAPIClient):
    """Minimal async subclass for testing."""

    AUTH_HEADER = "X-Api-Key"
    AUTH_PREFIX = ""
    API_PREFIX = "/api/v1"


class AsyncRetryClient(AsyncAPIClient):
    """Async subclass with retry enabled."""

    AUTH_HEADER = "x-api-key"
    AUTH_PREFIX = ""

    def __init__(self, **kwargs):
        super().__init__(retry_enabled=True, max_retries=2, retry_base_delay=0.01, **kwargs)


class TestAsyncConstructor:
    def test_requires_credential(self):
        with pytest.raises(ConfigError, match="No credential"):
            TestAsyncClient(base_url="https://example.com")

    def test_requires_base_url(self):
        with pytest.raises(ConfigError, match="No URL"):
            TestAsyncClient(credential="key")

    def test_api_prefix_appended(self):
        client = TestAsyncClient(base_url="https://example.com", credential="key")
        assert client.base_url == "https://example.com/api/v1"
        # cleanup is async, but the object is constructed


class TestAsyncHTTPMethods:
    @pytest.mark.anyio
    async def test_get(self, httpx_mock):
        httpx_mock.add_response(json={"id": 1})
        async with TestAsyncClient(base_url="https://example.com", credential="key") as client:
            result = await client.get("/items/1")
        assert result == {"id": 1}

    @pytest.mark.anyio
    async def test_post(self, httpx_mock):
        httpx_mock.add_response(json={"id": 2}, status_code=201)
        async with TestAsyncClient(base_url="https://example.com", credential="key") as client:
            result = await client.post("/items", json={"name": "new"})
        assert result == {"id": 2}

    @pytest.mark.anyio
    async def test_put(self, httpx_mock):
        httpx_mock.add_response(json={"updated": True})
        async with TestAsyncClient(base_url="https://example.com", credential="key") as client:
            result = await client.put("/items/1", json={"name": "changed"})
        assert result == {"updated": True}

    @pytest.mark.anyio
    async def test_patch(self, httpx_mock):
        httpx_mock.add_response(json={"patched": True})
        async with TestAsyncClient(base_url="https://example.com", credential="key") as client:
            result = await client.patch("/items/1", json={"name": "patched"})
        assert result == {"patched": True}

    @pytest.mark.anyio
    async def test_delete(self, httpx_mock):
        httpx_mock.add_response(status_code=204, content=b"")
        async with TestAsyncClient(base_url="https://example.com", credential="key") as client:
            result = await client.delete("/items/1")
        assert result == {}


class TestAsyncErrorMapping:
    @pytest.mark.anyio
    async def test_401_raises_authentication_error(self, httpx_mock):
        httpx_mock.add_response(status_code=401, json={"error": "unauthorized"})
        async with TestAsyncClient(base_url="https://example.com", credential="key") as client:
            with pytest.raises(AuthenticationError):
                await client.get("/protected")

    @pytest.mark.anyio
    async def test_500_raises_api_error(self, httpx_mock):
        httpx_mock.add_response(status_code=500, json={"error": "fail"})
        async with TestAsyncClient(base_url="https://example.com", credential="key") as client:
            with pytest.raises(APIError):
                await client.get("/broken")

    @pytest.mark.anyio
    async def test_connect_error(self, httpx_mock):
        httpx_mock.add_exception(httpx.ConnectError("refused"))
        async with TestAsyncClient(base_url="https://example.com", credential="key") as client:
            with pytest.raises(ConnectionError):
                await client.get("/unreachable")


class TestAsyncRetry:
    @pytest.mark.anyio
    async def test_retries_on_5xx(self, httpx_mock):
        httpx_mock.add_response(status_code=500, json={"error": "fail"})
        httpx_mock.add_response(json={"ok": True})
        async with AsyncRetryClient(base_url="https://example.com", credential="key") as client:
            result = await client.get("/flaky")
        assert result == {"ok": True}
        assert len(httpx_mock.get_requests()) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
cd packages/kctl-lib && uv run pytest tests/test_async_api_client.py -v --tb=short 2>&1 | head -10
```
Expected: FAIL with `ModuleNotFoundError: No module named 'kctl_lib.async_api_client'`

- [ ] **Step 3: Commit test file**

```bash
git add packages/kctl-lib/tests/test_async_api_client.py
git commit -m "test: add failing tests for AsyncAPIClient base class"
```

---

### Task 5: Implement AsyncAPIClient

**Files:**
- Create: `packages/kctl-lib/src/kctl_lib/async_api_client.py`

- [ ] **Step 1: Write the implementation**

Create `packages/kctl-lib/src/kctl_lib/async_api_client.py`:

```python
"""Base asynchronous HTTP API client for kctl-* CLIs.

Async mirror of APIClient. Same class attributes, same error mapping,
but uses httpx.AsyncClient and async/await methods.

    class OdooAsyncClient(AsyncAPIClient):
        AUTH_HEADER = "Authorization"
        AUTH_PREFIX = "Bearer"
        API_PREFIX = "/api/v1"
"""

from __future__ import annotations

import asyncio
import os
import random
import sys
from typing import Any, Self

import httpx

from kctl_lib.exceptions import (
    APIError,
    AuthenticationError,
    ConfigError,
    ConnectionError,
)


def _is_debug() -> bool:
    return os.environ.get("KCTL_DEBUG", "").strip() in ("1", "true", "yes")


class AsyncAPIClient:
    """Base asynchronous HTTP API client with configurable auth, retry, and error mapping."""

    # --- Subclass overrides ---
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer"
    API_PREFIX: str = ""
    BASE_URL: str = ""

    def __init__(
        self,
        base_url: str = "",
        credential: str = "",
        timeout: float = 30.0,
        retry_enabled: bool = False,
        max_retries: int = 3,
        retry_base_delay: float = 2.0,
        retry_max_delay: float = 60.0,
    ) -> None:
        if not credential:
            raise ConfigError("No credential configured. Check your profile or pass --api-key / --token.")

        resolved_url = base_url or self.BASE_URL
        if not resolved_url:
            raise ConfigError("No URL configured. Run: config init")

        resolved_url = resolved_url.rstrip("/")
        if self.API_PREFIX and not resolved_url.endswith(self.API_PREFIX):
            resolved_url = f"{resolved_url}{self.API_PREFIX}"

        self._base_url = resolved_url
        self._credential = credential
        self._timeout = timeout
        self._retry_enabled = retry_enabled
        self._max_retries = max_retries if retry_enabled else 0
        self._retry_base_delay = retry_base_delay
        self._retry_max_delay = retry_max_delay
        self._debug = _is_debug()

        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                **self._build_auth_header(),
            },
            timeout=timeout,
            follow_redirects=True,
        )

    @property
    def base_url(self) -> str:
        return self._base_url

    def _build_auth_header(self) -> dict[str, str]:
        value = f"{self.AUTH_PREFIX} {self._credential}" if self.AUTH_PREFIX else self._credential
        return {self.AUTH_HEADER: value}

    def _log_debug(self, msg: str) -> None:
        if self._debug:
            print(f"[DEBUG] {msg}", file=sys.stderr)

    def _is_retryable(self, status_code: int) -> bool:
        return status_code >= 500

    def _retry_delay(self, attempt: int) -> float:
        delay = min(self._retry_base_delay * (2**attempt), self._retry_max_delay)
        return random.uniform(0, delay)  # noqa: S311

    def _unwrap_response(self, response: httpx.Response) -> dict | list:
        if not response.content:
            return {}
        return response.json()

    def _map_error(self, response: httpx.Response) -> APIError | AuthenticationError:
        if response.status_code == 401:
            return AuthenticationError("Credential invalid or expired.")
        if response.status_code == 403:
            return AuthenticationError("Permission denied.")
        detail = ""
        try:
            body = response.json()
            detail = body.get("detail", body.get("error", body.get("message", str(body))))
        except Exception:
            detail = response.text[:200] if response.text else ""
        return APIError(status_code=response.status_code, detail=detail)

    async def _request(self, method: str, endpoint: str, **kwargs: Any) -> httpx.Response:
        url = endpoint.lstrip("/")
        timeout = kwargs.pop("timeout", None)
        if timeout is not None:
            kwargs["timeout"] = timeout

        last_exc: Exception | None = None
        attempts = self._max_retries + 1

        for attempt in range(attempts):
            try:
                self._log_debug(f"{method} {self._base_url}/{url} (attempt {attempt + 1})")
                response = await self._client.request(method, url, **kwargs)
                self._log_debug(f"  -> {response.status_code}")

                if response.status_code >= 400:
                    if self._retry_enabled and self._is_retryable(response.status_code) and attempt < self._max_retries:
                        delay = self._retry_delay(attempt)
                        self._log_debug(f"  Retryable {response.status_code}, sleeping {delay:.1f}s")
                        await asyncio.sleep(delay)
                        continue
                    raise self._map_error(response)

                return response

            except (AuthenticationError, APIError):
                raise
            except httpx.TimeoutException as e:
                last_exc = e
                if self._retry_enabled and attempt < self._max_retries:
                    delay = self._retry_delay(attempt)
                    await asyncio.sleep(delay)
                    continue
                raise ConnectionError(self._base_url, e) from e
            except httpx.ConnectError as e:
                last_exc = e
                if self._retry_enabled and attempt < self._max_retries:
                    delay = self._retry_delay(attempt)
                    await asyncio.sleep(delay)
                    continue
                raise ConnectionError(self._base_url, e) from e
            except httpx.HTTPError as e:
                last_exc = e
                raise ConnectionError(self._base_url, e) from e

        raise ConnectionError(self._base_url, last_exc)

    # --- Public async CRUD methods ---

    async def get(self, endpoint: str, params: dict | None = None, **kwargs: Any) -> dict | list:
        return self._unwrap_response(await self._request("GET", endpoint, params=params, **kwargs))

    async def post(self, endpoint: str, json: dict | None = None, **kwargs: Any) -> dict | list:
        return self._unwrap_response(await self._request("POST", endpoint, json=json, **kwargs))

    async def put(self, endpoint: str, json: dict | None = None, **kwargs: Any) -> dict | list:
        return self._unwrap_response(await self._request("PUT", endpoint, json=json, **kwargs))

    async def patch(self, endpoint: str, json: dict | None = None, **kwargs: Any) -> dict | list:
        return self._unwrap_response(await self._request("PATCH", endpoint, json=json, **kwargs))

    async def delete(self, endpoint: str, **kwargs: Any) -> dict | list:
        return self._unwrap_response(await self._request("DELETE", endpoint, **kwargs))

    # --- Lifecycle ---

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()
```

- [ ] **Step 2: Install anyio for async test support and run tests**

Run:
```bash
cd packages/kctl-lib && uv add --dev anyio pytest-anyio && uv run pytest tests/test_async_api_client.py -v --tb=short
```

If `pytest-anyio` is not available, use `anyio` with pytest-httpx's built-in async support. The `@pytest.mark.anyio` marker should work with pytest-httpx >= 0.35.0 which bundles async test support.

Expected: All tests PASS.

- [ ] **Step 3: Run linting and type check**

Run:
```bash
cd packages/kctl-lib && uv run ruff check src/kctl_lib/async_api_client.py && uv run mypy src/kctl_lib/async_api_client.py
```
Expected: No errors.

- [ ] **Step 4: Commit**

```bash
git add packages/kctl-lib/src/kctl_lib/async_api_client.py packages/kctl-lib/tests/test_async_api_client.py
git commit -m "feat: add base AsyncAPIClient class for async kctl-* CLIs"
```

---

### Task 6: Update __init__.py exports and run full test suite

**Files:**
- Modify: `packages/kctl-lib/src/kctl_lib/__init__.py`

- [ ] **Step 1: Add new exports to __init__.py**

Add these imports and update `__all__` in `packages/kctl-lib/src/kctl_lib/__init__.py`:

```python
from kctl_lib.api_client import APIClient
from kctl_lib.async_api_client import AsyncAPIClient
```

Add to `__all__` list (alphabetical order):

```python
__all__ = [
    "APIClient",
    "APIError",
    "AppContextBase",
    "AppNotFoundError",
    "AsyncAPIClient",
    "AuthenticationError",
    "CheckResult",
    "CommandError",
    "ConfigError",
    "ConnectionError",
    "DockerError",
    "DockerManager",
    "DoctorCheck",
    "Issue",
    "KctlError",
    "NotFoundError",
    "Output",
    "ValidationError",
    "run_doctor",
]
```

- [ ] **Step 2: Run the full test suite**

Run:
```bash
cd packages/kctl-lib && uv run pytest tests/ -v --tb=short
```
Expected: All tests pass (187 existing + new api_client + async_api_client tests).

- [ ] **Step 3: Run full lint and type check**

Run:
```bash
cd packages/kctl-lib && uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/ && uv run mypy src/
```
Expected: No errors.

- [ ] **Step 4: Commit**

```bash
git add packages/kctl-lib/src/kctl_lib/__init__.py
git commit -m "feat: export APIClient and AsyncAPIClient from kctl-lib public API"
```

---

### Task 7: Update uv.lock and verify build

**Files:**
- Modify: `uv.lock` (auto-generated)

- [ ] **Step 1: Rebuild lock file**

Run:
```bash
cd /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-platform && uv lock
```
Expected: Lock file regenerated with httpx as core dep.

- [ ] **Step 2: Verify package builds**

Run:
```bash
cd packages/kctl-lib && uv build
```
Expected: Wheel and sdist created in `dist/` with version 0.3.0.

- [ ] **Step 3: Commit lock file**

```bash
git add uv.lock
git commit -m "chore: update uv.lock for kctl-lib v0.3.0"
```

---

## Verification Checklist

After all tasks complete:

- [ ] `uv run pytest tests/ -v` — all tests pass (187 + new)
- [ ] `uv run ruff check src/ tests/` — no lint errors
- [ ] `uv run ruff format --check src/ tests/` — properly formatted
- [ ] `uv run mypy src/` — no type errors
- [ ] `uv build` — builds successfully as v0.3.0
- [ ] `python -c "from kctl_lib import APIClient, AsyncAPIClient; print('OK')"` — exports work
