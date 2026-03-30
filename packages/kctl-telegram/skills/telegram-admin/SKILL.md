---
name: telegram-admin
description: >
  Kodemeio Telegram bot platform administration. Supports multiple instances
  via profiles. Covers multi-bot management, group tracking, message sending/
  broadcasting/scheduling, Chatwoot inbox integration, health monitoring,
  and dashboard overview. Use when working with kctl-telegram CLI or managing
  the kodemeio-telegram FastAPI service.
version: 1.0.0
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Glob
  - Grep
---

# Telegram Administration

## Managed Instances

kctl-telegram supports multiple instances via profiles:

| Profile | URL | Use |
|---|---|---|
| `kodemeio` | https://telegram.kodeme.io | Kodemeio notification bots |

```bash
# Target a specific instance
kctl-telegram -p kodemeio bots list
kctl-telegram -p kodemeio health

# Switch default profile
kctl-telegram config use kodemeio
```

Config: `~/.config/kodemeio/config.yaml`

## CLI Tool: kctl-telegram

Installed globally via `uv tool install ./cli`. Run `kctl-telegram` from anywhere.

### Global Options

```bash
kctl-telegram [--json] [--quiet] [--profile NAME] [--url URL] [--api-key KEY] <command>
```

- `--profile / -p`: target a specific instance
- `--url`: override API base URL
- `--api-key`: override API key
- `--json`: output as JSON (for scripting/piping)
- `--quiet / -q`: suppress info messages

## Multi-Instance Management

```bash
kctl-telegram config init                                          # Interactive setup
kctl-telegram config add <name> --url <url> [--api-key KEY]        # Add/update profile
kctl-telegram config use <name>                                    # Switch default
kctl-telegram config remove <name> [--service-only] [--force]      # Remove profile
kctl-telegram config profiles                                      # List all with status
kctl-telegram config current                                       # Show active + connection
kctl-telegram config show                                          # Full config (masked)
kctl-telegram config set <key> <value>                             # Edit config
kctl-telegram config test                                          # Test connection
kctl-telegram config migrate                                       # Migrate flat -> scoped format
```

## Health & Dashboard

```bash
kctl-telegram health [--watch] [--interval 10]                     # Health score (0-100)
kctl-telegram dashboard [--watch] [--interval 10] [--compact]      # System overview
```

Health scoring: API health (30pts) + readiness (30pts) + bots exist (20pts) + groups exist (20pts).

## Bot Management

```bash
kctl-telegram bots list                                            # All registered bots
kctl-telegram bots get <id>                                        # Bot details
kctl-telegram bots add --token <BOT_TOKEN> [--display-name NAME]   # Register new bot
kctl-telegram bots update <id> [--display-name] [--is-active]      # Update bot
kctl-telegram bots remove <id> [--force]                           # Deactivate bot
```

## Group Management

```bash
kctl-telegram groups list                                          # All tracked groups
kctl-telegram groups get <id>                                      # Group details
kctl-telegram groups update <id> --field <f> --value <v>           # Update group settings
```

## Message Operations

```bash
kctl-telegram messages send --chat-id ID --text "msg" [--bot-id] [--parse-mode]   # Send message
kctl-telegram messages broadcast --text "msg" [--bot-id] [--parse-mode]            # Broadcast to all groups
kctl-telegram messages schedule --text "msg" --target-id ID --at "ISO" [--bot-id]  # Schedule
kctl-telegram messages scheduled                                                    # List pending
kctl-telegram messages cancel <id>                                                  # Cancel scheduled
```

## Chatwoot Integration

```bash
kctl-telegram chatwoot list                                        # List Chatwoot inboxes
kctl-telegram chatwoot add --bot-id ID --inbox-id ID --base-url URL --api-token TK  # Add inbox
kctl-telegram chatwoot remove <id> [--force]                       # Remove inbox mapping
```

## API Structure

The CLI talks to the kodemeio-telegram FastAPI service:

- **Base URL**: `https://telegram.kodeme.io/api/v1`
- **Auth**: `X-Api-Key` header
- **Resources**: bots, groups, messages, chatwoot/inboxes
- **Health**: GET /api/v1/health, GET /api/v1/ready

## Architecture

- **FastAPI** + python-telegram-bot (multi-bot, webhook mode)
- **PostgreSQL** (shared via kodemeio-postgres-16)
- **Redis** (rate limiting, caching)
- **BotManager** orchestrates multiple bots
- **APScheduler** for scheduled messages
- **Chatwoot/Odoo** integrations via webhook relay

## Troubleshooting

```bash
# Check health
kctl-telegram health

# Watch health continuously
kctl-telegram health --watch

# Test connection
kctl-telegram config test

# Check bot status
kctl-telegram bots list

# JSON output for debugging
kctl-telegram --json bots list | jq .
```
