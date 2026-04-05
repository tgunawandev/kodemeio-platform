---
name: api-admin
description: >
  FastAPI platform management via kctl-api CLI (55 groups, ~231 commands).
  MUST use for ANY kctl-api operation.
  Triggers on: "ai", "apps", "attach", "audit", "auth", "automation", "background-job", "bench", "breaking", "broadcast", "build", "cache", "call", "chat", "check", "check-safety", "checkout", "clean", "clients", "config", "connect", "connections", "consumers", "containers", "conversation", "conversations", "copilots", "correlation", "cors", "count", "coverage", "current", "dashboard", "db", "dd", "dead-letter", "deep", "delete-conversation", "deploy", "deps", "deps-check", "dev", "diff", "dl", "docker", "doctor", "down", "downgrade", "download", "dr", "ds", "du", "endpoint", "endpoints", "enqueue", "env", "errors", "expire-audit", "export", "files", "fl", "flush", "fmt", "follow", "generate", "graph", "hc", "headers", "health", "heartbeat", "history", "images", "info", "init", "install", "jo", "jobs", "kctl-api", "keys", "keys-by-prefix".
  Auto-generated: 2026-04-05
  registry_hash: c99de89d0de1
---

# api-admin — kctl-api CLI Reference

> Auto-generated from `kctl-api` command registry. Do not edit manually.
> To regenerate: `kctl-api skill generate`
> To add custom content: edit `SKILL.extra.md` in the same directory.

## Overview

**CLI:** `kctl-api`
**Command groups:** 55
**Total commands:** ~231
**Install:** `cd cli && uv tool install --editable .`

## Global Options

| Flag | Description |
|------|-------------|
| `--json` | JSON output |
| `--quiet`, `-q` | Suppress info messages |
| `--format`, `-f` | Output format: pretty/json/csv/yaml |
| `--no-header` | Omit CSV header row |
| `--profile`, `-p` | Config profile name |
| `--version`, `-V` | Show version |

## Command Reference

### `kctl-api ai`

AI platform — copilots, chat, conversations.

| Command | Description |
|---------|-------------|
| `ai chat <message> [--copilot] [--conversation_id]` | Send a chat message to an AI copilot via POST /api/v1/ai/chat. |
| `ai conversation <conversation_id>` | Get conversation details and messages via GET /api/v1/ai/conversations/{id}. |
| `ai conversations [--page] [--per_page]` | List AI conversations via GET /api/v1/ai/conversations. |
| `ai copilots` | List available AI copilots via GET /api/v1/ai/copilots. |
| `ai delete-conversation <conversation_id> [--force]` | Delete an AI conversation via DELETE /api/v1/ai/conversations/{id}. |
| `ai health` | Check AI service health via GET /api/v1/ai/health. |

### `kctl-api apps`

App registry — list and inspect monorepo apps.

| Command | Description |
|---------|-------------|
| `apps deps <name>` | Show dependencies for an app (reads pyproject.toml). |
| `apps env <name>` | Show environment variables for an app (reads .env.example). |
| `apps info <name>` | Show details for a specific app from the registry. |
| `apps list` | List all known apps in the kodemeio-fastapi monorepo. |

### `kctl-api auth`

Authentication and identity management.

| Command | Description |
|---------|-------------|
| `auth login [--email] [--password]` | Authenticate with email and password, cache JWT tokens in profile. |
| `auth logout` | Clear cached tokens from the active profile. |
| `auth refresh` | Refresh the JWT access token using the refresh token. |
| `auth token-info [--token]` | Decode and display JWT token claims (without cryptographic verification). |
| `auth whoami` | Display current authenticated user info. |

### `kctl-api automation`

Automation templates — list, create, update, delete, run.

| Command | Description |
|---------|-------------|
| `automation create <name> <trigger_type> [--config_json]` | Create a new automation template via POST. |
| `automation delete <template_id> [--force]` | Delete an automation template via DELETE. |
| `automation get <template_id>` | Get automation template details. |
| `automation list [--page] [--per_page]` | List automation templates. |
| `automation run <template_id> [--data_json]` | Manually trigger an automation template via POST. |
| `automation update <template_id> [--name] [--enabled] [--config_json]` | Update an automation template via PATCH. |

