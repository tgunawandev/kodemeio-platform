# kctl-waha

Command reference for `kctl-waha` (7 groups, ~29 commands).

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

### `kctl-waha bridge`

Manage WAHA bridge sidecar.

| Command | Description |
|---------|-------------|
| `bridge health` | Check bridge sidecar health. |
| `bridge setup-chatwoot [--name] [--callback_url]` | Setup Chatwoot inbox integration via bridge. |
| `bridge setup-webhook [--session] [--webhook_url]` | Setup WAHA webhook via bridge. |
| `bridge status` | Show bridge setup status (WAHA, Chatwoot, Odoo config). |

### `kctl-waha config`

Manage CLI configuration and profiles.

| Command | Description |
|---------|-------------|
| `config add <name> [--url] [--api_key] [--bridge_url] [--set_default]` | Add or update a profile's WAHA connection. |
| `config current` | Show the active profile and connection status. |
| `config init [--url] [--api_key] [--bridge_url] [--name]` | Initialize CLI configuration (interactive if no flags given). |
| `config migrate` | Migrate config from flat format to service-scoped format. |
| `config profiles` | List all profiles with WAHA connection status. |
| `config remove <name> [--force] [--service_only]` | Remove a profile or just its WAHA config. |
| `config set <key> <value> [--profile_arg]` | Set a configuration value for the current service. |
| `config show` | Show full configuration (API keys masked). |
| `config test` | Test API connection with current configuration. |
| `config use <name>` | Switch the default profile. |

### `kctl-waha dashboard`

System overview dashboard.

### `kctl-waha health`

Health checks and diagnostics.

### `kctl-waha messages`

Send WhatsApp messages.

| Command | Description |
|---------|-------------|
| `messages send <phone> <text> [--session]` | Send a text message. |
| `messages send-image <phone> <url> [--caption] [--session]` | Send an image message. |

### `kctl-waha sessions`

Manage WhatsApp sessions.

| Command | Description |
|---------|-------------|
| `sessions delete <name> [--force]` | Delete a WhatsApp session. |
| `sessions get [--name]` | Show session details. |
| `sessions list [--all_sessions]` | List WhatsApp sessions. |
| `sessions logout [--name] [--force]` | Logout from a WhatsApp session. |
| `sessions me [--name]` | Show current session account info. |
| `sessions qr [--name]` | Get QR code for session authentication. |
| `sessions restart [--name]` | Restart a WhatsApp session (stop + start). |
| `sessions start [--name] [--engine]` | Start a WhatsApp session. |
| `sessions stop [--name]` | Stop a WhatsApp session. |

### `kctl-waha webhooks`

Manage session webhooks.

| Command | Description |
|---------|-------------|
| `webhooks list` | List webhook configurations for all sessions. |
| `webhooks set <session> <url> [--events] [--hmac_key]` | Set webhook configuration for a session. |
