# kctl-dbgate

CLI for [DBGate](https://dbgate.org/) — the web-based database management UI. Part of the Kodemeio `kctl-*` family (shared config at `~/.config/kodemeio/config.yaml`, scoped under `dbgate`).

**Version:** 0.2.0 — wraps ~70 of DBGate's 121 REST endpoints across 10 command groups.

## Install

From the workspace root:

```bash
uv sync                                           # installs all kctl-* packages
uv tool install --editable packages/kctl-dbgate   # makes `kctl-dbgate` globally available
```

## Configure

```bash
# Interactive
kctl-dbgate config init

# Or explicit
kctl-dbgate config set url https://dbgate.local.kodeme.io
kctl-dbgate config set login admin
kctl-dbgate config set password '<your-password>'
```

Config is saved under the active profile in `~/.config/kodemeio/config.yaml`:

```yaml
default_profile: kodemeio
profiles:
  kodemeio:
    dbgate:
      url: https://dbgate.local.kodeme.io
      login: admin
      password: ****
```

Use `-p <profile>` to target a different tenant:

```bash
kctl-dbgate -p idtpp connections list
```

### Env var overrides

| Variable | Purpose |
|----------|---------|
| `KCTL_DBGATE_URL` | Override URL |
| `KCTL_DBGATE_LOGIN` | Override login |
| `KCTL_DBGATE_PASSWORD` | Override password |
| `KCTL_DBGATE_PROFILE` | Default profile name |

## Command groups

```
kctl-dbgate --help

┌─────────────┬──────────────────────────────────────────────────────────┐
│ config      │ CLI profile management + DBGate server settings          │
│ health      │ HTTP + auth + container quick check                      │
│ doctor      │ 6 diagnostic checks with --fix hints                     │
│ connections │ CRUD for DBGate connection definitions                   │
│ servers     │ Server-level DB operations (ping, create-db, drop-db)    │
│ query       │ SQL/script execution with --format/--file/--var          │
│ sessions    │ Query session lifecycle (create, kill)                   │
│ plugins     │ DBGate plugin install/uninstall/upgrade                  │
│ history     │ Query history read/write                                 │
│ storage     │ Admin-password rotation                                  │
└─────────────┴──────────────────────────────────────────────────────────┘
```

Run any subcommand with `--help` for full flag documentation. All commands honor the global flags: `--json`, `--format {pretty,json,csv,yaml,tsv}`, `--no-header`, `--quiet`.

## Connections

```bash
# List all connections (shows `Source` column: "user" vs "env")
kctl-dbgate connections list

# Detail
kctl-dbgate connections get <connection_id>

# Test reachability (uses DBGate's own /connections/test)
kctl-dbgate connections test <connection_id>

# Create a new one (Postgres example)
kctl-dbgate connections create \
    --label "dokploy-postgres" \
    --engine postgres@dbgate-plugin-postgres \
    --server 10.0.0.3 \
    --port 5432 \
    --user app --password '…' \
    --database dokploy

# Update (only pass flags for fields you want to change)
kctl-dbgate connections update <connection_id> --password 'new-password'

# Delete
kctl-dbgate connections delete <connection_id> --force

# SQLite / DuckDB databases (file-based)
kctl-dbgate connections new-sqlite --label metrics --file /data/metrics.db
kctl-dbgate connections new-duckdb --label analytics --file /data/analytics.duckdb
```

### Engine strings

| Database | `--engine` value |
|----------|------------------|
| PostgreSQL | `postgres@dbgate-plugin-postgres` |
| MySQL / MariaDB | `mysql@dbgate-plugin-mysql` |
| MSSQL | `mssql@dbgate-plugin-mssql` |
| MongoDB | `mongo@dbgate-plugin-mongo` |
| Redis | `redis@dbgate-plugin-redis` |
| SQLite | `sqlite@dbgate-plugin-sqlite` |
| DuckDB | `duckdb@dbgate-plugin-duckdb` |
| Oracle | `oracle@dbgate-plugin-oracle` |

## Servers (server-level DB operations)

```bash
kctl-dbgate servers ping <connection_id>                   # just-connected check
kctl-dbgate servers summary <connection_id>                # database list on this server
kctl-dbgate servers create-database <connection_id> --name mydb
kctl-dbgate servers drop-database  <connection_id> --name mydb --force
kctl-dbgate servers refresh <connection_id>                # refresh metadata cache
kctl-dbgate servers disconnect <connection_id>             # force disconnect
```

## Query

Execute SQL directly (or JS scripts for Mongo):

```bash
# Inline SQL
kctl-dbgate query run --connection <id> --database dokploy \
    --sql "SELECT version()"

# From a file
kctl-dbgate query run --connection <id> --database dokploy \
    --file schema.sql

# With variable substitution (`{{var}}` → value)
kctl-dbgate query run --connection <id> --database dokploy \
    --sql "SELECT * FROM {{table}} LIMIT {{n}}" \
    --var table=users --var n=10 \
    --format csv

# SELECT convenience
kctl-dbgate query select --connection <id> --database dokploy \
    --table users --where "active = true" --limit 100

# Preview (doesn't execute)
kctl-dbgate query preview --connection <id> --database dokploy \
    --sql "DROP TABLE users"

# Mongo / NoSQL JS scripts
kctl-dbgate query eval --connection <mongo_id> --database mydb \
    --script aggregations.js
```

**Note on `--var`:** simple string substitution, not SQL-parameterized. Don't pass untrusted input.

## Sessions

```bash
kctl-dbgate sessions create --connection <id> --database mydb
kctl-dbgate sessions kill <session_id>
```

## Plugins

```bash
kctl-dbgate plugins list
kctl-dbgate plugins install dbgate-plugin-csv
kctl-dbgate plugins upgrade dbgate-plugin-csv
kctl-dbgate plugins uninstall dbgate-plugin-csv
```

## Config (CLI profiles + DBGate server settings)

```bash
# CLI profile mgmt (stored in ~/.config/kodemeio/config.yaml)
kctl-dbgate config init
kctl-dbgate config show
kctl-dbgate config set <key> <value>
kctl-dbgate config use <profile>
kctl-dbgate config profiles
kctl-dbgate config current
kctl-dbgate config remove <profile> [--force] [--service-only]

# DBGate server settings (stored in /root/.dbgate/ on the server)
kctl-dbgate config server-show                  # POST /config/get
kctl-dbgate config server-set --key <k> --value <v>
kctl-dbgate config server-changelog             # DBGate changelog
kctl-dbgate config server-export settings.yaml  # export server settings + connections
kctl-dbgate config server-import settings.yaml  # import
```

## History

```bash
kctl-dbgate history list                                   # latest queries
kctl-dbgate history add --connection <id> --sql "..."      # append a record
```

## Health & Doctor

```bash
kctl-dbgate health check           # quick live check (HTTP + auth + container)
kctl-dbgate doctor                 # full 6-check diagnostic with fix hints
```

Doctor checks: URL configured → credentials configured → HTTP reachable → login succeeds → `/config/get` readable → server-summary reachable (skipped if no connections).

## Storage

```bash
# Rotate DBGate's admin password (persisted to /root/.dbgate/user.json)
kctl-dbgate storage set-admin-password --password 'new-password'
```

## Global flags

Every command supports:

| Flag | Purpose |
|------|---------|
| `-p, --profile` | Select kctl-dbgate profile |
| `--url` / `--login` / `--password` | Per-invocation override (no profile state change) |
| `-f, --format` | `pretty` (default), `json`, `csv`, `tsv`, `yaml` |
| `--json` | Shortcut for `--format json` |
| `--no-header` | Omit header row in CSV/TSV |
| `--quiet` / `-q` | Suppress info messages |
| `-V, --version` | Print version and exit |

## API coverage

- **Wrapped (≈ 70):** everything under `connections`, `server-connections`, `database-connections` (query surface), `config`, `sessions`, `plugins`, `query-history`, `storage`, plus `auth/login` for session bootstrap.
- **Skipped (≈ 50):** `archive/*`, `apps/*`, `jsldata/*`, `files/*`, `runners/*`, `uploads/*`, `connections/dblogin-*`, `auth/oauth-*`. These are UI-state / plugin-internal endpoints with no CLI value.

Full endpoint inventory: 121 endpoints across 15 groups. See `/tmp/dbgate-endpoints.txt` (generated via `grep -oE 'apiCall\("[^"]+' /home/dbgate-docker/public/build/bundle.js`).

## Known upstream issue

`plugins install <package>` currently fails at the Node layer inside DBGate with a path-resolution error. The CLI payload is correct per `bundle.js` — this is a server-side issue. Install plugins via the web UI for now.

## Development

```bash
cd packages/kctl-dbgate
uv run pytest -q                  # 52 tests
uv run ruff check src/ tests/
uv run mypy src/ --strict
uv run kctl-dbgate --help
```

Test harness uses `pytest-httpx` for HTTP mocking — no live network calls in tests.

## License

MIT
