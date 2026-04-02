# kctl-telegram

Command reference for `kctl-telegram` (7 groups, ~28 commands).

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

### `kctl-telegram bots`

Manage Telegram bots.

| Command | Description |
|---------|-------------|
| `bots add <token> [--display_name]` | Register a new Telegram bot. |
| `bots get <bot_id>` | Show bot details. |
| `bots list` | List all registered bots. |
| `bots remove <bot_id> [--force]` | Remove a bot. |
| `bots update <bot_id> [--display_name] [--is_active]` | Update a bot's settings. |

### `kctl-telegram chatwoot`

Manage Chatwoot integrations.

| Command | Description |
|---------|-------------|
| `chatwoot add <bot_id> <inbox_identifier> <base_url> <api_token>` | Link a Chatwoot inbox to a Telegram bot. |
| `chatwoot list` | List Chatwoot inboxes linked to Telegram bots. |
| `chatwoot remove <inbox_id> [--force]` | Remove a Chatwoot inbox integration. |

### `kctl-telegram config`

Manage CLI configuration and profiles.

| Command | Description |
|---------|-------------|
| `config add <name> [--url] [--api_key] [--set_default]` | Add or update a profile's Telegram connection. |
| `config current` | Show the active profile and connection status. |
| `config init [--url] [--api_key] [--name]` | Initialize CLI configuration (interactive if no flags given). |
| `config migrate` | Migrate config from flat format to service-scoped format. |
| `config profiles` | List all profiles with Telegram connection status. |
| `config remove <name> [--force] [--service_only]` | Remove a profile or just its Telegram config. |
| `config set <key> <value> [--profile_arg]` | Set a configuration value for the current service. |
| `config show` | Show full configuration (API keys masked). |
| `config test` | Test API connection with current configuration. |
| `config use <name>` | Switch the default profile. |

### `kctl-telegram dashboard`

System overview dashboard.

### `kctl-telegram groups`

Manage Telegram groups.

| Command | Description |
|---------|-------------|
| `groups get <group_id>` | Show group details. |
| `groups list` | List all tracked groups. |
| `groups update <group_id> <field> <value>` | Update a group field. |

### `kctl-telegram health`

Health checks and diagnostics.

### `kctl-telegram messages`

Send and manage messages.

| Command | Description |
|---------|-------------|
| `messages broadcast <text> [--bot_id] [--parse_mode]` | Broadcast a message to all groups. |
| `messages cancel <message_id>` | Cancel a scheduled message. |
| `messages schedule <text> <target_id> <at> [--bot_id]` | Schedule a message for later delivery. |
| `messages scheduled` | List scheduled messages. |
| `messages send <chat_id> <text> [--bot_id] [--parse_mode]` | Send a message to a specific chat. |
