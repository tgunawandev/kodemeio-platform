# CLAUDE.md - kctl-accurate

Kodemeio CLI for the Accurate Online API.

## Quick start

```bash
uv sync --all-packages
uv run --project ../.. pytest packages/kctl-accurate/tests/ -v
```

## Architecture

```
src/kctl_accurate/
├── cli.py                 # Typer app + @app.callback for global flags
├── core/
│   ├── config.py          # SERVICE_KEY=accurate, ServiceConfig, resolve_connection
│   ├── client.py          # AccurateClientWrapper translates SDK exceptions
│   ├── exceptions.py      # SDK→KctlError translator (drives exit codes)
│   └── callbacks.py       # AppContext(AppContextBase), lazy client
└── commands/
    ├── config_cmd.py      # init/list/show/use/add/remove/set/test
    ├── auth.py            # token-info/refresh/logout
    └── doctor_cmd.py      # ConfigCheck + TokenCheck + DbListCheck
```

## Key constraints

- SERVICE_KEY: `"accurate"` — config at `profiles.<name>.accurate.*`
- Depends on `kctl-lib>=0.4.0` (workspace) and `kodemeio-accurate>=0.4.0,<1.0.0` (PyPI)
- All SDK exceptions translated at the wrapper boundary in `core/client.py`
- Secrets always masked in any non-debug output (per `~/.claude/rules/security.md`)
- Exit-code contract enforced by `KctlError` subclass (see `core/exceptions.py`)
- One profile = one tenant. Multi-tenant via multiple profiles, not multi-target invocation.

## What's next

- Phase 2: 23 module command groups (`customers list`, `invoices get`, etc.) generated from `core/columns.py:MODULE_REGISTRY`
- Phase 3: `extract`, `export`, `indo` (e-Faktur + 3 validators + 3 statement extractors)

See `kodemeio-accurate/docs/superpowers/specs/2026-04-30-kctl-accurate-design.md` for the full design.
