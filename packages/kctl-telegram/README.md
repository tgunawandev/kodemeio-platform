# kctl-telegram

Kodemeio Telegram CLI — manage the multi-bot Telegram notification platform.

## Installation

```bash
uv tool install .
```

## Quick Start

```bash
kctl-telegram config init
kctl-telegram health
kctl-telegram dashboard
kctl-telegram bots list
```

## Command Groups

| Group | Description |
|-------|-------------|
| `config` | Manage CLI configuration and profiles |
| `health` | Health checks and diagnostics |
| `dashboard` | System overview dashboard |
| `bots` | Manage Telegram bots |
| `groups` | Manage Telegram groups |
| `messages` | Send and manage messages |
| `chatwoot` | Manage Chatwoot integrations |

## Global Options

| Option | Short | Description |
|--------|-------|-------------|
| `--json` | | Output as JSON |
| `--quiet` | `-q` | Suppress info messages |
| `--format` | `-f` | Output format: pretty, json, csv, yaml |
| `--no-header` | | Suppress table headers (csv) |
| `--profile` | `-p` | Config profile name |
| `--url` | | API URL override |
| `--api-key` | | API key override |
| `--version` | `-V` | Show version and exit |

## Configuration

Config lives in `~/.config/kodemeio/config.yaml` under the `telegram` service key.

```bash
# Initialize default profile
kctl-telegram config init

# Add a named profile
kctl-telegram config add prod \
  --url https://telegram-api.example.com \
  --api-key $TELEGRAM_API_KEY

# Switch active profile
kctl-telegram config use prod

# Show current profile (key masked)
kctl-telegram config show
```

## Development

```bash
uv run pytest tests/ -v
uv run ruff check src/
uv run mypy src/
```
