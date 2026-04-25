# kctl-supa

kctl-supa — Kodemeio Supabase CLI for managing self-hosted Supabase instances.

## Installation

```bash
uv pip install -e packages/kctl-supa
```

## Quick Start

```bash
# Add a profile
kctl-supa config add terakidz \
  --url https://supa.terakidz.com \
  --service-role-key <key> \
  --ssh-host 49.13.14.79 \
  --container-prefix terakidz-supabase-prod

# Set as default
kctl-supa config use terakidz

# Check health
kctl-supa health check

# Dashboard overview
kctl-supa dashboard show
```

## Command Reference

| Group | Panel | Description |
|-------|-------|-------------|
| config | Admin & Config | Profile management |
| security | Admin & Config | RLS policies, JWT inspection, API keys |
| doctor | Admin & Config | Diagnostic checks |
| health | Services | Service health checks |
| status | Services | Container status |
| dashboard | Services | Overview dashboard |
| monitor | Services | Performance monitoring |
| db | Database | Database operations |
| backup | Database | Backup management |
| maintenance | Database | Vacuum, reindex, analyze |
| migrate | Database | SQL migrations |
| auth | Auth & Users | User management |
| storage | Storage & Files | Bucket operations |
| realtime | Realtime & Functions | Realtime status |
| functions | Realtime & Functions | Edge functions |
| logs | Operations | Log tailing/search |
| deploy | Operations | Stack deployment |

## Config Format

```yaml
# ~/.config/kodemeio/config.yaml
profiles:
  terakidz:
    supabase:
      url: https://supa.terakidz.com
      service_role_key: <key>
      anon_key: <key>
      db_password: <pass>
      ssh_host: 49.13.14.79
      ssh_user: root
      ssh_key: ~/.ssh/id_ed25519
      container_prefix: terakidz-supabase-prod
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `KCTL_SUPA_URL` | Supabase instance URL |
| `KCTL_SUPA_SERVICE_ROLE_KEY` | Service role JWT key |
| `KCTL_SUPA_ANON_KEY` | Anonymous JWT key |
| `KCTL_SUPA_SSH_HOST` | SSH host for container access |
| `KCTL_SUPA_CONTAINER_PREFIX` | Docker container name prefix |
| `KCTL_SUPA_PROFILE` | Active config profile name |
