---
name: authentik-admin
description: >
  Authentik identity provider (auth.kodeme.io) administration via kctl-ak CLI. MUST use for ANY SSO, OAuth2, LDAP, SAML, or authentication infrastructure task. Triggers on: "kctl-ak", "authentik", "SSO", "OAuth provider", "LDAP", "SAML", "forward auth", "auth.kodeme.io", "create user authentik", "authentication", "identity provider", or ANY auth infrastructure question.
version: 1.0.0
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Glob
  - Grep
---

# Authentik Administration for Kodemeio

## System Overview

- **Authentik 2026.2.1** at `https://auth.kodeme.io`
- **No Redis** -- cache is PostgreSQL-backed (since 2025.10+)
- **External PostgreSQL** at `10.0.0.3` (Hetzner private network)
- **3 services**: Server, Worker, LDAP outpost
- **Deployed**: Dokploy with Traefik reverse proxy on `dokploy.kodeme.io`

## CLI Tool: kctl-ak

The CLI is installed in the project at `cli/` and available via the venv:

```bash
# Run from the kodemeio-authentik project root:
cli/.venv/bin/kctl-ak <command>

# Or if installed globally:
kctl-ak <command>
```

Configuration is stored at `~/.config/kodemeio/config.yaml` with profiles.

### Global Options

```bash
kctl-ak [--json] [--quiet] [--profile NAME] [--url URL] [--token TOKEN] <command>
```

### User Management

```bash
kctl-ak users list [--page N] [--active|--inactive]
kctl-ak users get <id|username|email>
kctl-ak users search <term>
kctl-ak users create <email> [--name NAME] [--username NAME] [--password PASS] [--groups g1,g2]
kctl-ak users update <identifier> <field> <value>
kctl-ak users password <identifier> [password]
kctl-ak users recovery <identifier>
kctl-ak users activate <identifier>
kctl-ak users deactivate <identifier>
kctl-ak users delete <identifier> [--force]
kctl-ak users groups <identifier>
kctl-ak users invite <email> [--name NAME] [--groups g1,g2]
kctl-ak users export [--format json|csv]
kctl-ak users bulk-import <file.json>
kctl-ak users me
```

### Role-Based Provisioning

```bash
kctl-ak users roles                                    # List available roles
kctl-ak users role <name>                              # Show role details
kctl-ak users provision <email> <role> [role2...]      # Provision user with roles
```

Roles are defined in `roles/*.yaml`. Each maps to a set of groups.

| Role | Description | Use Case |
|---|---|---|
| `admin` | Full IT admin | All apps + superuser |
| `basic-user` | Standard employee | Mattermost only |
| `office-user` | Office worker | Mattermost + Grafana view |
| `erp-user` | ERP user | Mattermost + Odoo |
| `devops` | DevOps engineer | Mattermost + Grafana admin + N8N |
| `mattermost-user` | Chat only | Mattermost |

### Group Management

```bash
kctl-ak groups list
kctl-ak groups get <id|name>
kctl-ak groups tree                                    # Visual hierarchy
kctl-ak groups create <name> [--parent NAME] [--superuser]
kctl-ak groups add-user <group> <user>
kctl-ak groups remove-user <group> <user>
kctl-ak groups members <id|name>
kctl-ak groups sync [--dry-run] [--file PATH]          # Sync from group-structure.yaml
kctl-ak groups export [--format json|yaml]
```

### Application & Provider Management

```bash
kctl-ak apps list
kctl-ak apps get <slug>
kctl-ak apps create <name> <slug> [--provider ID] [--launch-url URL]
kctl-ak apps launch-urls
kctl-ak apps access <slug>

kctl-ak providers list [--type oauth2|ldap|saml|proxy]
kctl-ak providers oauth2 list|get|create|credentials|delete
kctl-ak providers ldap list|get|create|delete
kctl-ak providers saml list|get|create|metadata|delete
kctl-ak providers proxy list|get|create|delete
```

