# kctl-claude

Kodemeio Claude Code CLI — manage local and remote Claude Code environments.

## Installation

```bash
uv tool install .
```

## Quick Start

```bash
kctl-claude config init
kctl-claude status
kctl-claude doctor
kctl-claude env list
```

## Command Groups

| Group | Description |
|-------|-------------|
| `config` | Manage CLI configuration and profiles |
| `api` | SDK REST API operations |
| `backup` | Backup and restore Claude Code runtime |
| `doctor` | Diagnostics and health checks |
| `env` | Environment file management |
| `setup` | Setup Claude Code on local, VPS, or Docker |
| `status` | Status dashboard and health checks |
| `sync` | Sync config between local `~/.claude` and repo |
| `verify` | Verify Claude Code config completeness |

Top-level commands: `completions`, `update`

## Configuration

Config lives in `~/.config/kodemeio/config.yaml` under the `claude` service key.

```bash
# Initialize a profile
kctl-claude config init

# Add a named profile
kctl-claude config add work --url https://api.anthropic.com --api-key $ANTHROPIC_API_KEY

# Switch active profile
kctl-claude config use work

# Show current profile (secrets masked)
kctl-claude config show
```

## Global Options

| Option | Short | Description |
|--------|-------|-------------|
| `--json` | | Output as JSON |
| `--quiet` | `-q` | Suppress info messages |
| `--verbose` | `-v` | Show debug output |
| `--version` | `-V` | Show version and exit |

## Shell Completions

```bash
# Generate completions (prints to stdout)
kctl-claude completions zsh
kctl-claude completions bash
kctl-claude completions fish

# Install completions automatically
kctl-claude completions zsh --install
kctl-claude completions bash --install
```

## Self-Update

```bash
kctl-claude update
```

## Development

```bash
uv run pytest tests/ -v
uv run ruff check src/
uv run mypy src/
```
