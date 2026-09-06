# Kodemeio Dokploy architecture

## Purpose

`kodemeio-dokploy` is the desired-state and operations repository for services
hosted through the Kodemeio Dokploy fleet. It describes what should run, the
infrastructure required to run it, and how operators verify and recover it.

## Ownership boundaries

| Concern | Source of truth |
|---|---|
| Deploy manifests, bases, tenants, and environment contracts | This repository |
| Dokploy and Traefik bootstrap | This repository |
| Cloudflare and Hetzner Terraform modules | This repository |
| Monitoring rules and operational runbooks | This repository |
| `kctl-dokploy` and other `kctl-*` implementation | `kodemeio-skills` |
| Secret values | 1Password and ignored local environment files |
| Current runtime state | Dokploy API and the target servers |

CLI source must not be copied into this repository. Deployment tooling is
installed as a pinned external dependency.

## Control flow

```text
tenant definitions ──generate──▶ instance manifests
       │                              │
       │                              ├──extends──▶ reusable bases
       │                              └──references▶ ignored env files
       │
       └──────────────────────────────▶ kctl-dokploy
                                          │
                  ┌───────────────────────┼────────────────────────┐
                  ▼                       ▼                        ▼
             Cloudflare               Dokploy                 PostgreSQL
             DNS / TLS          compose / env / domain       database setup
                                          │
                                          ▼
                                Traefik + dokploy-network
                                          │
                                          ▼
                                   running services
```

The deployment pipeline validates and preflights before mutating DNS,
databases, compose services, environment variables, domains, schedules, or
backups. Deployment submission is asynchronous; completion requires polling
and health verification.

## Environments and profiles

Manifests are separated into `local`, `staging`, and `production` directories.
Every command and automation job must provide `-p/--profile` explicitly.

Profiles follow the `kctl` prefix inheritance model:

```text
<platform>-<tenant>-<stack>-<app>[-<environment>]
```

Automation must not depend on a workstation's default profile.

## Networking

- Standard HTTP services attach to the external `dokploy-network`.
- Traefik domains provide ingress and TLS.
- Standard HTTP ports are not published directly to the host.
- Direct TCP/UDP exposure is an exception that must be documented in the
  manifest and relevant runbook.
- The `dokploy` and `traefik` containers are platform dependencies and are
  excluded from automated stop, cleanup, and removal actions.

## Secrets

Committed `.env.*.example` files define required variables without values.
Real values remain in 1Password or ignored files under `deploys/env/`.

CI receives deployment configuration through protected GitHub environment
secrets. Terraform state, API keys, database dumps, and pulled environment
files are never committed.

## Infrastructure

The root Terraform configuration in `infra/` owns Cloudflare and Hetzner
resources supporting the Dokploy fleet. Its modules are local so validation
does not depend on removed monorepo package paths.

Moving a Terraform root or backend requires a dedicated state-migration ADR;
repository restructuring alone must not silently relocate state.

## Delivery controls

Pull requests run offline tests, formatting, Terraform validation, and secret
scanning. Live deployment is workflow-dispatch only and uses a protected
GitHub environment.

Production deployment requires:

1. an explicit manifest path and profile;
2. successful manifest validation;
3. a reviewed dry-run;
4. environment approval;
5. deployment polling and health verification;
6. documented rollback.
