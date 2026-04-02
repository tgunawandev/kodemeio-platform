# Webhook Authentication Methods

Documents every authentication scheme used across Kodemeio platform integrations.
Each section covers how the method works, how it is verified in code, and how to
configure it for a new integration.

Last updated: 2026-04-03

---

## Summary Table

| Integration | Direction | Method | Header / Mechanism |
|-------------|-----------|--------|-------------------|
| Odoo → `/webhooks/odoo` | Inbound | HMAC-SHA256 | `X-Odoo-Webhook-Signature` |
| Odoo → `/webhooks/odoo-mm` | Inbound | Shared secret | `x-webhook-secret` (constant-time compare) |
| Mattermost → `/webhooks/odoo-mm/action` | Inbound | Mattermost integration token | Verified via MM bot token context |
| Mattermost → `/webhooks/odoo-mm/slash` | Inbound | Static slash token | `token` form field |
| Mattermost → `/webhooks/odoo-mm/dialog` | Inbound | Mattermost integration token | Verified via MM bot token context |
| Mattermost → `/webhooks/plane-mm/slash` | Inbound | Static slash token | `token` form field |
| Mattermost → `/webhooks/plane-mm/reply` | Inbound | Outgoing webhook token | `token` JSON field, constant-time compare |
| Plane → `/webhooks/plane-mm` | Inbound | HMAC-SHA256 | `X-Plane-Signature` |
| Plane → `/webhooks/plane` | Inbound | HMAC-SHA256 | `X-Plane-Signature` |
| GitHub → `/webhooks/github` | Inbound | HMAC-SHA256 (`sha256=` prefix) | `X-Hub-Signature-256` |
| Chatwoot → `/webhooks/chatwoot` | Inbound | HMAC-SHA256 | `X-Chatwoot-Signature` |
| `odoo-mm` → Mattermost API | Outbound | Bearer token | `Authorization: Bearer <MM_BOT_TOKEN>` |
| `plane-mm` → Mattermost API | Outbound | Bearer token | `Authorization: Bearer <MM_BOT_TOKEN>` |
| `plane-mm` → Plane API | Outbound | API key | `X-Api-Token: <PLANE_API_KEY>` |
| `events-sync` → Mattermost | Outbound | Incoming webhook URL | Token embedded in URL |
| `events-sync` → Telegram | Outbound | Bot token in URL | `https://api.telegram.org/bot<TOKEN>/sendMessage` |
| Odoo → WAHA (WhatsApp) | Outbound | API key header | `X-Api-Key: <WAHA_API_KEY>` |
| Odoo → Telegram Bot API | Outbound | Bearer token in URL | `https://api.telegram.org/bot<TOKEN>/...` |
| All services → Authentik OIDC | Outbound | OIDC / OAuth2 | Bearer JWT from auth.kodeme.io |
| kctl-* CLIs → service APIs | Outbound | API key / Bearer | Per-service, stored in `~/.config/kodemeio/config.yaml` |

---

## Method Details

### 1. HMAC-SHA256 (Generic)

Used by Odoo generic dispatch, Plane, and Chatwoot webhook endpoints.

**How it works:**
1. The source computes `HMAC-SHA256(raw_request_body, shared_secret)` and sends the
   hex digest in a request header.
2. FastAPI reads the raw body bytes before parsing JSON, recomputes the HMAC, and
   compares using `hmac.compare_digest` (constant-time to prevent timing attacks).
3. If the digest does not match, the endpoint returns `401` immediately.

**Verification function (from `kodemeio_webhook.verify`):**
```python
import hashlib
import hmac

def verify_hmac_sha256(body: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(
        secret.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
```

**Headers per integration:**

| Source | Header name | Value format |
|--------|-------------|-------------|
| Odoo `base_webhook` | `X-Odoo-Webhook-Signature` | raw hex digest |
| Plane | `X-Plane-Signature` | raw hex digest |
| Chatwoot | `X-Chatwoot-Signature` | raw hex digest |

**Environment variables:**

| App | Variable | Purpose |
|-----|----------|---------|
| `odoo-mm` | `WEBHOOK_SECRET_ODOO` | Validates inbound `/webhooks/odoo` |
| `plane-mm` | `WEBHOOK_SECRET_PLANE` | Validates inbound `/webhooks/plane` and `/webhooks/plane-mm` |
| `webhook-chatwoot` | `WEBHOOK_SECRET_CHATWOOT` | Validates inbound `/webhooks/chatwoot` |

**Configuration:**
- In Odoo, set the secret on the `webhook.endpoint` record (auth type: none; add the
  header manually via the Headers tab, or configure via `base_webhook` secret field).
- In Plane: Workspace → Settings → Webhooks → Secret.
- In Chatwoot: Account → Settings → Integrations → Webhooks → Secret token.

