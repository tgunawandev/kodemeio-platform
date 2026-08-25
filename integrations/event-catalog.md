# Event Catalog

All events that flow through the Kodemeio integration layer, organized by domain.
Each entry includes the event name as it appears in Redis Streams (the canonical form),
its source, a brief payload description, and which consumers handle it.

Last updated: 2026-04-03

---

## Notation

- **Stream event** — the string written to Redis Streams by the dispatcher
- **Source** — the service that produces the event
- **Payload** — key fields in the JSON body (abbreviated; see source code for full schema)
- **Consumers** — services or handlers that process the event

---

## Domain: Approvals

Events from Odoo's tier-validation workflow. These are handled synchronously by the
`odoo-mm` FastAPI app — they do not go through Redis Streams.

### validation_requested

| Field | Value |
|-------|-------|
| Odoo event name | `validation_requested` |
| Source addon | `mattermost_integration` |
| Inbound route | `POST /webhooks/odoo-mm` |
| Consumers | `odoo-mm` → Mattermost DM to each reviewer |

**Payload (abbreviated):**
```json
{
  "event": "validation_requested",
  "model": "purchase.order",
  "record_id": 142,
  "display_name": "PO/2026/00042",
  "record_url": "https://erp.kodeme.io/web#id=142&model=purchase.order",
  "database": "kodemeio_prod",
  "requester": { "name": "Budi Santoso", "email": "budi@example.com" },
  "reviewers": [
    { "name": "Ani Wijaya", "email": "ani@example.com" }
  ],
  "extra_data": {}
}
```

### validation_approved

| Field | Value |
|-------|-------|
| Odoo event name | `validation_approved` |
| Source addon | `mattermost_integration` |
| Inbound route | `POST /webhooks/odoo-mm` |
| Consumers | `odoo-mm` → Mattermost channel notification |

**Payload (abbreviated):**
```json
{
  "event": "validation_approved",
  "model": "purchase.order",
  "record_id": 142,
  "display_name": "PO/2026/00042",
  "record_url": "https://erp.kodeme.io/web#id=142&model=purchase.order",
  "database": "kodemeio_prod",
  "requester": { "name": "Budi Santoso", "email": "budi@example.com" },
  "all_reviews": [
    { "reviewer": "Ani Wijaya", "status": "approved", "note": "" }
  ],
  "extra_data": {}
}
```

### validation_rejected

Same structure as `validation_approved` with `"event": "validation_rejected"`.
The `extra_data` field typically contains the rejection reason entered via the
Mattermost dialog.

### validation_restarted

Same structure as `validation_approved` with `"event": "validation_restarted"`.
Fired when a requester resets the validation cycle.

---

## Domain: Sales

Events from the Odoo sales and order management modules.

### odoo.order.created

| Field | Value |
|-------|-------|
| Stream event | `odoo.order.created` |
| Source | Odoo `base_webhook` addon, model `sale.order` |
| Inbound route | `POST /webhooks/odoo` |
| Consumers | `events-sync` → Mattermost or Telegram notification |

**Payload (abbreviated):**
```json
{
  "event": "confirmed",
  "model": "sale.order",
  "record_id": 56,
  "database": "kodemeio_prod",
  "data": {
    "name": "S00056",
    "partner_id": [12, "PT Mandiri Agro"],
    "amount_total": 4500000.0,
    "currency_id": [14, "IDR"],
    "date_order": "2026-04-03T09:15:00",
    "user_id": [3, "Sales User"]
  }
}
```

**Consumers:**
- `events-sync` handler `handle_odoo_order_created` — logs and can trigger downstream sync
- `telegram_integration` addon — direct call to Telegram Bot API via `base_webhook`
- `whatsapp_integration` addon — WhatsApp confirmation via WAHA

### odoo.invoice.paid

| Field | Value |
|-------|-------|
| Stream event | `odoo.invoice.paid` |
| Source | Odoo `base_webhook` addon, model `account.move` |
| Inbound route | `POST /webhooks/odoo` |
| Consumers | `events-sync` → notification handlers |

**Payload (abbreviated):**
```json
{
  "event": "paid",
  "model": "account.move",
  "record_id": 211,
  "database": "kodemeio_prod",
  "data": {
    "name": "INV/2026/0042",
    "partner_id": [12, "PT Mandiri Agro"],
    "amount_total": 4500000.0,
    "currency_id": [14, "IDR"],
    "invoice_date": "2026-04-02",
    "invoice_date_due": "2026-05-02"
  }
}
```