### `kctl-api build`

Docker image builds — dev, prod, all.

| Command | Description |
|---------|-------------|
| `build all [--dev_mode]` | Build all Docker images via scripts/build all. |
| `build dev [--app_name]` | Build development Docker image(s) via scripts/build --dev. |
| `build prod [--app_name]` | Build production Docker image(s) via scripts/build. |

### `kctl-api clean`

Cleanup — all, cache, build, pycache.

| Command | Description |
|---------|-------------|
| `clean all [--dry_run] [--force]` | Remove all build artifacts, caches, and __pycache__ directories. |
| `clean build [--dry_run]` | Remove dist/ and *.egg-info build artifacts. |
| `clean cache [--dry_run]` | Remove .ruff_cache, .mypy_cache, .pytest_cache directories. |
| `clean pycache [--dry_run]` | Remove all __pycache__ directories and .pyc/.pyo files. |

### `kctl-api config`

Manage connection profiles and configuration.

| Command | Description |
|---------|-------------|
| `config add <name> [--url] [--ai_url] [--api_key] [--database_url] [--redis_url] [--default]` | Add a new connection profile. |
| `config current` | Show active profile name and connection status. |
| `config init` | Interactive setup wizard: prompt for URL, email, password; login to get JWT; save profile. |
| `config migrate` | Migrate from old flat format to service-scoped YAML. |
| `config profiles` | List all connection profiles. |
| `config remove <name> [--force]` | Delete a connection profile. |
| `config set <key> <value>` | Set a config value on the active profile. |
| `config show` | Show full configuration with masked secrets. |
| `config test` | Test current profile connectivity (GET /api/v1/health). |
| `config use <name>` | Switch the default profile. |

### `kctl-api dashboard`

Dashboard — overview, live monitoring.

| Command | Description |
|---------|-------------|
| `dashboard live` | Live dashboard with auto-refresh (not yet implemented). |
| `dashboard overview` | Show a combined overview: health + jobs + recent activity. |

### `kctl-api db`

Database management — tables, migrations, queries, shell.

| Command | Description |
|---------|-------------|
| `db check-safety` | Analyze pending Alembic migrations for destructive operations. |
| `db connections` | Show active database connections. |
| `db count <table>` | Count rows in a table via direct async query. |
| `db downgrade [--revision] [--force]` | Downgrade database to a previous migration revision. |
| `db generate <message>` | Generate a new Alembic migration via scripts/db generate. |
| `db history` | Show Alembic migration history via scripts/db history. |
| `db migrate` | Run Alembic upgrade head via scripts/db migrate. |
| `db query <sql> [--force]` | Execute a raw SQL query via async engine. |
| `db reset [--force] [--skip_seed]` | Drop + recreate + migrate + seed the database. |
| `db seed [--app_name] [--force]` | Seed the database with test/dev data via scripts/db seed. |
| `db shell` | Open an interactive psql shell to the configured database. |
| `db size` | Show database size per table. |
| `db slow-queries [--min_ms] [--limit]` | Show slow queries from pg_stat_statements (requires pg_stat_statements extension). |
| `db tables` | List database tables via direct async query. |

### `kctl-api dd`

Alias: dev down

### `kctl-api deploy`

Deployment management — status, logs, restart, rollback.

| Command | Description |
|---------|-------------|
| `deploy list` | List all deployments (will use Dokploy API). |
| `deploy logs <app_name> [--tail]` | View deployment logs (will use Dokploy API). |
| `deploy restart <app_name>` | Restart a deployed app (will use Dokploy API). |
| `deploy rollback <app_name> [--revision]` | Rollback a deployment to a previous revision (will use Dokploy API). |
| `deploy status [--app_name]` | Show deployment status (will use Dokploy API). |

