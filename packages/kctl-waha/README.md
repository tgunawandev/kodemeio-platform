# kctl-waha

Kodemeio WAHA CLI - manage WhatsApp HTTP API sessions and messaging.

## Install

```bash
uv tool install ./cli
# or
pip install -e ./cli
```

## Quick Start

```bash
kctl-waha config init
kctl-waha health
kctl-waha dashboard
kctl-waha sessions list
```

## Commands

- `config` — Profile and connection management
- `health` — Health checks with scoring
- `dashboard` — System overview
- `sessions` — WhatsApp session lifecycle
- `messages` — Send text and image messages
- `webhooks` — Webhook configuration
- `bridge` — Chatwoot/Odoo bridge integration