---

## Domain: Inventory / Warehouse

Events from Odoo stock and warehouse operations.

### odoo.stock.moved

| Field | Value |
|-------|-------|
| Stream event | `odoo.stock.moved` |
| Source | Odoo `base_webhook` addon, model `stock.picking` |
| Inbound route | `POST /webhooks/odoo` |
| Consumers | `events-sync` handler `handle_odoo_stock_moved` |

**Payload (abbreviated):**
```json
{
  "event": "done",
  "model": "stock.picking",
  "record_id": 88,
  "database": "kodemeio_prod",
  "data": {
    "name": "WH/OUT/00088",
    "origin": "S00056",
    "state": "done",
    "location_id": [5, "WH/Stock"],
    "location_dest_id": [8, "Partners/Customers"],
    "move_ids": [
      { "product_id": [7, "Product A"], "product_uom_qty": 10.0 }
    ]
  }
}
```

**Consumers:**
- `events-sync` handler — logs move, can notify warehouse team
- `whatsapp_integration` — optional delivery notification to customer

---

## Domain: HR & Payroll

Events from Odoo HR modules. These travel via the `base_webhook` generic path.

### odoo.hr.employee.created

| Field | Value |
|-------|-------|
| Stream event | `odoo.hr.employee.created` |
| Source | Odoo `base_webhook` addon, model `hr.employee` |
| Inbound route | `POST /webhooks/odoo` |
| Consumers | Downstream HR sync (planned) |

**Payload (abbreviated):**
```json
{
  "event": "created",
  "model": "hr.employee",
  "record_id": 31,
  "database": "kodemeio_prod",
  "data": {
    "name": "Dewi Rahayu",
    "department_id": [4, "Engineering"],
    "job_id": [9, "Backend Developer"],
    "work_email": "dewi@example.com"
  }
}
```

### odoo.hr.leave.approved

| Field | Value |
|-------|-------|
| Stream event | `odoo.hr.leave.approved` |
| Source | Odoo `base_webhook` addon, model `hr.leave` |
| Inbound route | `POST /webhooks/odoo` |
| Consumers | Telegram notification to employee |

**Payload (abbreviated):**
```json
{
  "event": "approved",
  "model": "hr.leave",
  "record_id": 14,
  "database": "kodemeio_prod",
  "data": {
    "employee_id": [31, "Dewi Rahayu"],
    "holiday_status_id": [2, "Annual Leave"],
    "date_from": "2026-04-10",
    "date_to": "2026-04-11",
    "number_of_days": 2.0
  }
}
```

---

## Domain: DevOps / CI

Events from GitHub via `webhook-github` FastAPI app.

### github.push

| Field | Value |
|-------|-------|
| Stream event | `github.push` |
| Source | GitHub repository webhook |
| GitHub header | `X-GitHub-Event: push` |
| Inbound route | `POST /webhooks/github` |
| Consumers | Mattermost `#dev-notifications` (planned) |

**Payload (abbreviated):**
```json
{
  "ref": "refs/heads/main",
  "before": "abc123",
  "after": "def456",
  "repository": { "full_name": "tgunawandev/kodemeio-dokploy" },
  "pusher": { "name": "tgunawan" },
  "commits": [
    {
      "id": "def456",
      "message": "feat(deploy): add new instance manifest",
      "author": { "name": "Tri Gunawan" },
      "modified": ["deploys/instances/example.yaml"]
    }
  ]
}
```

### github.pull_request

| Field | Value |
|-------|-------|
| Stream event | `github.pull_request` |
| GitHub header | `X-GitHub-Event: pull_request` |
| Inbound route | `POST /webhooks/github` |
| Consumers | Mattermost `#dev-notifications`, Linear sync (planned) |

**Payload (abbreviated):**
```json
{
  "action": "opened",
  "number": 47,
  "pull_request": {
    "title": "feat: add webhook catalog",
    "html_url": "https://github.com/tgunawandev/kodemeio-dokploy/pull/47",
    "state": "open",
    "user": { "login": "tgunawan" },
    "base": { "ref": "main" },
    "head": { "ref": "feat/webhook-catalog" }
  },
  "repository": { "full_name": "tgunawandev/kodemeio-dokploy" }
}
```

### github.workflow_run