---

### 2. HMAC-SHA256 with sha256= prefix (GitHub)

GitHub uses the same HMAC-SHA256 algorithm but prefixes the hex digest with `sha256=`.

**Verification function:**
```python
def verify_github_signature(body: bytes, signature: str, secret: str) -> bool:
    if not signature.startswith("sha256="):
        return False
    received = signature[len("sha256="):]
    expected = hmac.new(
        secret.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, received)
```

**Header:** `X-Hub-Signature-256`

**Environment variable:** `WEBHOOK_SECRET_GITHUB` in the `webhook-github` app.

**Configuration:**
- GitHub: Repository → Settings → Webhooks → Add webhook
- Content type: `application/json`
- Secret: value of `WEBHOOK_SECRET_GITHUB`
- Events: select individual events or "Send me everything" for the generic dispatch route

---

### 3. Shared Secret (Odoo → odoo-mm approval endpoint)

Used specifically for the `mattermost_integration` addon calling `/webhooks/odoo-mm`.
This is a simpler constant-value secret rather than HMAC because the payload is small
and the endpoint is synchronous (no replay concern beyond the network).

**How it works:**
1. Odoo sends the secret value in the `x-webhook-secret` header.
2. FastAPI compares it using `hmac.compare_digest` against the configured value to
   prevent timing attacks.
3. Mismatch returns `401`.

```python
secret = request.headers.get("x-webhook-secret", "")
if not hmac.compare_digest(secret, settings.ODOO_MM_WEBHOOK_SECRET.get_secret_value()):
    response.status_code = 401
    return {"error": "Unauthorized"}
```

**Environment variable:** `ODOO_MM_WEBHOOK_SECRET` in the `odoo-mm` app.

**Configuration in Odoo:**
Set the same secret value in the `mattermost_integration` system parameter:
`ir.config_parameter` key `mattermost.webhook_secret`.

---

### 4. Static Slash Token (Mattermost slash commands)

Mattermost slash commands include a static token in the `token` form field to identify
the configured slash command. FastAPI verifies the token is in its allowlist.

**How it works:**
```python
secret_val = settings.MM_SLASH_TOKEN.get_secret_value()
tokens = [t.strip() for t in secret_val.split(",") if t.strip()]
if tokens:
    token = str(body.get("token", ""))
    if token not in tokens:
        return {"text": "Unauthorized"}
```

The value supports a comma-separated list so multiple Mattermost teams/instances can
share one endpoint.

**Environment variables:**
- `MM_SLASH_TOKEN` in `odoo-mm` — for the `/approval` slash command
- `MM_SLASH_TOKEN` in `plane-mm` — for the `/plane` slash command

**Configuration in Mattermost:**
Main Menu → Integrations → Slash Commands → Add Slash Command.
Copy the generated token into the environment variable.

---

### 5. Outgoing Webhook Token (Mattermost thread replies → Plane)

Mattermost outgoing webhooks include a `token` field in the JSON payload. FastAPI
verifies it using `hmac.compare_digest`.

```python
token = payload.get("token", "")
expected = settings.MM_OUTGOING_WEBHOOK_TOKEN.get_secret_value()
if not hmac.compare_digest(token, expected):
    return {"text": ""}
```

Returning an empty `{"text": ""}` on auth failure prevents Mattermost from displaying
an error in the channel.

**Environment variable:** `MM_OUTGOING_WEBHOOK_TOKEN` in `plane-mm`.

**Configuration in Mattermost:**
Main Menu → Integrations → Outgoing Webhooks → Add Outgoing Webhook.
Set trigger URL to `https://api.kodeme.io/webhooks/plane-mm/reply`.
Copy the generated token into the environment variable.

---

### 6. Bearer Token (outbound to Mattermost API)

`odoo-mm` and `plane-mm` authenticate to the Mattermost REST API using a bot user's
personal access token.

**Headers sent:**
```
Authorization: Bearer <MM_BOT_TOKEN>
```

**Environment variable:** `MM_BOT_TOKEN` (SecretStr) in both `odoo-mm` and `plane-mm`.

**Configuration in Mattermost:**
Account Settings → Security → Personal Access Tokens → Create Token.
The bot user must have the following roles:
- `create_post` — to post messages
- `manage_channel_members` — to create DM channels
- `read_channel` — to look up user/channel IDs

---

### 7. API Key — Plane REST API

`plane-mm` authenticates outbound calls to the Plane API using an API key in a custom
header.

**Header sent:**
```
X-Api-Token: <PLANE_API_KEY>
```

**Environment variable:** `PLANE_API_KEY` (SecretStr) in `plane-mm`.

