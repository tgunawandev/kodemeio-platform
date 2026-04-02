# kctl-grafana

Command reference for `kctl-grafana` (11 groups, ~32 commands).

> Auto-generated on 2026-04-02. Do not edit manually.
> Regenerate with: `uv run python scripts/generate-cli-docs.py`

## Global Options

| Flag | Description |
|------|-------------|
| `--json` | JSON output |
| `--quiet`, `-q` | Suppress info messages |
| `--format`, `-f` | Output format: pretty/json/csv/yaml |
| `--no-header` | Omit headers in CSV output |
| `--profile`, `-p` | Config profile name |
| `--version`, `-V` | Show version |

## Commands

### `kctl-grafana alert`

Alert rule management.

| Command | Description |
|---------|-------------|
| `alert contacts` | List notification contact points. |
| `alert list` | List alert rules with current state. |
| `alert show <uid>` | Show alert rule details. |
| `alert silence <uid> [--duration] [--comment]` | Silence an alert rule for a given duration. |

### `kctl-grafana annotation`

Annotation management (deploy markers, events).

| Command | Description |
|---------|-------------|
| `annotation add <text> [--tags] [--dashboard_uid]` | Add an annotation (useful for deploy markers). |
| `annotation list [--from_time] [--to_time] [--tags] [--limit]` | List recent annotations. |

### `kctl-grafana backup`

Backup and restore dashboards and datasources.

| Command | Description |
|---------|-------------|
| `backup create [--output_dir]` | Export all dashboards and datasources to a backup directory. |
| `backup restore <backup_dir> [--skip_datasources] [--skip_dashboards]` | Restore dashboards and datasources from a backup directory. |

### `kctl-grafana config`

Manage CLI configuration and profiles.

| Command | Description |
|---------|-------------|
| `config export` | Export current configuration as YAML. |
| `config init [--url] [--api_key] [--org_id] [--name]` | Initialize CLI configuration. |
| `config remove <name> [--force]` | Remove a profile. |
| `config show` | Show configuration (keys masked). |
| `config test` | Test API connection. |
| `config use <name>` | Switch default profile. |

### `kctl-grafana dashboard`

Dashboard management.

| Command | Description |
|---------|-------------|
| `dashboard export <uid> [--output_file]` | Export dashboard JSON to file. |
| `dashboard import <file_path> [--folder_uid] [--overwrite]` | Import dashboard from JSON file. |
| `dashboard list` | List all dashboards. |
| `dashboard search <query>` | Search dashboards by name or tag. |
| `dashboard show <uid>` | Show dashboard metadata and panel summary. |
| `dashboard star <uid> [--unstar]` | Star or unstar a dashboard. |

### `kctl-grafana datasource`

Datasource management.

| Command | Description |
|---------|-------------|
| `datasource list` | List all datasources with type and status. |
| `datasource show <name>` | Show datasource configuration details. |
| `datasource test [--name]` | Test datasource connectivity. |

### `kctl-grafana folder`

Folder organization.

| Command | Description |
|---------|-------------|
| `folder create <title> [--uid]` | Create a new folder. |
| `folder delete <uid> [--force]` | Delete a folder and all its dashboards. |
| `folder list` | List all folders. |

### `kctl-grafana health`

Health checks for Grafana API.

| Command | Description |
|---------|-------------|
| `health check` | Check Grafana API connectivity, version, and org info. |
| `health detailed` | Detailed health check including all datasources. |

### `kctl-grafana selftest`

Self-test diagnostics.

| Command | Description |
|---------|-------------|
| `selftest run` | Run diagnostic checks for kctl-grafana. |

### `kctl-grafana status`

Quick status overview.

| Command | Description |
|---------|-------------|
| `status overview` | Show Grafana status overview: dashboard count, datasource health, active alerts, version. |

### `kctl-grafana user`

Organization user management.

| Command | Description |
|---------|-------------|
| `user add <email> [--role]` | Add a user to the organization. |
| `user list` | List organization users. |
