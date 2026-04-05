# kctl-grafana

Grafana monitoring platform CLI — manage dashboards, datasources, alerts, users, and backups.

## Installation

```bash
uv tool install kctl-grafana
```

Requires `kctl-lib>=0.4.0` (installed automatically).

## Quick Start

```bash
# Configure a profile
kctl-grafana config init

# Check Grafana connectivity
kctl-grafana health check

# View platform status
kctl-grafana status overview

# List all dashboards
kctl-grafana dashboard list

# Export a dashboard to file
kctl-grafana dashboard export <uid> --output my-dashboard.json

# Add a deploy annotation
kctl-grafana annotation add "Deployed v1.2.3" --tags deploy,production

# Backup all dashboards and datasources
kctl-grafana backup create --output ./grafana-backup
```

## Command Groups

| Group | Description | Key Commands |
|-------|-------------|--------------|
| `config` | Profile management | `init`, `add`, `use`, `show`, `validate`, `remove`, `set`, `profiles`, `current` |
| `health` | API health checks | `check`, `detailed` |
| `status` | Quick overview | `overview` |
| `dashboard` | Dashboard management | `list`, `show`, `export`, `import`, `search`, `star` |
| `datasource` | Datasource management | `list`, `show`, `test` |
| `alert` | Alert rule management | `list`, `show`, `silence`, `contacts` |
| `folder` | Folder organization | `list`, `create`, `delete` |
| `annotation` | Deploy markers & events | `add`, `list` |
| `user` | Organization user management | `list`, `add` |
| `backup` | Backup and restore | `create`, `restore` |
| `selftest` | Self-test diagnostics | `run` |

## Command Reference

### dashboard

```bash
kctl-grafana dashboard list
kctl-grafana dashboard show <uid>
kctl-grafana dashboard export <uid> --output dashboard.json
kctl-grafana dashboard import dashboard.json --folder <folder-uid>
kctl-grafana dashboard search "kubernetes"
kctl-grafana dashboard star <uid>
kctl-grafana dashboard star <uid> --unstar
```

### datasource

```bash
kctl-grafana datasource list
kctl-grafana datasource show <name>
kctl-grafana datasource test              # Test all datasources
kctl-grafana datasource test <name>       # Test a specific datasource
```

### alert

```bash
kctl-grafana alert list
kctl-grafana alert show <uid>
kctl-grafana alert silence <uid> --duration 1h --comment "Maintenance window"
kctl-grafana alert contacts
```

### annotation

```bash
kctl-grafana annotation add "Deploy v2.0" --tags deploy,prod
kctl-grafana annotation add "Incident" --dashboard <uid>
kctl-grafana annotation list --from 24h --tags deploy
```

### backup

```bash
kctl-grafana backup create --output ./backup-2026-04-05
kctl-grafana backup restore ./backup-2026-04-05
kctl-grafana backup restore ./backup-2026-04-05 --skip-datasources
```

### folder

```bash
kctl-grafana folder list
kctl-grafana folder create "Production Dashboards"
kctl-grafana folder delete <uid> --force
```

### user

```bash
kctl-grafana user list
kctl-grafana user add user@example.com --role Editor
```

## Global Options

| Option | Short | Description |
|--------|-------|-------------|
| `--profile` | `-p` | Config profile name |
| `--format` | `-f` | Output format: `pretty`, `json`, `csv`, `yaml` |
| `--json` | | Shortcut for `--format json` |
| `--quiet` | `-q` | Suppress info messages |
| `--no-header` | | Omit headers in CSV output |
| `--debug` | | Enable debug logging |
| `--url` | | Grafana API URL override |
| `--api-key` | | Grafana API key override |
| `--version` | `-V` | Show version and exit |

## Configuration

Config lives in `~/.config/kodemeio/config.yaml` under the `grafana` service key.

```bash
# Interactive setup
kctl-grafana config init

# Add a named profile
kctl-grafana config add --profile production \
  --url https://grafana.kodeme.io \
  --api-key <service-account-token>

# Switch active profile
kctl-grafana config use production

# Show current config (secrets masked)
kctl-grafana config show
```

Example `~/.config/kodemeio/config.yaml` entry:

```yaml
grafana:
  default_profile: production
  profiles:
    production:
      url: https://grafana.kodeme.io
      api_key: ${GRAFANA_API_KEY}
```

## Development

```bash
cd packages/kctl-grafana
uv sync --all-extras
uv run pytest tests/ -v
uv run mypy src/
uv run ruff check src/
uv build
```