**Configuration in Plane:**
Profile → API Tokens → Create API Token.
Grant access to the workspace containing the projects being bridged.

---

### 8. Incoming Webhook URL (events-sync → Mattermost)

The `events-sync` service sends Mattermost notifications via an incoming webhook URL.
The token is embedded in the URL path, so no separate header is required.

```
https://chat.kodeme.io/hooks/<incoming_webhook_token>
```

**Environment variable:** `MATTERMOST_WEBHOOK_URL` in `events-sync`.

**Configuration in Mattermost:**
Main Menu → Integrations → Incoming Webhooks → Add Incoming Webhook.
Select the default channel. Copy the full URL (including the token) into the env var.

---

### 9. Telegram Bot Token in URL

The `events-sync` service and Odoo `telegram_integration` addon call the Telegram Bot
API with the token in the URL path.

```
https://api.telegram.org/bot<BOT_TOKEN>/sendMessage
```

**Environment variables:**
- `TELEGRAM_BOT_TOKEN` in `events-sync`
- Configured in Odoo `telegram_integration` system parameters or webhook endpoint URL

**Obtaining a token:**
Chat with `@BotFather` on Telegram → `/newbot` → copy the provided token.

The token must never appear in logs or committed files. Use `SecretStr` in Pydantic
settings and mask it in any debug output.

---

### 10. API Key (Odoo → WAHA)

Odoo `whatsapp_integration` sends messages to WAHA using an API key in a request header.

**Header sent:**
```
X-Api-Key: <WAHA_API_KEY>
```

**Configuration:**
- Set `WAHA_API_KEY` in WAHA's environment.
- Configure the matching value in the Odoo `webhook.endpoint` record for WAHA (auth
  type: api_key, header name: `X-Api-Key`).

**WAHA endpoint:** `https://waha.kodeme.io/api/sendText`

---

### 11. Authentik OIDC / OAuth2 (service-to-service SSO)

All services that require user authentication use Authentik at `auth.kodeme.io` as the
OIDC provider. This is not a webhook authentication method but is listed here for
completeness.

**Flow:**
1. Service redirects user to `https://auth.kodeme.io/application/o/<slug>/authorize/`.
2. Authentik authenticates and returns a JWT access token.
3. Service validates the JWT against Authentik's JWKS endpoint.

**Relevant services:** React PWAs, Next.js websites, Odoo (when OIDC login is enabled).

**Configuration:** Each application is registered in Authentik as an OAuth2 Provider.
The client ID, client secret, and redirect URIs are stored in the service's environment
variables and must not be committed to git.

---

### 12. API Keys for kctl-* CLIs

All kctl-* CLI tools authenticate to their target services using API keys or bearer
tokens stored in `~/.config/kodemeio/config.yaml` under service-scoped profile keys.

```yaml
profiles:
  default:
    dokploy: { url: https://dokploy.kodeme.io, api_key: ${DOKPLOY_API_KEY} }
    ak:       { url: https://auth.kodeme.io,   api_key: ${AUTHENTIK_API_KEY} }
    grafana:  { url: https://grafana.kodeme.io, api_key: ${GRAFANA_API_KEY} }
```

Values reference environment variables via `${VAR}` expansion. The config file itself
should not contain plaintext secrets. `kctl-* config show` always masks secrets using
the `first4****last4` pattern.

---

## Security Practices

### Secret rotation

1. Generate a new secret (use `openssl rand -hex 32`).
2. Update the FastAPI service environment variable via Dokploy.
3. Update the source system (GitHub, Plane, Chatwoot, Odoo) to use the new secret.
4. Redeploy the FastAPI service. Old events in flight may fail once during rotation.

### Fail-open vs fail-closed

All webhook endpoints in this platform are **fail-closed**: if the secret is not
configured (`""`), the endpoint logs a warning but still accepts the request. This
allows initial setup without a secret. Once `WEBHOOK_SECRET_*` is set to a non-empty
value, any request without a valid signature is rejected with `401`.

To enforce fail-closed in production, ensure all `WEBHOOK_SECRET_*` environment
variables are set before deploying.

### Secret storage

- Secrets are injected via Dokploy environment variables (never in `docker-compose.yml`
  committed to git).
- Reference values are stored in 1Password vault `kodemeio` and accessed via `kctl-op`.
- Never log the raw secret value. Pydantic's `SecretStr` type prevents accidental
  inclusion in log output.
- Never write secrets to CLAUDE.md, README.md, or any documentation file.

### Replay prevention

The current implementation does not use timestamps or nonces. The HMAC-SHA256 scheme
alone prevents forgery but not replay of a legitimately captured request. If replay
protection is needed for a high-value endpoint, add a `X-Webhook-Timestamp` header and
reject requests older than 5 minutes.
