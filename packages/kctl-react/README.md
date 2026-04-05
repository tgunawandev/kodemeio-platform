# kctl-react

Kodemeio React Monorepo CLI — manage 11 Vite PWAs + 14 shared packages.

Part of the kctl-\* CLI ecosystem (alongside kctl-ak, kctl-odoo, kctl-pg, etc.), built with Python + Typer + Rich.

## Install

```bash
cd cli && uv tool install .
```

## Quick Start

```bash
kctl-react dashboard          # Full monorepo overview
kctl-react apps list          # List all 11 apps
kctl-react doctor             # Comprehensive health check
kctl-react info               # Quick project info
```

## Command Groups

| Group         | Key Subcommands                                                           | Purpose                                  |
| ------------- | ------------------------------------------------------------------------- | ---------------------------------------- |
| `apps`        | `list`, `ports`, `status`, `health --watch`, `info`, `dashboard`, `doctor`, `clean` | App inventory, health & routing    |
| `dev`         | `start`, `logs`, `list`                                                   | Dev server management                    |
| `build`       | `[app] --analyze`, `size`, `compare`, `history`, `chunks`, `bundle`       | Production builds + bundle analysis      |
| `test`        | `[app] --coverage --watch`, `count`, `summary`, `coverage`, `naming`, `threshold`, `snapshots` | Vitest testing             |
| `lint`        | `[app] --fix`, `format --check`, `strict-check`, `tsconfig-audit`, `conventions` | ESLint + TypeScript + Prettier      |
| `codegen`     | `[app]`, `status`, `diff`, `endpoints`, `verify`, `drift`, `schema-health` | OpenAPI type generation                 |
| `deps`        | `outdated`, `audit`, `graph`, `list`, `why`, `duplicates`, `size`, `upgrade`, `stack`, `health` | Dependency management          |
| `env`         | `show`, `diff`, `validate`                                                | .env management                          |
| `scaffold`    | `page`, `hook`, `form`, `test`, `component`                               | Code scaffolding                         |
| `deploy`      | `build`, `status`, `logs`, `down --force`, `images`, `ps`, `readiness`    | Docker Compose deployment                |
| `packages`    | `list`, `consumers`, `size`                                               | Shared package inspection                |
| `clean`       | `[app] --all`                                                             | Clean build artifacts                    |
| `pwa`         | `status`, `cache-list`, `cache-clear`, `manifest-validate`, `offline-report`, `sw-info` | PWA / service worker management |
| `e2e`         | `test`, `list`, `report`, `discover`, `install`, `screenshots`            | Playwright E2E testing                   |
| `perf`        | `lighthouse`, `history`, `pwa`, `bundle`, `vitals`, `images`, `fonts`     | Performance & Core Web Vitals            |
| `security`    | `audit`, `scan`, `secrets`, `headers`, `licenses`, `report`               | Security & license scanning              |
| `a11y`        | `audit`, `report`, `violations`                                           | Accessibility audits (axe-core)          |
| `i18n`        | `coverage`, `missing`, `unused`, `sort`, `diff`, `validate`, `interpolation`, `sync-stub` | i18n key management          |
| `state`       | `query-keys`, `consistency`, `hooks-audit`, `invalidation-map`            | TanStack Query state analysis            |
| `bundle`      | `budget`, `duplicates`, `treeshake`, `compare`, `impact`                  | Bundle budget & tree-shaking             |
| `ui`          | `audit`, `compliance`, `anti-patterns`, `components`, `theme-check`, `add`, `diff`, `search`, `docs`, `preset` | shadcn/ui component audit  |
| `observe`     | `sentry`, `errors`, `uptime`                                              | Error tracking & uptime observability    |
| `monitor`     | `health`, `ssl`                                                           | HTTP health + SSL certificate checks     |
| `affected`    | `[default]`, `test`, `build`, `lint`                                      | Turborepo affected graph queries         |
| `pipeline`    | `gate`, `affected-gate`, `release`                                        | CI/CD pipeline gates                     |
| `cap`         | `status`, `doctor`, `init`, `add`, `sync`, `run`, `open`, `build`, `dev`, `devices` | Capacitor native mobile        |
| `docker`      | `ps`, `logs`, `restart`, `image-size`                                     | Docker container management              |
| `maintenance` | `health-report`, `cleanup`, `dr-status`, `count-test-files`, `deps-sync`  | Repo maintenance & DR checks             |
| `compliance`  | `audit`, `fix`, `prompt`, `api-check`, `api-health`                       | Compliance policy enforcement            |
| `doctor`      | `check`                                                                   | Comprehensive health check               |
| `dashboard`   | `show --watch --interval`                                                 | Monorepo overview                        |
| `config`      | `init`, `add`, `use`, `show`, `set`, `validate`, `remove`, `profiles`, `current` | Profile management               |
| `skill`       | `generate`                                                                | Auto-generate SKILL.md from CLI          |
| `info`        |                                                                           | Quick project summary                    |

