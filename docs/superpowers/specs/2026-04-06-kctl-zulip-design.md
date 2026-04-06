# kctl-zulip Design Spec

**Date:** 2026-04-06
**Status:** Approved
**Approach:** Clean migration from kodemeio-zulip/cli/ into monorepo packages/kctl-zulip/ with full kctl-lib integration

## Overview

Create a mature kctl-zulip CLI package in the kodemeio-platform monorepo (`packages/kctl-zulip/`), migrating and upgrading the existing standalone CLI from `kodemeio-zulip/cli/`. The CLI manages Zulip team chat instances (zulip.kodeme.io) with the same maturity level as kctl-odoo.

**Source:** `/home/tgunawan/project/00-new-projects/kodemeio-workspace/kodemeio-zulip/cli/` (21 command modules, ~2,579 LOC)
**Target:** `packages/kctl-zulip/` in kodemeio-platform monorepo
**Staging manifest:** `deploys/instances/staging/kod-infra-zulip.yaml`

## Package Structure

```
packages/kctl-zulip/
├── src/kctl_zulip/
│   ├── __init__.py                    # version = "0.2.0"
│   ├── __main__.py                    # python -m kctl_zulip
│   ├── cli.py                         # Main Typer app + error handler
│   ├── core/
│   │   ├── __init__.py
│   │   ├── callbacks.py               # AppContext(AppContextBase) - lazy client/output
│   │   ├── client.py                  # ZulipClient (custom, not APIClient subclass)
│   │   ├── config.py                  # SERVICE_KEY="zulip", resolve_connection(), ServiceConfig
│   │   └── output.py                  # Re-export: from kctl_lib.output import Output
│   └── commands/
│       ├── __init__.py
│       ├── users.py                   # Port from existing
│       ├── streams.py                 # Port from existing
│       ├── messages.py                # Port from existing
│       ├── topics.py                  # Port from existing
│       ├── groups.py                  # Port from existing
│       ├── realm.py                   # Port from existing
│       ├── invitations.py             # Port from existing
│       ├── emoji.py                   # Port from existing
│       ├── health.py                  # Port from existing
│       ├── dashboard.py               # Port from existing
│       ├── announce.py                # Port from existing
│       ├── reactions.py               # Port from existing
│       ├── presence.py                # Port from existing
│       ├── scheduled.py               # Port from existing
│       ├── muted.py                   # Port from existing
│       ├── drafts.py                  # Port from existing
│       ├── profile_fields.py          # Port from existing
│       ├── alert_words.py             # Port from existing
│       ├── linkifiers.py              # Port from existing
│       ├── config_cmd.py              # Rewritten to use kctl-lib config functions
│       ├── doctor_cmd.py              # NEW: 5 health checks
│       └── skill_cmd.py               # NEW: skill generate (hidden)
├── tests/
│   ├── __init__.py
│   ├── conftest.py                    # Standard fixtures
│   ├── test_users.py
│   ├── test_streams.py
│   ├── test_messages.py
│   ├── test_groups.py
│   ├── test_config.py
│   ├── test_client.py
│   ├── test_doctor.py
│   ├── test_health.py
│   ├── test_dashboard.py
│   ├── test_emoji.py
│   ├── test_invitations.py
│   ├── test_realm.py
│   ├── test_reactions.py
│   ├── test_presence.py
│   ├── test_scheduled.py
│   ├── test_muted.py
│   ├── test_drafts.py
│   ├── test_profile_fields.py
│   ├── test_alert_words.py
│   ├── test_linkifiers.py
│   ├── test_announce.py
│   ├── test_topics.py
│   ├── test_resolve_connection.py
│   └── test_cli.py
├── e2e/
│   ├── playwright.config.ts
│   ├── package.json
│   ├── tsconfig.json
│   ├── fixtures/
│   │   ├── zulip-auth.ts              # API key auth helper
│   │   ├── zulip-helpers.ts           # Stream/message helpers
│   │   └── zulip-test.ts              # Extended test fixture
│   └── tests/
│       ├── global-setup.ts
│       ├── scenarios/
│       │   ├── login.spec.ts          # Web login via Authentik OIDC
│       │   └── messaging.spec.ts      # Send/receive messages
│       ├── smoke/
│       │   └── health.spec.ts         # API health check
│       └── shared/
│           └── navigation.spec.ts     # Sidebar/stream navigation
├── skills/
│   └── zulip-admin/
│       └── SKILL.md                   # Auto-generated via skill generate
├── docs/
│   └── completions.md
├── pyproject.toml
└── README.md                          # 200+ lines
```

