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

Run `kctl-claw <group> --help` for subcommands within each group.

## Global Options

| Flag | Short | Description |
|---|---|---|
| `--json` | | Output as JSON |
| `--quiet` | `-q` | Suppress info messages |
| `--format` | `-f` | Output format: `pretty` / `json` / `csv` / `yaml` |
| `--no-header` | | Omit table headers |
| `--profile` | `-p` | Config profile name |
| `--root` | | Project root override |
| `--live` | | Push config changes and trigger reload |
| `--version` | `-V` | Show version |

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
