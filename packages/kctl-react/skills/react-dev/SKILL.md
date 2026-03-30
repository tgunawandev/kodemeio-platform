---
name: react-dev
description: >
  Universal React/Next.js monorepo CLI via kctl-react. Works on any Turbo + pnpm
  monorepo — auto-discovers apps and packages from the filesystem. 17 command groups,
  85+ commands covering app management (list, status, health, info, dashboard, doctor,
  clean), dev servers, builds with history tracking and bundle treemap, testing with
  Vitest JSON parsing, linting, OpenAPI codegen with diff, dependency analysis with
  duplicate detection and version sync, env management, scaffolding, Docker deployment
  with readiness checks, Playwright E2E, git-aware affected detection, security
  scanning (secrets, headers, license compliance, aggregated report), performance
  profiling (Lighthouse CI, score history, PWA readiness), CI/CD pipeline (gate,
  affected-gate, release), Capacitor native app management (init, add, sync, run,
  open, build, doctor, dev, status), and config management. Use when working with
  kctl-react CLI or managing any Turbo + pnpm monorepo.
version: 7.0.0
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Glob
  - Grep
---

# kctl-react — Universal Monorepo CLI

## Overview

- **Universal**: Works on any Turbo + pnpm monorepo (Vite, Next.js, or mixed)
- **Auto-discovery**: Scans `apps/` and `packages/` directories — no hardcoded app list
- **Framework-aware**: Detects both `dist/` (Vite) and `.next/` (Next.js) build output
- **CLI**: Python (Typer + Rich), installed via `uv tool install ./cli`
- **Config**: `~/.config/kodemeio/config.yaml` → service key: `react`
- **17 command groups, 85+ commands, 202 tests**

## Verified monorepos

- **kodemeio-react**: 11 Vite PWA apps (ports 4004-4014)
- **kontenos-react**: 1 Vite PWA app (port 4015)
- **kodemeio-next**: 4 Next.js apps (ports 4000-4003)

## Global Options

```bash
kctl-react [--json] [--quiet] [--profile NAME] [--root PATH] <command>
```

## Project root resolution (priority order)

1. `--root /path/to` flag
2. `KCTL_REACT_ROOT` env var
3. Profile config (`kctl-react config add myrepo --root /path/to`)
4. Auto-detect: walk up from CWD to find `turbo.json` + `apps/`

## Command Reference

### apps — App inventory, health, and utilities

```bash
kctl-react apps list                # Auto-discovered apps with ports
kctl-react apps ports               # Port assignments
kctl-react apps status [APP]        # Dir/pkg/src/build/env/tests check
kctl-react apps health [APP]        # Check running dev servers
kctl-react apps health --watch      # Continuous health monitoring
kctl-react apps info                # Version, root, profile, node/pnpm
kctl-react apps dashboard           # Full monorepo overview
kctl-react apps dashboard --watch   # Continuous refresh
kctl-react apps doctor              # Check node, pnpm, git, docker, apps, packages
kctl-react apps clean [APP]         # Remove dist/, .next/, .turbo/, coverage/
kctl-react apps clean --all         # Also remove node_modules
```

### dev — Dev server management

```bash
kctl-react dev start [APP]          # Start via Turbo (all or one)
kctl-react dev logs APP             # Tail dev output
kctl-react dev list                 # List apps and dev commands
```

### build — Production builds + analysis

```bash
kctl-react build [APP]              # Build for production
kctl-react build APP --analyze      # Build + save size snapshot
kctl-react build size               # Bundle sizes (detects dist/ and .next/)
kctl-react build compare            # Compare vs last snapshot
kctl-react build history            # Size history over time
kctl-react build chunks APP         # Per-file chunk breakdown
kctl-react build bundle APP         # Treemap-style bundle composition
kctl-react build bundle APP --top 30  # Show top 30 largest files
```

### test — Testing with deep Vitest integration

```bash
kctl-react test [APP]               # Run vitest via Turbo
kctl-react test APP --coverage      # With coverage
kctl-react test APP --watch         # Watch mode
kctl-react test count               # Test file inventory per app
kctl-react test summary [APP]       # Parse vitest JSON → pass/fail/skip per app
kctl-react test coverage            # Aggregate coverage-summary.json across apps
```

### lint — Code quality

```bash
kctl-react lint [APP]               # ESLint + TypeScript type-check
kctl-react lint APP --fix           # Auto-fix
kctl-react lint format              # Run Prettier
kctl-react lint format --check      # Check only
```

### codegen — OpenAPI with diff and endpoint extraction

```bash
kctl-react codegen [APP]            # Fetch schema + regenerate types
kctl-react codegen status           # Setup status per app
kctl-react codegen diff APP         # Regenerate + show git diff of changes
kctl-react codegen endpoints APP    # Extract API paths from generated types
```

### affected — Git-aware change detection

```bash
kctl-react affected                 # Which apps changed (vs HEAD~1)
kctl-react affected --base main     # Which apps changed vs main branch
kctl-react affected test            # Run tests only for affected apps
kctl-react affected build           # Build only affected apps
kctl-react affected lint            # Lint only affected apps
```

Package changes propagate: if `packages/core/` changes, all apps depending on `@*/core` are affected.

### deps — Deep dependency analysis

```bash
kctl-react deps outdated [APP]      # Check outdated deps
kctl-react deps audit               # Security audit
kctl-react deps graph               # Internal package dependency tree
kctl-react deps list                # All workspace packages
kctl-react deps why PACKAGE         # Which apps/packages depend on it
kctl-react deps duplicates          # Find version inconsistencies across workspaces
kctl-react deps size                # Disk usage of node_modules
kctl-react deps sync                # Check key dep version consistency
kctl-react deps sync --fix          # Auto-fix to highest version + pnpm install
```

