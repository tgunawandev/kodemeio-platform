---
name: notion-admin
description: >
  Notion wiki management via kctl-notion CLI (8 groups, ~25 commands).
  MUST use for ANY kctl-notion operation.
  Triggers on: "append", "blocks", "check", "config", "current", "databases", "export", "generate", "health", "init", "kctl-notion", "pages", "profile", "profiles", "query", "remove", "search", "skill", "test", "users", "validate".
  Auto-generated: 2026-04-05
  registry_hash: 71d9722263b3
---

# notion-admin — kctl-notion CLI Reference

> Auto-generated from `kctl-notion` command registry. Do not edit manually.
> To regenerate: `kctl-notion skill generate`
> To add custom content: edit `SKILL.extra.md` in the same directory.

## Overview

**CLI:** `kctl-notion`
**Command groups:** 8
**Total commands:** ~25
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

Usage: `kctl-notion search <query> [--type] [--limit]`

### `kctl-notion skill`

Claude Code skill management.

| Command | Description |
|---------|-------------|
| `skill generate [--output] [--install] [--check]` | Auto-generate SKILL.md from CLI command registry. |

**Examples:**
```bash
kctl-notion skill generate
kctl-notion skill generate --install
kctl-notion skill generate --check
```

### `kctl-notion users`

Workspace user management.

| Command | Description |
|---------|-------------|
| `users list` | List workspace members and bots. |
| `users me` | Show current bot/integration user. |

## Configuration

Shared config: `~/.config/kodemeio/config.yaml`

```bash
kctl-notion config init       # Interactive setup
kctl-notion config show       # Show current config
kctl-notion config profiles   # List profiles
kctl-notion config current    # Show active profile
kctl-notion config validate   # Verify config
```
