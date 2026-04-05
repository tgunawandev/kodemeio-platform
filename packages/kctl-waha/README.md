# kctl-waha

Kodemeio WAHA CLI — manage WhatsApp HTTP API sessions and messaging.

## Installation

```bash
uv tool install .
```

## Quick Start

```bash
kctl-waha config init
kctl-waha health
kctl-waha dashboard
kctl-waha sessions list
```

## Command Groups

| Group | Description |
|-------|-------------|
| `config` | Manage CLI configuration and profiles |
| `health` | Health checks and diagnostics |
| `dashboard` | System overview dashboard |
| `sessions` | Manage WhatsApp sessions |
| `messages` | Send WhatsApp messages |
| `webhooks` | Manage session webhooks |
| `bridge` | Manage WAHA bridge sidecar (Chatwoot/Odoo) |

## Global Options

| Option | Short | Description |
|--------|-------|-------------|
| `--json` | | Output as JSON |
| `--quiet` | `-q` | Suppress info messages |
| `--profile` | `-p` | Config profile name |
| `--url` | | API URL override |
| `--api-key` | | API key override |
| `--bridge-url` | | Bridge URL override |
| `--version` | `-V` | Show version and exit |

## Configuration

Config lives in `~/.config/kodemeio/config.yaml` under the `waha` service key.

```bash
# Initialize default profile
kctl-waha config init

# Add a named profile
kctl-waha config add prod \
  --url https://waha.example.com \
  --api-key $WAHA_API_KEY

# Switch active profile
kctl-waha config use prod

# Show current profile (key masked)
kctl-waha config show
```

## Development

```bash
uv run pytest tests/ -v
uv run ruff check src/
uv run mypy src/
```
