# Cross-Service Integrations

This directory documents all cross-service integrations in the Kodemeio platform. It is
reference documentation — nothing here is executable configuration or infrastructure.
The actual implementation lives in the source repositories listed below.

## Repository Map

| Repo | Integrations |
|------|--------------|
| `kodemeio-odoo` | FastAPI webhook apps (`odoo-mm`, `plane-mm`, `webhook-github`, `webhook-chatwoot`, `events-sync`); Odoo addons (`base_webhook`, `mattermost_integration`, `telegram_integration`, `whatsapp_integration`) |
| `kodemeio-dokploy` | kctl-* CLIs that drive service orchestration |

---

## Architecture Overview

Events flow through a two-layer pipeline:

```
External Source                Ingestion Layer                  Fanout / Consumers
──────────────                 ───────────────                  ──────────────────
Odoo (18)          ──HMAC──►  POST /webhooks/odoo        ──►  Redis Streams
GitHub             ──sig────►  POST /webhooks/github       ──►  Redis Streams
Chatwoot           ──HMAC──►  POST /webhooks/chatwoot     ──►  Redis Streams
Plane              ──HMAC──►  POST /webhooks/plane        ──►  Redis Streams
Mattermost         ──token─►  POST /webhooks/odoo-mm/*    ──►  Odoo API (action callbacks)
Mattermost         ──token─►  POST /webhooks/plane-mm/*   ──►  Plane API (reply sync)
```

```
Redis Streams  ──►  events-sync consumer group  ──►  Mattermost (incoming webhook)
                                                 ──►  Telegram Bot API
                                                 ──►  Internal DB writes
               ──►  odoo-mm consumer group     ──►  (async post-processing)
```

Every inbound webhook endpoint validates the request signature before touching the payload.
Failed signature checks return `401` immediately; the source is expected to retry.

---

## FastAPI Apps

All webhook apps live under `kodemeio-odoo/src/fastapi/apps/` and are deployed as
separate Docker containers via Dokploy.

### odoo-mm

Handles Odoo approval workflow events and Mattermost interactive callbacks.

**Inbound routes:**

| Method | Path | Source | Purpose |
|--------|------|--------|---------|
| POST | `/webhooks/odoo-mm` | Odoo `mattermost_integration` addon | Approval events (requested / approved / rejected / restarted) |
| POST | `/webhooks/odoo-mm/action` | Mattermost | Interactive button click (approve / reject) |
| POST | `/webhooks/odoo-mm/dialog` | Mattermost | Dialog form submission |
| POST | `/webhooks/odoo-mm/slash` | Mattermost | `/approval` slash command |
| POST | `/webhooks/odoo` | Odoo `base_webhook` | Generic Odoo event dispatch → Redis Streams |

**Outbound calls:**
- Mattermost API (DM to reviewers, channel notification on status change)
- Odoo JSON-RPC (read record details for approval context)

### plane-mm

Handles Plane project management events and bidirectional Mattermost sync.

**Inbound routes:**

| Method | Path | Source | Purpose |
|--------|------|--------|---------|
| POST | `/webhooks/plane-mm` | Plane | Issue events (created / updated / deleted / comment) |
| POST | `/webhooks/plane-mm/slash` | Mattermost | `/plane` slash command |
| POST | `/webhooks/plane-mm/reply` | Mattermost outgoing webhook | Thread replies → Plane comments |
| POST | `/webhooks/plane` | Plane | Generic Plane event dispatch → Redis Streams |

**Outbound calls:**
- Mattermost API (channel notifications, subscribed channels from Redis)
- Plane API (resolve project/issue for reply sync)

### webhook-github

Receives GitHub webhook events and dispatches to Redis Streams.

**Inbound routes:**

| Method | Path | Source | Purpose |
|--------|------|--------|---------|
| POST | `/webhooks/github` | GitHub | All repository events |

**Event types dispatched:**

| GitHub event | Stream event type |
|-------------|-------------------|
| `push` | `github.push` |
| `pull_request` | `github.pull_request` |
| `workflow_run` | `github.workflow_run` |
| `issues` | `github.issues` |
| `issue_comment` | `github.issue_comment` |
| `create` | `github.create` |
| `delete` | `github.delete` |
| `release` | `github.release` |

### webhook-chatwoot

Receives Chatwoot customer support events and dispatches to Redis Streams.

**Inbound routes:**

| Method | Path | Source | Purpose |
|--------|------|--------|---------|
| POST | `/webhooks/chatwoot` | Chatwoot | All account events |

**Event types dispatched:**

