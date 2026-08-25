# kctl-react

Command reference for `kctl-react` (34 groups, ~174 commands).

> Auto-generated on 2026-04-02. Do not edit manually.
> Regenerate with: `uv run python scripts/generate-cli-docs.py`

## Global Options

| Flag | Description |
|------|-------------|
| `--json` | JSON output |
| `--quiet`, `-q` | Suppress info messages |
| `--format`, `-f` | Output format: pretty/json/csv/yaml |
| `--no-header` | Omit headers in CSV output |
| `--profile`, `-p` | Config profile name |
| `--version`, `-V` | Show version |

## Commands

### `kctl-react a11y`

Accessibility auditing (WCAG 2.1).

| Command | Description |
|---------|-------------|
| `a11y audit <app_name> [--url]` | Run axe-core accessibility audit. |
| `a11y report <app_name>` | Full WCAG 2.1 AA compliance report. |
| `a11y violations <app_name> [--severity]` | List accessibility violations filtered by severity. |

### `kctl-react affected`

Git-aware change detection and targeted operations.

| Command | Description |
|---------|-------------|
| `affected build [--base]` | Build only affected apps. |
| `affected lint [--base]` | Lint only affected apps. |
| `affected test [--base] [--coverage]` | Run tests only for affected apps. |

### `kctl-react apps`

App inventory, status, and health checks.

| Command | Description |
|---------|-------------|
| `apps clean [--app_name] [--all_]` | Clean dist, .turbo, and coverage directories. |
| `apps dashboard [--watch] [--interval]` | Show monorepo overview dashboard. |
| `apps doctor` | Run comprehensive monorepo health checks. |
| `apps health [--app_name] [--watch] [--interval]` | Check health of running dev servers. |
| `apps info` | Show quick project info: version, root, profile, node/pnpm versions. |
| `apps list` | List all apps with ports and package names. |
| `apps ports` | Show port assignments for all apps. |
| `apps status [--app_name]` | Check status of app(s): directory exists, package.json, env file, dist. |

### `kctl-react build`

Production builds and bundle analysis.

| Command | Description |
|---------|-------------|
| `build bundle <app_name> [--top]` | Show treemap-style bundle composition for a built app. |
| `build chunks <app_name>` | Show chunk breakdown for a built app. |
| `build compare [--app_name]` | Compare current bundle sizes against last recorded snapshot. |
| `build history` | Show build size history over time. |
| `build size [--app_name]` | Show bundle sizes for built app(s). |

### `kctl-react bundle`

Advanced bundle analysis.

| Command | Description |
|---------|-------------|
| `bundle budget <app_name> [--max_js]` | Check bundle sizes against budgets. |
| `bundle compare <app_name>` | Compare current build against saved snapshot. |
| `bundle duplicates` | Detect packages bundled at different versions across apps. |
| `bundle impact <app_name> [--top]` | Show which chunks contribute most to bundle size. |
| `bundle treeshake <app_name>` | Detect imports that may prevent tree-shaking. |

### `kctl-react cap`

Capacitor native app management (Android/iOS).

| Command | Description |
|---------|-------------|
| `cap add <app_name> <platform>` | Add a native platform (android/ios) to an app. |
| `cap build <app_name> <platform> [--release]` | Build native artifact (APK/AAB for Android, IPA for iOS). |
| `cap dev <app_name> <platform>` | Start Vite dev server with live-reload on a native device. |
| `cap devices` | List connected Android devices and emulators via ADB. |
| `cap doctor [--app_name] [--platform]` | Comprehensive Capacitor build environment validation. |
| `cap emulator [--start] [--create]` | List, create, or start Android emulators. |
| `cap init <app_name> [--app_id]` | Initialize Capacitor for an app (creates capacitor.config.ts). |
| `cap install <app_name> [--device] [--build_type]` | Install APK on a connected device or emulator. |
| `cap keystore <app_name> [--alias] [--validity]` | Generate a signing keystore for release builds. |
| `cap launch <app_name> [--device]` | Launch the app on a connected device or emulator. |
| `cap logs <app_name> [--device] [--clear]` | Show live logcat output filtered to the app (Ctrl+C to stop). |
| `cap open <app_name> <platform>` | Open native project in Android Studio or Xcode. |
| `cap run <app_name> <platform> [--target]` | Build, sync, and deploy to a device or emulator. |
| `cap status` | Show Capacitor status for all apps. |
| `cap sync <app_name> [--platform] [--skip_build]` | Build web assets and sync to native platforms. |

### `kctl-react clean`

Clean build artifacts and caches.

| Command | Description |
|---------|-------------|
| `clean run [--app_name] [--all_]` | Clean dist, .turbo, and coverage directories. |

