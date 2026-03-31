# kctl-* CLI Standardization — Full kctl-lib Integration

**Date:** 2026-03-29
**Scope:** All 16 kctl-* CLIs across kodemeio-platform, kodemeio-core, kodemeio-saas, kodemeio-app
**Goal:** Replace duplicated core/ modules with kctl-lib imports; standardize structure, CI/CD, tests, and code style

---

## 1. Current State

### 1.1 Repos and CLI Inventory

| Repo | CLIs | Uses kctl-lib | Test Coverage |
|------|------|------------------|---------------|
| **kodemeio-platform** | kctl-lib (shared lib) | N/A — IS the library | 187 tests |
| **kodemeio-app** | kctl-next, kctl-react, kctl-api, kctl-odoo, kctl-claw | Yes (>=0.2.1) | Varies |
| **kodemeio-core** | kctl-ak, kctl-cf, kctl-dokploy, kctl-gatus, kctl-mdm, kctl-hz, kctl-pg, kctl-waha | No | 0–33 test files |
| **kodemeio-saas** | kctl-1password, kctl-claude, kctl-telegram | No | 0–9 test files |

### 1.2 Key Problems

1. **Duplicated core modules** — 11 CLIs each maintain their own exceptions.py, output.py, callbacks.py, config.py, client.py. Same code, drifting implementations.
2. **No shared API client** — Every httpx-based CLI duplicates constructor, CRUD methods, error mapping, auth headers. kctl-lib lacks a base APIClient.
3. **Inconsistent structure** — Entry points (`cli:app` vs `cli:_run`), version constants (`VERSION` vs `__version__`), line-length (100 vs 120), ruff rules vary.
4. **Missing CI/CD** — kctl-claude has no validation pipeline. Others lack test execution in CI.
5. **Missing tests** — 5 of 8 kodemeio-core CLIs and 2 of 3 kodemeio-saas CLIs have zero tests.
6. **No CLAUDE.md in CLI dirs** — Most CLAUDE.md files are at the service level, not the CLI level.

---

## 2. Architecture

### 2.1 Target Module Dependency

```
kctl-lib (v0.3.0)                   Each kctl-* CLI
┌─────────────────────────┐            ┌──────────────────────────┐
│ exceptions.py           │◄───────────│ core/exceptions.py       │ re-export + add service-specific
│ output.py               │◄───────────│ core/output.py           │ re-export only
│ callbacks.py            │◄───────────│ core/callbacks.py        │ subclass AppContextBase
│ config.py               │◄───────────│ core/config.py           │ define ServiceConfig + re-export
│ api_client.py      [NEW]│◄───────────│ core/client.py           │ subclass APIClient
│ async_api_client.py[NEW]│◄───────────│ core/async_client.py     │ subclass AsyncAPIClient (if needed)
│ plugins.py              │◄───────────│ core/plugins.py          │ re-export + configure entry point
│ runner.py               │◄───────────│ (direct import)          │
│ docker.py               │◄───────────│ (direct import)          │
│ doctor_base.py          │◄───────────│ (direct import)          │
│ history.py              │◄───────────│ core/history.py          │ wrap with app name
│ testing.py              │◄───────────│ tests/conftest.py        │ import fixtures
│ monitor_base.py         │◄───────────│ (direct import)          │
│ completions.py          │◄───────────│ (direct import)          │
│ self_update.py          │◄───────────│ (direct import)          │
│ validate.py             │◄───────────│ (direct import)          │
│ git_ops.py              │◄───────────│ (direct import)          │
│ skill_generator.py      │◄───────────│ (direct import)          │
└─────────────────────────┘            └──────────────────────────┘
```

### 2.2 New: APIClient Base Class Design

```python
# kctl_lib/api_client.py

class APIClient:
    """Base synchronous HTTP API client for kctl-* CLIs."""

    # Subclass overrides
    AUTH_HEADER: str = "Authorization"       # e.g. "x-api-key", "Auth-API-Token"
    AUTH_PREFIX: str = "Bearer"              # e.g. "" for raw token
    API_PREFIX: str = ""                     # e.g. "/api", "/api/v1"
    BASE_URL: str = ""                       # Hard-coded base URL (optional)

    def __init__(
        self,
        base_url: str = "",
        credential: str = "",
        timeout: float = 30.0,
        retry_enabled: bool = False,
        max_retries: int = 3,
        retry_base_delay: float = 2.0,
        retry_max_delay: float = 60.0,
    ) -> None: ...

    # Core CRUD — all return parsed JSON (dict | list)
    def get(self, endpoint: str, params: dict | None = None, **kwargs) -> dict | list: ...
    def post(self, endpoint: str, json: dict | None = None, **kwargs) -> dict | list: ...
    def put(self, endpoint: str, json: dict | None = None, **kwargs) -> dict | list: ...
    def patch(self, endpoint: str, json: dict | None = None, **kwargs) -> dict | list: ...
    def delete(self, endpoint: str, **kwargs) -> dict | list | None: ...

    # Internal — subclasses can override
    def _request(self, method: str, endpoint: str, **kwargs) -> httpx.Response: ...
    def _build_auth_header(self) -> dict[str, str]: ...
    def _unwrap_response(self, response: httpx.Response) -> dict | list: ...
    def _map_error(self, response: httpx.Response) -> KctlError: ...
    def _is_retryable(self, status_code: int) -> bool: ...

    # Context manager
    def __enter__(self) -> Self: ...
    def __exit__(self, *args) -> None: ...
```