### `kctl-api deps`

Dependency management — audit, outdated, licenses, graph, size.

| Command | Description |
|---------|-------------|
| `deps audit [--fix]` | Run security audit via uv or pip-audit. |
| `deps graph` | Show the dependency graph via uv tree. |
| `deps licenses [--allow]` | Generate a license report for all installed packages. |
| `deps outdated` | Show outdated packages across all workspace members. |
| `deps size [--top]` | Show installed package sizes. |

### `kctl-api dev`

Development environment — up, down, rebuild, logs.

| Command | Description |
|---------|-------------|
| `dev attach <service>` | Attach to a running container's shell. |
| `dev down` | Stop the development stack. |
| `dev logs [--service] [--follow] [--tail]` | View docker compose logs. |
| `dev rebuild [--service]` | Rebuild and restart docker compose services. |
| `dev up [--build] [--odoo_mm] [--plane_mm] [--all_services]` | Start the development stack via scripts/dev. |

### `kctl-api dl`

Alias: deploy logs <app>

Usage: `kctl-api dl [--app_name]`

### `kctl-api docker`

Docker management — images, containers, network, volumes, system.

| Command | Description |
|---------|-------------|
| `docker containers [--all_containers]` | List running (or all) Docker containers. |
| `docker images` | List Docker images for the project. |
| `docker network` | List Docker networks and show which containers are attached. |
| `docker system` | Show Docker system disk usage and resource summary. |
| `docker volumes` | List Docker volumes used by the project. |

### `kctl-api doctor`

Environment validation — check, fix, report.

| Command | Description |
|---------|-------------|
| `doctor check` | Check Python, uv, Docker, PostgreSQL, Redis, and .env configuration. |
| `doctor fix` | Auto-fix common environment issues. |
| `doctor report` | Generate a full diagnostic report. |

### `kctl-api dr`

Alias: dev rebuild

### `kctl-api ds`

Alias: deploy status

### `kctl-api du`

Alias: dev up

### `kctl-api env`

Environment management — validate, diff, template, sync.

| Command | Description |
|---------|-------------|
| `env diff [--file_a] [--file_b]` | Diff two .env files, or .env vs .env.example if no args given. |
| `env sync [--dry_run]` | Sync .env keys across monorepo apps — add missing keys from root .env.example. |
| `env template [--source] [--output] [--force]` | Generate .env.example from .env by stripping values. |
| `env validate [--env_file]` | Validate .env against .env.example — show missing and extra keys. |

### `kctl-api files`

File management — upload, download, list, delete.

| Command | Description |
|---------|-------------|
| `files delete <file_id> [--force]` | Delete a file by ID via DELETE /api/v1/files/{id}. |
| `files download <file_id> [--output_path]` | Download a file by ID via GET /api/v1/files/{id}/download. |
| `files info <file_id>` | Get file metadata by ID. |
| `files list [--page] [--per_page]` | List uploaded files with pagination. |
| `files stats` | Get file storage statistics via GET /api/v1/files/stats. |
| `files upload <file_path>` | Upload a file via POST /api/v1/files/upload. |

### `kctl-api fl`

Alias: files list

### `kctl-api fmt`

Code formatting — run, check.

| Command | Description |
|---------|-------------|
| `fmt check` | Check formatting without modifying files (ruff format --check). |
| `fmt run` | Format code via scripts/fmt. |

### `kctl-api hc`

Alias: health all

### `kctl-api health`

Health checks for API services, database, and Redis.

| Command | Description |
|---------|-------------|
| `health ai [--watch] [--interval]` | Check ai-main health (GET /api/v1/ai/health). |
| `health all [--watch] [--interval]` | Run all health checks and display aggregated results. |
| `health api [--watch] [--interval]` | Check api-main health (GET /api/v1/health). |
| `health db [--watch] [--interval]` | Check database connectivity (async SELECT 1). |
| `health deep` | Deep health check — DB, Redis, all external service dependencies. |
| `health deps-check` | Verify external service dependencies are reachable. |
| `health redis [--watch] [--interval]` | Check Redis connectivity (async PING). |