### env — Environment management

```bash
kctl-react env show APP             # Show .env variables
kctl-react env diff APP1 APP2       # Compare envs between apps
kctl-react env validate [APP]       # Check required keys exist
```

### scaffold — Code generation

```bash
kctl-react scaffold page APP Name       # New page component
kctl-react scaffold hook APP resource   # TanStack Query hook
kctl-react scaffold component APP Name  # New component
```

### deploy — Docker Compose + container intelligence

```bash
kctl-react deploy build APP         # Build + deploy
kctl-react deploy status APP        # Container status
kctl-react deploy logs APP [-f]     # Container logs
kctl-react deploy down APP [--force] # Stop (with confirmation)
kctl-react deploy images            # Docker image sizes for all apps
kctl-react deploy ps                # Running kodemeio containers
kctl-react deploy readiness         # Deployment readiness per app
```

### e2e — Playwright E2E and screenshots

```bash
kctl-react e2e screenshots [APP]    # Capture screenshots
kctl-react e2e test [APP]           # Run Playwright tests
kctl-react e2e test --headed        # Visible browser mode
kctl-react e2e test --ui            # Playwright UI mode
kctl-react e2e report               # Open HTML test report
```

### packages — Shared package inspection

```bash
kctl-react packages list            # Packages with versions
kctl-react packages consumers PKG   # Which apps use a package
kctl-react packages size            # Source size per package
```

### security — Security scanning and compliance

```bash
kctl-react security secrets [APP]        # Scan source for hardcoded keys/tokens/passwords
kctl-react security headers APP          # Check CSP, HSTS, X-Frame on running app
kctl-react security licenses [APP]       # License compliance check
kctl-react security licenses --check GPL-3.0  # Fail on disallowed licenses
kctl-react security report [APP]         # Aggregated report of all checks
kctl-react security report --strict      # Exit 1 if any check has findings
```

### perf — Performance profiling

```bash
kctl-react perf lighthouse APP           # Run Lighthouse CI with budget comparison
kctl-react perf lighthouse APP --budget budget.json  # Custom budget thresholds
kctl-react perf history APP              # Lighthouse score + build size trends
kctl-react perf pwa [APP]               # PWA readiness check (manifest, SW, icons)
```

### pipeline — CI/CD gates and releases

```bash
kctl-react pipeline gate [APP]           # Full gate: lint → type-check → test → audit → build
kctl-react pipeline gate --skip-build    # Skip the build step
kctl-react pipeline gate --strict        # Also run secrets scan
kctl-react pipeline affected-gate        # Gate only for git-affected apps
kctl-react pipeline affected-gate --base main  # Custom base ref
kctl-react pipeline release APP          # Build Docker image (tag: git SHA)
kctl-react pipeline release APP --tag v1.0.0   # Custom tag
kctl-react pipeline release APP --push   # Build + push to GHCR
```

### cap — Capacitor native app management

```bash
kctl-react cap status                      # Which apps have Capacitor configured
kctl-react cap init APP                    # Create capacitor.config.ts (appId: io.kodeme.<app>)
kctl-react cap init APP --app-id com.x.y   # Custom bundle ID
kctl-react cap add APP android|ios         # Add native platform (scaffolds android/ or ios/)
kctl-react cap sync APP [platform]         # Build web + sync to native (key workflow)
kctl-react cap sync APP --skip-build       # Sync only (skip Vite build)
kctl-react cap run APP android|ios         # Build + sync + deploy to device/emulator
kctl-react cap open APP android|ios        # Open in Android Studio / Xcode
kctl-react cap build APP android|ios       # Build native artifact (APK/IPA)
kctl-react cap build APP android --release # Signed release build
kctl-react cap dev APP android|ios         # Live-reload dev on device
kctl-react cap doctor [APP]               # 14-point preflight validation
kctl-react cap devices                    # List connected devices/emulators via ADB
kctl-react cap install APP [-d SERIAL]    # Install APK on device
kctl-react cap launch APP [-d SERIAL]     # Launch app on device
kctl-react cap logs APP [-d SERIAL]       # Tail logcat filtered to app
kctl-react cap keystore APP               # Generate signing keystore for release
kctl-react cap emulator                   # List Android emulators (AVDs)
kctl-react cap emulator --create NAME     # Create new emulator
kctl-react cap emulator --start           # Start first available emulator
```

### config — Multi-profile management

```bash
kctl-react config init              # Interactive setup
kctl-react config add NAME --root PATH  # Add profile for a monorepo
kctl-react config use NAME          # Switch default profile
kctl-react config current           # Show active profile
kctl-react config show              # Show all config
kctl-react config set KEY VALUE     # Set config value
kctl-react config profiles          # List all profiles
```

## Multi-monorepo usage

```bash
# Option 1: Auto-detect (cd into repo)
cd /path/to/any-turbo-monorepo && kctl-react dashboard

# Option 2: Profiles
kctl-react config add kodemeio --root /path/to/kodemeio-react
kctl-react config add kontenos --root /path/to/kontenos-react
kctl-react -p kontenos apps list

# Option 3: --root flag
kctl-react --root /path/to/monorepo apps list
```

## JSON output for scripting

```bash
kctl-react --json apps list | jq '.[].app'
kctl-react --json apps dashboard | jq '.running_apps'
kctl-react --json deps duplicates | jq '.[].package'
kctl-react --json affected | jq '.affected'
```