**How each CLI subclasses:**

```python
# kctl_dokploy/core/client.py
class DokployClient(APIClient):
    AUTH_HEADER = "x-api-key"
    AUTH_PREFIX = ""
    API_PREFIX = "/api"

    def __init__(self, base_url: str, api_key: str, **kwargs):
        super().__init__(base_url=base_url, credential=api_key,
                         retry_enabled=True, **kwargs)

    # Service-specific methods
    def list_projects(self) -> list[dict]: ...
    def deploy(self, app_id: str) -> dict: ...
```

```python
# kctl_cf/core/client.py
class CloudflareClient(APIClient):
    BASE_URL = "https://api.cloudflare.com/client/v4"

    def _unwrap_response(self, response):
        data = response.json()
        if not data.get("success"):
            raise APIError(...)
        return data["result"]
```

### 2.3 New: AsyncAPIClient Base Class

Mirror of APIClient using `httpx.AsyncClient`. Same class attributes and method signatures with `async def`. Only used by kctl-api and kctl-odoo currently.

---

## 3. Standards to Enforce

### 3.1 Structural Standards

| Aspect | Standard | Current Violations |
|--------|----------|--------------------|
| Entry point | `cli:_run` (wrapped with error handling) | kctl-ak, kctl-pg, kctl-1password, kctl-telegram use `cli:app` |
| Version constant | `__version__` in `__init__.py` | kctl-1password uses `VERSION` |
| Package layout | `cli/src/kctl_{name}/` with `core/` and `commands/` | All compliant |
| Core modules | Re-export from kctl_lib, service-specific additions only | 11 CLIs fully duplicate |
| pyproject.toml | hatchling, kctl-lib>=0.3.0, standardized dev deps | 11 CLIs missing kctl-lib dep |

### 3.2 Code Style Standards

| Setting | Value |
|---------|-------|
| Python | >=3.12 |
| Ruff target-version | py312 |
| Ruff line-length | 120 |
| Ruff select | E, F, I, W, UP, B, SIM, N |
| mypy | strict=true, python_version=3.12 |

### 3.3 CI/CD Standards

Every CLI gets a `validate.yml` workflow:
1. Python linting: `uv run ruff check src/ tests/`
2. Format check: `uv run ruff format --check src/ tests/`
3. Type check: `uv run mypy src/`
4. Tests: `uv run pytest tests/ -v --tb=short`
5. Secret detection: grep for tokens/keys in committed files

### 3.4 Test Standards

| Requirement | Detail |
|-------------|--------|
| Location | `cli/tests/` |
| Framework | pytest |
| Minimum | smoke test (CLI loads, --help works) + core module tests |
| Fixtures | Use `kctl_lib.testing` (mock_output, mock_app_context, temp_config) |
| conftest.py | Import shared fixtures from kctl_lib.testing |

### 3.5 Global Options (all CLIs)

| Flag | Short | Required |
|------|-------|----------|
| `--json` | `-j` | Yes |
| `--quiet` | `-q` | Yes |
| `--format` | `-f` | Yes |
| `--no-header` | — | Yes |
| `--profile` | `-p` | Yes (except kctl-claude, kctl-pg) |
| `--version` | `-V` | Yes |

### 3.6 Config Subcommands (all CLIs with profile support)

All 9: init, add, use, show, validate, remove, set, profiles, current

---

## 4. Migration Plan

### Phase 1: kctl-lib v0.3.0 (kodemeio-platform)

**Changes to kctl-lib:**
- Add `api_client.py` — Base `APIClient` class
- Add `async_api_client.py` — Base `AsyncAPIClient` class
- Add tests for both new modules
- Update `__init__.py` exports
- Bump version to 0.3.0

**Breaking changes:** None. Pure additions. All existing kodemeio-app CLIs continue working.

**Validation:** All 187 existing tests pass + new tests for api_client/async_api_client.

### Phase 2: kodemeio-core (8 CLIs)

Migrate in order of maturity (most tests first, easiest to validate):

