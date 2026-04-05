# kctl-* CLI Quality Sweep — Design Spec

**Date:** 2026-04-05
**Goal:** Bring all 22 kctl-* CLIs to 9+/10 quality rating using horizontal sweeps
**Approach:** Proportional excellence (option B) via horizontal sweeps (option B)

## Scope

22 CLIs after deleting kctl-gatus. Every CLI is rated 9+/10 proportional to its scope — a 27-command CLI at 9/10 means "as good as a 27-command CLI can be."

### Rating Criteria (9/10 means)

| Aspect | 9/10 threshold |
|--------|---------------|
| Tests | >35% test LOC ratio, conftest.py, proper fixtures, mocks |
| Docs | README proportional to complexity (min 40L), 95%+ docstrings |
| Type Safety | mypy strict (already done everywhere) |
| Error Handling | Consistent kctl_lib.exceptions usage, validation at CLI boundaries |
| kctl-lib | Uses all 9 standard modules that apply |
| SKILL.md | Present and accurate |
| E2E | Only for 5 critical-path CLIs |

---

## Sweep 0: Delete kctl-gatus

**Rationale:** 2K LOC, 27 commands, 5.5% test ratio. Overlaps with kctl-grafana (alerting) and kctl-dokploy (health checks). Lowest-value CLI in the fleet.

**Actions:**
1. Remove `packages/kctl-gatus/` directory
2. Remove references from:
   - `CLAUDE.md` — workspace members table, key paths table
   - `docs/cli/kctl-gatus.md`
   - `monitoring/README.md`
   - Runbooks referencing kctl-gatus
   - Any superpowers skill files for gatus-admin
3. Update workspace: 22 packages remain (21 CLI tools + kctl-lib shared library). The `[tool.uv.workspace] members = ["packages/*"]` glob auto-excludes the deleted directory.

**Result:** 21 CLI tools + kctl-lib = 22 packages in workspace.

---

## Sweep 1: README + SKILL.md (Docs Layer)

**Parallelizable:** Yes — all 22 CLIs simultaneously.

### README Standards

| CLI size | Target length | Required sections |
|----------|--------------|-------------------|
| Small (<30 cmds) | 40-60 lines | Install, Quick Start, Command Groups, Config, Dev |
| Medium (30-100 cmds) | 80-120 lines | + Aliases, Global Options, Shell Completions |
| Large (100+ cmds) | 150+ lines | + Plugins, Architecture, E2E, Version Highlights |

**Gold standard:** kctl-odoo README (227 lines).

**CLIs needing README work:**

| Fix | CLIs |
|-----|------|
| Missing/empty | glitchtip, mailcow, redis, pg (0 lines) |
| Too short (<40L) | cf (3L), dokploy (3L), grafana (3L), github (17L), linear (17L), notion (17L), sentry (17L) |
| Adequate (>40L, may need polish) | ak (93L), api (73L), claude (40L), claw (135L), hz (49L), op (40L), react (89L), rmm (42L), rustdesk (40L), telegram (30L), waha (30L) |
| Good as-is | odoo (227L) |

### SKILL.md

12 CLIs missing: api, claude, github, grafana, linear, mailcow, notion, op, redis, rmm, rustdesk, sentry.

**Method:** Use `kctl_lib.skill_generator` — run `skill generate` for each CLI. Review output for accuracy.

---

## Sweep 2: Test Infrastructure (conftest.py + fixtures)

**Parallelizable:** Yes — all 22 CLIs simultaneously.

### Standard Fixtures (every CLI)

```python
# tests/conftest.py — minimum required fixtures

@pytest.fixture()
def mock_config(tmp_path, monkeypatch):
    """Redirect config to tmp_path. Prevents touching real ~/.config/kodemeio/."""

@pytest.fixture()
def mock_output():
    """Capture Output calls for assertion. Uses kctl_lib.testing.mock_output()."""

@pytest.fixture()
def mock_app_context():
    """Fake AppContext with mock output. Uses kctl_lib.testing.mock_app_context()."""
```

### Additional Fixtures by CLI Type

| CLI type | CLIs | Extra fixtures |
|----------|------|---------------|
| API-based | cf, hz, ak, api, claw, grafana, sentry, glitchtip, rmm, github, notion, mailcow, waha, telegram, rustdesk, dokploy | `mock_api_client` — httpx mock responses, response factory |
| SSH-based | pg, redis | `mock_ssh_tunnel`, `mock_ssh_run` |
| Subprocess-based | op | `mock_subprocess` |
| Docker-based | react, dokploy | `mock_docker_manager` |
| GraphQL-based | linear | `mock_graphql_client` |

