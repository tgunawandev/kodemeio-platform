# Contributing to kodemeio-dokploy

## Scope

This repository owns Dokploy deployment desired state, supporting
infrastructure, monitoring, and operational documentation. CLI implementation
belongs in [kodemeio-cli](https://github.com/tgunawandev/kodemeio-cli).

## Setup

```bash
git clone https://github.com/tgunawandev/kodemeio-dokploy.git
cd kodemeio-dokploy
uv sync
```

Install the pinned deployment client separately:

```bash
uv tool install "kctl-dokploy==0.16.6"
```

## Workflow

1. Create a `feat/`, `fix/`, `docs/`, or `chore/` branch.
2. Change manifests, bases, tenant definitions, infrastructure, or operations.
3. Run `just check`.
4. Preview live-facing changes with an explicit profile and `--dry-run`.
5. Open a pull request and review the generated deployment plan.

Use Conventional Commits, for example:

```text
feat(deploys): add staging manifest for mac-react-sfa
fix(infra): correct Dokploy server firewall rules
docs(runbooks): document PostgreSQL failover
```

## Safety

- Never commit real `.env` files, credentials, API keys, Terraform state, or
  deployment output containing secrets.
- Never use `--skip-preflight` in routine operation.
- Never stop or remove the `dokploy` or `traefik` platform containers.
- Keep standard HTTP services on the external `dokploy-network` and route them
  through Traefik.
- Production changes require the protected GitHub environment.
