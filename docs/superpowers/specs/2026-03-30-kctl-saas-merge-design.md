# Design: Merge kodemeio-saas kctl-* CLIs into kodemeio-platform

**Date:** 2026-03-30
**Status:** Approved
**Scope:** Move 6 kctl-* CLIs from kodemeio-saas into kodemeio-platform/packages/

## Context

The kodemeio-saas repo contains 6 independent kctl-* CLI repos, each under `kodemeio-{service}/cli/`. These need to be consolidated into the kodemeio-platform monorepo alongside kctl-lib and kctl-rustdesk.

### Source CLIs (kodemeio-saas)

| Current Name | Location | Commands | Has Non-CLI Code |
|---|---|---|---|
| kctl-1password | `kodemeio-1password/cli/` | config, health, discover, status, push, pull, diff, vault, projects, backup | Yes — `src/kodemeio_1password/` (diff, parser, sync, discovery, onepassword) |
| kctl-github | `kodemeio-github/cli/` | config, health, dashboard, repos, ci, prs, secrets, labels, stats, billing | No |
| kctl-linear | `kodemeio-linear/cli/` | config, health, dashboard, issues, cycles, projects, teams, labels, users | No |
| kctl-notion | `kodemeio-notion/cli/` | config, health, pages, databases, users | No |
| kctl-sentry | `kodemeio-sentry/cli/` | config, health, projects, issues, stats | No |
| kctl-telegram | `kodemeio-telegram/cli/` | config, health, dashboard, bots, groups, messages, chatwoot | No (bot service exists but CLI doesn't import it) |

### Target Structure (kodemeio-platform)

Currently has: `packages/kctl-lib/` (v0.3.1) and `packages/kctl-rustdesk/` (v0.1.0).
Workspace: `members = ["packages/*"]` — no config change needed.

## Architecture

### Final Layout

```
kodemeio-platform/packages/
├── kctl-lib/        # existing shared library (v0.3.1)
├── kctl-rustdesk/      # existing example CLI (v0.1.0)
├── kctl-op/            # renamed from kctl-1password, refactored
├── kctl-github/        # direct copy
├── kctl-linear/        # direct copy
├── kctl-notion/        # direct copy
├── kctl-sentry/        # direct copy
└── kctl-telegram/      # CLI only (bot stays in kodemeio-saas)
```

### Package Structure (per CLI)

Each CLI follows the standard template pattern:

```
packages/kctl-{service}/
├── pyproject.toml
├── README.md
├── src/kctl_{service}/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py
│   ├── commands/
│   │   ├── __init__.py
│   │   ├── config_cmd.py
│   │   ├── health.py
│   │   └── {domain}.py ...
│   └── core/
│       ├── __init__.py
│       ├── callbacks.py
│       ├── client.py
│       ├── config.py
│       ├── exceptions.py
│       └── plugins.py
└── tests/
    └── ...
```

## kctl-op Refactor (formerly kctl-1password)

### Rename

| Before | After |
|---|---|
| Package: `kctl-1password` | `kctl-op` |
| Module: `kctl_1password` | `kctl_op` |
| Entry point: `kctl-1password` | `kctl-op` |
| SERVICE_KEY: `"onepassword"` | `"op"` |
| Env prefix: `KCTL_1PASSWORD_*` | `KCTL_OP_*` |

### Library Absorption

The `kodemeio_1password` library (6 modules) gets absorbed into `kctl_op/core/`:

| Source (`kodemeio_1password/`) | Target (`kctl_op/core/`) |
|---|---|
| `diff.py` | `diff.py` |
| `parser.py` | `parser.py` |
| `sync.py` | `sync.py` |
| `discovery.py` | `discovery.py` |
| `onepassword.py` | `op_client.py` |
| `config.py` | Merge into existing `config.py` |

### Import Updates

All imports change:
- `from kodemeio_1password.diff import ...` → `from kctl_op.core.diff import ...`
- `from kodemeio_1password.onepassword import ...` → `from kctl_op.core.op_client import ...`

## Other 5 CLIs — Direct Copy

For kctl-github, kctl-linear, kctl-notion, kctl-sentry, kctl-telegram:

1. Copy `cli/src/`, `cli/tests/`, `cli/pyproject.toml` into `packages/kctl-{service}/`
2. Update `pyproject.toml`:
   - Add `[tool.uv.sources]` for workspace kctl-lib reference
   - Verify `kctl-lib >= 0.3.0` dependency
3. No code changes needed

### pyproject.toml Update Pattern

```toml
[tool.uv.sources]
kctl-lib = { workspace = true }
```

## What Stays in kodemeio-saas

- `kodemeio-telegram/` — bot service code, alembic, schemas, handlers (everything except `cli/`)
- `kodemeio-1password/bin/` — shell scripts (install-op-cli, op-sync, setup-1password)
- `kodemeio-1password/config/` — if still referenced by shell scripts
- All `cli/` directories: removed or marked deprecated after merge is verified

## Template Alignment

During merge, verify each CLI conforms to the copier template conventions:

- 6 global options: `--json`, `--quiet/-q`, `--format/-f`, `--no-header`, `--profile/-p`, `--version/-V`
- 9 standard config subcommands: init, add, use, show, validate, remove, set, profiles, current
- Error handling via `_run()` wrapper with `handle_cli_error()`
- AppContext extends `AppContextBase` from kctl-lib
- Plugin discovery via entry points

Fix deviations during the merge process.

## CI/CD

- Existing `ci.yml` workflow handles all workspace members automatically
- Each CLI can be published to PyPI independently via version tags
- Tests run via `uv run pytest` within each package directory

## Migration Order

1. kctl-github, kctl-linear, kctl-notion, kctl-sentry (simple copies, no deps)
2. kctl-telegram (CLI only, verify no bot imports)
3. kctl-op (rename + refactor, most complex)

## Success Criteria

- All 6 CLIs are workspace members under `packages/`
- `uv sync --all-extras` succeeds from repo root
- All existing tests pass for each CLI
- kctl-op entry point works: `uv run kctl-op --version`
- No imports from `kodemeio_1password` remain
- Config migration: `config.yaml` key `onepassword` → `op` documented