### `kctl-api jo`

Alias: jobs overview

### `kctl-api jobs`

Background job management — overview, status, enqueue.

| Command | Description |
|---------|-------------|
| `jobs enqueue <function> [--data_json]` | Enqueue a new background job (admin-only) via POST /api/v1/jobs/enqueue. |
| `jobs get <job_id>` | Get detailed job information via GET /api/v1/jobs/{id}. |
| `jobs overview` | Show job queue overview (GET /api/v1/jobs/queues/overview). |
| `jobs status <job_id>` | Get status of a specific job via GET /api/v1/jobs/{id}. |

### `kctl-api lint`

Linting — check, fix, strict.

| Command | Description |
|---------|-------------|
| `lint check` | Run ruff check + mypy via scripts/lint. |
| `lint fix` | Run ruff check --fix to auto-fix lint issues. |
| `lint strict` | Run mypy in strict mode. |

### `kctl-api logs`

Log viewer — follow, errors, search, tail.

| Command | Description |
|---------|-------------|
| `logs correlation <request_id> [--service] [--tail_lines]` | Trace a request across services by correlation/request ID. |
| `logs errors [--service] [--tail]` | Show only error-level log lines from services. |
| `logs follow [--service] [--tail]` | Follow service logs in real time. |
| `logs search <pattern> [--service] [--tail]` | Search service logs for a pattern. |
| `logs structured [--service] [--tail_lines] [--level] [--event]` | Parse and display JSON (structured) log lines from services. |
| `logs tail [--service] [--lines]` | Show the last N lines of service logs. |

### `kctl-api marketplace`

Extension marketplace — browse, install, publish.

| Command | Description |
|---------|-------------|
| `marketplace get <extension_id>` | Get extension details. |
| `marketplace install <extension_id>` | Install a marketplace extension via POST. |
| `marketplace list [--page] [--per_page] [--category]` | List marketplace extensions. |
| `marketplace publish <manifest_path>` | Publish a new extension via POST /api/v1/marketplace/extensions. |
| `marketplace review <extension_id> <rating> [--comment]` | Submit a review for an extension via POST. |
| `marketplace search <query> [--page] [--per_page]` | Search marketplace extensions by name or description. |
| `marketplace uninstall <extension_id> [--force]` | Uninstall a marketplace extension via DELETE. |
| `marketplace versions <extension_id>` | List available versions for an extension via GET. |

### `kctl-api monitor`

Production monitoring — live, metrics, uptime.

| Command | Description |
|---------|-------------|
| `monitor live [--interval]` | Live dashboard — API health, DB, Redis, container status refreshed every N seconds. |
| `monitor metrics` | Fetch metrics from the API (Prometheus endpoint if available). |
| `monitor uptime [--duration] [--interval]` | Monitor API uptime — single check or continuous with SLA tracking. |

### `kctl-api notifications`

Send notifications — Mattermost, Telegram, broadcast.

| Command | Description |
|---------|-------------|
| `notifications broadcast <message> [--channel_type]` | Broadcast a message to all notification channels via POST /api/v1/notifications/broadcast. |
| `notifications mattermost <message> [--channel]` | Send a Mattermost notification via POST /api/v1/notifications/mattermost. |
| `notifications telegram <message> [--chat_id]` | Send a Telegram notification via POST /api/v1/notifications/telegram. |
| `notifications test [--channel_type]` | Send a test notification to verify configuration. |

### `kctl-api odoo`

Odoo proxy — search-read, call, create, write (admin-only).

| Command | Description |
|---------|-------------|
| `odoo call <model> <method> [--args_json] [--kwargs_json]` | Call an Odoo model method via POST /api/v1/odoo/call (admin-only). |
| `odoo create <model> <values_json>` | Create an Odoo record via POST /api/v1/odoo/create (admin-only). |
| `odoo search-read <model> [--domain] [--fields] [--limit]` | Search and read Odoo records via POST /api/v1/odoo/search-read (admin-only). |
| `odoo write <model> <record_id> <values_json>` | Update an Odoo record via POST /api/v1/odoo/write (admin-only). |