### `kctl-react codegen`

OpenAPI schema fetch and type generation.

| Command | Description |
|---------|-------------|
| `codegen diff <app_name>` | Show what types changed after regenerating OpenAPI types. |
| `codegen drift <app_name>` | Detect stale type references. |
| `codegen endpoints <app_name>` | List API endpoints from the app's generated types. |
| `codegen schema-health <app_name>` | Check OpenAPI codegen health for an app. |
| `codegen status` | Show codegen setup status for each app. |
| `codegen verify <app_name>` | Verify generated types are properly wired. |

### `kctl-react compliance`

Audit app compliance, auto-fix violations, and generate fix prompts.

| Command | Description |
|---------|-------------|
| `compliance api-check [--app_name] [--all_apps] [--offline] [--categories] [--min_score]` | Check frontend API hooks against OpenAPI schema. |
| `compliance api-health [--app_name] [--all_apps] [--url] [--timeout] [--token] [--categories] [--min_score]` | Run live health checks against backend API endpoints. |
| `compliance audit [--app_name] [--all_apps] [--min_score] [--categories]` | Run compliance audit on one or all apps. |
| `compliance fix [--app_name] [--all_apps] [--dry_run] [--categories]` | Apply auto-fixes for compliance violations. |
| `compliance prompt [--app_name] [--all_apps] [--output_file] [--categories]` | Generate markdown fix prompts for AI or human review. |

### `kctl-react config`

Manage CLI configuration and profiles.

| Command | Description |
|---------|-------------|
| `config add <name> [--root] [--api_url] [--odoo_url] [--odoo_db] [--set_default]` | Add or update a profile's React monorepo connection. |
| `config current` | Show the active profile and project root. |
| `config init [--root] [--api_url] [--name]` | Initialize CLI configuration (interactive if no flags given). |
| `config profiles` | List all profiles. |
| `config remove <name> [--force] [--service_only]` | Remove a profile or just its React config. |
| `config set <key> <value>` | Set a configuration value. |
| `config show` | Show full configuration. |
| `config test` | Verify configuration is valid. |
| `config use <name>` | Switch the default profile. |

### `kctl-react dashboard`

Monorepo overview dashboard.

| Command | Description |
|---------|-------------|
| `dashboard show [--watch] [--interval]` | Show monorepo overview dashboard. |

### `kctl-react deploy`

Docker Compose deployment management.

| Command | Description |
|---------|-------------|
| `deploy build <app_name>` | Build and deploy an app via Docker Compose. |
| `deploy down <app_name> [--force]` | Stop a deployed app. |
| `deploy images` | Show Docker images for all apps. |
| `deploy logs <app_name> [--follow]` | Show logs for a deployed app. |
| `deploy ps` | Show all running containers for kodemeio apps. |
| `deploy readiness` | Show deployment readiness status per app. |
| `deploy status <app_name>` | Show container status for a deployed app. |

### `kctl-react deps`

Dependency management and analysis.

| Command | Description |
|---------|-------------|
| `deps audit` | Run security audit on dependencies. |
| `deps duplicates` | Find packages with inconsistent versions across workspaces. |
| `deps graph` | Show internal package dependency graph. |
| `deps health` | Run dependency health checks and produce an overall score. |
| `deps list` | List all workspace packages. |
| `deps outdated [--app_name]` | Check for outdated dependencies. |
| `deps size` | Show node_modules disk usage. |
| `deps stack [--category]` | Show full external dependency inventory across the monorepo. |
| `deps sync [--fix]` | Check and fix version inconsistencies across ALL external dependencies. |
| `deps upgrade [--category] [--major] [--dry_run]` | Smart dependency upgrade — show outdated deps with context and apply upgrades. |
| `deps why <package>` | Show which apps depend on a specific package. |

### `kctl-react dev`

Dev server management.

| Command | Description |
|---------|-------------|
| `dev list` | List available apps and their dev ports. |
| `dev logs <app_name>` | Show build output / dev logs for an app (re-runs dev with output). |
| `dev start [--app_name]` | Start dev server(s) via Turbo. |

### `kctl-react docker`

Docker container management.

| Command | Description |
|---------|-------------|
| `docker image-size` | Show Docker image sizes. |
| `docker logs [--service] [--tail]` | Stream container logs. |
| `docker ps` | List running containers. |
| `docker restart <service>` | Restart a container. |

### `kctl-react doctor`

Monorepo health checks.

| Command | Description |
|---------|-------------|
| `doctor check` | Run comprehensive monorepo health checks. |

### `kctl-react e2e`

E2E testing and screenshots via Playwright.

