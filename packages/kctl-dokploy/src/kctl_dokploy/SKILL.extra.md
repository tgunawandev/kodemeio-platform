## Troubleshooting Workflow

When a deployment fails, use this exact flow:

```bash
# Step 1: Auto-diagnose (shows error type, container logs, suggestions)
kctl-dokploy deploy troubleshoot -f <manifest>

# Step 2: If you need more detail on containers
kctl-dokploy compose service-logs <compose-id> --service <name> --tail 200

# Step 3: If you need build/deployment logs
kctl-dokploy deployments logs --compose <compose-id>

# Step 4: If service is on remote server, list its containers
kctl-dokploy docker containers --server <server-name>
```

## Pre-Deploy Validation

```bash
# Single manifest
kctl-dokploy deploy preflight -f <manifest>

# Specific gates only
kctl-dokploy deploy preflight -f <manifest> --gates dns,env_sync,compose_assignment

# All manifests for a server
kctl-dokploy deploy preflight-all -d deploys/instances/production/ --server mac-prod-01
```

## Server Migration

```bash
kctl-dokploy deploy migrate validate -f deploys/migrations/<manifest>.yaml
kctl-dokploy deploy migrate plan -f deploys/migrations/<manifest>.yaml
kctl-dokploy deploy migrate apply -f deploys/migrations/<manifest>.yaml
kctl-dokploy deploy migrate apply -f deploys/migrations/<manifest>.yaml --resume
kctl-dokploy deploy migrate rollback -f deploys/migrations/<manifest>.yaml
kctl-dokploy deploy migrate cleanup -f deploys/migrations/<manifest>.yaml
```

## Critical Rules

1. **NEVER deploy ad-hoc** — always use manifest system at `deploys/`
2. **NEVER use raw SSH** — use `kctl-dokploy compose service-logs` or `docker containers --server`
3. **domain.service MUST match** service name in docker-compose.yml
4. **Run preflight before deploy** — `deploy apply` does this automatically
5. **env_file is source of truth** — env_overrides should NOT duplicate or wipe env_file values
6. **Global option --json goes BEFORE the command group** — e.g., `kctl-dokploy --json compose list`
