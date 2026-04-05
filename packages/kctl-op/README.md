# kctl-op

Kodemeio 1Password CLI — secret management and .env sync across all projects.

## Installation

```bash
uv tool install .
```

## Quick Start

```bash
kctl-op config init
kctl-op health
kctl-op vault list
kctl-op sync pull
```

## Command Groups

| Group | Description |
|-------|-------------|
| `config` | Manage CLI configuration and profiles |
| `health` | Health checks and diagnostics |
| `vault` | Vault management operations |
| `projects` | Project discovery and status |
| `push` | Push .env files to 1Password |
| `pull` | Pull secrets from 1Password to .env |
| `diff` | Show differences between local and 1Password |
| `discover` | Discover .env files in project directories |
| `backup` | Backup management for .env files |
| `status` | Check sync status |

Top-level commands: `list` (list all vault items)

## Configuration

Config lives in `~/.config/kodemeio/config.yaml` under the `op` service key.

```bash
# Initialize a profile
kctl-op config init

# Add a named profile
kctl-op config add prod --vault MyVault --token $OP_SERVICE_ACCOUNT_TOKEN

# Switch active profile
kctl-op config use prod

# Show current profile (token masked)
kctl-op config show
```

## Global Options

| Option | Short | Description |
|--------|-------|-------------|
| `--json` | | Output as JSON |
| `--quiet` | `-q` | Suppress non-essential output |
| `--format` | `-f` | Output format: pretty, json, csv, yaml |
| `--no-header` | | Omit header row in CSV output |
| `--profile` | `-p` | Config profile to use |
| `--vault` | | Override vault name |
| `--token` | | Override service account token |
| `--version` | `-V` | Show version and exit |

## Development

```bash
uv run pytest tests/ -v
uv run ruff check src/
uv run mypy src/
```
