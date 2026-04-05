# kctl-glitchtip

Kodemeio CLI for managing GlitchTip error tracking — projects, issues, teams, uptime monitors, alerts, and platform health.

## Installation

```bash
# Install from PyPI
uv tool install kctl-glitchtip

# Or add to workspace (monorepo)
uv add kctl-glitchtip
```

## Quick Start

```bash
# Initialize config
kctl-glitchtip config init

# List all projects
kctl-glitchtip projects list

# List unresolved issues in an org
kctl-glitchtip issues list --org kodemeio --status unresolved

# Show platform dashboard
kctl-glitchtip health dashboard

# List uptime monitors
kctl-glitchtip uptime list --org kodemeio
```

## Command Groups

| Group | Commands | Description |
|-------|----------|-------------|
| `projects` | `list`, `get`, `create`, `update`, `delete`, `dsn`, `dsn-create`, `stats` | Manage projects and DSN keys |
| `issues` | `list`, `get`, `resolve`, `ignore`, `delete`, `bulk-resolve` | Manage error issues |
| `events` | `list`, `cleanup` | View and clean up error events |
| `teams` | `list`, `get`, `create`, `delete`, `add-member`, `remove-member` | Manage teams and membership |
| `orgs` | `list`, `get` | View organizations and members |
| `users` | `list`, `create` | Manage users and invitations |
| `alerts` | `list`, `test-alert`, `test-webhook`, `test-email` | Manage alerts and notifications |
| `uptime` | `list`, `create`, `delete`, `checks` | Manage uptime monitors |
| `health` | `check`, `dashboard`, `celery-status`, `redis-info` | Platform health and diagnostics |
| `config` | `init`, `add`, `use`, `show`, `validate`, `remove`, `set`, `profiles`, `current` | Manage CLI profiles |

## Global Options

| Option | Description |
|--------|-------------|
| `--json` | Output as JSON |
| `--format / -f` | Output format: `pretty`, `json`, `csv`, `yaml` |
| `--quiet / -q` | Suppress informational messages |
| `--no-header` | Omit header row in CSV output |
| `--profile / -p` | Select config profile by name |
| `--url` | Override API URL for this invocation |
| `--token` | Override API token for this invocation |
| `--version / -V` | Show version and exit |

## Configuration

Config lives in `~/.config/kodemeio/config.yaml` under the `glitchtip` key.

```bash
# Initialize a profile interactively
kctl-glitchtip config init

# Add a named profile
kctl-glitchtip config add --profile prod \
  --url https://glitchtip.kodeme.io \
  --token YOUR_API_TOKEN

# Switch active profile
kctl-glitchtip config use prod

# Show current profile (token masked)
kctl-glitchtip config show
```

Example `~/.config/kodemeio/config.yaml`:

```yaml
glitchtip:
  default_profile: prod
  profiles:
    prod:
      url: https://glitchtip.kodeme.io
      token: ${GLITCHTIP_TOKEN}
```

Environment variables expand automatically — set `GLITCHTIP_TOKEN` in your shell or `.env`.

## Development

```bash
# Install dev dependencies
cd packages/kctl-glitchtip
uv sync --all-extras

# Run tests
uv run pytest tests/ -v

# Lint
uv run ruff check src/

# Type check
uv run mypy src/

# Run CLI locally
uv run kctl-glitchtip --help
```
