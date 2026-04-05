# kctl-dokploy

Kodemeio Dokploy CLI -- manage your Dokploy deployment platform and run declarative 13-phase deployment pipelines.

## Installation

```bash
uv tool install ./packages/kctl-dokploy
```

To upgrade after code changes:

```bash
uv tool install --force --reinstall ./packages/kctl-dokploy
```

## Quick Start

```bash
# Configure connection (interactive)
kctl-dokploy config init

# Verify connectivity
kctl-dokploy config test

# Dashboard overview
kctl-dokploy dashboard show

# List all projects
kctl-dokploy projects list

# List all compose services
kctl-dokploy compose list
```

### Deploy Workflow

The primary workflow uses declarative YAML manifests stored in `deploys/instances/`.

```bash
# Full deploy (all phases in one command)
kctl-dokploy deploy apply -f deploys/instances/production/mac-react-sfa.yaml

# Staged deploy (for troubleshooting)
kctl-dokploy deploy setup -f deploys/instances/production/mac-react-sfa.yaml   # Stage 1
kctl-dokploy deploy run   -f deploys/instances/production/mac-react-sfa.yaml   # Stage 2
kctl-dokploy deploy post  -f deploys/instances/production/mac-react-sfa.yaml   # Stage 3

# Batch deploy all manifests in a directory
kctl-dokploy deploy apply-all -d deploys/instances/production/

# Validate a manifest without deploying
kctl-dokploy deploy validate -f deploys/instances/production/mac-react-sfa.yaml

# Check current state vs manifest (dry-run)
kctl-dokploy deploy status -f deploys/instances/production/mac-react-sfa.yaml

# Dry-run any stage
kctl-dokploy deploy apply -f deploys/instances/production/mac-react-sfa.yaml --dry-run
```

### Preflight Checks

```bash
# Run preflight gates before deploying
kctl-dokploy deploy preflight -f deploys/instances/production/mac-react-sfa.yaml

# Run preflight for all manifests in a directory
kctl-dokploy deploy preflight-all -d deploys/instances/production/

# Filter by server
kctl-dokploy deploy preflight-all -d deploys/instances/production/ --server mac-prod-01

# Run specific gates only
kctl-dokploy deploy preflight -f <manifest> --gates dns,database,env_sync
```

### Troubleshooting

```bash
# Diagnose a failed deployment by manifest
kctl-dokploy deploy troubleshoot -f deploys/instances/production/mac-react-sfa.yaml

# Diagnose by compose service ID
kctl-dokploy deploy troubleshoot --compose OEK_dJRQZZMo9HKbQrQ0z

# View deployment logs
kctl-dokploy compose deployments logs --compose <id>
```

### Server Migration

```bash
kctl-dokploy deploy migrate validate -f deploys/migrations/mac-to-dedicated.yaml
kctl-dokploy deploy migrate plan     -f deploys/migrations/mac-to-dedicated.yaml
kctl-dokploy deploy migrate apply    -f deploys/migrations/mac-to-dedicated.yaml
kctl-dokploy deploy migrate apply    -f deploys/migrations/mac-to-dedicated.yaml --resume
kctl-dokploy deploy migrate rollback -f deploys/migrations/mac-to-dedicated.yaml
kctl-dokploy deploy migrate cleanup  -f deploys/migrations/mac-to-dedicated.yaml
```

## Command Groups

### Top-level Groups