| Field | Value |
|-------|-------|
| Stream event | `github.workflow_run` |
| GitHub header | `X-GitHub-Event: workflow_run` |
| Inbound route | `POST /webhooks/github` |
| Consumers | Telegram alert on failure, Mattermost `#ci-alerts` |

**Payload (abbreviated):**
```json
{
  "action": "completed",
  "workflow_run": {
    "name": "CI",
    "conclusion": "failure",
    "html_url": "https://github.com/org/repo/actions/runs/1234",
    "head_branch": "main",
    "run_number": 88
  },
  "repository": { "full_name": "tgunawandev/kodemeio-dokploy" }
}
```

### github.issues

| Field | Value |
|-------|-------|
| Stream event | `github.issues` |
| GitHub header | `X-GitHub-Event: issues` |
| Inbound route | `POST /webhooks/github` |
| Consumers | Linear sync (planned) |

**Payload (abbreviated):**
```json
{
  "action": "opened",
  "issue": {
    "number": 12,
    "title": "Webhook signature validation fails on large payloads",
    "html_url": "https://github.com/org/repo/issues/12",
    "user": { "login": "contributor" },
    "labels": [{ "name": "bug" }]
  }
}
```

### github.release

| Field | Value |
|-------|-------|
| Stream event | `github.release` |
| GitHub header | `X-GitHub-Event: release` |
| Inbound route | `POST /webhooks/github` |
| Consumers | Mattermost `#releases`, deployment pipeline trigger |

**Payload (abbreviated):**
```json
{
  "action": "published",
  "release": {
    "tag_name": "v0.5.0",
    "name": "kctl-lib v0.5.0",
    "html_url": "https://github.com/org/repo/releases/tag/v0.5.0",
    "body": "## Changelog\n- feat: new module"
  }
}
```

---

## Domain: Project Management

Events from Plane project management via `plane-mm` and `webhook-plane` FastAPI apps.

### plane.issue.created

| Field | Value |
|-------|-------|
| Stream event | `plane.issue.created` |
| Source | Plane workspace webhook |
| Plane event | `event: issue, action: created` |
| Inbound routes | `POST /webhooks/plane-mm` (sync → MM), `POST /webhooks/plane` (async → stream) |
| Consumers | Mattermost subscribed channel(s) for the project |

**Payload (abbreviated):**
```json
{
  "event": "issue",
  "action": "created",
  "data": {
    "id": "uuid-of-issue",
    "name": "Implement webhook catalog documentation",
    "priority": "medium",
    "state": "Todo",
    "project": "uuid-of-project",
    "created_by": "uuid-of-user"
  }
}
```

### plane.issue.updated

Same structure as `plane.issue.created` with `"action": "updated"`. The `data` object
includes `updated_attributes` keys that changed.

### plane.issue.deleted

Same structure with `"action": "deleted"`. Only `id` and `project` are guaranteed present.

### plane.comment.created

| Field | Value |
|-------|-------|
| Stream event | `plane.comment.created` |
| Source | Plane workspace webhook |
| Plane event | `event: comment, action: created` |
| Consumers | Mattermost subscribed channels |

**Payload (abbreviated):**
```json
{
  "event": "comment",
  "action": "created",
  "data": {
    "id": "uuid-of-comment",
    "comment_html": "<p>This looks good.</p>",
    "issue": "uuid-of-issue",
    "project": "uuid-of-project",
    "actor": "uuid-of-user"
  }
}
```

---

## Domain: Customer Support

Events from Chatwoot via `webhook-chatwoot` FastAPI app.

### chatwoot.message.created

| Field | Value |
|-------|-------|
| Stream event | `chatwoot.message.created` |
| Source | Chatwoot account webhook |
| Chatwoot event | `message_created` |
| Inbound route | `POST /webhooks/chatwoot` |
| Consumers | Odoo helpdesk ticket creation (planned) |

**Payload (abbreviated):**
```json
{
  "event": "message_created",
  "id": 501,
  "content": "Hello, I need help with my order.",
  "message_type": "incoming",
  "conversation": {
    "id": 88,
    "status": "open",
    "inbox_id": 2
  },
  "sender": {
    "id": 34,
    "name": "Customer Name",
    "email": "customer@example.com",
    "phone_number": "+6281234567890"
  },
  "account": { "id": 1, "name": "Kodemeio Support" }
}
```

### chatwoot.conversation.created