### Quick Setup (Provider + App in one command)

```bash
kctl-ak setup oauth2 "ServiceName" "https://service.kodeme.io/callback"
kctl-ak setup proxy "ServiceName" "https://service.kodeme.io"
kctl-ak setup admin <username>
kctl-ak setup recovery <username>
kctl-ak setup status
```

### Monitoring & Health

```bash
kctl-ak health [--watch]
kctl-ak dashboard [--compact] [--watch]
kctl-ak maintenance status|version|tasks|outposts|workers|config|clean
```

### Audit & Security

```bash
kctl-ak audit list [--action TYPE] [--user IDENT]
kctl-ak audit logins [--failed]
kctl-ak audit stats [--days N]
kctl-ak audit tail [--interval N]                      # Live tail

kctl-ak sessions list [--user IDENT]
kctl-ak sessions kill <session_id>
kctl-ak sessions kill-user <user> [--force]
kctl-ak sessions stats

kctl-ak tokens list [--user IDENT]
kctl-ak tokens create <identifier> <user> [--intent api]
kctl-ak tokens view <identifier>                       # Show actual key
kctl-ak tokens rotate <identifier>
kctl-ak tokens expire-all <user> [--force]
```

### Flows & Blueprints

```bash
kctl-ak flows list [--designation TYPE]
kctl-ak flows get <slug>
kctl-ak flows bindings <slug>
kctl-ak flows export <slug>

kctl-ak blueprints instances
kctl-ak blueprints apply <id>
kctl-ak blueprints export <flow_slug>
```

### Configuration

```bash
kctl-ak config init [--url URL] [--token TOKEN] [--name NAME]
kctl-ak config show
kctl-ak config set <key> <value>
kctl-ak config profiles
kctl-ak config current
kctl-ak config test
```

### Policy Management

```bash
kctl-ak policies list [--type TYPE]
kctl-ak policies get <id>
kctl-ak policies create-expression <name> --expression "..." [--execution-logging]
kctl-ak policies create-password <name> [--min-length N] [--symbol-charset CHARS]
kctl-ak policies create-reputation <name> [--threshold N]
kctl-ak policies test <id> --user <identifier>
kctl-ak policies bindings <id>
kctl-ak policies delete <id> [--force]
kctl-ak policies cache-clear
```

### Stage Management

```bash
kctl-ak stages list [--type TYPE]
kctl-ak stages get <id>
kctl-ak stages create-identification <name> --user-fields username,email [--password-stage ID]
kctl-ak stages create-password <name> [--backends BACKEND1,BACKEND2]
kctl-ak stages create-authenticator-validate <name> [--device-classes totp,webauthn]
kctl-ak stages create-authenticator-totp <name> [--digits 6] [--friendly-name NAME]
kctl-ak stages create-authenticator-webauthn <name> [--resident-key-requirement discouraged]
kctl-ak stages create-email <name> --template TEMPLATE [--host HOST] [--port PORT]
kctl-ak stages create-consent <name> [--mode always_require|permanent|expiring]
kctl-ak stages create-user-login <name> [--session-duration DURATION]
kctl-ak stages create-user-write <name> [--user-creation-mode never_create|create_when_required]
kctl-ak stages create-deny <name>
kctl-ak stages create-invitation <name> [--no-continue-without-invitation]
kctl-ak stages delete <id> [--force]
```

### Property Mapping Management

```bash
kctl-ak property-mappings list [--type TYPE]
kctl-ak property-mappings get <id>
kctl-ak property-mappings create-scope <name> --scope-name SCOPE --expression "..."
kctl-ak property-mappings create-ldap <name> --expression "..." --object-field FIELD
kctl-ak property-mappings create-saml <name> --expression "..." --saml-name ATTR
kctl-ak property-mappings test <id> --user <identifier> [--provider ID]
kctl-ak property-mappings export <id>
kctl-ak property-mappings delete <id> [--force]
kctl-ak property-mappings used-by <id>
```