### 6 CLIs Need conftest.py Created

ak, claude, mailcow, telegram, waha (gatus deleted).

### 16 CLIs Need conftest.py Audited

Ensure 3 standard fixtures present, add type-specific fixtures if missing.

**Gold standard:** kctl-react conftest.py (257 lines) — autouse isolation, filesystem mocking, monkeypatch config.

---

## Sweep 3: Test Coverage to 35%+

**Parallelizable:** Yes — all 22 CLIs simultaneously. Heaviest sweep.

### Coverage Gap Table

| CLI | Current ratio | Test LOC now | Test LOC target (35%) | Delta needed |
|-----|--------------|-------------|----------------------|-------------|
| telegram | 1% | 15 | 640 | +625 |
| mailcow | 4% | 182 | 1,546 | +1,364 |
| redis | 6% | 139 | 841 | +702 |
| waha | 7% | 144 | 773 | +629 |
| pg | 7% | 826 | 3,873 | +3,047 |
| api | 9% | 1,070 | 4,135 | +3,065 |
| github | 17% | 340 | 712 | +372 |
| sentry | 16% | 350 | 750 | +400 |
| hz | 20% | 1,088 | 1,876 | +788 |
| rmm | 20% | 677 | 1,180 | +503 |
| cf | 20% | 1,361 | 2,416 | +1,055 |
| glitchtip | 25% | 557 | 790 | +233 |
| op | 29% | 1,005 | 1,215 | +210 |
| claw | 30% | 2,130 | 2,480 | +350 |
| rustdesk | 31% | 518 | 580 | +62 |
| react | 32% | 4,994 | 5,440 | +446 |
| dokploy | 33% | 5,712 | 6,080 | +368 |
| ak | 21% | 2,214 | 3,719 | +1,505 |
| linear | 14% | 279 | 713 | +434 |
| notion | 46% | 702 | — | already met |
| claude | 45% | 981 | — | already met |
| grafana | 49% | 1,063 | — | already met |
| odoo | 19% | 12,835 | — | 12.8K test LOC is largest in fleet; ratio is low but absolute coverage is strong + has E2E |

### Testing Strategy by CLI Type

| Pattern | What to test | Mock strategy |
|---------|-------------|---------------|
| API-based | Command output formatting, error mapping, pagination | `mock_api_client.get.return_value = {...}` |
| SSH-based | Query building, output parsing, connection handling | `mock_ssh.return_value = SSHResult(...)` |
| Subprocess | Arg construction, output parsing, exit code handling | `mock_run.return_value = CompletedProcess(...)` |
| Config cmds | init/add/use/show/validate cycle | `temp_config()` from kctl_lib.testing |

**Priority:** Test commands used in production workflows. Skip trivial pass-through wrappers — test logic, not glue.

---

## Sweep 4: kctl-lib Integration Gaps

**Parallelizable:** Yes — 3 sub-sweeps × 22 CLIs.

### 9 Standard Modules (every CLI must use)

```
[x] config           — profile framework                    (88 imports, all CLIs)
[x] exceptions       — 9 exception classes                  (76 imports, all CLIs)
[x] callbacks        — AppContextBase subclass              (25 imports, ~5 missing)
[x] output           — Output class (not raw Rich)          (20 imports, ~5 using raw Rich)
[x] plugins          — KctlPlugin discovery                 (16 imports, ~6 missing)
[x] skill_generator  — skill generate command               (25 imports, covered in sweep 1)
[x] self_update      — self-update command + version warn   (2 imports, 20 CLIs missing)
[x] doctor_base      — doctor command with custom checks    (2 imports, 20 CLIs missing)
[x] completions      — shell completion install             (1 import, 21 CLIs missing)
```

### Three Massively Under-adopted Modules

**1. `self_update` (20 CLIs missing)**

Every CLI gets:
- `kctl-xx self-update` command
- Stale-version warning on startup (checks PyPI, warns if >7 days old)

**2. `doctor_base` (20 CLIs missing)**

Every CLI gets `kctl-xx doctor` with:
- 4 built-in checks (Python, uv, git, Docker)
- Custom checks per CLI type:

| CLI type | Custom doctor checks |
|----------|---------------------|
| API-based | API connectivity, auth token validity |
| SSH-based | SSH key exists, host reachable |
| Subprocess | Binary exists in PATH (e.g., `op` for kctl-op) |
| Docker-based | Docker daemon running, compose available |

**3. `completions` (21 CLIs missing)**