## Core Layer: kctl-lib Integration

### callbacks.py - AppContext

Extends `AppContextBase` from kctl-lib. Inherits `json_mode`, `quiet`, `profile`, `format`, `no_header`, and lazy `output` property.

```python
@dataclass
class AppContext(AppContextBase):
    url_override: str | None = None
    email_override: str | None = None
    api_key_override: str | None = None
    _client: ZulipClient | None = field(default=None, repr=False, init=False)

    @property
    def client(self) -> ZulipClient:
        if self._client is None:
            url, email, api_key = resolve_connection(
                profile_name=self.profile,
                url_override=self.url_override,
                email_override=self.email_override,
                api_key_override=self.api_key_override,
            )
            self._client = ZulipClient(base_url=url, email=email, api_key=api_key)
        return self._client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
```

### client.py - ZulipClient

Custom client (NOT subclassing kctl-lib APIClient) because Zulip has unique requirements:
- HTTP Basic auth (`email:api_key` tuple), not Bearer header
- POST uses form-data by default, not JSON
- Returns HTTP 200 with `{"result": "error"}` envelope — needs custom checking
- Has `post_multipart()` for emoji upload

Stays ~130 LOC, ported as-is from existing. Only change: import exceptions from `kctl_lib.exceptions` instead of local `kctl_zulip.core.exceptions`.

### config.py - Service Configuration

Replace existing 180 LOC with kctl-lib delegation (~60 LOC):

```python
SERVICE_KEY = "zulip"
ENV_PREFIX = "KCTL_ZULIP"

class ServiceConfig(BaseModel):
    url: str = ""
    email: str = ""
    api_key: str = ""

def resolve_connection(
    profile_name: str | None = None,
    url_override: str | None = None,
    email_override: str | None = None,
    api_key_override: str | None = None,
) -> tuple[str, str, str]:
    """Priority: CLI flags > env vars > profile config."""
    # Uses kctl_lib.config.get_service_config(), resolve_active_profile_name()
```

Drops: `load_raw_config`, `save_raw_config`, `load_config`, `_is_service_scoped`, `set_service_config`, `get_profile_names`, `get_default_profile`, `set_default_profile`, `remove_profile` — all provided by kctl-lib.

### output.py - Re-export

```python
from kctl_lib.output import Output
```

### Exceptions

No local `exceptions.py`. All commands import directly from `kctl_lib.exceptions`:
- `KctlError`, `ConfigError`, `AuthenticationError`, `NotFoundError`
- `APIError`, `ConnectionError`, `CommandError`, `ValidationError`

## CLI Entry Point

### Global Options

```
--json, --quiet/-q, --format/-f (pretty/json/csv/yaml), --no-header,
--profile/-p, --url, --email, --api-key, --version/-V
```

### Command Panels (rich_help_panel)

| Panel | Commands |
|-------|----------|
| Admin & Config | users, groups, realm, invitations, config |
| Messaging | messages, streams, topics, announce, drafts, scheduled |
| Personalization | emoji, reactions, presence, muted, alert-words, profile-fields, linkifiers |
| Monitoring | health, dashboard |
| Tools | doctor, self-update, completions, skill (hidden) |

### Error Handler

Replace 5 specific exception catches with `kctl_lib.handle_cli_error()`:

```python
def _run() -> None:
    try:
        app()
    except KctlError as e:
        handle_cli_error(e)
```

### Plugin Discovery

Entry point group: `kctl_zulip.plugins` for extensibility.

