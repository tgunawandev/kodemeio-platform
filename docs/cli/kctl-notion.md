# kctl-notion

Command reference for `kctl-notion` (7 groups, ~24 commands).

> Auto-generated on 2026-04-02. Do not edit manually.
> Regenerate with: `uv run python scripts/generate-cli-docs.py`

## Global Options

| Flag | Description |
|------|-------------|
| `--json` | JSON output |
| `--quiet`, `-q` | Suppress info messages |
| `--format`, `-f` | Output format: pretty/json/csv/yaml |
| `--no-header` | Omit headers in CSV output |
| `--profile`, `-p` | Config profile name |
| `--version`, `-V` | Show version |

## Commands

### `kctl-notion blocks`

Content block management.

| Command | Description |
|---------|-------------|
| `blocks append <page_id> <text> [--block_type]` | Append a text block to a page. |
| `blocks list <page_id> [--limit]` | List blocks in a page. |

### `kctl-notion config`

Profile and configuration management.

| Command | Description |
|---------|-------------|
| `config add <name>` | Add a new config profile. |
| `config current` | Show active profile and resolved context. |
| `config init` | Interactive config setup. |
| `config profiles` | List all config profiles. |
| `config remove <name>` | Remove a config profile. |
| `config set <key> <value>` | Set a single config value. |
| `config show` | Show current configuration. |
| `config test` | Test API connection with current configuration. |
| `config use <name>` | Switch active config profile. |
| `config validate` | Validate current config completeness. |

### `kctl-notion databases`

Database management.

| Command | Description |
|---------|-------------|
| `databases export <database_id> [--format] [--output]` | Export database to CSV or JSON file. |
| `databases list [--limit]` | List all databases accessible to the integration. |
| `databases query <database_id> [--filter] [--sort] [--descending] [--limit]` | Query database rows with optional filter and sort. |
| `databases show <database_id>` | Show database schema (properties and their types). |

### `kctl-notion health`

API health check.

### `kctl-notion pages`

Page management.

| Command | Description |
|---------|-------------|
| `pages create <parent> <title> [--database]` | Create a new page under a parent page or database. |
| `pages list [--parent] [--limit]` | List pages (recently edited). |
| `pages show <page_id>` | Show page title, properties, and content preview. |
| `pages update <page_id> [--title] [--archived]` | Update page properties (title, archived status). |

### `kctl-notion search`

Search across the Notion workspace.

### `kctl-notion users`

Workspace user management.

| Command | Description |
|---------|-------------|
| `users list` | List workspace members and bots. |
| `users me` | Show current bot/integration user. |
