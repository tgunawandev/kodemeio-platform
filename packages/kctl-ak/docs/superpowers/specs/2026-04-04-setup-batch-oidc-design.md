# Setup Batch — Bulk OAuth2 Provider Creation Design Spec

## Goal

Add `kctl-ak setup batch` command that reads `app-registry.yaml` and for each app
without an existing provider: creates an OAuth2 provider with the correct redirect
URI pattern, links it to the application, and outputs OIDC credentials.

## App Type Detection

Each app in the registry has a `type` field that determines the redirect URI pattern:

| Type | Redirect URI Pattern | Env Output |
|------|---------------------|------------|
| `react-spa` | `{launch_url}/callback` | `VITE_*` vars |
| `odoo` | `{launch_url}/auth_oauth/signin` | `ODOO_OAUTH_*` vars |
| `nextjs` | `{launch_url}/api/auth/callback/oidc` | `OIDC_*` / `NEXT_PUBLIC_*` vars |
| `proxy` | No provider (forward auth) | Skipped |
| (none) | Skipped | Skipped |

## Command

```bash
kctl-ak setup batch [--dry-run/--no-dry-run] [--file PATH] [--output-env]
```

- `--dry-run` (default True): show what would be created
- `--output-env`: after creating providers, print env vars per app
- `--file`: path to app-registry.yaml (default: auto-resolve)

## Algorithm

1. Load `app-registry.yaml`
2. Load all existing applications from API (`get_all("core/applications/")`)
3. For each app with a `type` in (`react-spa`, `odoo`, `nextjs`):
   a. Check if app exists in Authentik (by slug)
   b. Check if app already has a provider (`provider` field not null)
   c. If no provider: create OAuth2 provider, link to app
   d. If provider exists: skip (report as "already configured")
4. If `--output-env`: fetch credentials for each created/existing provider and
   format as env vars per app type

## Provider Creation Details

Uses the existing `kctl-ak setup oauth2` flow internally:
- Finds the authorization flow (implicit-consent or default-authentication-flow)
- Creates OAuth2 provider with name `{app_name} OIDC`
- Redirect URI computed from `type` + `launch_url`
- Links provider to application via PATCH

## Env Output Format

```
# === mac-react-wms (react-spa) ===
VITE_AUTH_MODE=oidc
VITE_OIDC_AUTHORITY=https://auth.kodeme.io/application/o/mac-react-wms/
VITE_WMS_OIDC_CLIENT_ID={client_id}
VITE_WMS_OIDC_REDIRECT_URI=https://wms-mac.mandiriagro.com/callback

# === mac-odoo-dist (odoo) ===
ODOO_OAUTH_PROVIDER_NAME=Authentik
ODOO_OAUTH_CLIENT_ID={client_id}
ODOO_OAUTH_AUTH_ENDPOINT=https://auth.kodeme.io/application/o/authorize/
ODOO_OAUTH_TOKEN_ENDPOINT=https://auth.kodeme.io/application/o/token/
ODOO_OAUTH_USERINFO_ENDPOINT=https://auth.kodeme.io/application/o/userinfo/

# === kod-nextjs-web (nextjs) ===
NEXT_PUBLIC_OIDC_ISSUER=https://auth.kodeme.io/application/o/kod-nextjs-web/
OIDC_CLIENT_ID={client_id}
OIDC_CLIENT_SECRET={client_secret}
OIDC_REDIRECT_URI=https://consulting.kodeme.io/api/auth/callback/oidc
```

## Changes to app-registry.yaml

Add `type` field to each app. Examples:

```yaml
- slug: mac-react-wms
  name: "MAC — WMS"
  type: react-spa
  group: "MAC — Mandiriagro"
  launch_url: https://wms-mac.mandiriagro.com

- slug: mac-odoo-dist
  name: "MAC — Odoo Distribution"
  type: odoo
  group: "MAC — Mandiriagro"
  launch_url: https://odoo-dist-mac.mandiriagro.com

- slug: gatus
  name: "Shared — Gatus"
  type: proxy
  group: "Shared — Infrastructure"
  launch_url: https://gatus.kodeme.io
```

Apps without `type` or with `type: proxy` are skipped for provider creation.

## Files Changed

| File | Change |
|------|--------|
| `packages/kctl-ak/src/kctl_ak/commands/setup.py` | Add `batch()` command |
| `config/app-registry.yaml` (kodemeio-authentik repo) | Add `type` field to all apps |
| `packages/kctl-ak/tests/test_commands/test_setup_batch.py` | Tests |

## Out of Scope

- Odoo `auth_oauth` module activation (done via Odoo UI/CLI, not kctl-ak)
- React app code changes (already supports OIDC)
- Next.js app code changes (already supports OIDC in 2 instances)
- Updating deploy env files automatically (manual copy from `--output-env`)