| Command | Description |
|---------|-------------|
| `e2e discover [--dry_run] [--json_output]` | Auto-discover app configs and regenerate e2e/app-registry.ts. |
| `e2e install` | Install Playwright browsers (chromium). |
| `e2e list [--app_name]` | List all discovered E2E tests. |
| `e2e report` | Open Playwright HTML test report. |
| `e2e screenshots [--app_name] [--mobile] [--desktop]` | Capture screenshots of all app pages via Playwright. |
| `e2e test [--app_name] [--headed] [--ui] [--shared_only] [--debug] [--screenshots] [--video] [--mobile] [--grep] [--api_only] [--pages_only]` | Run Playwright E2E tests. |

### `kctl-react env`

Environment variable management.

| Command | Description |
|---------|-------------|
| `env diff <app1> <app2>` | Compare .env files between two apps. |
| `env show <app_name>` | Show environment variables for an app. |
| `env validate [--app_name]` | Validate .env files exist and have required keys. |

### `kctl-react i18n`

Translation management (react-i18next).

| Command | Description |
|---------|-------------|
| `i18n coverage [--app_name] [--all_apps]` | Translation coverage — compare en.json vs id.json. |
| `i18n diff <app_name> [--base]` | Show keys added/removed between git refs. |
| `i18n interpolation <app_name>` | Check {{var}} placeholder consistency between en.json and id.json. |
| `i18n missing <app_name>` | List keys in en.json but not in id.json. |
| `i18n sort <app_name>` | Sort translation JSON keys alphabetically. |
| `i18n sync-stub <app_name>` | Generate stub entries in id.json for keys missing from en.json. |
| `i18n unused <app_name>` | Find translation keys not referenced in source code. |
| `i18n validate <app_name>` | Validate all translation JSON files for syntax and required keys. |

### `kctl-react info`

Show monorepo summary: apps, packages, and CLI version.

### `kctl-react lint`

Lint, type-check, and format code.

| Command | Description |
|---------|-------------|
| `lint conventions <app_name>` | Check project conventions for an app. |
| `lint format [--check]` | Run Prettier on the codebase. |
| `lint strict-check` | Verify all apps have TypeScript strict mode enabled. |
| `lint tsconfig-audit` | Audit tsconfig.json settings for consistency across all apps. |

### `kctl-react maintenance`

Maintenance utilities for the React monorepo.

| Command | Description |
|---------|-------------|
| `maintenance cleanup [--dry_run]` | Remove build artifacts (dist/, .turbo/, coverage/, node_modules/.cache). |
| `maintenance count-test-files` | Count test files (.test.ts / .test.tsx) per app. |
| `maintenance deps-sync [--exclude]` | Check dependency version consistency across all apps and packages. |
| `maintenance dr-status` | Check deployment readiness: Dockerfile, docker-compose, and .env files. |
| `maintenance health-report` | Show per-app health: test file count, codegen status, and dist presence. |

### `kctl-react monitor`

Production monitoring.

| Command | Description |
|---------|-------------|
| `monitor health <app_name> [--url]` | HTTP health check against deployed app. |
| `monitor ssl <domain>` | Check SSL certificate. |

### `kctl-react observe`

Error tracking and observability.

| Command | Description |
|---------|-------------|
| `observe errors [--app_name]` | Show error trends. |
| `observe sentry [--app_name]` | Show recent Sentry issues. |
| `observe uptime [--app_name]` | Show Gatus uptime status. |

### `kctl-react packages`

Shared package inspection and management.

| Command | Description |
|---------|-------------|
| `packages consumers <package_name>` | Show which apps use a specific shared package. |
| `packages list` | List all shared packages with versions and descriptions. |
| `packages size` | Show source size of each shared package. |

### `kctl-react perf`

Performance profiling and bundle analysis.

| Command | Description |
|---------|-------------|
| `perf bundle <app_name> [--budget_kb]` | Report bundle size breakdown for a built app (reads dist/assets/). |
| `perf fonts <app_name>` | Check font loading strategy (preload, self-hosted, font-display, woff2). |
| `perf history <app_name> [--limit]` | Show Lighthouse score and build size trends over time. |
| `perf images <app_name> [--max_size]` | Audit image assets in public/ and src/assets/ directories. |
| `perf lighthouse <app_name> [--budget] [--url]` | Run Lighthouse CI and compare against performance budget. |
| `perf pwa [--app_name]` | Check PWA readiness for each app. |
| `perf vitals <app_name>` | Check Core Web Vitals readiness (code splitting, lazy images, SVGs, scripts). |

### `kctl-react pipeline`

CI/CD pipeline gates, affected builds, and releases.

