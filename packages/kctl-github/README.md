# kctl-github

Cross-repo GitHub management CLI for kodemeio-* repositories.

## Installation

```bash
# From workspace root
uv tool install --editable packages/kctl-github

# Verify
kctl-github --version
```

## Quick Start

```bash
# Initialize config with your GitHub token
kctl-github config init

# Check API connectivity and rate limits
kctl-github health

# View dashboard overview of all repos
kctl-github dashboard

# List all kodemeio-* repositories
kctl-github repos list

# Check CI status across all repos
kctl-github ci status
```

## Command Groups

| Group       | Commands                                   | Description                                      |
|-------------|--------------------------------------------|--------------------------------------------------|
| `config`    | init, add, use, show, validate, remove, set, profiles, current | Profile management |
| `health`    | (default)                                  | API connectivity check and rate limit status     |
| `dashboard` | (default)                                  | Quick overview of repos, PRs, and CI status      |
| `repos`     | list, status, show                         | Cross-repo overview for kodemeio-* repositories  |
| `ci`        | status, show, stats, rerun, bulk-status    | CI/CD monitoring across repositories             |
| `prs`       | list, show, stale                          | Cross-repo pull request management               |
| `secrets`   | list, audit, set, rotate                   | Cross-repo Actions secret management             |
| `labels`    | list, sync, diff                           | Cross-repo label standardization                 |
| `stats`     | overview, activity, languages, contributors | Repository statistics and insights              |
| `billing`   | actions, storage, packages, overview       | GitHub Actions billing and usage                 |

## Global Options

All commands support these flags:

| Option              | Description                              |
|---------------------|------------------------------------------|
| `--json`            | Output as JSON                           |
| `--quiet`, `-q`     | Suppress info messages                   |
| `--format`, `-f`    | Output format: pretty, json, csv, yaml   |
| `--no-header`       | Omit header row in CSV output            |
| `--profile`, `-p`   | Use a named config profile               |
| `--version`, `-V`   | Show version and exit                    |

## Configuration

Config lives in `~/.config/kodemeio/config.yaml` under the `github` service key.

```bash
# Interactive setup
kctl-github config init

# Add a named profile
kctl-github config add --profile work

# Switch active profile
kctl-github config use work

# Show current config (tokens masked)
kctl-github config show
```

Required config fields:

| Field       | Description                        |
|-------------|------------------------------------|
| `token`     | GitHub personal access token       |
| `org`       | GitHub organization (e.g. kodemeio)|

## Development

```bash
# Install with dev extras
cd packages/kctl-github
uv sync --all-extras

# Run tests
uv run pytest tests/ -v

# Lint
uv run ruff check src/

# Type check
uv run mypy src/
```