| Group            | Description                                                         |
|------------------|---------------------------------------------------------------------|
| `config`         | CLI configuration (profiles, init, add, use, show, validate)        |
| `projects`       | Dokploy project CRUD and environment management                     |
| `applications`   | Application service management (non-compose apps)                   |
| `compose`        | Docker Compose service management (Dokploy's primary service type)  |
| `servers`        | Server management, monitoring, and cluster operations               |
| `databases`      | Managed database service management (Dokploy-managed DBs)           |
| `registry`       | Container registry configuration and access                         |
| `users`          | User CRUD, roles, and invite management                             |
| `git`            | Git provider integration (GitHub, GitLab, Bitbucket)                |
| `notifications`  | Notification channel management (Slack, email, webhook)             |
| `certificates`   | SSL/TLS certificate management                                      |
| `settings`       | Dokploy platform settings (SMTP, S3, general)                       |
| `docker`         | Docker image and container utilities                                 |
| `dashboard`      | Platform overview and health summary                                 |
| `diagnose`       | Diagnostics, maintenance, and platform health checks                |
| `deploy`         | Declarative deployment pipeline (13-phase, manifest-driven)         |
| `report`         | Platform usage and deployment reports                               |
| `template`       | Deployment template management                                      |
| `audit`          | Audit log queries and export                                        |
| `setup`          | Platform initial setup and onboarding                               |

### Compose Sub-Groups

The `compose` group mirrors Dokploy's UI tabs for managing individual services:

| Sub-group         | Description                                                    |
|-------------------|----------------------------------------------------------------|
| `compose backups`        | Backup destination configuration and backup triggers    |
| `compose domains`        | Traefik domain routing and SSL configuration            |
| `compose env`            | Environment variable management (push, pull, diff)      |
| `compose deployments`    | Deployment history, logs, and redeploy triggers         |
| `compose schedules`      | Cron job / scheduled task management                    |
| `compose patches`        | Service patch application                               |
| `compose volume-backups` | Volume backup configuration                             |
| `compose mounts`         | Volume mount management                                 |
| `compose ports`          | Port mapping management                                 |
| `compose security`       | Service-level security settings                         |
| `compose redirects`      | HTTP redirect rules                                     |
| `compose bulk`           | Bulk operations across multiple compose services        |

### Server Sub-Groups

| Sub-group           | Description                                          |
|---------------------|------------------------------------------------------|
| `servers monitoring` | Server resource monitoring (CPU, memory, disk)      |
| `servers cluster`    | Swarm/cluster node management                       |

### Project Sub-Groups

| Sub-group               | Description                                     |
|-------------------------|-------------------------------------------------|
| `projects environments` | Dokploy environment management per project      |

### Deploy Sub-Commands

| Sub-command              | Description                                                  |
|--------------------------|--------------------------------------------------------------|
| `deploy apply`           | All-in-one: run all 13 phases in sequence                   |
| `deploy apply-all`       | Batch apply all manifests in a directory                     |
| `deploy setup`           | Stage 1: DNS + DB + compose + env + domain (idempotent)     |
| `deploy run`             | Stage 2: trigger redeploy + wait for healthy                 |
| `deploy post`            | Stage 3: backup config + schedules + post-deploy hooks       |
| `deploy preflight`       | Run pre-deploy gate checks on a single manifest              |
| `deploy preflight-all`   | Run pre-deploy gate checks on all manifests in a directory   |
| `deploy validate`        | Validate manifest YAML without deploying                     |
| `deploy verify`          | Pre-deploy validation + post-deploy smoke tests              |
| `deploy status`          | Dry-run all phases to preview current state                  |
| `deploy list`            | List all discovered manifests and their domains              |
| `deploy troubleshoot`    | Diagnose failed deployment (logs, health, error type)        |
| `deploy migrate`         | Server-to-server migration pipeline                          |

## Deploy Pipeline

`kctl-dokploy deploy apply` runs a 13-phase pipeline orchestrating multiple kctl-* CLIs:

| # | Phase       | CLI Used       | Description                                               |
|---|-------------|----------------|-----------------------------------------------------------|
| 0 | preflight   | kctl-dokploy   | 10 gates: server, firewall, DNS, image pull, DB, compose, env sync (OIDC), source, network, SSL |
| 1 | dns         | kctl-cf        | Create/verify Cloudflare DNS record                       |
| 2 | database    | kctl-pg        | Create PostgreSQL database + application role             |
| 3 | registry    | kctl-dokploy   | Ensure container registry access configured               |
| 4 | compose     | kctl-dokploy   | Create or update Dokploy compose service                  |
| 5 | environment | kctl-dokploy   | Push env vars from manifest + env file                    |
| 6 | domain      | kctl-dokploy   | Configure Traefik domain routing + SSL                    |
| 7 | deploy      | kctl-dokploy   | Trigger redeploy                                          |
| 8 | verify      | kctl-dokploy   | Wait for healthcheck to pass                              |
| 9 | backup      | kctl-dokploy   | Configure backup destination + schedule                   |
| 10 | schedules  | kctl-dokploy   | Set up cron jobs (vacuum, session cleanup, etc.)          |
| 11 | volume-backups | kctl-dokploy | Configure volume backup destinations                    |
| 12 | post-deploy | kctl-odoo      | Install Odoo bundles/profiles (for Odoo service types)    |

### Preflight Gates

The preflight phase runs 10 gates before any infrastructure changes:

| Gate          | Checks                                                      |
|---------------|-------------------------------------------------------------|
| `server`      | Dokploy API reachable, server exists in inventory           |
| `firewall`    | Required ports accessible                                   |
| `dns`         | DNS record exists and resolves correctly                    |
| `image_pull`  | Container image pullable from registry                      |
| `database`    | PostgreSQL credentials valid, DB server reachable           |
| `compose`     | Compose service in valid state (not mid-deploy)             |
| `env_sync`    | OIDC and required env vars present in env file              |
| `source`      | Git source branch/ref accessible                            |
| `network`     | `dokploy-network` exists on target server                   |
| `ssl`         | SSL certificate valid and not near expiry                   |

### Manifest Format

Manifests follow the `{tenant}-{stack}-{app}.yaml` naming convention:

```yaml
# deploys/instances/production/mac-react-sfa.yaml
extends: bases/react-pwa.yaml

instance:
  name: mac-react-sfa

type: react-pwa
project: mac
server: mac-prod-01

domain:
  host: sfa.mandiriagro.com

healthcheck:
  path: /
  expected_status: 200

env_file: deploys/env/production/mac-react-sfa.env
```

## Global Options

```
--json                Output as JSON (machine-readable)
--quiet, -q           Suppress informational messages
--format, -f          Output format: pretty, json, csv, yaml
--no-header           Omit headers in CSV output
--debug               Enable debug logging
--profile, -p         Use a named config profile
--url                 Dokploy API URL override
--api-key             API key override
--version, -V         Show version and exit
```

## Command Aliases

Hidden short aliases are available for common operations:

| Alias | Expands to                |
|-------|---------------------------|
| `cl`  | `compose list`            |
| `cs`  | `compose start <id>`      |
| `cr`  | `compose redeploy <id>`   |
| `sl`  | `servers list`            |
| `pl`  | `projects list`           |
| `ds`  | `dashboard show`          |
| `dg`  | `diagnose run`            |
| `dl`  | `deployments list`        |
| `bl`  | `backups list`            |

Example:

```bash
kctl-dokploy cl                   # same as: kctl-dokploy compose list
kctl-dokploy cr OEK_dJRQZZMo9HKbQ  # same as: kctl-dokploy compose redeploy <id>
```

## Configuration

### Profiles

kctl-dokploy supports named profiles for managing multiple Dokploy instances:

```bash
# Create a profile (interactive)
kctl-dokploy config init

# Add a profile manually
kctl-dokploy config add production \
  --url https://dokploy.kodeme.io \
  --api-key $DOKPLOY_API_KEY

# Add a staging profile
kctl-dokploy config add staging \
  --url https://dokploy-stg.kodeme.io \
  --api-key $DOKPLOY_STAGING_KEY

# Switch default profile
kctl-dokploy config use production

# Use per-command
kctl-dokploy --profile staging compose list

# List all profiles
kctl-dokploy config profiles

# Show current profile (secrets masked)
kctl-dokploy config show
```

### Config File

Configuration is stored in `~/.config/kodemeio/config.yaml` under the `dokploy` service key, shared with all other kctl-* CLIs.

```yaml
# ~/.config/kodemeio/config.yaml (example shape)
profiles:
  default: production
  production:
    dokploy:
      url: https://dokploy.kodeme.io
      api_key: ${DOKPLOY_API_KEY}   # env var expansion supported
```

## Shell Completions

```bash
# Generate and install for your shell
kctl-dokploy --install-completion bash
kctl-dokploy --install-completion zsh
kctl-dokploy --install-completion fish

# Or use the skill subcommand
kctl-dokploy skill completions install
```

## Plugin Development

kctl-dokploy supports extending the CLI via Python entry points. Create a package that registers a Typer app under the `kctl_dokploy.plugins` entry point group:

```toml
# In your plugin's pyproject.toml
[project.entry-points."kctl_dokploy.plugins"]
my_plugin = "my_plugin.cli:app"
```

The plugin's `app` (a `typer.Typer` instance) will be registered as a command group automatically on startup.

## Development

### Running Tests

```bash
cd packages/kctl-dokploy
uv run pytest tests/ -v
```

### Linting and Formatting

```bash
cd packages/kctl-dokploy
uv run ruff check src/
uv run ruff format src/
```

### Type Checking

```bash
cd packages/kctl-dokploy
uv run mypy src/kctl_dokploy/
```

### Project Structure

```
packages/kctl-dokploy/
  src/kctl_dokploy/
    cli.py                  Main app + command group registration
    __init__.py             Version (0.3.5)
    core/
      callbacks.py          Global option handling (AppContext)
      api_client.py         HTTP client wrapping kctl-lib APIClient
      deployer.py           13-phase Deployer class
      manifest.py           DeployManifest Pydantic model + YAML loader
      preflight.py          Preflight gate runner
      troubleshoot.py       Deployment diagnosis engine
      deploy_validators.py  Pre/post deploy validators
    commands/
      aliases.py            Short command aliases
      deploy.py             Declarative deployment pipeline
      compose.py            Compose service management
      servers.py            Server management
      projects.py           Project management
      diagnose.py           Diagnostic commands
      ...                   (30+ command modules)
  tests/                    pytest test suite
  pyproject.toml            Package metadata and tool config
  README.md                 This file
```

### Workspace Commands

From the monorepo root:

```bash
# Install all workspace packages
uv sync --all-extras --all-packages

# Run kctl-dokploy tests only
uv run pytest packages/kctl-dokploy/tests/ -v

# Lint all packages
uv run ruff check packages/*/src/
```
