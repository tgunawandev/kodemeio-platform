# kctl-api

Kodemeio API CLI — manage your FastAPI platform.

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

## Commands

| Group | Description |
|-------|-------------|
| `ai` | AI/ML model and inference management |
| `apps` | Application lifecycle management |
| `auth` | Authentication and token management |
| `automation` | Workflow automation rules |
| `build` | Build and compilation tasks |
| `clean` | Cleanup operations |
| `config` | Profile and connection management |
| `dashboard` | Platform overview and statistics |
| `db` | Database operations and migrations |
| `deploy` | Deployment management |
| `deps` | Dependency management |
| `dev` | Developer tools and utilities |
| `docker` | Docker container operations |
| `doctor` | Diagnostic checks |
| `env` | Environment variable management |
| `files` | File and asset management |
| `fmt` | Code formatting |
| `health` | Health checks |
| `jobs` | Background job management |
| `lint` | Code linting |
| `logs` | Log streaming and filtering |
| `marketplace` | Marketplace integrations |
| `monitor` | Monitoring and metrics |
| `notifications` | Notification management |
| `openapi` | OpenAPI spec management |
| `perf` | Performance profiling |
| `rate-limit` | Rate limiting configuration |
| `realtime` | Real-time/WebSocket management |
| `redis` | Redis cache operations |
| `routes` | API route inspection |
| `saas` | Multi-tenant SaaS operations |
| `scaffold` | Code generation |
| `security` | Security audit and configuration |
| `services` | Service management |
| `shell` | Interactive shell |
| `streams` | Event stream management |
| `stripe` | Stripe billing integration |
| `test` | Test runner |
| `users` | User management |
| `webhooks` | Webhook configuration |
| `workflows` | Workflow orchestration |
| `ws` | WebSocket management |

## Development

```bash
uv run pytest tests/ -v
uv run ruff check src/
uv run mypy src/
```
