# kctl-glitchtip

Command reference for `kctl-glitchtip` (10 groups, ~49 commands).

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

### `kctl-glitchtip alerts`

Manage alerts and notifications.

| Command | Description |
|---------|-------------|
| `alerts list <org_slug> <project_slug>` | List project alerts. |
| `alerts test-alert <org_slug> <project_slug> <alert_id>` | Test a project alert. |
| `alerts test-email [--to]` | Send test email via Django (requires Docker access). |
| `alerts test-webhook <url>` | Send test alert to a webhook URL. |

### `kctl-glitchtip config`

Manage CLI configuration and profiles.

| Command | Description |
|---------|-------------|
| `config add <name> [--url] [--token] [--set_default]` | Add or update a profile's GlitchTip connection. |
| `config current` | Show the active profile and connection status. |
| `config init [--url] [--token] [--name]` | Initialize CLI configuration (interactive if no flags given). |
| `config migrate` | Migrate config from flat format to service-scoped format. |
| `config profiles` | List all profiles with GlitchTip connection status. |
| `config remove <name> [--force] [--service_only]` | Remove a profile or just its GlitchTip config. |
| `config set <key> <value> [--profile_arg]` | Set a configuration value for the current service. |
| `config show` | Show full configuration (tokens masked). |
| `config test` | Test API connection with current configuration. |
| `config use <name>` | Switch the default profile. |
| `config validate` | Validate configuration file syntax and required fields. |

### `kctl-glitchtip events`

Manage GlitchTip events.

| Command | Description |
|---------|-------------|
| `events cleanup [--days]` | Clean old events via Django management command (requires Docker access). |
| `events list <org_slug> <project_slug> [--limit]` | List recent events for a project. |

### `kctl-glitchtip health`

Health checks and monitoring.

| Command | Description |
|---------|-------------|
| `health celery-status` | Celery worker status. |
| `health check` | API health + container status. |
| `health dashboard` | Overview: projects, issues, events, teams. |
| `health redis-info` | Redis stats. |

### `kctl-glitchtip issues`

Manage GlitchTip issues and errors.

| Command | Description |
|---------|-------------|
| `issues bulk-resolve <org_slug> <project> [--force]` | Resolve all issues in a project. |
| `issues delete <issue_id> [--force]` | Delete an issue. |
| `issues get <issue_id>` | Get issue details with events. |
| `issues ignore <issue_id>` | Mark an issue as ignored. |
| `issues list <org_slug> [--project] [--status] [--sort] [--limit]` | List issues. |
| `issues resolve <issue_id>` | Mark an issue as resolved. |

### `kctl-glitchtip orgs`

Manage GlitchTip organizations.

| Command | Description |
|---------|-------------|
| `orgs get <org_slug>` | Get organization details. |
| `orgs list` | List organizations. |

### `kctl-glitchtip projects`

Manage GlitchTip projects.

| Command | Description |
|---------|-------------|
| `projects create <name> <org_slug> <team_slug> [--platform]` | Create a new project (returns DSN). |
| `projects delete <org_slug> <project_slug> [--force]` | Delete a project. |
| `projects dsn <org_slug> <project_slug>` | Show DSN keys for a project. |
| `projects dsn-create <org_slug> <project_slug> [--label]` | Create a new DSN key for a project. |
| `projects get <org_slug> <project_slug>` | Get project details. |
| `projects list` | List all projects with DSNs. |
| `projects stats <org_slug> <project_slug>` | Show event statistics for a project. |
| `projects update <org_slug> <project_slug> [--name] [--platform]` | Update project name or platform. |

### `kctl-glitchtip teams`

Manage GlitchTip teams.

| Command | Description |
|---------|-------------|
| `teams add-member <org_slug> <team_slug> <email>` | Add a member to a team. |
| `teams create <name> <org_slug>` | Create a new team. |
| `teams delete <org_slug> <team_slug> [--force]` | Delete a team. |
| `teams get <org_slug> <team_slug>` | Get team details with members. |
| `teams list <org_slug>` | List teams. |
| `teams remove-member <org_slug> <team_slug> <email>` | Remove a member from a team. |

### `kctl-glitchtip uptime`

Manage uptime monitors.

| Command | Description |
|---------|-------------|
| `uptime checks <monitor_id> [--org]` | Show recent checks for an uptime monitor. |
| `uptime create <name> <url> [--org] [--interval] [--monitor_type] [--expected_status]` | Create an uptime monitor. |
| `uptime delete <monitor_id> [--org] [--force]` | Delete an uptime monitor. |
| `uptime list [--org]` | List uptime monitors. |

### `kctl-glitchtip users`

Manage GlitchTip users.

| Command | Description |
|---------|-------------|
| `users create <email> [--superuser]` | Create a user. |
| `users list` | List users. |
