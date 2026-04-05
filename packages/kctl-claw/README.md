# kctl-claw

Kodemeio OpenClaw CLI — manage AI agent gateway instances from the terminal.

## Installation

**Development (editable):**
```bash
uv pip install -e ".[dev]"
```

**Production (from source):**
```bash
pip install /path/to/kctl-claw/
```

**Container (Dockerfile):**
The CLI is installed automatically inside the Docker image — no additional steps needed.

## Quick Start

```bash
# Status overview
kctl-claw status overview

# Health check
kctl-claw health check

# Tail gateway logs
kctl-claw logs tail --lines 50

# List agents
kctl-claw agents list

# List cron jobs
kctl-claw cron list

# Create a backup
kctl-claw backup create
```

## Command Groups

### Core Operations

| Group | Description |
|---|---|
| `agents` | Manage OpenClaw agents |
| `ai` | AI usage and cost analytics |
| `backup` | Backup and restore OpenClaw volumes |
| `config` | Manage OpenClaw configuration files |
| `cron` | Manage cron jobs |
| `deploy` | Deploy and manage the OpenClaw gateway container |
| `env` | Manage environment variables (.env.prod vs .env.example) |
| `health` | Deep health checks for gateway, configs, and Docker |
| `logs` | View OpenClaw gateway logs |
| `mcp` | Manage MCP server registry and tool profiles |
| `memory` | Manage agent memory and knowledge graph |
| `security` | Security audit and credential management |
| `skills` | Manage OpenClaw skills |
| `status` | Quick status dashboard |
| `telegram` | Manage Telegram bot configuration |
| `trading` | Trading bot operations (JournaltxDevBot) |

### Diagnostics & Debugging (SP6)

| Group | Description |
|---|---|
| `agents-test` | Run agent integration and regression tests |
| `config-drift` | Detect and reconcile config drift between environments |
| `cron-debug` | Debug and inspect cron job execution |
| `docker` | Docker container and image management |
| `doctor` | Diagnose environment, config, and connectivity issues |
| `lint` | Lint OpenClaw configs, manifests, and skill definitions |
| `mcp-test` | Test MCP server connectivity and tool invocations |
| `monitor` | Real-time gateway metrics and uptime monitoring |
| `pipeline` | Manage and inspect agent execution pipelines |
| `prompts` | Manage and preview system prompts |
| `skills-test` | Run skill unit and integration tests |
| `test` | General test runner for OpenClaw components |

Run `kctl-claw <group> --help` for subcommands within each group.

## Global Options

| Flag | Short | Default | Description |
|---|---|---|---|
| `--json` | | false | Output as JSON |
| `--quiet` | `-q` | false | Suppress info messages |
| `--format` | `-f` | `pretty` | Output format: `pretty` / `json` / `csv` / `yaml` |
| `--no-header` | | false | Omit table headers |
| `--profile` | `-p` | | Config profile name |
| `--root` | | | Project root override (overrides auto-detection) |
| `--live` | | false | Push config changes and trigger reload |
| `--version` | `-V` | | Show version and exit |

All options apply globally before the subcommand and can be combined:

```bash
kctl-claw --json --profile staging agents list
kctl-claw --format yaml health check
kctl-claw --quiet --no-header cron list
```

## Aliases

| Alias | Expands to |
|---|---|
| `st` | `status overview` |
| `hl` | `health check` |
| `cl` | `cron list` |
| `al` | `agents list` |
| `ml` | `mcp list` |
| `lt` | `logs tail` |
| `bc` | `backup create` |
| `du` | `deploy up` |

## Configuration

The CLI stores settings in `~/.config/kodemeio/config.yaml`. Use `kctl-claw config init` to create an initial profile, or edit the file directly:

```yaml
default_profile: default

profiles:
  default:
    claw:
      project_root: /path/to/kodemeio-openclaw
      gateway_url: https://openclaw.kodeme.io
      gateway_token: ${OPENCLAW_GATEWAY_TOKEN}
      compose_file: docker-compose.prod.yml
      env_file: .env.prod

  staging:
    claw:
      project_root: /path/to/kodemeio-openclaw-staging
      gateway_url: https://openclaw-staging.kodeme.io
      gateway_token: ${OPENCLAW_STAGING_TOKEN}
```

Switch profiles with `--profile` or the `KCTL_CLAW_PROFILE` environment variable. The project root is also auto-detected by walking up from the current directory looking for `config/openclaw.json`.

### Config Subcommands

```bash
kctl-claw config init        # Create initial profile interactively
kctl-claw config show        # Show current profile (secrets masked)
kctl-claw config validate    # Validate config file syntax and required fields
kctl-claw config profiles    # List all available profiles
kctl-claw config current     # Print active profile name
kctl-claw config add         # Add a new profile
kctl-claw config use         # Switch default profile
kctl-claw config set         # Set a single config key
kctl-claw config remove      # Delete a profile
```

## Shell Completions

Install shell completions for faster command entry:

```bash
# Zsh
kctl-claw --install-completion zsh
# Then add to ~/.zshrc:
source ~/.zsh_completions/_kctl-claw

# Bash
kctl-claw --install-completion bash
# Then add to ~/.bashrc:
source ~/.bash_completions/kctl-claw

# Fish
kctl-claw --install-completion fish
```

After installing, restart your shell or source your rc file. Tab-completion covers command groups, subcommands, and common flag values.

## Environment Variables

| Variable | Description |
|---|---|
| `KCTL_CLAW_PROFILE` | Override active profile (equivalent to `--profile`) |
| `OPENCLAW_GATEWAY_TOKEN` | Gateway API token (referenced in config via `${...}`) |
| `OPENCLAW_STAGING_TOKEN` | Staging gateway token |

## Development

```bash
# Run tests
uv run pytest tests/ -v

# Lint
uv run ruff check src/ tests/

# Format
uv run ruff format src/ tests/

# Type check
uv run mypy src/kctl_claw/

# All checks
uv run ruff check src/ tests/ && uv run ruff format src/ tests/ && uv run mypy src/kctl_claw/ && uv run pytest tests/
```

For full command reference and admin skill integration, see the `openclaw-admin` Claude Code skill in `skills/openclaw-admin/`.
