# kctl-dokploy E2E Tests

Playwright-based E2E tests for kctl-dokploy against live staging services.

## Setup

```bash
pnpm install
pnpm run install-browsers
```

## Run

```bash
# Against staging
export DOKPLOY_URL=https://dokploy.kodeme.io
export DOKPLOY_TOKEN=<your-token>
pnpm test

# Smoke tests only
pnpm test:smoke

# Visible browser
pnpm test:headed
```

## Env Vars

- `DOKPLOY_URL` — Base URL (default: https://dokploy.kodeme.io)
- `DOKPLOY_TOKEN` — API token
