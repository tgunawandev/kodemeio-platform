# kctl-rmm

Kodemeio Tactical RMM CLI — manage remote monitoring and management for all clients.

## Installation

```bash
uv tool install .
```

## Quick Start

```bash
kctl-rmm config init
kctl-rmm health
kctl-rmm dashboard
kctl-rmm agents list
```

## Setup

```bash
kctl-rmm config init
kctl-rmm config add abcfood --url https://api-rmm.abcfood.app --api-key $KEY
```

## Command Groups

| Group | Description |
|-------|-------------|
| `config` | Manage CLI configuration and profiles |
| `health` | Health checks and diagnostics |
| `dashboard` | System overview dashboard |
| `agents` | Manage Tactical RMM agents |
| `scripts` | Manage and execute scripts |
| `clients` | Manage clients and sites |
| `software` | Software inventory management |
| `patches` | Manage Windows patches and updates |
| `alerts` | Manage alerts |
| `tasks` | Manage automated tasks |
| `services` | Manage Windows services on remote agents |
| `drivers` | Driver management (POS58 thermal printer) |
| `remote` | Remote access (Take Control, terminal, MeshCentral) |
| `maintenance` | RMM stack maintenance (docker services) |
| `checks` | Manage automated checks |
| `winupdates` | Manage Windows Updates on agents |
| `linux` | Linux agent management (install/update/uninstall) |
| `rustdesk` | RustDesk remote access (connect, deploy, manage) |

## Usage Examples

```bash
# Remote Access (opens browser)
kctl-rmm remote takecontrol PCTMIGBJ     # Take Control by hostname
kctl-rmm remote rmm                      # Open RMM dashboard
kctl-rmm remote mesh                     # Open MeshCentral

# Agents
kctl-rmm agents list
kctl-rmm agents summary
kctl-rmm agents offline

# Scripts
kctl-rmm scripts list
kctl-rmm scripts run 136 --agent <id>

# Monitoring
kctl-rmm dashboard
kctl-rmm health

# Multi-profile
kctl-rmm -p abcfood agents list
kctl-rmm -p abcfood remote takecontrol DESKTOP-KR118VQ
```

## Global Options

| Option | Short | Description |
|--------|-------|-------------|
| `--json` | | Output as JSON |
| `--quiet` | `-q` | Suppress info messages |
| `--format` | | Output format: pretty, json, csv, yaml |
| `--no-header` | | Omit table headers |
| `--profile` | `-p` | Config profile name |
| `--url` | | API URL override |
| `--api-key` | | X-API-KEY override |
| `--version` | `-V` | Show version and exit |

## Configuration

Config lives in `~/.config/kodemeio/config.yaml` under the `rmm` service key.

```bash
# Initialize default profile
kctl-rmm config init

# Add a client-specific profile
kctl-rmm config add abcfood \
  --url https://api-rmm.abcfood.app \
  --api-key $RMM_API_KEY

# List all profiles
kctl-rmm config profiles

# Show current profile
kctl-rmm config show
```

## Development

```bash
uv run pytest tests/ -v
uv run ruff check src/
uv run mypy src/
```
