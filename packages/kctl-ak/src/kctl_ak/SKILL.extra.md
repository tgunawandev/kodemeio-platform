## OAuth2 Provider Management for React SPAs

React PWAs (SPA clients) MUST use `client_type: public` — they cannot keep secrets.

```bash
# Check current client type
kctl-ak providers oauth2 get <id>

# Fix to public if needed
kctl-ak providers oauth2 update <id> --client-type public

# Get credentials
kctl-ak providers oauth2 credentials <id>
```

## Critical Rules

1. React/SPA apps = `public` client type (NEVER `confidential`)
2. Server-side apps (Odoo, FastAPI) = `confidential` client type
3. Redirect URIs must exactly match what the app sends