| Command | Description |
|---------|-------------|
| `pipeline affected-gate [--base] [--strict]` | Run gate only for apps affected by git changes. |
| `pipeline gate [--app_name] [--strict] [--skip_build]` | Run full CI gate: lint → type-check → test → audit → build. |
| `pipeline release <app_name> [--tag] [--push]` | Build Docker image for an app and optionally push to GHCR. |

### `kctl-react pwa`

PWA and Service Worker management (Vite apps).

| Command | Description |
|---------|-------------|
| `pwa cache-clear <app_name>` | Clear built service worker files. |
| `pwa cache-list <app_name>` | List precached URLs from service worker manifest. |
| `pwa manifest-validate <app_name>` | Validate web app manifest against PWA requirements. |
| `pwa offline-report <app_name>` | Analyze offline support coverage. |
| `pwa status <app_name>` | Show PWA status — service worker version, precache count, manifest. |
| `pwa sw-info <app_name>` | Show vite-plugin-pwa configuration. |

### `kctl-react scaffold`

Scaffold new apps, pages, hooks, and components.

| Command | Description |
|---------|-------------|
| `scaffold component <app_name> <name>` | Scaffold a new component. |
| `scaffold form <app_name> <name>` | Scaffold a react-hook-form + zod form component. |
| `scaffold hook <app_name> <resource>` | Scaffold a TanStack Query API hook. |
| `scaffold page <app_name> <name>` | Scaffold a new page component. |
| `scaffold test <app_name> <name>` | Scaffold a vitest test file. |

### `kctl-react security`

Security scanning and compliance checks.

| Command | Description |
|---------|-------------|
| `security audit [--app_name] [--detail]` | Run pnpm audit — show vulnerabilities with severity, CVEs, and fix commands. |
| `security deps-license [--app_name] [--check]` | Check license compliance across dependencies. |
| `security headers <app_name> [--url]` | Check security headers on a running app. |
| `security licenses [--app_name] [--check]` | Check license compliance across dependencies. |
| `security report [--app_name] [--strict]` | Run all security checks and produce an aggregated report. |
| `security scan [--app_name]` | Combined security scan: dependency audit + secret detection. |
| `security secrets [--app_name]` | Scan source code for hardcoded API keys, tokens, and passwords. |

### `kctl-react skill`

Claude Code skill management.

| Command | Description |
|---------|-------------|
| `skill generate [--output] [--install]` | Auto-generate SKILL.md from CLI command registry. |

### `kctl-react state`

TanStack Query static analysis (query keys, hooks audit, invalidation map).

| Command | Description |
|---------|-------------|
| `state consistency <app_name>` | Check query key consistency — duplicates and mutations missing invalidation. |
| `state hooks-audit <app_name>` | Audit hook best practices — imports, onError handlers, getErrorMessage usage. |
| `state invalidation-map <app_name>` | Show mutation → invalidation mapping for all hook files. |
| `state query-keys <app_name>` | List all TanStack Query queryKey definitions in hook files and inline queries. |

### `kctl-react test`

Run tests across the monorepo.

| Command | Description |
|---------|-------------|
| `test count` | Count test files per app. |
| `test coverage` | Show aggregated test coverage across all apps. |
| `test naming` | Check test file naming conventions across all apps. |
| `test snapshots <app_name>` | List vitest snapshot files for an app. |
| `test summary [--app_name]` | Run tests with JSON reporter and show parsed summary. |
| `test threshold [--min_pct]` | Enforce minimum coverage threshold across all apps. |

### `kctl-react ui`

UI component audit and shadcn compliance.

| Command | Description |
|---------|-------------|
| `ui add [--component] [--all_components] [--overwrite] [--dry_run]` | Install a shadcn component into @kodemeio/ui. |
| `ui anti-patterns <app_name>` | Detect React anti-patterns: inline styles, CSS modules, styled-components, direct DOM access. |
| `ui audit <app_name>` | Find raw HTML elements that should be shadcn components. |
| `ui compliance <app_name>` | Score shadcn compliance as % of clean TSX files (no violations). |
| `ui components <app_name>` | List shadcn components used by the app. |
| `ui diff <component>` | Show diff for a shadcn component update. |
| `ui docs <component>` | Get shadcn component documentation and API reference. |
| `ui info` | Show shadcn project configuration from packages/ui. |
| `ui installed` | List all installed shadcn components in @kodemeio/ui. |
| `ui preset <name> [--reinstall] [--dry_run] [--target]` | Apply a shadcn theme preset — extract CSS vars into the monorepo theme system. |
| `ui search <query> [--limit]` | Search the shadcn component registry. |
| `ui theme-check <app_name>` | Validate theme CSS variable references and Tailwind v4 patterns. |
| `ui unused` | Find installed components not used by any app. |