| Chatwoot event | Stream event type |
|---------------|-------------------|
| `message_created` | `chatwoot.message.created` |
| `message_updated` | `chatwoot.message.updated` |
| `conversation_created` | `chatwoot.conversation.created` |
| `conversation_status_changed` | `chatwoot.conversation.status_changed` |
| `conversation_assigned` | `chatwoot.conversation.assigned` |
| `contact_created` | `chatwoot.contact.created` |

### events-sync

Consumer service that reads from Redis Streams and fans out to notification channels.

**Handlers:**

| Event pattern | Action |
|--------------|--------|
| `notification.*` where `channel=mattermost` | Posts via Mattermost incoming webhook URL |
| `notification.*` where `channel=telegram` | Sends via Telegram Bot API |
| `odoo.order.created` | Syncs order to local DB / triggers downstream |
| `odoo.invoice.paid` | Records payment, can trigger notifications |
| `odoo.*.stock.moved` | Updates inventory records |
| `user.sync.*` | Creates or updates local user records |
| `data.export.*` | Processes export request |

---

## Odoo Addons

### base_webhook

Universal webhook infrastructure used by all other integration addons. Provides the
`webhook.endpoint` model with:
- Auth types: none, basic, bearer, api_key, oauth2
- Retry with exponential backoff
- Async processing via `queue_job`
- Full call log audit trail
- Jinja2 payload templating

Any addon can trigger a webhook by calling `env['webhook.endpoint'].send(payload)`.

### mattermost_integration

Depends on `base_webhook` and `base_tier_validation`. Fires on tier-validation lifecycle
events (requested, approved, rejected, restarted) and POSTs to the `odoo-mm` FastAPI
service at `/webhooks/odoo-mm`.

### telegram_integration

Sends Telegram notifications for business events: order confirmed, invoice posted, stock
moved, purchase approved. Configures notification rules and user mappings. Uses `base_webhook`
endpoints configured to call the Telegram Bot API directly or via the `events-sync` service.

### whatsapp_integration

Sends WhatsApp messages via WAHA (waha.kodeme.io) or Meta Cloud API using `base_webhook`
endpoints. Supports sale order confirmations, invoice delivery, and stock alerts.

### tpm_management_webhook

Bridge addon (`auto_install: True`) that adds webhook delivery to `tpm_management` when
`base_webhook` is present. Fires on TPM lifecycle events via `base_webhook` infrastructure.

---

## Adding a New Integration

### Step 1: Define the source event

Determine which service produces the event and what its webhook payload looks like.
Document the event in `event-catalog.md`.

### Step 2: Choose a delivery pattern

**Pattern A — Direct webhook (synchronous):**
Source calls a FastAPI endpoint → FastAPI calls destination API directly.
Use when the source requires an immediate HTTP response (e.g., Mattermost action callbacks).

**Pattern B — Stream dispatch (async):**
Source calls a FastAPI endpoint → FastAPI writes to Redis Streams → Consumer reads and acts.
Use for all other cases. Provides retry, backpressure, and fanout to multiple consumers.

### Step 3: Implement the FastAPI route

Add a new router to the appropriate FastAPI app or create a new app under
`kodemeio-odoo/src/fastapi/apps/<name>/`.

```python
router = APIRouter(prefix="/webhooks/<source>", tags=["<source>"])

@router.post("")
async def receive_webhook(request: Request, response: Response) -> dict:
    body = await request.body()
    # 1. Validate signature (see auth-methods.md)
    # 2. Parse payload
    # 3. Resolve event type
    # 4. dispatcher.dispatch(event_type, source, payload)
    return {"status": "ok", "event_type": event_type}
```

### Step 4: Configure the source

Register the webhook URL in the source service:
- **GitHub:** Repository → Settings → Webhooks → Add webhook
- **Plane:** Workspace → Settings → Webhooks → Add webhook
- **Chatwoot:** Account → Settings → Integrations → Webhooks
- **Odoo:** Technical → Webhook Endpoints → New

Set the secret and confirm the `Content-Type: application/json` header is sent.

### Step 5: Add a consumer (Pattern B only)

Register a handler in `events-sync` or the relevant consumer app:

```python
async def handle_my_event(event: dict[str, str]) -> None:
    ...

# In main.py subscription registration:
app.state.dispatcher.subscribe("myservice.event.type", handle_my_event)
```

### Step 6: Update this documentation

- Add the route to `webhook-routes.yaml`
- Add all events to `event-catalog.md`
- Document the auth method in `auth-methods.md` if it is new

---

## Related Documentation

- `webhook-routes.yaml` — Complete declarative route map
- `event-catalog.md` — All events organized by domain
- `auth-methods.md` — Authentication methods per integration
- `docs/service-map.md` — Service dependency graph and blast radius
- `docs/architecture.md` — Platform architecture overview