1. **kctl-dokploy** (33 tests) — highest confidence
2. **kctl-hz** (6 tests)
3. **kctl-pg** (5 tests)
4. **kctl-cf** (3 tests)
5. **kctl-ak** (0 tests — add smoke tests first)
6. **kctl-gatus** (0 tests — add smoke tests first)
7. **kctl-mdm** (0 tests — add smoke tests first)
8. **kctl-waha** (0 tests — add smoke tests first)

**Per-CLI migration checklist:**
- [ ] Add `kctl-lib>=0.3.0` to pyproject.toml dependencies
- [ ] Replace `core/exceptions.py` — re-export from kctl_lib + add service-specific
- [ ] Replace `core/output.py` — re-export from kctl_lib
- [ ] Replace `core/callbacks.py` — subclass AppContextBase
- [ ] Replace `core/config.py` — use ConfigFile + define ServiceConfig
- [ ] Replace `core/client.py` — subclass APIClient
- [ ] Update all command imports to use new core paths
- [ ] Standardize entry point to `cli:_run`
- [ ] Standardize `__version__` in `__init__.py`
- [ ] Standardize pyproject.toml (ruff, mypy, line-length=120)
- [ ] Add/update `validate.yml` CI workflow
- [ ] Add smoke tests if none exist
- [ ] Verify all existing tests pass
- [ ] Add `core/plugins.py` if missing (use kctl_lib.plugins)

### Phase 3: kodemeio-saas (3 CLIs)

Same checklist as Phase 2, applied to:

1. **kctl-telegram** (9 test files, extraction markers) — easiest
2. **kctl-1password** (0 CLI tests)
3. **kctl-claude** (0 tests, most divergent structure)

**kctl-claude special handling:**
- Add missing `core/config.py` (profile support)
- Add missing `core/exceptions.py`
- Rename `core/context.py` → `core/callbacks.py` (align with standard)
- Keep `core/checks.py` and `core/paths.py` as service-specific modules
- Add `validate.yml` workflow (currently only has notify.yml)

### Phase 4: kodemeio-app (5 CLIs)

Update existing kctl-lib consumers:

1. **kctl-api** — Migrate `core/client.py` and `core/async_client.py` to subclass new base classes
2. **kctl-odoo** — Same as kctl-api
3. **kctl-claw** — Bump kctl-lib to >=0.3.0. Keep `core/gateway_client.py` and `core/docker_client.py` as-is (different patterns from httpx APIClient)
4. **kctl-next** — Bump kctl-lib to >=0.3.0, no other changes needed
5. **kctl-react** — Same as kctl-next

### Phase 5: Scaffold Placeholders (kodemeio-saas)

Use copier template for 4 empty directories:
```bash
copier copy templates/kctl-cli/ kodemeio-github/cli/   # kctl-github
copier copy templates/kctl-cli/ kodemeio-linear/cli/   # kctl-linear
copier copy templates/kctl-cli/ kodemeio-notion/cli/   # kctl-notion
copier copy templates/kctl-cli/ kodemeio-sentry/cli/   # kctl-sentry
```

Each gets the standard structure with kctl-lib>=0.3.0 from day one.

---

## 5. Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Breaking kctl-lib for existing consumers | Phase 1 is additive only — no changes to existing modules |
| Import path changes break commands | Each CLI migration updates all imports atomically |
| kctl-pg uses psycopg, not httpx | kctl-pg skips APIClient migration — keeps its own SSH tunnel client. Still migrates exceptions/output/callbacks/config |
| kctl-claude has divergent structure | Explicit special handling documented in Phase 3 |
| 4 CLIs have 0 tests | Add smoke tests before migrating core modules |
| Large scope (16 CLIs) | Order by test coverage — validate most-tested first |

---

## 6. Success Criteria

- [ ] All 16 CLIs depend on kctl-lib>=0.3.0
- [ ] No duplicated exceptions.py, output.py, callbacks.py, config.py across CLIs
- [ ] All API-backed CLIs subclass APIClient (except kctl-pg)
- [ ] All CLIs have validate.yml CI with lint + format + type check + tests
- [ ] All CLIs have at minimum smoke tests
- [ ] Ruff line-length=120, select=[E,F,I,W,UP,B,SIM,N] everywhere
- [ ] Entry points standardized to `cli:_run`
- [ ] `__version__` naming consistent everywhere
- [ ] All existing tests continue to pass after migration

---

## 7. Out of Scope

- Adding new features to any CLI
- Changing CLI command names or behavior
- Extracting resolve.py or pagination (too service-specific)
- Migrating kctl-pg's SSH tunnel client to APIClient
- Building actual functionality for placeholder CLIs (just scaffold)
- Refactoring command modules — only touching core/ and infrastructure