### `kctl-api openapi`

OpenAPI spec — export, validate, diff, breaking changes.

| Command | Description |
|---------|-------------|
| `openapi breaking [--base]` | Detect breaking changes — removed endpoints, changed types, removed fields. |
| `openapi clients` | Show information about generating client SDKs from the OpenAPI spec. |
| `openapi diff [--base]` | Diff OpenAPI spec between current state and a git ref. |
| `openapi export [--fmt] [--output]` | Fetch /openapi.json from running API and export as JSON or YAML. |
| `openapi validate` | Check spec completeness — missing descriptions, examples, error schemas. |

### `kctl-api perf`

Performance — bench, profile, latency, endpoints.

| Command | Description |
|---------|-------------|
| `perf bench <endpoint> [--rps] [--duration] [--method]` | Load test an endpoint — target RPS for a duration. |
| `perf endpoints [--samples] [--tag]` | Measure response times for all GET endpoints from the OpenAPI spec. |
| `perf latency [--endpoint] [--samples]` | Show latency percentiles for an endpoint. |
| `perf profile <endpoint> [--samples] [--method]` | Profile endpoint execution — timing breakdown over N samples. |

### `kctl-api rate-limit`

Rate limit — tiers, test, status, simulate.

| Command | Description |
|---------|-------------|
| `rate-limit simulate <tier>` | Show expected rate limit behavior for a tier. |
| `rate-limit status` | Inspect Redis rate limit keys (rl: prefix). |
| `rate-limit test <endpoint> [--tier] [--count]` | Send sequential requests to test rate limit behavior. |
| `rate-limit tiers` | Show tier rate limit configuration (requests per minute). |

### `kctl-api realtime`

Real-time features — presence, heartbeat, subscribe.

| Command | Description |
|---------|-------------|
| `realtime heartbeat [--scope]` | Send a heartbeat ping via POST /api/v1/realtime/presence/{scope}/heartbeat. |
| `realtime presence [--scope]` | Get online users for a scope via GET /api/v1/realtime/presence/{scope}. |
| `realtime subscribe <channel>` | Subscribe to a real-time SSE channel via GET /api/v1/realtime/sse/{channel}. |

### `kctl-api redis`

Redis management — info, keys, get, delete, stats.

| Command | Description |
|---------|-------------|
| `redis delete <key> [--force]` | Delete a Redis key. |
| `redis expire-audit [--limit]` | Find keys without TTL (potential memory leaks). |
| `redis flush [--force]` | Flush the current Redis database (FLUSHDB). |
| `redis get <key>` | Get a Redis key value. |
| `redis info` | Show Redis server info via async PING + INFO. |
| `redis keys [--pattern] [--limit]` | List Redis keys matching a pattern via async SCAN. |
| `redis keys-by-prefix [--limit]` | Group Redis keys by prefix (up to first colon). |
| `redis memory` | Show memory usage per key prefix. |
| `redis monitor [--duration]` | Real-time Redis MONITOR — show commands as they execute. |
| `redis pubsub` | Show active Pub/Sub channels and subscriber counts. |
| `redis stats` | Show Redis memory and key statistics. |

### `kctl-api routes`

Endpoint introspection — list, auth, middleware, unprotected.

| Command | Description |
|---------|-------------|
| `routes auth` | Group endpoints by authentication requirement. |
| `routes graph` | Show route count per tag/module/router. |
| `routes list` | List all API endpoints with methods, paths, and auth status. |
| `routes middleware <path>` | Describe the middleware chain for a specific endpoint path. |
| `routes unprotected` | Find endpoints without authentication requirements. |

### `kctl-api saas`

SaaS tenant management — create, status, plans.

