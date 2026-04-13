---
name: mattermost-admin
description: >
  Mattermost team chat administration via kctl-mm CLI (24 groups, ~109 commands).
  MUST use for ANY kctl-mm operation.
  Triggers on: "activate", "activity", "archive", "assign", "audit", "bots", "cancel", "channels", "check", "cleanup", "completions", "compliance", "components", "config", "create-incoming", "create-outgoing", "current", "dashboard", "deactivate", "delete-incoming", "delete-outgoing", "demote", "deploy", "disable", "doctor", "down", "enable", "export", "full", "generate", "health", "import", "import-export", "init", "install", "integrations", "invite", "jobs", "json", "kctl-mm", "ldap-sync", "ldap-test", "list-incoming", "list-outgoing", "login", "logs", "maintenance", "members", "metrics", "mm-config", "oauth-create", "oauth-delete", "oauth-list", "optimize", "permissions", "plugins", "posts", "profile", "profiles", "promote", "pull", "quick", "rebuild", "reload", "remove", "rename", "reset-caches", "reset-pwd", "restart", "saml-metadata", "search", "security", "self-update", "skill", "status", "summary", "teams", "test-email", "unpin", "users".
  Auto-generated: 2026-04-13
  registry_hash: f8f9a0e3c528
---

# mattermost-admin — kctl-mm CLI Reference

> Auto-generated from `kctl-mm` command registry. Do not edit manually.
> To regenerate: `kctl-mm skill generate`
> To add custom content: edit `SKILL.extra.md` in the same directory.

## Overview

**CLI:** `kctl-mm`
**Command groups:** 24
**Total commands:** ~109
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

### `kctl-mm audit`

Audit & compliance reports.

| Command | Description |
|---------|-------------|
| `audit compliance <report_id> <out>` |  |
| `audit login <username>` |  |
| `audit security` |  |

### `kctl-mm bots`

Bot management.

| Command | Description |
|---------|-------------|
| `bots create <username> <display>` |  |
| `bots delete <bot_id>` |  |
| `bots disable <bot_id>` |  |
| `bots enable <bot_id>` |  |
| `bots list` |  |

### `kctl-mm channels`

Channel management.

| Command | Description |
|---------|-------------|
| `channels add <team_name> <channel_name> <user>` |  |
| `channels archive <team_name> <channel_name>` |  |
| `channels create <team_name> <channel_name> <display> [--private]` |  |
| `channels get <team_name> <channel_name>` |  |
| `channels list <team_name>` |  |
| `channels members <team_name> <channel_name>` |  |
| `channels remove <team_name> <channel_name> <user>` |  |
| `channels rename <team_name> <channel_name> <new_display>` |  |

### `kctl-mm completions`

Generate or install shell completions.

### `kctl-mm config`

Manage CLI configuration and Mattermost profiles.

| Command | Description |
|---------|-------------|
| `config add <name> [--url] [--token] [--team] [--set_default]` | Add or update a profile's Mattermost connection. |
| `config current` | Show the active profile and connection status. |
| `config init [--url] [--token] [--team] [--name]` | Initialize CLI configuration (interactive if no flags given). |
| `config profiles` | List all profiles with Mattermost connection status. |
| `config remove <name> [--force] [--service_only]` | Remove a profile or just its Mattermost config. |
| `config set <key> <value> [--profile_arg]` | Set a configuration value for the Mattermost service. |
| `config show` | Show full configuration (secrets masked). |
| `config use <name>` | Switch the default profile. |
| `config validate` | Validate the active profile's Mattermost connection. |

**Examples:**
```bash
kctl-mm config set url https://mm.new.io
kctl-mm config set token new-token-value
kctl-mm config set default_profile production
```

### `kctl-mm dashboard`

Operational dashboard.

| Command | Description |
|---------|-------------|
| `dashboard activity` |  |
| `dashboard full` |  |
| `dashboard json` |  |
| `dashboard summary` |  |
| `dashboard watch [--interval]` |  |

### `kctl-mm deploy`

Deploy lifecycle operations.

| Command | Description |
|---------|-------------|
| `deploy down` |  |
| `deploy pull` |  |
| `deploy rebuild` |  |
| `deploy restart` |  |
| `deploy up` |  |

### `kctl-mm doctor`

Diagnose kctl-mm configuration and connectivity.

### `kctl-mm health`

Health checks.

| Command | Description |
|---------|-------------|
| `health components` |  |
| `health json` |  |
| `health metrics` |  |
| `health quick` |  |
| `health status` |  |

### `kctl-mm import-export`

Bulk import/export (mmctl).