## Monorepo Architecture

kctl-react manages a **Turborepo monorepo** with Vite PWAs, shared packages, and Docker-based deployments:

```
kodemeio-react/
├── apps/                     # 11 Vite PWA apps (+ optional Next.js)
│   ├── sfa/                  # Sales Force Automation
│   ├── hrms/                 # Human Resource Management
│   ├── iam/                  # Identity & Access Management
│   ├── fin/                  # Finance & Accounting
│   ├── inv/                  # Inventory & Warehouse
│   ├── crm/                  # Customer Relationship Management
│   ├── ops/                  # Operations Management
│   ├── procurement/          # Procurement & Purchasing
│   ├── pos/                  # Point of Sale
│   ├── dashboard/            # Executive Dashboard
│   └── portal/               # Customer/Vendor Portal
├── packages/                 # 14 shared packages
│   ├── ui/                   # shadcn/ui component library
│   ├── api-client/           # Generated OpenAPI clients
│   ├── auth/                 # Authentik OIDC integration
│   ├── i18n/                 # i18next translations
│   ├── hooks/                # Shared React hooks
│   ├── utils/                # Shared utilities
│   └── ...                   # Additional domain packages
├── turbo.json                # Turborepo pipeline config
├── pnpm-workspace.yaml       # pnpm workspace definition
└── docker-compose.yml        # Multi-app compose (nginx routing)
```

### Tech Stack

| Layer | Technology |
|-------|-----------|
| Bundler | Vite 6 |
| Framework | React 19 + TypeScript (strict) |
| Styling | Tailwind CSS v4 |
| Components | shadcn/ui |
| Server state | TanStack Query v5 |
| Forms | react-hook-form + zod |
| PWA | vite-plugin-pwa (Workbox) |
| E2E | Playwright |
| Testing | Vitest |
| Monorepo | Turborepo + pnpm workspaces |
| API clients | OpenAPI-generated (never hand-written) |

## 11 PWA Apps Overview

Each app is a full Vite PWA with service worker, offline support, and OIDC authentication via Authentik:

| App | Domain Pattern | Description |
|-----|---------------|-------------|
| `sfa` | sfa.{tenant}.com | Sales Force Automation — orders, pipelines, visits |
| `hrms` | hrms.{tenant}.com | Human Resources — employees, attendance, payroll |
| `iam` | iam.{tenant}.com | Identity & Access — roles, users, permissions |
| `fin` | fin.{tenant}.com | Finance — invoices, payments, journals |
| `inv` | inv.{tenant}.com | Inventory — stock moves, warehouses, lots |
| `crm` | crm.{tenant}.com | CRM — leads, opportunities, pipelines |
| `ops` | ops.{tenant}.com | Operations — projects, tasks, timesheets |
| `procurement` | proc.{tenant}.com | Procurement — RFQs, purchase orders, vendors |
| `pos` | pos.{tenant}.com | Point of Sale — sessions, orders, payments |
| `dashboard` | dash.{tenant}.com | Executive dashboards — KPIs, charts |
| `portal` | portal.{tenant}.com | Customer/vendor self-service portal |

