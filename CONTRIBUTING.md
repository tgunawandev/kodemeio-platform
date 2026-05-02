# Contributing to kodemeio-platform

## Scope

This repository contains **infrastructure only**: deployment manifests, environment configs, server mapping, and operational tooling.

For CLI tool development (kctl-*), see [kodemeio-cli](https://github.com/tgunawandev/kodemeio-cli).

## Quick Start

```bash
git clone https://github.com/tgunawandev/kodemeio-platform.git
cd kodemeio-platform
```

## Development Workflow

### 1. Create a branch

```bash
git checkout -b feat/my-feature    # feat/, fix/, chore/, refactor/
```

Branch naming must match commit type prefix.

### 2. Make changes

- Edit deployment manifests in `deploys/instances/`
- Add new base templates in `deploys/bases/`
- Update tenant definitions in `deploys/tenants/`
- Add runbooks in `runbooks/`

### 3. Commit

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(deploys): add staging manifest for mac-react-sfa
fix(deploys): correct postgres port in tpp-odoo-erp manifest
chore(infra): update monitoring configs
docs: update architecture.md
```

### 4. Push and create PR

```bash
git push -u origin feat/my-feature
gh pr create
```

## What NOT to Do

- Never commit `.env` files, API keys, or secrets
- Never use `docker run` directly — use Docker Compose via Dokploy
- Never skip pre-commit hooks (`--no-verify`)