### Certificate Management

```bash
kctl-ak certificates list
kctl-ak certificates get <id>
kctl-ak certificates generate <name> [--validity-days 365]
kctl-ak certificates import <name> --cert-file CERT --key-file KEY
kctl-ak certificates download <id> [--format pem|der]
kctl-ak certificates delete <id> [--force]
kctl-ak certificates used-by <id>
```

### Outpost Management

```bash
kctl-ak outposts list
kctl-ak outposts get <id>
kctl-ak outposts create <name> --type proxy|ldap|radius [--providers ID1,ID2]
kctl-ak outposts update <id> [--name NAME] [--providers ID1,ID2]
kctl-ak outposts delete <id> [--force]
kctl-ak outposts health <id>
kctl-ak outposts deploy <id>
kctl-ak outposts service-connections list
kctl-ak outposts service-connections create <name> --url URL [--tls-verify] [--local]
```

### Brand Management

```bash
kctl-ak brands list
kctl-ak brands get <id>
kctl-ak brands create <domain> [--branding-title TITLE] [--branding-logo URL] [--flow-authentication SLUG]
kctl-ak brands update <id> [--branding-title TITLE] [--branding-logo URL]
kctl-ak brands delete <id> [--force]
kctl-ak brands current
```

### Notification Management

```bash
kctl-ak notifications list [--unread]
kctl-ak notifications get <id>
kctl-ak notifications mark-read <id>
kctl-ak notifications mark-all-read
kctl-ak notifications rules list
kctl-ak notifications rules create <name> --group ID --transports ID1,ID2 --severity notice|warning|alert
kctl-ak notifications transports list
kctl-ak notifications transports create <name> --mode webhook|email|slack [--webhook-url URL]
kctl-ak notifications transports test <id>
```

### System Administration

```bash
kctl-ak system info
kctl-ak system tasks
kctl-ak system runners
kctl-ak system license
```

## Provider Decision Tree

When connecting a new service to Authentik:

1. **Service supports OIDC/OAuth2?** -> Use **OAuth2 Provider**
   - `kctl-ak setup oauth2 "ServiceName" "https://service.kodeme.io/callback"`
   - Best for: Mattermost, Grafana, Odoo, Gitea, Plane, Zulip, most modern apps

2. **Service supports SAML?** -> Use **SAML Provider**
   - `kctl-ak providers saml create "ServiceName" "https://service.kodeme.io/saml/acs"`
   - Best for: Enterprise apps (AWS, Google Workspace)

3. **Service supports LDAP bind?** -> Use **LDAP Provider**
   - Already configured at `ldap://auth.kodeme.io:389`
   - Best for: Legacy apps, mail servers

4. **Service has NO auth support?** -> Use **Proxy Provider** (forward auth)
   - `kctl-ak setup proxy "ServiceName" "https://service.kodeme.io"`
   - Best for: Gatus, static sites, internal dashboards
   - Requires Traefik middleware labels

## Forward Auth Setup (Proxy Provider)

For services without built-in OIDC (e.g., Gatus):

1. Create proxy provider and application:
   ```bash
   kctl-ak setup proxy "Gatus" "https://gatus.kodeme.io"
   ```

2. Add provider to embedded outpost (via Authentik UI)

3. In the protected service's docker-compose, add Traefik labels:
   ```yaml
   labels:
     - "traefik.http.middlewares.authentik-forward-auth.forwardAuth.address=http://authentik-server:9000/outpost.goauthentik.io/auth/traefik"
     - "traefik.http.middlewares.authentik-forward-auth.forwardAuth.trustForwardHeader=true"
     - "traefik.http.middlewares.authentik-forward-auth.forwardAuth.authResponseHeaders=X-authentik-username,X-authentik-groups,X-authentik-entitlements,X-authentik-email,X-authentik-name,X-authentik-uid"
     - "traefik.http.routers.<service>.middlewares=authentik-forward-auth"
   ```

