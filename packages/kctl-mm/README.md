# kctl-mm

Kodemeio CLI for managing Mattermost Team Edition instances. Part of the
[kodemeio-platform](../../) monorepo.

Manage users, teams, channels, posts, webhooks, bots, plugins, integrations,
and server operations from the command line with profile-based multi-instance
support.

## Installation

```bash
# From workspace root (development)
uv sync --all-extras --all-packages

# Standalone install
uv tool install ./packages/kctl-mm
```

## Quick Start

```bash
# 1. Configure a profile
kctl-mm config init

# 2. Check server health
kctl-mm health

# 3. List users
kctl-mm users list

# 4. List teams
kctl-mm teams list

# 5. List channels in a team
kctl-mm channels list --team kodemeio
```

## Command Groups

kctl-mm provides 24 command groups covering administration, messaging, server
operations, and integrations for Mattermost Team Edition.

### Admin & Config

| Group | Description |
|-------|-------------|
| `config` | Profile management (init, add, use, show, validate, remove, set, profiles, current) |
| `users` | User administration (list, get, create, deactivate, reactivate, update, reset-password) |
| `teams` | Team administration (list, get, create, update, delete, add-member, remove-member) |
| `channels` | Channel CRUD (list, get, create, update, delete, archive, add-member, remove-member) |
| `permissions` | Role & permission management (list, get, assign, revoke) |
| `mm-config` | Mattermost server config (show, get, set, patch, reload, diff) |

### Messaging

| Group | Description |
|-------|-------------|
| `posts` | Post management (create, get, update, delete, search, pin, unpin) |

### Server Ops

| Group | Description |
|-------|-------------|
| `status` | Server status and version info |
| `logs` | Fetch and stream server logs |
| `deploy` | Deploy / redeploy Mattermost stack |
| `health` | Health checks (ping, DB, cluster, connectivity) |
| `dashboard` | Overview dashboard with server stats |
| `maintenance` | Server maintenance (recycle DB, reload config, clear cache) |
| `jobs` | Background job management (list, get, cancel) |
| `audit` | Audit log queries |
| `import-export` | Bulk import / export (users, teams, channels, posts) |

### Integrations

| Group | Description |
|-------|-------------|
| `webhooks` | Incoming & outgoing webhook management |
| `bots` | Bot account management (list, create, update, disable, assign-owner) |
| `plugins` | Plugin management (list, install, enable, disable, remove, upload) |
| `integrations` | Slash commands & OAuth apps |

### Tools

| Group | Description |
|-------|-------------|
| `doctor` | Diagnostic checks (config, connectivity, auth, API version) |
| `self-update` | Check for PyPI updates and upgrade via `uv tool` |
| `completions` | Generate/install shell completions (zsh, bash, fish) |
| `skill` | Auto-generate SKILL.md from Typer introspection (hidden) |

## Global Options

| Option | Short | Description |
|--------|-------|-------------|
| `--json` | | Output as JSON (shortcut for `--format json`) |
| `--quiet` | `-q` | Suppress info messages |
| `--format` | `-f` | Output format: `pretty`, `json`, `csv`, `yaml` |
| `--no-header` | | Omit headers in CSV output |
| `--profile` | `-p` | Config profile name |
| `--url` | | API URL override |
| `--token` | | Personal access token override |
| `--version` | `-V` | Show version and exit |

## Configuration

kctl-mm uses the shared Kodemeio config framework at
`~/.config/kodemeio/config.yaml` with service key `mm`.

### Profile Schema Example

```yaml
mm:
  active_profile: production
  profiles:
    production:
      url: https://mm.kodeme.io
      token: ${MM_TOKEN}
      team: kodemeio
    staging:
      url: https://stg-mm.kodeme.io
      token: ${MM_STAGING_TOKEN}
      team: kodemeio
```

### Profile Setup

```bash
# Interactive setup
kctl-mm config init

# Manual profile
kctl-mm config add production \
  --url https://mm.kodeme.io \
  --token YOUR_PERSONAL_ACCESS_TOKEN

# Switch profiles
kctl-mm config use production
kctl-mm config current
kctl-mm config profiles
```

### Multi-Instance Support

Each profile can target a different Mattermost instance. Use `--profile` to
override the active profile for a single command:

```bash
kctl-mm --profile staging health
kctl-mm --profile production users list --json
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `KCTL_MM_URL` | Mattermost server URL |
| `KCTL_MM_TOKEN` | Personal access token |
| `KCTL_MM_PROFILE` | Default profile name |

Environment variables override config file values. CLI flags (`--url`,
`--token`) take highest precedence.

## Shell Completions

```bash
# Generate completion script
kctl-mm completions zsh

# Install completions (writes to shell config dir)
kctl-mm completions zsh --install
kctl-mm completions bash --install
kctl-mm completions fish --install
```

## Development

```bash
# Run tests
uv run pytest tests/ -v

# Lint
uv run ruff check src/

# Type check
uv run mypy src/

# Build
uv build
```

### Project Structure

```
packages/kctl-mm/
├── src/kctl_mm/
│   ├── cli.py              # Main Typer app + command registration (Task 4)
│   ├── core/               # Shared core (callbacks, client, config)
│   └── commands/           # 24 command group modules
├── tests/                  # pytest unit tests
└── pyproject.toml          # Package metadata
```

## References

- Design spec: [`docs/superpowers/specs/2026-04-13-kctl-mm-design.md`](../../docs/superpowers/specs/2026-04-13-kctl-mm-design.md)
- Skill directory: [`skills/mattermost-admin/`](../../skills/mattermost-admin/)

## License

Internal -- Kodemeio Pte Ltd.