| Command | Description |
|---------|-------------|
| `saas create <name> [--plan]` | Create a new SaaS tenant via POST /api/v1/saas/tenants. |
| `saas list [--page] [--per_page]` | List SaaS tenants via GET /api/v1/saas/tenants. |
| `saas select-plan <tenant_id> <plan>` | Change tenant plan via POST /api/v1/saas/tenants/{slug}/select-plan. |
| `saas status <tenant_id>` | Get tenant provisioning status via GET /api/v1/saas/tenants/{slug}/status. |

### `kctl-api scaffold`

Scaffold — new app, endpoint, model, webhook.

| Command | Description |
|---------|-------------|
| `scaffold app <name> [--app_type] [--port]` | Scaffold a new deployable app via scripts/new-app. |
| `scaffold background-job <name> [--app_name]` | Scaffold an ARQ background job boilerplate. |
| `scaffold endpoint <app_name> <name>` | Scaffold a new API endpoint in an existing app. |
| `scaffold middleware <name> [--app_name]` | Scaffold a Starlette/FastAPI middleware boilerplate. |
| `scaffold migration <message> [--autogenerate]` | Generate an Alembic migration file. |
| `scaffold model <name> [--table]` | Scaffold a new SQLAlchemy model with Alembic migration. |
| `scaffold service <name> [--app_name]` | Scaffold a service class boilerplate file. |
| `scaffold webhook <name> [--port]` | Scaffold a new standalone webhook receiver app. |

### `kctl-api security`

Security — audit, secrets, CORS, headers, deps.

| Command | Description |
|---------|-------------|
| `security audit` | Run a combined security report: deps, secrets, and CORS. |
| `security cors` | Audit CORS configuration in the codebase. |
| `security deps` | Scan dependencies for known vulnerabilities (alias for: kctl-api deps audit). |
| `security headers [--url]` | Check security headers on a URL. |
| `security secrets [--path]` | Scan source code for potential secrets and credentials. |

### `kctl-api services`

Docker Compose services — list, status, restart, logs.

| Command | Description |
|---------|-------------|
| `services down [--volumes]` | Stop and remove docker compose services. |
| `services list` | List all docker compose services and their status. |
| `services logs <service> [--follow] [--tail]` | View logs for a docker compose service. |
| `services restart <service>` | Restart a docker compose service. |
| `services status <service>` | Show status of a specific docker compose service. |
| `services up [--service] [--build] [--detach]` | Start docker compose services. |

### `kctl-api shell`

Interactive Python REPL with API context.

| Command | Description |
|---------|-------------|
| `shell api` | Start a Python REPL with an httpx client pre-loaded for API calls. |
| `shell db` | Start a Python REPL with an async SQLAlchemy DB session pre-loaded. |
| `shell redis` | Start a Python REPL with a Redis async client pre-loaded. |
| `shell start` | Start an interactive Python REPL with pre-loaded API client and helpers. |

### `kctl-api skill`

Claude Code skill management.

| Command | Description |
|---------|-------------|
| `skill generate [--output] [--install]` | Auto-generate SKILL.md from CLI command registry. |

### `kctl-api streams`

Redis Streams — list, read, trim, dead-letter.

| Command | Description |
|---------|-------------|
| `streams consumers <stream_name> <group>` | List consumers in a consumer group via XINFO CONSUMERS. |
| `streams dead-letter [--stream_name] [--count]` | Read messages from the dead-letter stream. |
| `streams list` | List all Redis Streams via SCAN for stream-type keys. |
| `streams read <stream_name> [--count] [--start]` | Read messages from a Redis Stream via XRANGE. |
| `streams replay <source_stream> <target_stream> [--count] [--force]` | Replay messages from one stream to another via XRANGE + XADD. |
| `streams trim <stream_name> [--maxlen] [--force]` | Trim a Redis Stream to a maximum length via XTRIM. |

### `kctl-api stripe`

Stripe integration — checkout, portal, webhooks.

