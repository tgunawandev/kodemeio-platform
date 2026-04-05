# kctl-pg E2E Tests

Playwright-based E2E tests for kctl-pg verifying SSH connectivity and CLI health checks.

## Setup

```bash
pnpm install
pnpm run install-browsers
```

## Run

```bash
# Against staging PostgreSQL host via SSH
export PG_HOST=10.0.0.2
export PG_PASSWORD=<your-password>
export KCTL_PG_PROFILE=production
pnpm test

# Smoke tests only
pnpm test:smoke

# Visible browser
pnpm test:headed
```

## Env Vars

- `PG_HOST` — PostgreSQL host (SSH target)
- `PG_PASSWORD` — PostgreSQL password
- `KCTL_PG_PROFILE` — kctl-pg profile name to use (required for smoke tests)
