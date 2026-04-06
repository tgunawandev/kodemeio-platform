# kctl-zulip

Kodemeio CLI for managing Zulip team chat instances. Part of the
[kodemeio-platform](../../) monorepo (22nd CLI tool).

Manage streams, users, messages, emoji, presence, invitations, and more
from the command line with profile-based multi-instance support.

## Installation

```bash
# From workspace root (development)
uv sync --all-extras --all-packages

# Standalone install
uv tool install ./packages/kctl-zulip
```

## Quick Start

```bash
# 1. Configure a profile
kctl-zulip config init

# 2. Check server health
kctl-zulip health check

# 3. List users
kctl-zulip users list

# 4. List streams
kctl-zulip streams list

# 5. Send a message
kctl-zulip messages send --stream general --topic "Hello" --content "Hi from kctl-zulip!"
```

## Command Groups

kctl-zulip provides 22 command groups organized into five panels.

### Admin & Config

| Group | Description |
|-------|-------------|
| `config` | Profile management (init, add, use, show, validate, remove, set, profiles, current) |
| `users` | User administration (list, get, create, deactivate, reactivate, update) |
| `groups` | User group management (list, get, create, delete, add-members, remove-members) |
| `realm` | Realm/organization settings (get, update, get-emoji, upload-emoji) |
| `invitations` | Invite management (list, send, resend, revoke) |

### Messaging

| Group | Description |
|-------|-------------|
| `messages` | Send, fetch, search, edit, delete, and flag messages |
| `streams` | Stream CRUD, subscribe, unsubscribe, archive |
| `topics` | Topic listing, resolution, and deletion |
| `announce` | Broadcast announcements to streams |
| `drafts` | Draft message management (list, create, edit, delete) |
| `scheduled` | Scheduled message management (list, create, delete) |

### Personalization

| Group | Description |
|-------|-------------|
| `emoji` | Custom emoji management (list, upload, delete) |
| `reactions` | Message reaction management (add, remove, get) |
| `presence` | User presence/status (get, set, list) |
| `muted` | Muted users and topics (list, add, remove) |
| `alert-words` | Alert word management (list, add, remove) |
| `profile-fields` | Custom profile field management (list, create, update, delete, reorder) |
| `linkifiers` | Linkifier/regex pattern management (list, create, update, delete) |

### Monitoring

| Group | Description |
|-------|-------------|
| `health` | Server health checks and connectivity verification |
| `dashboard` | Overview dashboard with server stats |

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
| `--email` | | Auth email override |
| `--api-key` | | API key override |
| `--version` | `-V` | Show version and exit |

## Configuration

kctl-zulip uses the shared Kodemeio config framework at
`~/.config/kodemeio/config.yaml` with service key `zulip`.

### Profile Setup

```bash
# Interactive setup
kctl-zulip config init

# Manual profile
kctl-zulip config add production \
  --set url=https://zulip.kodeme.io \
  --set email=bot@kodeme.io \
  --set api_key=YOUR_API_KEY

# Switch profiles
kctl-zulip config use production
kctl-zulip config current
kctl-zulip config profiles
```

### Multi-Instance Support

Each profile can target a different Zulip instance. Use `--profile` to
override the active profile for a single command:

```bash
kctl-zulip --profile staging health check
kctl-zulip --profile production users list --json
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `KCTL_ZULIP_URL` | Zulip server URL |
| `KCTL_ZULIP_EMAIL` | Bot email address |
| `KCTL_ZULIP_API_KEY` | Bot API key |
| `KCTL_ZULIP_PROFILE` | Default profile name |

Environment variables override config file values. CLI flags (`--url`,
`--email`, `--api-key`) take highest precedence.

## Shell Completions

```bash
# Generate completion script
kctl-zulip completions zsh

# Install completions (writes to shell config dir)
kctl-zulip completions zsh --install
kctl-zulip completions bash --install
kctl-zulip completions fish --install
```

See [docs/completions.md](docs/completions.md) for detailed instructions.

## E2E Testing (Playwright)

The `e2e/` directory contains Playwright-based API tests for verifying
connectivity against a live Zulip instance.

```bash
cd packages/kctl-zulip/e2e
pnpm install
ZULIP_URL=https://zulip.kodeme.io npx playwright test
npx playwright show-report
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
packages/kctl-zulip/
├── src/kctl_zulip/
│   ├── cli.py              # Main Typer app + command registration
│   ├── core/               # Shared core (callbacks, client, config)
│   └── commands/           # 22 command group modules
├── tests/                  # pytest unit tests (58 tests)
├── e2e/                    # Playwright E2E tests
├── docs/                   # Additional documentation
├── skills/                 # SKILL.md for Claude Code
└── pyproject.toml          # Package metadata
```

## License

Internal -- Kodemeio Pte Ltd.
