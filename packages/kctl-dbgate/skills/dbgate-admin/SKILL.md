---
name: dbgate-admin
description: >
  DBGate web-based database management UI administration via kctl-dbgate CLI (11 groups, ~43 commands).
  MUST use for ANY kctl-dbgate operation.
  Triggers on: "check", "config", "connections", "create-database", "current", "disconnect", "doctor", "drop-database", "eval", "generate", "health", "history", "init", "install", "kctl-dbgate", "kill", "monitor", "new-duckdb", "new-sqlite", "ping", "plugins", "preview", "profile", "profiles", "query", "refresh", "remove", "select", "server-changelog", "server-export", "server-import", "server-set", "server-show", "servers", "sessions", "set-admin-password", "skill", "storage", "summary", "test", "uninstall", "upgrade".
  Auto-generated: 2026-04-18
  registry_hash: 32d34e9d504d
---

# dbgate-admin — kctl-dbgate CLI Reference

> Auto-generated from `kctl-dbgate` command registry. Do not edit manually.
> To regenerate: `kctl-dbgate skill generate`
> To add custom content: edit `SKILL.extra.md` in the same directory.

## Overview

**CLI:** `kctl-dbgate`
**Command groups:** 11
**Total commands:** ~43
**Install:** `cd cli && uv tool install --editable .`

## Global Options

| Flag | Description |
|------|-------------|
| `--json` | JSON output |
| `--quiet`, `-q` | Suppress info messages |
| `--format`, `-f` | Output format: pretty/json/csv/yaml |
| `--no-header` | Omit CSV header row |
| `--profile`, `-p` | Config profile name |
| `--version`, `-V` | Show version |

## Command Reference

### `kctl-dbgate config`

Manage CLI configuration and profiles.

| Command | Description |
|---------|-------------|
| `config current` | Show the active profile and connection status. |
| `config init [--url] [--login] [--password] [--name]` | Initialize CLI configuration (interactive if no flags given). |
| `config profiles` | List all profiles with DBGate connection status. |
| `config remove <name> [--force] [--service_only]` | Remove a profile or just its DBGate config. |
| `config server-changelog` | Show DBGate server changelog (POST /config/changelog). |
| `config server-export <outfile>` | Dump the server's /config/get response to a YAML file. |
| `config server-import <infile> [--dry_run]` | Import connections + settings from a YAML file. |
| `config server-set <key> <value>` | Update a single server-side setting (POST /config/update-settings). |
| `config server-show` | Show DBGate's server-side configuration (POST /config/get). |
| `config set <key> <value> [--profile_arg]` | Set a configuration value for the current service. |
| `config show` | Show full configuration (secrets masked). |
| `config use <name>` | Switch the default profile. |

### `kctl-dbgate connections`

Manage DBGate database connections.

| Command | Description |
|---------|-------------|
| `connections create <label> <engine> <server> <port> <user> <password> [--database]` | Create a new database connection. |
| `connections delete <conid> [--force]` | Delete a connection. |
| `connections get <conid>` | Show full detail for a single connection. |
| `connections list` | List all connections known to DBGate (env-configured + user-added). |
| `connections new-duckdb <label> <file>` | Create a new DuckDB-backed connection. |
| `connections new-sqlite <label> <file>` | Create a new SQLite-backed connection. |
| `connections test <conid>` | Test a connection. |
| `connections update <conid> [--label] [--engine] [--server] [--port] [--user] [--password] [--database]` | Update an existing connection (pass only the fields to change). |

### `kctl-dbgate doctor`

Run diagnostic health checks.

### `kctl-dbgate health`

Health checks and monitoring.

| Command | Description |
|---------|-------------|
| `health check` | HTTP + auth + container health. |

### `kctl-dbgate history`

Browse and append to DBGate query history.

| Command | Description |
|---------|-------------|
| `history add <connection> <sql> [--database]` | Append an entry to the query history. |
| `history list` | List query history entries. |

### `kctl-dbgate plugins`

Manage DBGate plugins.

| Command | Description |
|---------|-------------|
| `plugins install <package>` | Install a plugin package. |
| `plugins list` | List plugins in use (derived from connection engines). |
| `plugins uninstall <package>` | Uninstall a plugin package. |
| `plugins upgrade <package>` | Upgrade a plugin to its latest version. |

### `kctl-dbgate query`

Run SQL / eval scripts against DBGate connections.

| Command | Description |
|---------|-------------|
| `query eval <connection> <database> <script>` | Evaluate a JSON/JS script (for MongoDB/NoSQL engines). |
| `query preview [--connection] [--database] [--sql] [--file] [--variables]` | Show the SQL that would be sent (after variable substitution). |
| `query run <connection> <database> [--sql] [--file] [--variables]` | Run SQL and print the result rows. |
| `query select <connection> <database> <table> [--limit] [--where]` | Convenience wrapper: SELECT * FROM <table> [WHERE ...] LIMIT N. |

### `kctl-dbgate servers`

Server-level database management (ping, summary, create/drop DB).

| Command | Description |
|---------|-------------|
| `servers create-database <conid> <name>` | Create a new database on the server. |
| `servers disconnect <conid>` | Disconnect a server-level connection. |
| `servers drop-database <conid> <name> [--force]` | Drop a database on the server. |
| `servers ping <conid>` | Ping a server-level connection (keeps it alive). |
| `servers refresh <conid>` | Refresh server metadata cache. |
| `servers summary <conid>` | Show databases on a server. |

### `kctl-dbgate sessions`

Manage DBGate database sessions.

| Command | Description |
|---------|-------------|
| `sessions create <connection> <database>` | Create a new database session. |
| `sessions kill <sesid>` | Kill a session. |
| `sessions ping <sesid>` | Check a session's status. |

### `kctl-dbgate skill`

Claude Code skill management.

| Command | Description |
|---------|-------------|
| `skill generate [--output] [--install] [--check]` | Auto-generate SKILL.md from CLI command registry. |

**Examples:**
```bash
kctl-dbgate skill generate
kctl-dbgate skill generate --install
kctl-dbgate skill generate --check
```

### `kctl-dbgate storage`

DBGate storage/admin operations.

| Command | Description |
|---------|-------------|
| `storage set-admin-password <password> [--yes]` | Rotate the DBGate admin password. |

## Configuration

Shared config: `~/.config/kodemeio/config.yaml`

```bash
kctl-dbgate config init       # Interactive setup
kctl-dbgate config show       # Show current config
kctl-dbgate config profiles   # List profiles
kctl-dbgate config current    # Show active profile
kctl-dbgate config validate   # Verify config
```
