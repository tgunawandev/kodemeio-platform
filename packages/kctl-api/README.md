# kctl-api

Kodemeio API CLI — manage your FastAPI platform.

231 commands across 46 groups covering the full lifecycle: development, deployment,
observability, AI integration, multi-tenant SaaS, and API analysis.

## Installation

```bash
uv tool install .
```

## Quick Start

```bash
kctl-api config init
kctl-api health
kctl-api dashboard
kctl-api routes list
```

## Global Options

These options are available on every command and must be passed before the subcommand.

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--json` | | false | Output as JSON |
| `--quiet` | `-q` | false | Suppress info messages |
| `--format` | `-f` | `pretty` | Output format: `pretty`, `json`, `csv`, `yaml` |
| `--no-header` | | false | Omit table headers (for scripting) |
| `--profile` | `-p` | | Config profile name |
| `--url` | | | API URL override |
| `--ai-url` | | | AI API URL override |
| `--api-key` | | | API key override |
| `--database-url` | | | Database URL override |
| `--redis-url` | | | Redis URL override |
| `--version` | `-V` | | Show version and exit |

Example: output JSON, suppress headers, use a non-default profile:

```bash
kctl-api -p staging --json --no-header users list
```

## Command Groups

### Authentication & Access

| Group | Description |
|-------|-------------|
| `config` | Profile and connection management (init, add, use, show, validate, remove, set, profiles, current) |
| `auth` | Authentication and token management |
| `health` | Health checks — endpoint reachability and latency |

### API Resources

| Group | Description |
|-------|-------------|
| `users` | User management — list, get, create, update, deactivate |
| `files` | File and asset management |
| `jobs` | Background job management — queue, status, overview, cancel |
| `workflows` | Workflow orchestration |
| `automation` | Workflow automation rules |
| `notifications` | Notification management |
| `webhooks` | Webhook configuration |
| `marketplace` | Marketplace integrations |
| `saas` | Multi-tenant SaaS operations |
| `stripe` | Stripe billing integration |
| `odoo` | Odoo ERP proxy operations |
| `realtime` | Real-time event management |

### AI Platform

| Group | Description |
|-------|-------------|
| `ai` | AI/ML model and inference management |
| `tenant-ai` | Per-tenant AI configuration and quotas |

### Infrastructure

| Group | Description |
|-------|-------------|
| `db` | Database operations and migrations |
| `redis` | Redis cache operations |
| `streams` | Event stream management |
| `services` | Service management |
| `deploy` | Deployment management — apply, status, logs, rollback |
| `apps` | Application lifecycle management |
| `docker` | Docker container operations |

### Development Tools

| Group | Description |
|-------|-------------|
| `dev` | Developer tools — up, down, rebuild, reload |
| `test` | Test runner |
| `lint` | Code linting |
| `fmt` | Code formatting |
| `build` | Build and compilation tasks |
| `scaffold` | Code generation |
| `shell` | Interactive REPL shell |

### API Analysis & Testing

| Group | Description |
|-------|-------------|
| `openapi` | OpenAPI spec management — export, validate, diff |
| `routes` | API route inspection — list, describe, search |
| `rate-limit` | Rate limiting configuration |
| `ws` | WebSocket management |
| `perf` | Performance profiling and benchmarking |

### Environment & Security

| Group | Description |
|-------|-------------|
| `doctor` | Diagnostic checks — connectivity, config, dependencies |
| `env` | Environment variable management |
| `security` | Security audit and configuration |
| `deps` | Dependency management |
| `clean` | Cleanup operations |

### Observability & Monitoring

| Group | Description |
|-------|-------------|
| `logs` | Log streaming and filtering |
| `dashboard` | Platform overview and statistics |
| `monitor` | Monitoring and metrics |

### Utility

| Group | Description |
|-------|-------------|
| `skill` | Auto-generate SKILL.md from CLI introspection |

## Command Aliases

Hidden short aliases for frequent operations. All aliases forward global flags
(`--profile`, `--json`, `--format`, etc.) to the underlying command automatically.

| Alias | Expands to | Description |
|-------|-----------|-------------|
| `hc` | `health all` | Full health check |
| `dl [app]` | `deploy logs <app>` | Stream deploy logs (default: `api-main`) |
| `ds` | `deploy status` | Deployment status |
| `ul` | `users list` | List users |
| `fl` | `files list` | List files |
| `jo` | `jobs overview` | Jobs overview |
| `du` | `dev up` | Start dev stack |
| `dd` | `dev down` | Stop dev stack |
| `dr` | `dev rebuild` | Rebuild dev containers |
| `tr` | `test run all` | Run all tests |

Example:

```bash
kctl-api -p staging hc      # health all on staging profile
kctl-api dl api-worker      # stream logs for api-worker app
kctl-api jo                 # jobs overview
```

## Shell Completions

Generate and install completions for your shell:

```bash
# Zsh
kctl-api --install-completion zsh

# Bash
kctl-api --install-completion bash

# Fish
kctl-api --install-completion fish

# Print without installing (manual setup)
kctl-api --show-completion zsh
```

After installing, restart your shell or source the completion file.

## Configuration

Config lives at `~/.config/kodemeio/config.yaml` and is shared across all kctl-* CLIs.
The `api` service key scopes kctl-api settings.

```bash
# Set up initial profile
kctl-api config init

# Add a second profile (e.g., staging)
kctl-api config add --profile staging

# Switch active profile
kctl-api config use staging

# Show current config (secrets masked)
kctl-api config show

# Validate profile connectivity
kctl-api config validate
```

## Architecture Note

kctl-api uses an async-capable HTTP client (`AsyncAPIClient` from `kctl-lib`) under the
hood. Long-running commands (log streaming, WebSocket tailing, performance profiling)
run on an asyncio event loop, while quick CRUD operations use the synchronous
`APIClient` path for simpler error propagation.

Command modules are registered lazily via `_register_commands()` at import time, so
`--help` and completions are available with minimal startup overhead even with 46
command groups loaded.

Plugins can extend kctl-api by exporting an entry point under the
`kctl_api.plugins` group — they are discovered and loaded automatically at startup.

## Development

```bash
uv run pytest tests/ -v
uv run ruff check src/
uv run mypy src/
```
