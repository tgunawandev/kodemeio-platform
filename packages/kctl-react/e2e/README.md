# kctl-react E2E Tests

Playwright-based E2E tests for kctl-react against the kodemeio-react monorepo.

## Setup

```bash
pnpm install
pnpm run install-browsers
```

## Run

```bash
# Point at local monorepo checkout
export REACT_MONOREPO_PATH=/path/to/kodemeio-react
pnpm test

# Smoke tests only
pnpm test:smoke

# Visible browser
pnpm test:headed
```

## Env Vars

- `REACT_MONOREPO_PATH` — Absolute path to the kodemeio-react monorepo checkout
