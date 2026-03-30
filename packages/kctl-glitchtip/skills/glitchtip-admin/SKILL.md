---
name: glitchtip-admin
description: >
  GlitchTip error tracking administration via kctl-glitchtip CLI. MUST use for ANY error tracking, DSN key, issue management, or GlitchTip operation. Triggers on: "kctl-glitchtip", "glitchtip", "error tracking", "DSN key", "sentry", "issue tracking", "uptime monitor glitchtip", "error alert", or ANY error tracking platform task.
---

# GlitchTip Admin Skill

You are an expert at managing GlitchTip error tracking instances via the `kctl-glitchtip` CLI.

## CLI Overview

`kctl-glitchtip` is a Typer-based Python CLI that talks to GlitchTip's Sentry-compatible REST API (`/api/0/`).
It uses shared multi-service profiles at `~/.config/kodemeio/config.yaml` under the `glitchtip` service key.

### Installation

```bash
cd cli && uv tool install .
```

### Configuration

```bash
# Interactive setup
kctl-glitchtip config init

# Non-interactive
kctl-glitchtip config add kodemeio \
  --url https://glitchtip.kodeme.io \
  --token <api-token-from-glitchtip-ui>

# Switch profiles
kctl-glitchtip config use kodemeio

# Test connection
kctl-glitchtip config test
```

Config lives in `~/.config/kodemeio/config.yaml`:
```yaml
profiles:
  kodemeio:
    glitchtip:
      url: https://glitchtip.kodeme.io
      token: <token>
```

### Global Flags

All commands support:
- `--json` — JSON output (data to stdout, status to stderr)
- `--quiet` / `-q` — Suppress info messages
- `--profile` / `-p` — Override active profile
- `--url` — Override API URL
- `--token` — Override API token

## Command Reference

### Projects

```bash
# List all projects
kctl-glitchtip projects list

# Get project details
kctl-glitchtip projects get <org-slug> <project-slug>

# Create project (returns DSN)
kctl-glitchtip projects create <name> --org <org-slug> --team <team-slug> [--platform python]

# Update project name or platform
kctl-glitchtip projects update <org-slug> <project-slug> [--name "New Name"] [--platform javascript]

# Delete project
kctl-glitchtip projects delete <org-slug> <project-slug> [--force]

# Show DSN keys
kctl-glitchtip projects dsn <org-slug> <project-slug>

# Create new DSN key
kctl-glitchtip projects dsn-create <org-slug> <project-slug> [--label "my-key"]

# Project statistics
kctl-glitchtip projects stats <org-slug> <project-slug>
```

### Issues

```bash
# List issues
kctl-glitchtip issues list --org <org-slug> [--project <slug>] [--status unresolved]

# Get issue details
kctl-glitchtip issues get <issue-id>

# Resolve issue
kctl-glitchtip issues resolve <issue-id>

# Ignore issue
kctl-glitchtip issues ignore <issue-id>

# Delete issue
kctl-glitchtip issues delete <issue-id> [--force]

# Bulk resolve all issues in a project
kctl-glitchtip issues bulk-resolve --org <org-slug> --project <project-slug>
```

### Teams

```bash
# List teams
kctl-glitchtip teams list --org <org-slug>

# Get team details with members
kctl-glitchtip teams get --org <org-slug> <team-slug>

# Create team
kctl-glitchtip teams create <name> --org <org-slug>

# Delete team
kctl-glitchtip teams delete --org <org-slug> <team-slug> [--force]

# Add/remove members
kctl-glitchtip teams add-member --org <org-slug> <team-slug> <email>
kctl-glitchtip teams remove-member --org <org-slug> <team-slug> <email>
```

### Organizations

```bash
# List organizations
kctl-glitchtip orgs list

# Get organization details (includes members)
kctl-glitchtip orgs get <org-slug>
```

### Events