| Command | Description |
|---------|-------------|
| `import-export export <team> [--out]` |  |
| `import-export import <local_path>` |  |
| `import-export jobs` |  |

### `kctl-mm integrations`

OAuth / LDAP / SAML integrations (mmctl).

| Command | Description |
|---------|-------------|
| `integrations ldap-sync` |  |
| `integrations ldap-test` |  |
| `integrations oauth-create <name> <callback_url>` |  |
| `integrations oauth-delete <oauth_id>` |  |
| `integrations oauth-list` |  |
| `integrations saml-metadata` |  |

### `kctl-mm jobs`

Job management.

| Command | Description |
|---------|-------------|
| `jobs cancel <job_id>` |  |
| `jobs list [--job_type]` |  |
| `jobs status <job_id>` |  |

### `kctl-mm logs`

Tail Mattermost service logs.

| Command | Description |
|---------|-------------|
| `logs logs [--service] [--lines]` | Tail logs for a Mattermost service. |

### `kctl-mm maintenance`

Server maintenance commands.

| Command | Description |
|---------|-------------|
| `maintenance cleanup` |  |
| `maintenance optimize` |  |
| `maintenance reset-caches` |  |
| `maintenance vacuum` |  |

### `kctl-mm mm-config`

Mattermost server config (REST + mmctl).

| Command | Description |
|---------|-------------|
| `mm-config export <local_path>` |  |
| `mm-config get <key>` |  |
| `mm-config reload` |  |
| `mm-config set <key> <value>` |  |
| `mm-config show` |  |
| `mm-config test-email` |  |

### `kctl-mm permissions`

Permissions & role management (mmctl).

| Command | Description |
|---------|-------------|
| `permissions add <role> <perm>` |  |
| `permissions assign <role> <user>` |  |
| `permissions get <role>` |  |
| `permissions list` |  |
| `permissions remove <role> <perm>` |  |

### `kctl-mm plugins`

Plugin management (mmctl).

| Command | Description |
|---------|-------------|
| `plugins delete <plugin_id>` |  |
| `plugins disable <plugin_id>` |  |
| `plugins enable <plugin_id>` |  |
| `plugins install <local_path>` |  |
| `plugins list` |  |

### `kctl-mm posts`

Post management.

| Command | Description |
|---------|-------------|
| `posts create <channel_id> <message>` |  |
| `posts delete <post_id>` |  |
| `posts get <post_id>` |  |
| `posts pin <post_id>` |  |
| `posts search <team_id> <terms>` |  |
| `posts unpin <post_id>` |  |

### `kctl-mm self-update`

Check for updates and upgrade kctl-mm.

### `kctl-mm skill`

Claude Code skill management.

| Command | Description |
|---------|-------------|
| `skill generate [--output] [--install] [--check]` | Auto-generate SKILL.md from CLI command registry. |

**Examples:**
```bash
kctl-mm skill generate
kctl-mm skill generate --install
kctl-mm skill generate --check
```

### `kctl-mm status`

Show Mattermost service status.

### `kctl-mm teams`

Team management.

| Command | Description |
|---------|-------------|
| `teams add <team_name> <user>` |  |
| `teams archive <team_name>` |  |
| `teams create <name> <display>` |  |
| `teams delete <team_name> [--confirm]` |  |
| `teams get <team_name>` |  |
| `teams list` |  |
| `teams members <team_name>` |  |
| `teams remove <team_name> <user>` |  |

### `kctl-mm users`

User management.

| Command | Description |
|---------|-------------|
| `users activate <username>` |  |
| `users create <email> <username> <password>` |  |
| `users deactivate <username>` |  |
| `users demote <username>` |  |
| `users get <username>` |  |
| `users invite <email> <team>` |  |
| `users list [--page] [--per_page]` |  |
| `users promote <username>` |  |
| `users reset-pwd <username>` |  |
| `users search <query>` |  |

### `kctl-mm webhooks`

Webhook management.

| Command | Description |
|---------|-------------|
| `webhooks create-incoming <channel_id> <display>` |  |
| `webhooks create-outgoing <team_id> <trigger>` |  |
| `webhooks delete-incoming <hook_id>` |  |
| `webhooks delete-outgoing <hook_id>` |  |
| `webhooks list` |  |
| `webhooks list-incoming` |  |
| `webhooks list-outgoing` |  |

## Configuration

Shared config: `~/.config/kodemeio/config.yaml`

```bash
kctl-mm config init       # Interactive setup
kctl-mm config show       # Show current config
kctl-mm config profiles   # List profiles
kctl-mm config current    # Show active profile
kctl-mm config validate   # Verify config
```
