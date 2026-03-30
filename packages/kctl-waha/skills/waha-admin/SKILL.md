---
name: waha-admin
description: >
  WAHA (WhatsApp HTTP API) administration via kctl-waha CLI. MUST use for ANY WhatsApp session, message sending, webhook, or bridge configuration task. Triggers on: "kctl-waha", "waha", "whatsapp", "WA session", "send whatsapp", "whatsapp webhook", "chatwoot whatsapp", or ANY WhatsApp integration task.
version: 1.0.0
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Glob
  - Grep
---

# WAHA Administration

## Managed Instances

kctl-waha supports multiple WAHA instances via profiles:

| Profile | URL | Use |
|---|---|---|
| `kodemeio` | https://waha.kodeme.io | Kodemeio WhatsApp API |

```bash
# Target a specific instance
kctl-waha -p kodemeio sessions list
kctl-waha -p kodemeio health

# Switch default profile
kctl-waha config use kodemeio
```

Config: `~/.config/kodemeio/config.yaml`

## CLI Tool: kctl-waha

Installed globally via `uv tool install ./cli`. Run `kctl-waha` from anywhere.

### Global Options

```bash
kctl-waha [--json] [--quiet] [--profile NAME] [--url URL] [--api-key KEY] [--bridge-url URL] <command>
```

- `--profile / -p`: target a specific instance
- `--url`: override WAHA API URL (port 3000)
- `--api-key`: override WAHA API key
- `--bridge-url`: override bridge URL (port 3050)
- `--json`: output as JSON
- `--quiet / -q`: suppress info messages

## Multi-Instance Management

```bash
kctl-waha config init                                              # Interactive setup
kctl-waha config add <name> --url <url> [--api-key KEY] [--bridge-url URL]  # Add profile
kctl-waha config use <name>                                        # Switch default
kctl-waha config remove <name> [--service-only] [--force]          # Remove profile
kctl-waha config profiles                                          # List all with status
kctl-waha config current                                           # Show active + connection
kctl-waha config show                                              # Full config (masked)
kctl-waha config set <key> <value>                                 # Edit config
kctl-waha config test                                              # Test connection
kctl-waha config migrate                                           # Migrate format
```

## Health & Dashboard

```bash
kctl-waha health [--watch] [--interval 10]                         # Health score (0-100)
kctl-waha dashboard [--watch] [--interval 10] [--compact]          # System overview
```

Health scoring: WAHA health (30pts) + active sessions (30pts) + version (20pts) + bridge health (20pts).

## Session Management

```bash
kctl-waha sessions list [--all]                                    # List sessions (active or all)
kctl-waha sessions get <name>                                      # Session details
kctl-waha sessions start <name> [--engine NOWEB|WEBJS]             # Create/start session
kctl-waha sessions stop <name>                                     # Stop session (keeps auth)
kctl-waha sessions restart <name>                                  # Restart session
kctl-waha sessions logout <name> [--force]                         # Logout WhatsApp
kctl-waha sessions delete <name> [--force]                         # Delete session permanently
kctl-waha sessions qr <name>                                       # Get QR code for auth
kctl-waha sessions me <name>                                       # Authenticated account info
```

Session statuses: WORKING, STOPPED, SCAN_QR_CODE, STARTING, FAILED.

## Message Sending

```bash
kctl-waha messages send <phone> <text> [--session default]         # Send text message
kctl-waha messages send-image <phone> <url> [--caption] [--session default]  # Send image
```

Phone number auto-formatting: `+6281234567890` → `6281234567890@c.us`

## Webhook Configuration

```bash
kctl-waha webhooks list                                            # Show per-session webhook config
kctl-waha webhooks set <session> --url URL [--events msg,ack] [--hmac-key KEY]  # Configure
```

Available events: message, message.any, message.ack, session.status, group.v2.join, presence.update, call.received.

## Bridge Integration

The bridge (Node.js sidecar, port 3050) connects WAHA to Chatwoot and Odoo:

```bash
kctl-waha bridge health                                            # Bridge health check
kctl-waha bridge status                                            # Bridge config status
kctl-waha bridge setup-chatwoot [--name] [--callback-url]          # Create Chatwoot inbox
kctl-waha bridge setup-webhook [--session] [--webhook-url]         # Configure WAHA webhook → bridge
```

## Architecture

- **WAHA Server** (devlikeapro/waha-plus) — WhatsApp HTTP API, port 3000
- **Bridge** (Node.js + Hono) — Chatwoot/Odoo integration, port 3050
- **PostgreSQL** — Session persistence
- **Redis** — Message deduplication, BullMQ queue

### Anti-Detection System

4-layer defense for WhatsApp account safety:
1. Rate limiting (30-60s delay, max 200 msgs/day)
2. Human-like workflow (seen → typing → delay → send)
3. Residential proxy (never datacenter)
4. 21-day warm-up schedule

### Data Flows

- **Incoming**: WhatsApp → WAHA → bridge → Chatwoot (agents see message)
- **Outgoing**: Chatwoot reply → bridge → anti-detection → WAHA → WhatsApp
- **ERP**: Odoo → WAHA → WhatsApp (orders, invoices)

## API Structure

**WAHA API** (port 3000):
- Sessions: GET/POST/PUT/DELETE /api/sessions/
- Messages: POST /api/sendText, /api/sendImage
- Auth: `X-Api-Key` header

**Bridge API** (port 3050):
- Health: GET /health
- Setup: GET /setup/status, POST /setup/chatwoot-inbox, POST /setup/waha-webhook

## Troubleshooting

```bash
# Check full system health
kctl-waha health

# Check if sessions are connected
kctl-waha sessions list --all

# Get QR code for new session
kctl-waha sessions qr default

# Check bridge connectivity
kctl-waha bridge health

# JSON output for debugging
kctl-waha --json sessions list | jq .
```
