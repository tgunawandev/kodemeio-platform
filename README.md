# kodemeio-platform

Shared infrastructure for the Kodemeio CLI ecosystem.

## Packages

### kctl-common

Shared core library for all `kctl-*` CLI tools (kctl-next, kctl-odoo, kctl-react, kctl-api, kctl-claw).

**Install:** `uv add kctl-common`

**Modules:**
- `kctl_common.exceptions` — Unified exception hierarchy
- `kctl_common.output` — Multi-format output (pretty/json/csv/yaml)
- `kctl_common.config` — Profile management (`~/.config/kodemeio/config.yaml`)
- `kctl_common.callbacks` — `AppContextBase` abstract context
- `kctl_common.runner` — Shell command runner + git helpers
- `kctl_common.plugins` — Plugin discovery via entry points
- `kctl_common.history` — SQLite history tracking
- `kctl_common.testing` — Shared test fixtures

## Development

```bash
uv sync --all-extras
uv run pytest packages/kctl-common/tests/ -v
uv run ruff check packages/kctl-common/src/
uv run mypy packages/kctl-common/src/
```
