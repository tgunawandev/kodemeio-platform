# kctl-rustdesk

Kodemeio RustDesk CLI — manage RustDesk server infrastructure.

## Installation

```bash
uv tool install .
```

## Quick Start

```bash
kctl-rustdesk config init
kctl-rustdesk health
kctl-rustdesk dashboard
kctl-rustdesk peers list
```

## Command Groups

| Group | Description |
|-------|-------------|
| `config` | Manage CLI configuration and profiles |
| `health` | Health checks for RustDesk server |
| `dashboard` | System overview dashboard |
| `peers` | Manage RustDesk peers (devices) |
| `users` | Manage RustDesk users |
| `audit` | Audit logs and connection history |
| `backup` | Backup and restore RustDesk server data |
| `setup` | Server setup and configuration |
| `maintenance` | Maintenance and operational tasks |

## Global Options

| Option | Short | Description |
|--------|-------|-------------|
| `--json` | | Output as JSON |
| `--quiet` | `-q` | Suppress info messages |
| `--format` | `-f` | Output format: pretty, json, csv, yaml |
| `--no-header` | | Omit column headers |
| `--profile` | `-p` | Config profile |
| `--host` | | Server host override |
| `--version` | `-V` | Show version and exit |

## Configuration

Config lives in `~/.config/kodemeio/config.yaml` under the `rustdesk` service key.

```bash
# Initialize default profile
kctl-rustdesk config init

# Add a named profile
kctl-rustdesk config add prod \
  --host https://rustdesk.example.com \
  --api-key $RUSTDESK_API_KEY

# Switch active profile
kctl-rustdesk config use prod

# Show current profile (key masked)
kctl-rustdesk config show
```

## Development

```bash
uv run pytest tests/ -v
uv run ruff check src/
uv run mypy src/
```
