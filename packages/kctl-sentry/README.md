# kctl-sentry

Sentry error tracking CLI — error triage, release tracking, and project management for the Kodemeio platform.

## Installation

```bash
# From workspace (development)
uv tool install --editable packages/kctl-sentry

# From PyPI
uv tool install kctl-sentry
```

## Quick Start

```bash
# Initialize configuration
kctl-sentry config init

# Check connectivity
kctl-sentry health check

# List all projects
kctl-sentry projects list

# Triage open issues
kctl-sentry issues list --project my-project

# View error stats
kctl-sentry stats errors --project my-project
```

## Command Groups

| Group | Commands | Description |
|-------|----------|-------------|
| `config` | init, add, use, show, set, remove, profiles, current, test, migrate | Manage profiles and credentials |
| `health` | check | Verify Sentry API connectivity |
| `dashboard` | overview | High-level summary across all projects |
| `issues` | list, show, resolve, ignore, bulk-resolve, assign | Error issue triage and management |
| `projects` | list, show, dsn, create | Project listing, details, and DSN retrieval |
| `releases` | list, show, create, associate | Release tracking and commit association |
| `alerts` | list, show, create | Alert rule management |
| `stats` | events, errors | Event and error volume statistics |
| `teams` | list, show | Team membership and details |
| `environments` | list | Environment listing per project |

## Global Options

All commands accept these options:

| Option | Short | Description |
|--------|-------|-------------|
| `--json` | | Output as JSON |
| `--format` | `-f` | Output format: `pretty`, `json`, `csv`, `yaml` |
| `--quiet` | `-q` | Suppress info messages |
| `--no-header` | | Omit header row in table/CSV output |
| `--profile` | `-p` | Config profile name |
| `--auth-token` | | Auth token override (bypasses config) |
| `--version` | `-V` | Show version and exit |

## Configuration

Config is stored in `~/.config/kodemeio/config.yaml` under the `sentry` key.

```bash
# Create a new profile
kctl-sentry config init

# Add a named profile
kctl-sentry config add --profile prod

# Switch active profile
kctl-sentry config use prod

# Show current config (secrets masked)
kctl-sentry config show

# Test connectivity
kctl-sentry config test
```

### Config Keys

| Key | Description |
|-----|-------------|
| `url` | Sentry instance URL (e.g. `https://sentry.io` or self-hosted) |
| `auth_token` | Sentry auth token with `project:read`, `event:read` scopes |
| `org` | Default organization slug |

## Common Workflows

```bash
# Bulk resolve all resolved issues in a project
kctl-sentry issues bulk-resolve --project my-project --status resolved

# Create a release and associate commits
kctl-sentry releases create --project my-project --version 1.2.3
kctl-sentry releases associate --project my-project --version 1.2.3

# Get DSN for SDK integration
kctl-sentry projects dsn my-project

# View event volume over the last 24h
kctl-sentry stats events --project my-project --period 24h
```

## Development

```bash
cd packages/kctl-sentry
uv sync --all-extras
uv run pytest tests/ -v
uv run mypy src/
uv run ruff check src/
```
