# kctl-telegram

Kodemeio Telegram CLI - manage the multi-bot Telegram notification platform.

## Install

```bash
uv tool install ./cli
# or
pip install -e ./cli
```

## Quick Start

```bash
kctl-telegram config init
kctl-telegram health
kctl-telegram dashboard
kctl-telegram bots list
```

## Commands

- `config` — Profile and connection management
- `health` — Health checks with scoring
- `dashboard` — System overview
- `bots` — Bot CRUD operations
- `groups` — Group management
- `messages` — Send, broadcast, schedule messages
- `chatwoot` — Chatwoot inbox integration
