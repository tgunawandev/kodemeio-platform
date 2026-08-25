# kctl-linear

Command reference for `kctl-linear` (9 groups, ~30 commands).

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

### `kctl-linear config`

Profile and configuration management.

| Command | Description |
|---------|-------------|
| `config add <name>` | Add a new config profile. |
| `config current` | Show active profile and resolved context. |
| `config init` | Interactive config setup. |
| `config profiles` | List all config profiles. |
| `config remove <name>` | Remove a config profile. |
| `config set <key> <value>` | Set a single config value. |
| `config show` | Show current configuration. |
| `config test` | Test API connection with current configuration. |
| `config use <name>` | Switch active config profile. |
| `config validate` | Validate current config completeness. |

### `kctl-linear cycles`

Cycle (sprint) management.

| Command | Description |
|---------|-------------|
| `cycles current [--team]` | Show current active cycle with progress and issues. |
| `cycles list [--team] [--limit]` | List past and upcoming cycles. |
| `cycles show <cycle_id>` | Show cycle details: scope, completed, remaining issues. |
| `cycles stats [--team]` | Show velocity trends across recent cycles. |

### `kctl-linear dashboard`

Quick overview dashboard.

### `kctl-linear health`

API health check.

### `kctl-linear issues`

Issue management.

| Command | Description |
|---------|-------------|
| `issues comment <issue_id> <body>` | Add a comment to an issue. |
| `issues create <title> [--team] [--description] [--priority] [--assignee]` | Create a new issue. |
| `issues list [--team] [--state] [--assignee] [--limit]` | List issues with optional filters. |
| `issues search <query> [--limit]` | Full-text search for issues. |
| `issues show <issue_id>` | Show issue details, comments, and history. |
| `issues update <issue_id> [--state] [--assignee] [--priority] [--title] [--description]` | Update an existing issue. |

### `kctl-linear labels`

Label management.

| Command | Description |
|---------|-------------|
| `labels create <name> [--color] [--team]` | Create a new label. |
| `labels list [--team]` | List all labels, optionally filtered by team. |

### `kctl-linear projects`

Project tracking.

| Command | Description |
|---------|-------------|
| `projects list` | List active projects with progress. |
| `projects show <project_id>` | Show project details, milestones, and member issues. |

### `kctl-linear teams`

Team information.

| Command | Description |
|---------|-------------|
| `teams list` | List all teams with member counts. |
| `teams show <team_id>` | Show team members, workflow states, and labels. |

### `kctl-linear users`

User information.

| Command | Description |
|---------|-------------|
| `users list` | List all workspace members. |
| `users me` | Show current authenticated user. |
