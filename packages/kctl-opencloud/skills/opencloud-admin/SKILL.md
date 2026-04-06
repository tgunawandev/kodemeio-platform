---
name: opencloud-admin
description: OpenCloud file platform administration via kctl-opencloud CLI (8 groups, ~35 commands). MUST use for ANY kctl-opencloud operation.
triggers:
  - kctl-opencloud
  - opencloud
  - cloud.kodeme.io
  - file storage
  - spaces
  - drives
---

# OpenCloud Administration

Use the `kctl-opencloud` CLI for all OpenCloud management tasks.

## Command Groups

| Group | Description |
|-------|-------------|
| `health` | Health checks with 5-probe scoring |
| `dashboard` | System overview and statistics |
| `config` | Profile and connection management |
| `users` | User CRUD and search |
| `groups` | Group management and membership |
| `spaces` | Drive/space lifecycle and quota |
| `shares` | Sharing links and permissions |
| `doctor` | Diagnostic checks |

## Common Patterns

```bash
# Health
kctl-opencloud health check
kctl-opencloud health check --watch

# Users
kctl-opencloud users list
kctl-opencloud users list --search "john"
kctl-opencloud users get <id>
kctl-opencloud users create user@kodeme.io --name "User Name"
kctl-opencloud users delete <id> --force

# Groups
kctl-opencloud groups list
kctl-opencloud groups create "Team Name"
kctl-opencloud groups add-member <group-id> <user-id>

# Spaces
kctl-opencloud spaces list
kctl-opencloud spaces list --type project
kctl-opencloud spaces create "Project Name" --description "..."
kctl-opencloud spaces quota <id>

# Dashboard
kctl-opencloud dashboard show
kctl-opencloud dashboard show --json

# Configuration
kctl-opencloud config init
kctl-opencloud config show
kctl-opencloud config test
```

## JSON Output

All commands support `--json` for machine-readable output:
```bash
kctl-opencloud --json users list
kctl-opencloud --json spaces list
```