All apps connect to the `kctl-api` FastAPI backend and Odoo 18 via generated API clients.

## Global Options

```bash
kctl-react [OPTIONS] COMMAND [ARGS]...
```

| Option | Short | Description |
|--------|-------|-------------|
| `--json` | | Machine-readable JSON output (data to stdout, status to stderr) |
| `--quiet` | `-q` | Suppress info messages |
| `--profile NAME` | `-p` | Config profile name |
| `--root PATH` | | Monorepo root override (auto-detects from `turbo.json`) |
| `--format FORMAT` | `-f` | Output format: `pretty`, `json`, `csv`, `yaml` |
| `--no-header` | | Omit header row in CSV output |
| `--version` | `-V` | Show version and exit |

## Shell Completions

```bash
# Install completions (run once)
kctl-react --install-completion

# Or generate and source manually
kctl-react --show-completion zsh   # zsh
kctl-react --show-completion bash  # bash
kctl-react --show-completion fish  # fish
```

Completions are generated by Typer and cover all command groups, subcommands, and flags.

## Configuration

Shared config at `~/.config/kodemeio/config.yaml` (same file as kctl-ak, kctl-odoo, etc.):

```yaml
default_profile: default
profiles:
  default:
    react:
      project_root: /path/to/kodemeio-react
      api_url: https://api.kodeme.io
  mac:
    react:
      project_root: /path/to/kodemeio-react
      api_url: https://api.mandiriagro.com
```

Auto-detects project root from `turbo.json` when not configured.

### Config Commands

```bash
kctl-react config init              # Initialize config profile
kctl-react config add --profile mac # Add a new profile
kctl-react config use mac           # Switch active profile
kctl-react config show              # Show current config (secrets masked)
kctl-react config validate          # Validate config file
kctl-react config profiles          # List all profiles
kctl-react config current           # Show active profile name
```

## Common Workflows

```bash
# Daily development
kctl-react dev start sfa            # Start SFA dev server
kctl-react dev logs sfa             # Follow dev server logs
kctl-react apps health --watch      # Watch app health status

# Build & test
kctl-react build sfa --analyze      # Build with bundle analyzer
kctl-react test sfa --coverage      # Test with coverage report
kctl-react lint sfa --fix           # Lint + auto-fix

# Code generation
kctl-react codegen sfa              # Regenerate OpenAPI types
kctl-react codegen drift            # Detect API drift vs spec

# E2E testing
kctl-react e2e install              # Install Playwright + browsers
kctl-react e2e test --app sfa       # Run E2E tests for SFA
kctl-react e2e screenshots          # Screenshot all apps

# Performance
kctl-react perf lighthouse sfa      # Lighthouse audit
kctl-react perf vitals sfa          # Core Web Vitals check

# Security
kctl-react security audit           # pnpm audit (vulnerabilities)
kctl-react security secrets         # Scan for hardcoded secrets
kctl-react security licenses        # License compliance check

# PWA management
kctl-react pwa status sfa           # Service worker status
kctl-react pwa manifest-validate sfa # Validate PWA manifest

# Deployment
kctl-react deploy build sfa         # Build Docker image
kctl-react deploy status            # Show running containers
kctl-react deploy logs sfa          # Container logs
```

## Development

```bash
cd cli
uv run --extra dev pytest tests/ -v    # Run 73 tests
uv run --extra dev ruff check src/     # Lint
uv run --extra dev mypy src/           # Type check
```

## Architecture

Follows the kctl-\* ecosystem pattern:

```
cli/src/kctl_react/
├── core/           # Config, output, callbacks, runner, exceptions
├── commands/       # One file per command group (31 groups)
├── cli.py          # Main Typer app + command registration
└── py.typed        # PEP 561 marker
```

Each command module registers a Typer sub-app that is mounted in `cli.py`. The `AppContext` dataclass (in `core/callbacks.py`) carries lazy-initialized `Output`, resolved `project_root`, and discovered `apps`/`packages` maps across all commands.

Third-party plugins are auto-discovered via `kctl_react.plugins` entry points — external packages can add new command groups without modifying this repo.