**CRITICAL**: Use `http://authentik-server:9000` (network alias on dokploy-network), NOT the external URL. The external URL hairpins through Traefik and breaks `X-Forwarded-Host` header matching.

## Group Naming Convention

```
{prefix}-{tier}-{identifier}[-{sub-identifier}]

Prefix:  ak- (Authentik-managed)
Tiers:
  admin  -- Superuser / admin groups
  svc    -- Service accounts
  role   -- Access bundles (maps to provisioning roles)
  app    -- Per-application access
  dept   -- Department groups
```

Examples: `ak-admin-super`, `ak-role-devops`, `ak-app-grafana-admin`, `ak-dept-engineering`

## Integration Targets

| Service | Type | Domain | Provider |
|---|---|---|---|
| Gatus | Forward Auth | gatus.kodeme.io | Proxy |
| Mailcow | OAuth2/OIDC | mail.kodeme.io | OAuth2 |
| Mattermost | OAuth2/OIDC | chat.kodeme.io | OAuth2 |
| Odoo | OAuth2/OIDC | erp.kodeme.io | OAuth2 |
| Grafana | OAuth2/OIDC | grafana.kodeme.io | OAuth2 |
| Plane | OAuth2/OIDC | plane.kodeme.io | OAuth2 |
| Zulip | OAuth2/OIDC | zulip.kodeme.io | OAuth2 |
| Outline | OAuth2/OIDC | outline.kodeme.io | OAuth2 |
| GlitchTip | OAuth2/OIDC | glitchtip.kodeme.io | OAuth2 |
| LDAP | LDAP | auth.kodeme.io:389 | LDAP |

## API Reference

Base URL: `https://auth.kodeme.io/api/v3/`

Key endpoints:
- `core/users/` -- User CRUD
- `core/groups/` -- Group CRUD + `{pk}/add_user/`, `{pk}/remove_user/`
- `core/applications/` -- Application CRUD (keyed by slug)
- `providers/oauth2/`, `providers/ldap/`, `providers/saml/`, `providers/proxy/`
- `flows/instances/` -- Flow management (keyed by slug)
- `events/events/` -- Audit log
- `core/authenticated_sessions/` -- Session management
- `core/tokens/` -- Token CRUD + `{id}/view_key/`
- `managed/blueprints/` -- Blueprint instances
- `admin/system/` -- System info
- `admin/version/` -- Version info
- `outposts/instances/` -- Outpost management
- `policies/all/` -- Policy management
- `stages/all/` -- Stage management
- `propertymappings/all/` -- Property mapping management
- `crypto/certificatekeypairs/` -- Certificate management
- `core/brands/` -- Brand management
- `events/notifications/` -- Notification management
- `events/rules/` -- Notification rules
- `events/transports/` -- Notification transports

## Troubleshooting

### User cannot access an application
1. `kctl-ak users groups <user>` -- check group membership
2. `kctl-ak apps access <app-slug>` -- check policy bindings
3. `kctl-ak audit list --user <user>` -- check auth events

### Forward auth returning 401/403
1. Verify the service uses `http://authentik-server:9000` NOT external URL
2. Check outpost has the proxy provider assigned
3. `kctl-ak maintenance outposts` -- verify outpost health
4. Check Traefik labels include all required `authResponseHeaders`

### Health check degraded
1. `kctl-ak health` -- see which checks fail
2. `kctl-ak maintenance status` -- check DB and cache
3. `kctl-ak maintenance workers` -- verify worker running

### OAuth2 token issues
1. `kctl-ak providers oauth2 get <id>` -- check token validity
2. `kctl-ak tokens list --user <user>` -- check user tokens
3. `kctl-ak audit logins --failed` -- check for auth failures
