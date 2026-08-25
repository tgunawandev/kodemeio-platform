# CLAUDE.md — kodemeio-dokploy

This repository owns Dokploy deployment desired state, infrastructure,
monitoring, and operational runbooks. CLI implementation belongs in
`kodemeio-cli`.

## Key paths

| Path | Purpose |
|---|---|
| `deploys/bases/` | Reusable deployment bases |
| `deploys/instances/` | Local, staging, and production desired state |
| `deploys/env/` | Ignored values and committed sanitized examples |
| `deploys/tenants/` | Generator inputs |
| `deploys/bootstrap/` | Dokploy/Traefik bootstrap |
| `infra/` | Terraform root and local modules |
| `ops/monitoring/` | Monitoring configuration |
| `ops/runbooks/` | Incident and recovery procedures |
| `ops/scripts/` | Operational utilities |
| `docs/archive/` | Historical, non-authoritative material |

## Commands

```bash
uv sync
just test
just lint
just fmt-check
terraform -chdir=infra init -backend=false
terraform -chdir=infra validate

kctl-dokploy -p <profile> doctor ai-summary
kctl-dokploy -p <profile> deploy validate -f <manifest>
kctl-dokploy -p <profile> deploy apply -f <manifest> --dry-run
```

## Rules

- Always pass an explicit `kctl-dokploy` profile.
- Treat read-only validation, status, and doctor operations as safe.
- Preview live-facing operations before applying them.
- Never commit real env files, credentials, Terraform state, or dumps.
- Do not modify files in `docs/archive/` to describe current behavior.
- Do not add `kctl-*` source or package scaffolding here.
- Standard HTTP services use the external `dokploy-network` and Traefik.
- Never stop or remove `dokploy` or `traefik`.
- Deploys are asynchronous; verify completion and health.
- Preserve ignored files under `deploys/env/` during repository moves.

See `README.md` and `docs/architecture.md` for the current system boundary.