| Field | Value |
|-------|-------|
| Stream event | `chatwoot.conversation.created` |
| Chatwoot event | `conversation_created` |
| Inbound route | `POST /webhooks/chatwoot` |
| Consumers | Odoo lead/ticket sync, team notification |

**Payload (abbreviated):**
```json
{
  "event": "conversation_created",
  "id": 88,
  "status": "open",
  "inbox_id": 2,
  "meta": {
    "sender": { "name": "Customer Name", "email": "customer@example.com" },
    "channel": "Channel::Api"
  },
  "account": { "id": 1, "name": "Kodemeio Support" }
}
```

### chatwoot.conversation.status_changed

| Field | Value |
|-------|-------|
| Stream event | `chatwoot.conversation.status_changed` |
| Chatwoot event | `conversation_status_changed` |
| Inbound route | `POST /webhooks/chatwoot` |
| Consumers | Odoo helpdesk ticket status update |

**Payload (abbreviated):**
```json
{
  "event": "conversation_status_changed",
  "id": 88,
  "status": "resolved",
  "current_status": "open",
  "account": { "id": 1, "name": "Kodemeio Support" }
}
```

### chatwoot.contact.created

| Field | Value |
|-------|-------|
| Stream event | `chatwoot.contact.created` |
| Chatwoot event | `contact_created` |
| Inbound route | `POST /webhooks/chatwoot` |
| Consumers | Odoo partner sync (res.partner) |

**Payload (abbreviated):**
```json
{
  "event": "contact_created",
  "id": 34,
  "name": "Customer Name",
  "email": "customer@example.com",
  "phone_number": "+6281234567890",
  "account": { "id": 1 }
}
```

---

## Domain: Notifications (internal routing)

Generic notification events written to Redis Streams by any service and consumed
by `events-sync`. These are internal events, not externally sourced.

### notification.send

| Field | Value |
|-------|-------|
| Stream event | `notification.*` (any key where `channel` field is set) |
| Source | Any FastAPI app or consumer via dispatcher |
| Consumers | `events-sync` — routes to Mattermost or Telegram |

**Payload:**
```json
{
  "channel": "mattermost",
  "text": "Sale order S00056 confirmed for PT Mandiri Agro — IDR 4,500,000",
  "target": "CHANNEL_ID_OR_EMPTY"
}
```

```json
{
  "channel": "telegram",
  "text": "Invoice INV/2026/0042 paid. Amount: IDR 4,500,000",
  "target": "-100123456789"
}
```

---

## Event Type Index

| Stream event | Source | Consumer(s) |
|-------------|--------|-------------|
| `odoo.order.created` | Odoo sale.order | events-sync, telegram, whatsapp |
| `odoo.invoice.paid` | Odoo account.move | events-sync, whatsapp |
| `odoo.stock.moved` | Odoo stock.picking | events-sync |
| `odoo.hr.employee.created` | Odoo hr.employee | downstream HR sync |
| `odoo.hr.leave.approved` | Odoo hr.leave | telegram |
| `github.push` | GitHub | Mattermost #dev-notifications |
| `github.pull_request` | GitHub | Mattermost, Linear |
| `github.workflow_run` | GitHub | Telegram, Mattermost #ci-alerts |
| `github.issues` | GitHub | Linear |
| `github.release` | GitHub | Mattermost #releases |
| `plane.issue.created` | Plane | Mattermost subscribed channels |
| `plane.issue.updated` | Plane | Mattermost subscribed channels |
| `plane.issue.deleted` | Plane | Mattermost subscribed channels |
| `plane.comment.created` | Plane | Mattermost subscribed channels |
| `plane.cycle.created` | Plane | Mattermost subscribed channels |
| `plane.module.created` | Plane | Mattermost subscribed channels |
| `plane.project.created` | Plane | Mattermost subscribed channels |
| `chatwoot.message.created` | Chatwoot | Odoo helpdesk |
| `chatwoot.conversation.created` | Chatwoot | Odoo helpdesk |
| `chatwoot.conversation.status_changed` | Chatwoot | Odoo helpdesk |
| `chatwoot.contact.created` | Chatwoot | Odoo res.partner |
| `notification.*` (mattermost) | Any consumer | events-sync → Mattermost |
| `notification.*` (telegram) | Any consumer | events-sync → Telegram |

> Note: Approval events (`validation_requested`, `validation_approved`, etc.) are handled
> synchronously by `odoo-mm` and are not written to Redis Streams.
