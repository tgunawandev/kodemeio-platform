# kctl-sentry

Command reference for `kctl-sentry` (10 groups, ~28 commands).

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

### `kctl-sentry alerts`

Manage alert rules.

| Command | Description |
|---------|-------------|
| `alerts create <project> <name> [--metric] [--threshold] [--time_window]` | Create a new metric alert rule. |
| `alerts list [--project]` | List alert rules. |
| `alerts show <rule_id> <project>` | Show alert rule details and trigger history. |

### `kctl-sentry config`

Manage CLI configuration and profiles.

| Command | Description |
|---------|-------------|
| `config init [--auth_token] [--organization] [--url] [--default_project] [--name]` | Initialize CLI configuration. |
| `config show` | Show configuration. |
| `config test` | Test API connection. |
| `config use <name>` | Switch default profile. |

### `kctl-sentry dashboard`

Quick overview of Sentry state.

| Command | Description |
|---------|-------------|
| `dashboard overview` | Show unresolved issues, recent releases, and alert status across projects. |

### `kctl-sentry environments`

Manage project environments.

| Command | Description |
|---------|-------------|
| `environments list [--project]` | List environments for a project (e.g. |

### `kctl-sentry health`

API connectivity checks.

| Command | Description |
|---------|-------------|
| `health check` | Check Sentry API connectivity, org info, and rate limits. |

### `kctl-sentry issues`

Error triage — list, inspect, resolve, ignore, assign issues.

| Command | Description |
|---------|-------------|
| `issues assign <issue_id> <to>` | Assign an issue to a team member. |
| `issues bulk-resolve <project> [--before] [--force]` | Bulk-resolve old unresolved issues in a project. |
| `issues ignore <issue_id> [--duration] [--count]` | Ignore an issue, optionally for a duration or until N more events. |
| `issues list [--project] [--status] [--limit] [--sort]` | List recent issues for a project. |
| `issues resolve <issue_id> [--release]` | Resolve an issue. |
| `issues show <issue_id>` | Show issue details, stack trace, and affected users. |

### `kctl-sentry projects`

Manage Sentry projects.

| Command | Description |
|---------|-------------|
| `projects create <name> <team> [--platform]` | Create a new project. |
| `projects dsn <slug>` | Get DSN key for SDK configuration. |
| `projects list` | List all projects with issue counts. |
| `projects show <slug>` | Show project details. |

### `kctl-sentry releases`

Manage releases and deploy tracking.

| Command | Description |
|---------|-------------|
| `releases associate <version> <commits>` | Associate commits with a release for tracking regressions. |
| `releases create <version> <project>` | Create a new release for a project. |
| `releases list [--project] [--limit]` | List recent releases. |
| `releases show <version>` | Show release details and associated issues. |

### `kctl-sentry stats`

Event and error statistics.

| Command | Description |
|---------|-------------|
| `stats errors [--project] [--period]` | Show error rate trends for a project. |
| `stats events [--project] [--period]` | Show event volume for a project or organization. |

### `kctl-sentry teams`

Manage teams.

| Command | Description |
|---------|-------------|
| `teams list` | List all teams in the organization. |
| `teams show <slug>` | Show team details, members, and assigned projects. |