| Command | Description |
|---------|-------------|
| `stripe checkout <price_id> [--success_url] [--cancel_url]` | Create a Stripe checkout session via POST /api/v1/stripe/checkout. |
| `stripe portal` | Create a Stripe customer portal session via POST /api/v1/stripe/portal. |
| `stripe webhook-status` | Check Stripe webhook endpoint status via GET /api/v1/stripe/webhook-status. |

### `kctl-api tenant-ai`

Tenant AI — chat, stream, history, usage.

| Command | Description |
|---------|-------------|
| `tenant-ai chat <message> [--tenant_id]` | Send a chat message to the tenant AI via POST /api/v1/tenant-ai/chat. |
| `tenant-ai history [--tenant_id] [--page] [--per_page]` | List tenant AI conversation history via GET /api/v1/tenant-ai/history. |
| `tenant-ai stream <message> [--tenant_id]` | Stream a chat response from the tenant AI via POST /api/v1/tenant-ai/chat/stream. |
| `tenant-ai usage [--tenant_id]` | Get tenant AI usage statistics via GET /api/v1/tenant-ai/usage. |

### `kctl-api test`

Test runner — run, coverage, watch.

| Command | Description |
|---------|-------------|
| `test coverage [--app_name]` | Run tests with coverage report via scripts/test --cov. |
| `test run [--app_name] [--verbose] [--marker] [--keyword]` | Run tests via scripts/test. |
| `test watch [--app_name]` | Run tests in watch mode (requires pytest-watch). |

### `kctl-api tr`

Alias: test run all

### `kctl-api ul`

Alias: users list

### `kctl-api users`

User management — list, create, update, delete, roles, tiers.

| Command | Description |
|---------|-------------|
| `users create <email> <name> [--password]` | Create a new user via POST /api/v1/auth/register. |
| `users delete <identifier> [--force]` | Soft-delete a user via DELETE /api/v1/users/{id}. |
| `users get <identifier>` | Get detailed user information by ID or email. |
| `users list [--page] [--per_page] [--search]` | List users with pagination and optional search. |
| `users set-role <identifier> <role>` | Set user role via PATCH /api/v1/users/{id}. |
| `users set-tier <identifier> <tier>` | Set user tier via PATCH /api/v1/users/{id}. |
| `users update <identifier> [--name] [--email]` | Update user fields via PATCH /api/v1/users/{id}. |

### `kctl-api webhooks`

Webhook management — recent, replay, verify.

| Command | Description |
|---------|-------------|
| `webhooks recent [--limit] [--source]` | List recent webhook deliveries (requires webhook audit API — not yet available). |
| `webhooks replay <webhook_id>` | Replay a webhook delivery (requires webhook audit API — not yet available). |
| `webhooks verify <source>` | Verify webhook signature configuration (requires webhook audit API — not yet available). |

### `kctl-api workflows`

Workflow management — start, status, list.

| Command | Description |
|---------|-------------|
| `workflows list [--page] [--per_page]` | List workflow runs via GET /api/v1/workflows. |
| `workflows start <workflow_name> [--data_json]` | Start a new workflow run via POST /api/v1/workflows/start. |
| `workflows status <run_id>` | Check workflow run status via GET /api/v1/workflows/{run_id}. |

### `kctl-api ws`

WebSocket testing — connect, send, listen, load-test.

| Command | Description |
|---------|-------------|
| `ws connect <endpoint> [--token]` | Open a WebSocket connection and show the handshake. |
| `ws listen <endpoint> [--duration] [--token]` | Listen for incoming WebSocket messages for a duration. |
| `ws load-test <endpoint> [--connections] [--duration] [--token]` | Concurrent WebSocket connection load test. |
| `ws send <endpoint> <message> [--token] [--timeout]` | Send a message over WebSocket and show the response. |

## Configuration

Shared config: `~/.config/kodemeio/config.yaml`

```bash
kctl-api config init       # Interactive setup
kctl-api config show       # Show current config
kctl-api config profiles   # List profiles
kctl-api config current    # Show active profile
kctl-api config validate   # Verify config
```