## Command Modules

### Port Strategy (20 existing modules)

Minimal changes per file:
1. Remove local exception imports, use `kctl_lib.exceptions`
2. Output comes from `ctx.obj.output` (same interface)
3. Add `rich_help_panel` to each `typer.Typer()` help string

No logic changes — commands are thin wrappers around `client.get/post/patch/delete` + `output.table/detail/success/error`.

### LOC Breakdown

| Module | LOC | Action |
|--------|-----|--------|
| config_cmd | 477 | **Rewrite** using kctl-lib config functions (~150 LOC) |
| streams | 230 | Port as-is |
| users | 173 | Port as-is |
| groups | 171 | Port as-is |
| messages | 157 | Port as-is |
| dashboard | 135 | Port as-is |
| health | 133 | Port as-is |
| profile_fields | 125 | Port as-is |
| scheduled | 121 | Port as-is |
| drafts | 116 | Port as-is |
| muted | 105 | Port as-is |
| presence | 97 | Port as-is |
| realm | 93 | Port as-is |
| emoji | 86 | Port as-is |
| invitations | 84 | Port as-is |
| reactions | 79 | Port as-is |
| linkifiers | 71 | Port as-is |
| alert_words | 54 | Port as-is |
| topics | 40 | Port as-is |
| announce | 32 | Port as-is |
| doctor_cmd | ~80 | **New** |
| skill_cmd | ~30 | **New** |

### New: Doctor Command

5 checks using `kctl_lib.doctor_base.DoctorCheck` protocol:

| # | Check | Pass | Warn | Fail | Fix Command |
|---|-------|------|------|------|-------------|
| 1 | Python Version | 3.12+ | — | < 3.12 | — |
| 2 | uv Available | uv x.y.z | — | not installed | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| 3 | Config Valid | Profile + URL shown | No profile configured | Config missing/corrupt | `kctl-zulip config init` |
| 4 | API Connectivity | Zulip x.y (200 OK) | Slow (>5s) | Connection refused | `curl -s <url>/api/v1/server_settings` |
| 5 | Authentication | `user@kodeme.io (admin)` | — | 401/403 | `kctl-zulip config set api_key <key>` |

Checks 1-2 use kctl-lib built-in checks. Checks 3-5 are Zulip-specific dataclasses.
Check 4 hits public `/api/v1/server_settings` (no auth). Check 5 hits `/api/v1/users/me` (auth required).

## Testing Strategy

### conftest.py Fixtures

| Fixture | Returns | Purpose |
|---------|---------|---------|
| `runner` | `CliRunner()` | Typer CLI test runner |
| `mock_client` | `MagicMock(spec=ZulipClient)` | Mocked Zulip API client |
| `mock_config(tmp_path, monkeypatch)` | `Path` | Temp config dir |
| `mock_output` | `Output(json_mode=True, quiet=True)` | Via `kctl_lib.testing.mock_output()` |
| `mock_context(mock_client, mock_output)` | `AppContext` | Full context with mocks |

### Test Pattern

Each command module gets a test file that patches `resolve_connection` + `ZulipClient`:

```python
def test_users_list(runner, mock_client):
    mock_client.get.return_value = {"members": [{"user_id": 1, "full_name": "Alice"}]}
    with patch("kctl_zulip.core.callbacks.resolve_connection", return_value=("url", "e", "k")), \
         patch("kctl_zulip.core.callbacks.ZulipClient", return_value=mock_client):
        result = runner.invoke(app, ["users", "list", "--json"])
    assert result.exit_code == 0
```

### Test Files (24 total)

