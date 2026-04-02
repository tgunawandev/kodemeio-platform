# kctl-gatus

Command reference for `kctl-gatus` (7 groups, ~26 commands).

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

### `kctl-gatus alerts`

Manage and test alert channels.

| Command | Description |
|---------|-------------|
| `alerts history` | Show recent alert triggers (from endpoint results). |
| `alerts test [--channel] [--telegram_token] [--telegram_chat_id] [--mattermost_webhook] [--smtp_host] [--smtp_port]` | Test alert channels by sending a test message. |

### `kctl-gatus config`

Manage CLI configuration and profiles.

| Command | Description |
|---------|-------------|
| `config add <name> [--url] [--api_key] [--set_default]` | Add or update a profile's Gatus connection. |
| `config current` | Show the active profile and connection status. |
| `config init [--url] [--api_key] [--name]` | Initialize CLI configuration (interactive if no flags given). |
| `config migrate` | Migrate config from flat format to service-scoped format. |
| `config profiles` | List all profiles with Gatus connection status. |
| `config remove <name> [--force] [--service_only]` | Remove a profile or just its Gatus config. |
| `config set <key> <value> [--profile_arg]` | Set a configuration value for the current service. |
| `config show` | Show full configuration (keys masked). |
| `config test` | Test API connection with current configuration. |
| `config use <name>` | Switch the default profile. |

### `kctl-gatus dashboard`

Dashboard overview with comprehensive metrics.

| Command | Description |
|---------|-------------|
| `dashboard overview` | Show comprehensive dashboard: groups, up/down counts, worst performers. |

### `kctl-gatus discovery`

Manage the auto-discovery sidecar.

| Command | Description |
|---------|-------------|
| `discovery config` | Show the current discovery configuration (from Gatus endpoint groups). |
| `discovery endpoints` | List only auto-discovered endpoints (group: auto-dokploy). |
| `discovery status` | Check if the discovery sidecar is running and show its status. |
| `discovery trigger [--container] [--compose_file]` | Force a re-discovery run by restarting the discovery sidecar. |

### `kctl-gatus endpoints`

Manage and query monitored endpoints.

| Command | Description |
|---------|-------------|
| `endpoints get <key>` | Get detailed status for a specific endpoint. |
| `endpoints list` | List all monitored endpoints with their current status. |
| `endpoints response-time <key> [--duration]` | Get response time data for an endpoint. |
| `endpoints search <query>` | Search endpoints by name or group. |
| `endpoints uptime <key> [--duration]` | Get uptime data for an endpoint. |

### `kctl-gatus health`

Check Gatus health and endpoint summary.

| Command | Description |
|---------|-------------|
| `health check` | Check Gatus API health and show an endpoint summary. |
| `health dashboard` | Rich table with all endpoints, status, uptime, and response time. |

### `kctl-gatus results`

View endpoint check results and history.

| Command | Description |
|---------|-------------|
| `results list <key> [--limit]` | Show recent check results for an endpoint. |
| `results summary` | Show summary of all endpoints: counts of up/down/unknown. |
