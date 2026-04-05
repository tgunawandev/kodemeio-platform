# kctl-ak E2E Tests

Playwright-based E2E tests for kctl-ak against live Authentik SSO staging services.

## Setup

```bash
pnpm install
pnpm run install-browsers
```

## Run

```bash
# Against staging
export AUTHENTIK_URL=https://auth.kodeme.io
export AUTHENTIK_TOKEN=<your-token>
pnpm test

# Smoke tests only
pnpm test:smoke

# Visible browser
pnpm test:headed
```

## Env Vars

- `AUTHENTIK_URL` — Base URL (default: https://auth.kodeme.io)
- `AUTHENTIK_TOKEN` — API token