Every CLI gets `kctl-xx completions install` for zsh/bash/fish.

---

## Sweep 5: Error Handling Standardization

**Parallelizable:** Yes — all 22 CLIs simultaneously.

### HTTP Status → Exception Mapping (all API-based CLIs)

```python
401/403 → AuthenticationError
404    → NotFoundError
422    → ValidationError
5xx    → APIError
Timeout → ConnectionError
```

~8 CLIs currently catch generic `Exception` or `httpx.HTTPError` instead.

### `handle_cli_error()` Wrapper

kctl-lib provides a standard error formatter for terminal output. 6 CLIs have ad-hoc error formatting — replace with the standard wrapper.

### Input Validation at CLI Boundaries

Add `ValidationError` for user-facing inputs:
- **pg:** database names (SQL injection risk)
- **cf:** domain names
- **hz:** server names
- **dokploy:** manifest YAML structure (already has some)
- **All CLIs:** profile names in config commands

**NOT adding:** validation for internal code paths. Only CLI argument boundaries.

---

## Sweep 6: E2E Tests (5 CLIs Only)

**Not parallelizable** — shared staging services. Run sequentially.

### Which CLIs Get E2E

| CLI | Justification | Test scope |
|-----|--------------|-----------|
| kctl-odoo | Already has 645 test files | Maintain + extend |
| kctl-dokploy | 13-phase deployment pipeline | Deploy dry-run, compose CRUD, domain routing, env push |
| kctl-react | 11 PWA apps management | Build verification, app discovery, dev server startup |
| kctl-pg | DB provisioning in deploy pipeline | Create/drop test DB, user grants, backup/restore |
| kctl-ak | SSO/auth for all services | Provider CRUD, application CRUD, flow testing |

### E2E Structure (per CLI)

```
packages/kctl-XX/e2e/
├── playwright.config.ts    # Multi-project: setup → tests
├── fixtures/
│   ├── auth.ts             # Login/auth helpers using active profile
│   └── helpers.ts          # Service-specific helpers
├── tests/
│   ├── global-setup.ts     # Authenticate once, save session
│   ├── smoke/              # Basic connectivity + list operations
│   └── scenarios/          # CRUD workflows
```

Connection uses active kctl profile (staging) for credentials. No hardcoded secrets.

### Why NOT the Other 17

- API wrappers (cf, hz, grafana, sentry, etc.) — upstream APIs are stable; mocked unit tests suffice
- Utility CLIs (op, claude, github) — local operations, no live service worth E2E testing
- Comms (telegram, waha, mailcow) — low-frequency manual operations

---

## Execution Summary

### Sweep Order & Dependencies

```
Sweep 0: Delete kctl-gatus           → 1 task
   │
   ▼
Sweep 1: README + SKILL.md           → 22 tasks (parallel)
   │
   ▼
Sweep 2: conftest.py + fixtures      → 22 tasks (parallel)
   │
   ▼
Sweep 3: Test coverage to 35%+       → 22 tasks (parallel)
   │
   ▼
Sweep 4: kctl-lib integration        → 66 tasks (3 sub-sweeps × 22, parallel)
   │
   ▼
Sweep 5: Error handling              → 22 tasks (parallel)
   │
   ▼
Sweep 6: E2E tests (5 CLIs)          → 4 tasks (sequential, odoo already done)
```

**Total: 159 tasks**

### Projected Outcome

| Aspect | Before (avg) | After |
|--------|-------------|-------|
| Tests | 18% ratio | 35%+ |
| README >40L | 50% | 100% |
| SKILL.md | 50% | 100% |
| kctl-lib modules used | 4-5/CLI | 9 standard/CLI |
| conftest.py | 75% | 100% |
| Error handling | ad-hoc | standardized 9-exception pattern |
| E2E | 1 CLI | 5 CLIs |
| Doctor command | 2 CLIs | 22 CLIs |
| Self-update | 2 CLIs | 22 CLIs |
| Shell completions | 1 CLI | 22 CLIs |

### Projected Ratings

| Rating | CLIs |
|--------|------|
| 10/10 | kctl-odoo |
| 9.5/10 | kctl-dokploy, kctl-react, kctl-ak, kctl-api, kctl-claw |
| 9.0/10 | kctl-cf, kctl-pg, kctl-op, kctl-claude, kctl-hz, kctl-grafana, kctl-rmm, kctl-notion, kctl-rustdesk, kctl-sentry, kctl-glitchtip, kctl-mailcow, kctl-redis, kctl-linear, kctl-github, kctl-telegram, kctl-waha |

**All 22 CLIs at 9+/10.**
