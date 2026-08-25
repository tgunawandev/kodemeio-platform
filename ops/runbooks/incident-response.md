# Incident response

## Start

Record the affected service, start time, operator, and intended profile. For P1
and P2 incidents, notify the operations channel before changing live state.

Run read-only diagnostics:

```bash
kctl-dokploy -p <profile> --json doctor ai-summary
kctl-dokploy -p <profile> dashboard
kctl-dokploy -p <profile> deployments queue
kctl-dokploy -p <profile> maintenance stale
```

Locate the compose ID and inspect runtime logs:

```bash
kctl-dokploy -p <profile> compose search --name <service-name>
kctl-dokploy -p <profile> compose service-logs <compose-id> --tail 200
kctl-dokploy -p <profile> compose deployments list --compose <compose-id>
```

Use [the service map](../../docs/service-map.md) to evaluate upstream
dependencies and blast radius.

## Before changing state

1. Capture the current deployment ID and logs.
2. Confirm a recent backup for stateful services.
3. Identify the manifest and rollback target.
4. Preview the manifest:

```bash
kctl-dokploy -p <profile> deploy validate -f <manifest>
kctl-dokploy -p <profile> deploy apply -f <manifest> --dry-run
```

Do not stop or remove `dokploy` or `traefik`. If the control plane itself is
unavailable, use the provider console or SSH recovery procedure with a second
operator.

## Recovery

Prefer reapplying reviewed desired state:

```bash
kctl-dokploy -p <profile> deploy apply -f <manifest>
```

If a simple compose redeploy is appropriate:

```bash
kctl-dokploy -p <profile> compose redeploy <compose-id>
```

Deployment submission is asynchronous. Confirm completion and health:

```bash
kctl-dokploy -p <profile> deploy status -f <manifest>
kctl-dokploy -p <profile> compose deployments list --compose <compose-id>
```

## Close

- Confirm customer-facing health and dependency recovery.
- Record commands, deployment IDs, timeline, root cause, and rollback state.
- Create a post-incident document under `ops/runbooks/incidents/` for P1/P2.
- Add or update a specific runbook only after its commands are validated
  against the current CLI command tree.