```bash
# List recent events
kctl-glitchtip events list <org-slug> <project-slug> [--limit 50]

# Clean old events (requires Docker)
kctl-glitchtip events cleanup [--days 90]
```

### Uptime Monitors

```bash
# List uptime monitors
kctl-glitchtip uptime list [--org <org-slug>]

# Create an uptime monitor
kctl-glitchtip uptime create --name "My Service" --url https://example.com [--org <org-slug>] [--interval 60] [--type Ping] [--expected-status 200]

# Delete an uptime monitor
kctl-glitchtip uptime delete <monitor-id> [--org <org-slug>] [--force]

# Show recent checks for a monitor
kctl-glitchtip uptime checks <monitor-id> [--org <org-slug>]
```

### Users

```bash
# List users
kctl-glitchtip users list

# Create/invite user
kctl-glitchtip users create <email>

# Create superuser (requires Docker)
kctl-glitchtip users create <email> --superuser
```

### Health & Monitoring

```bash
# Full health check (API + containers)
kctl-glitchtip health check

# Dashboard overview
kctl-glitchtip health dashboard

# Celery worker status (requires Docker)
kctl-glitchtip health celery-status

# Redis info (requires Docker)
kctl-glitchtip health redis-info
```

### Alerts & Notifications

```bash
# List project alerts
kctl-glitchtip alerts list --org <org-slug> --project <project-slug>

# Test a specific alert
kctl-glitchtip alerts test-alert --org <org-slug> --project <project-slug> <alert-id>

# Test webhook URL
kctl-glitchtip alerts test-webhook <url>

# Test email (requires Docker)
kctl-glitchtip alerts test-email [--to admin@kodeme.io]
```

### Config Management

```bash
kctl-glitchtip config init          # Interactive setup
kctl-glitchtip config add <name>    # Add profile
kctl-glitchtip config use <name>    # Switch profile
kctl-glitchtip config remove <name> # Remove profile
kctl-glitchtip config show          # Show all config
kctl-glitchtip config set <key> <val> # Set config value
kctl-glitchtip config profiles      # List profiles with status
kctl-glitchtip config current       # Show active profile
kctl-glitchtip config test          # Test connection
kctl-glitchtip config migrate       # Migrate flat -> scoped format
```

## Environment Variables

Priority (highest to lowest):
1. CLI flags (`--url`, `--token`)
2. `KCTL_GLITCHTIP_URL` / `KCTL_GLITCHTIP_TOKEN`
3. `GLITCHTIP_API_URL` / `GLITCHTIP_API_TOKEN`
4. Config profile

Profile selection: `--profile` flag > `KCTL_GLITCHTIP_PROFILE` env > config default.

## API Notes

- GlitchTip uses Sentry-compatible API at `/api/0/`
- Auth: `Authorization: Bearer <token>` (API token from GlitchTip UI Settings > API Tokens)
- Most list endpoints return JSON arrays directly (not paginated objects)
- DSN format: `https://<public_key>@glitchtip.kodeme.io/<project_id>`
- Uptime monitors: `GET/POST /api/0/organizations/{org}/monitors/`, checks at `.../monitors/{id}/checks/`

## Common Workflows

### Set up error tracking for a new app
```bash
kctl-glitchtip projects create my-app --org kodemeio --team backend --platform python
# Copy the DSN from output into your app's Sentry SDK config
```

### Triage errors
```bash
kctl-glitchtip issues list --org kodemeio --status unresolved --sort -count
kctl-glitchtip issues get <id>
kctl-glitchtip issues resolve <id>
```

### Bulk cleanup
```bash
kctl-glitchtip issues bulk-resolve --org kodemeio --project old-app --force
kctl-glitchtip events cleanup --days 30
```

### Monitor service uptime
```bash
kctl-glitchtip uptime create --name "API" --url https://api.kodeme.io/health --type GET --interval 60
kctl-glitchtip uptime list
kctl-glitchtip uptime checks <monitor-id>
```