| File | Tests | Covers |
|------|-------|--------|
| test_users.py | list, get, create, update, deactivate, reactivate | CRUD + role changes |
| test_streams.py | list, get, create, update, delete, subscribe, unsubscribe | CRUD + subscriptions |
| test_messages.py | list, send (stream + DM), update, delete | Send paths |
| test_groups.py | list, get, create, update, delete, add/remove-member | CRUD + membership |
| test_config.py | init, add, use, show, remove, profiles, current, test | Config lifecycle |
| test_client.py | get, post, patch, delete, post_multipart, check_health, error envelope | ZulipClient core |
| test_doctor.py | all 5 checks pass/fail/warn | Doctor framework |
| test_health.py | health check, watch mode | Monitoring |
| test_dashboard.py | dashboard output | Summary display |
| test_emoji.py | list, upload, delete | Multipart upload |
| test_invitations.py | list, create, revoke | Invite lifecycle |
| test_realm.py | settings, get, update | Server settings |
| test_reactions.py | add, remove, list | Message reactions |
| test_presence.py | list, get, set-status | User presence |
| test_scheduled.py | list, create, update, delete | Scheduled messages |
| test_muted.py | topics, mute/unmute topic/user | Mute management |
| test_drafts.py | list, create, update, delete | Draft CRUD |
| test_profile_fields.py | list, create, update, delete, reorder | Custom fields |
| test_alert_words.py | list, add, remove | Alert words |
| test_linkifiers.py | list, create, delete | Pattern linkifiers |
| test_announce.py | send announcement | Broadcast |
| test_topics.py | list topics | Topic listing |
| test_resolve_connection.py | priority: CLI > env > config, missing fields | Config resolution |
| test_cli.py | version flag, help, error handler, unknown command | CLI entry point |

### Pytest Markers

- `@pytest.mark.smoke` — tests requiring a live Zulip instance
- `@pytest.mark.integration` — tests reading real config files

### E2E (Playwright)

Lightweight skeleton with 3 scenarios:
- `login.spec.ts` — Zulip web login via Authentik OIDC
- `messaging.spec.ts` — Send message, verify in stream
- `health.spec.ts` — Hit `/api/v1/server_settings`, verify 200

Env vars: `ZULIP_URL`, `ZULIP_EMAIL`, `ZULIP_API_KEY`

## pyproject.toml

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "kctl-zulip"
version = "0.2.0"
description = "Kodemeio Zulip CLI - manage Zulip team chat"
readme = "README.md"
license = "MIT"
requires-python = ">=3.12"
authors = [{ name = "Kodemeio", email = "dev@kodeme.io" }]
dependencies = [
    "kctl-lib>=0.4.0",
    "httpx>=0.28.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-httpx>=0.35.0",
    "pytest-cov>=6.0.0",
    "ruff>=0.9.0",
    "mypy>=1.14.0",
    "types-PyYAML>=6.0.0",
]

[project.scripts]
kctl-zulip = "kctl_zulip.cli:_run"

[tool.hatch.build.targets.wheel]
packages = ["src/kctl_zulip"]

[tool.ruff]
target-version = "py312"
line-length = 120

[tool.ruff.lint]
select = ["E", "F", "I", "W", "UP", "B", "SIM"]

[tool.mypy]
python_version = "3.12"
strict = true

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "integration: tests that read real config files",
    "smoke: tests that require a live Zulip instance",
]
```

Drops direct `typer`, `rich`, `pydantic`, `pyyaml` deps — they come transitively via `kctl-lib>=0.4.0`.

## Workspace Integration

- Add `"packages/kctl-zulip"` to root `pyproject.toml` workspace members
- Update `CLAUDE.md`: add kctl-zulip to workspace members table (21 -> 22), Key Paths, Developer & SaaS Tools section

## Summary

| Aspect | Metric |
|--------|--------|
| Package location | `packages/kctl-zulip/` in monorepo |
| Core layer | kctl-lib integration (AppContextBase, Output, config, exceptions) |
| Client | Custom ZulipClient (Basic auth, form POST, error envelope) |
| Command groups | 22 (20 ported + doctor + skill) |
| Command count | ~70 commands |
| Standard commands | doctor, self-update, completions, skill generate |
| Test files | 24 unit test files + conftest |
| E2E | Playwright skeleton (3 scenarios) |
| SKILL.md | Auto-generated via `skill generate` |
| README | 200+ lines |
| Version | 0.2.0 |
