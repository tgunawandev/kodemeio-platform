# kctl-* CLI Standards

## Command Naming

| Concern | Canonical Name |
|---------|---------------|
| Code generation | `scaffold` |
| Diagnostics | `doctor` |
| Cleanup | `clean` |
| Dashboard | `dashboard` |
| Skill docs generation | `skill generate` |

## Global Options (required in every CLI)

| Flag | Short | Purpose |
|------|-------|---------|
| `--json` | `-j` | JSON output shorthand |
| `--quiet` | `-q` | Suppress info messages |
| `--format` | `-f` | Output format: pretty/json/csv/yaml |
| `--no-header` | — | Omit CSV header row |
| `--profile` | `-p` | Config profile name |
| `--version` | `-V` | Show version |

## Standard `config` Subcommands

Every CLI must implement: `init`, `add`, `use`, `show`, `validate`, `remove`, `set`, `profiles`, `current`.

## Client Pattern

CLIs with HTTP APIs should subclass `APIClient` (or `AsyncAPIClient`) from `kctl-lib`:

- Set `AUTH_HEADER`, `AUTH_PREFIX`, `API_PREFIX` as class attributes to configure authentication and URL prefixing.
- Override `_unwrap_response` for envelope APIs (e.g., Cloudflare wraps all responses in `{"result": ..., "success": ...}`).
- Enable retry with `retry_enabled=True` for unreliable or rate-limited APIs. Retry uses exponential backoff with jitter.
- Override `_map_error` to extract service-specific error messages from non-2xx responses.

### Exceptions

Not all CLIs use HTTP-based clients:

| CLI | Client approach |
|-----|----------------|
| kctl-pg | `psycopg` (PostgreSQL wire protocol) |
| kctl-odoo | JSON-RPC via `httpx` (custom, not APIClient) |
| kctl-1password | `subprocess` calls to `op` CLI |

## Error Handling

Use `handle_cli_error()` from kctl-lib in `_run()`.

## History

Use `HistoryStore` from kctl-lib. DB at `~/.local/share/kodemeio/{cli-name}/history.db`.
