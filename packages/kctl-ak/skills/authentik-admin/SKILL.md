---
name: authentik-admin
description: >
  Authentik identity provider (auth.kodeme.io) administration via kctl-ak CLI. MUST use for ANY SSO, OAuth2, LDAP, SAML, or authentication infrastructure task. Triggers on: "kctl-ak", "authentik", "SSO", "OAuth provider", "LDAP", "SAML", "forward auth", "auth.kodeme.io", "create user authentik", "authentication", "identity provider", or ANY auth infrastructure question.
version: 2.0.0
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

Installed via uv workspace at `packages/kctl-ak/` in the kodemeio-platform repo.

```bash
kctl-ak <command>
```

Configuration is stored at `~/.config/kodemeio/config.yaml` with profiles.

### Global Options

```bash
kctl-ak [--json] [--quiet/-q] [--profile/-p NAME] [--url URL] [--token TOKEN] [--version/-V] <command>
```

---

## Command Reference

### users — User management and provisioning

```bash
kctl-ak users list [--page N] [--page-size N] [--active] [--inactive]
kctl-ak users get <id|username|email>
kctl-ak users search <term>
kctl-ak users create <email> [--name NAME] [--username NAME] [--password PASS] [--groups g1,g2] [--superuser]
kctl-ak users update <identifier> <field> <value>
kctl-ak users password <identifier> [new_password]
kctl-ak users recovery <identifier>
kctl-ak users activate <identifier>
kctl-ak users deactivate <identifier>
kctl-ak users delete <identifier> [--force]
kctl-ak users groups <identifier>
kctl-ak users invite <email> [--name NAME] [--groups g1,g2] [--send-mail]
kctl-ak users re-invite <identifier>
kctl-ak users pending
kctl-ak users bulk-invite <file.json> [--send-mail]
kctl-ak users export [--format json|csv]
kctl-ak users bulk-import <file.json>
kctl-ak users me
```

### users — Role-Based Provisioning

```bash
kctl-ak users roles [--verify]              # List available roles (--verify checks groups exist in Authentik)
kctl-ak users role <name> [--verify]         # Show role details (--verify checks groups exist)
kctl-ak users provision <email> <role> [role2...] [--name NAME] [--username NAME] [--send-mail]
```

Roles are defined in `roles/*.yaml`. Each maps to a set of Authentik groups.

| Role | Description | Use Case |
|---|---|---|
| `admin` | Full IT admin | All apps + superuser |
| `basic-user` | Standard employee | Mattermost only |
| `office-user` | Office worker | Mattermost + Grafana view |
| `erp-user` | ERP user | Mattermost + Odoo |
| `devops` | DevOps engineer | Mattermost + Grafana admin + N8N |
| `mattermost-user` | Chat only | Mattermost |

### provision — Cross-system user provisioning (Authentik + Mailcow + Odoo)

```bash
kctl-ak provision onboard <email> --name "Full Name" --company mac [--dry-run]   # Create user across AK + Mailcow + Odoo
kctl-ak provision offboard <email> [--dry-run]                                   # Disable user across all systems
kctl-ak provision status <email>                                                 # Check user status across all systems
kctl-ak provision sync --company mac [--dry-run]                                 # Poll HRMS, reconcile against Authentik
kctl-ak provision sync --all [--dry-run]                                         # Sync all companies
```

Provisioning chain steps (onboard): Authentik user → Mailcow mailbox → Odoo portal users → Welcome email.
Deprovisioning chain steps (offboard): Disable AK user → Kill sessions → Disable mailbox → Deactivate Odoo users.

Config: `provision-config.yaml` (companies, domains, HRMS sources, Odoo targets).
Secrets via env vars: `MAILCOW_API_KEY`, `ODOO_<SLUG>_DB`, `ODOO_<SLUG>_KEY`.

### groups — Group management and hierarchy

```bash
kctl-ak groups list [--page N]
kctl-ak groups get <id|name>
kctl-ak groups tree
kctl-ak groups create <name> [--parent NAME] [--superuser]
kctl-ak groups update <identifier> <field> <value>
kctl-ak groups delete <identifier> [--force]
kctl-ak groups add-user <group> <user>
kctl-ak groups remove-user <group> <user>
kctl-ak groups members <id|name>
kctl-ak groups sync [--dry-run/--no-dry-run] [--prune] [--file PATH]  # 3-phase create/update/prune from group-structure.yaml
kctl-ak groups export [--format json|yaml]
```

### apps — Application management

```bash
kctl-ak apps list                                                    # List apps with Group column
kctl-ak apps get <slug>
kctl-ak apps create <name> <slug> [--provider ID] [--launch-url URL] [--description TEXT]
kctl-ak apps update <slug> <field> <value>
kctl-ak apps delete <slug> [--force]
kctl-ak apps set-icon <slug> <file-or-url>                           # Upload icon from local file or URL
kctl-ak apps sync [--dry-run/--no-dry-run] [--prune] [--file PATH]   # 3-phase create/update/prune from app-registry.yaml
kctl-ak apps launch-urls
kctl-ak apps access <slug>
kctl-ak apps audit                           # Show apps with missing providers or no launch URL
kctl-ak apps orphaned                        # List apps with no active provider
```

### providers — Provider management (OAuth2, LDAP, SAML, Proxy)

```bash
kctl-ak providers list [--type oauth2|ldap|saml|proxy]

# OAuth2 subcommands
kctl-ak providers oauth2 list
kctl-ak providers oauth2 get <id>
kctl-ak providers oauth2 create <name> <redirect_uri> [--client-type confidential|public]
kctl-ak providers oauth2 credentials <id>
kctl-ak providers oauth2 delete <id> [--force]

# LDAP subcommands
kctl-ak providers ldap list
kctl-ak providers ldap get <id>
kctl-ak providers ldap create <name> [--base-dn DN] [--search-group GROUP]
kctl-ak providers ldap delete <id> [--force]

# SAML subcommands
kctl-ak providers saml list
kctl-ak providers saml get <id>
kctl-ak providers saml create <name> <acs_url> [--audience AUDIENCE] [--issuer ISSUER]
kctl-ak providers saml metadata <id>
kctl-ak providers saml delete <id> [--force]

# Proxy subcommands
kctl-ak providers proxy list
kctl-ak providers proxy get <id>
kctl-ak providers proxy create <name> <external_host> [--internal-host URL] [--mode forward_single|forward_domain]
kctl-ak providers proxy delete <id> [--force]
```

### flows — Authentication flow management

```bash
kctl-ak flows list [--designation TYPE]
kctl-ak flows get <slug>
kctl-ak flows bindings <slug>
kctl-ak flows stages <slug>
kctl-ak flows export <slug>
kctl-ak flows execute <slug>
```

### audit — Event and audit log management

```bash
kctl-ak audit list [--page N] [--action TYPE] [--user IDENT] [--client-ip IP]
kctl-ak audit logins [--failed]
kctl-ak audit changes [--model TYPE]
kctl-ak audit get <event_id>
kctl-ak audit stats [--days N]
kctl-ak audit export [--days N] [--format json|csv]
kctl-ak audit tail [--interval N]
kctl-ak audit suspicious                     # Show suspicious events (failed logins, privilege changes)
```

### sessions — Authenticated session management

```bash
kctl-ak sessions list [--user IDENT]
kctl-ak sessions get <session_id>
kctl-ak sessions kill <session_id>
kctl-ak sessions kill-user <user> [--force]
kctl-ak sessions stats
kctl-ak sessions active
```

### tokens — API token management

```bash
kctl-ak tokens list [--user IDENT]
kctl-ak tokens get <identifier>
kctl-ak tokens create <identifier> <user> [--intent api|verify] [--expiring] [--description TEXT]
kctl-ak tokens view <identifier>             # Show the actual token key
kctl-ak tokens delete <identifier> [--force]
kctl-ak tokens rotate <identifier>           # Delete + recreate with same settings, show new key
kctl-ak tokens expire-all <user> [--force]   # Delete all tokens for a user
```

### blueprints — Blueprint management

```bash
kctl-ak blueprints instances
kctl-ak blueprints get <id>
kctl-ak blueprints apply <id>
kctl-ak blueprints export <flow_slug>
```

### maintenance — System maintenance and administration

```bash
kctl-ak maintenance status
kctl-ak maintenance version
kctl-ak maintenance tasks
kctl-ak maintenance run <task_id>
kctl-ak maintenance cache-clear
kctl-ak maintenance outposts
kctl-ak maintenance workers
kctl-ak maintenance config
kctl-ak maintenance clean
kctl-ak maintenance settings
kctl-ak maintenance impersonation
```

### setup — Setup wizards

```bash
kctl-ak setup status
kctl-ak setup oauth2 <name> <redirect_uri>
kctl-ak setup proxy <name> <external_host>
kctl-ak setup admin <username>
kctl-ak setup recovery <username>
kctl-ak setup app <name> <slug> [--provider-type TYPE]
```

### health — Health checks

```bash
kctl-ak health [--watch] [--interval N]
```

### dashboard — System overview

```bash
kctl-ak dashboard [--watch] [--interval N] [--compact]
kctl-ak dashboard --security                 # Security-focused view (failed logins, token usage, policy denials)
```

### config — CLI configuration and profiles

```bash
kctl-ak config init [--url URL] [--token TOKEN] [--name NAME]
kctl-ak config add [--name NAME] [--url URL] [--token TOKEN]
kctl-ak config use <profile>
kctl-ak config remove <profile>
kctl-ak config show
kctl-ak config set <key> <value>
kctl-ak config profiles
kctl-ak config current
kctl-ak config test
kctl-ak config migrate
```

### mail — Email operations via SMTP

```bash
kctl-ak mail test <to_email>
kctl-ak mail send-recovery <identifier>
kctl-ak mail send-welcome <identifier>
kctl-ak mail send-password <identifier>
kctl-ak mail recovery-link <identifier>
```

### policies — Policy management

```bash
kctl-ak policies list [--type TYPE]
kctl-ak policies get <id>
kctl-ak policies create <name> [--type expression|password|reputation] [--expression "..."]
kctl-ak policies update <id> <field> <value>
kctl-ak policies delete <id> [--force]
kctl-ak policies bindings
kctl-ak policies bind <policy_id> --target <target_id> [--order N] [--negate] [--enabled]
kctl-ak policies unbind <binding_id> [--force]
kctl-ak policies test <id> --user <identifier>
```

### stages — Stage management

```bash
kctl-ak stages list [--type TYPE]
kctl-ak stages get <id>
kctl-ak stages create-prompt <name> [--fields FIELD1,FIELD2]
kctl-ak stages create-password <name> [--backends BACKEND1,BACKEND2]
kctl-ak stages create-identification <name> --user-fields username,email [--password-stage ID]
kctl-ak stages create-consent <name> [--mode always_require|permanent|expiring]
kctl-ak stages create-email <name> --template TEMPLATE [--host HOST] [--port PORT]
kctl-ak stages create-user-login <name> [--session-duration DURATION]
kctl-ak stages create-user-logout <name>
kctl-ak stages create-authenticator-validate <name> [--device-classes totp,webauthn]
kctl-ak stages update <id> <field> <value>
kctl-ak stages delete <id> [--force]
kctl-ak stages prompts                       # List prompt field definitions
```

### property-mappings — Property mapping management

```bash
kctl-ak property-mappings list [--type TYPE]
kctl-ak property-mappings get <id>
kctl-ak property-mappings create-scope <name> --scope-name SCOPE --expression "..."
kctl-ak property-mappings create-saml <name> --expression "..." --saml-name ATTR
kctl-ak property-mappings create-ldap <name> --expression "..." --object-field FIELD
kctl-ak property-mappings create-scim <name> --expression "..."
kctl-ak property-mappings update <id> <field> <value>
kctl-ak property-mappings delete <id> [--force]
kctl-ak property-mappings test <id> --user <identifier> [--provider ID]
```

### certificates — Certificate and key pair management

```bash
kctl-ak certificates list
kctl-ak certificates get <id>
kctl-ak certificates create <name> --cert-file CERT [--key-file KEY]
kctl-ak certificates generate <name> [--validity-days 365]
kctl-ak certificates delete <id> [--force]
kctl-ak certificates view <id>               # Show parsed certificate details
kctl-ak certificates used-by <id>
```

### outposts — Outpost instance management

```bash
kctl-ak outposts list
kctl-ak outposts get <id>
kctl-ak outposts create <name> --type proxy|ldap|radius [--providers ID1,ID2]
kctl-ak outposts update <id> [--name NAME] [--providers ID1,ID2]
kctl-ak outposts delete <id> [--force]
kctl-ak outposts health <id>
kctl-ak outposts connections                 # List service connections
kctl-ak outposts create-connection <name> --url URL [--tls-verify] [--local]
kctl-ak outposts delete-connection <id> [--force]
```

### brands — Brand/tenant management

```bash
kctl-ak brands list
kctl-ak brands get <id>
kctl-ak brands create <domain> [--branding-title TITLE] [--branding-logo URL] [--flow-authentication SLUG]
kctl-ak brands update <id> [--branding-title TITLE] [--branding-logo URL]
kctl-ak brands delete <id> [--force]
kctl-ak brands current
```

### notifications — Notification management

```bash
kctl-ak notifications list [--unread]
kctl-ak notifications rules                  # List notification rules
kctl-ak notifications create-rule <name> --group ID --transports ID1,ID2 --severity notice|warning|alert
kctl-ak notifications update-rule <id> [--name NAME] [--severity SEVERITY]
kctl-ak notifications delete-rule <id> [--force]
kctl-ak notifications transports             # List notification transports
kctl-ak notifications create-transport <name> --mode webhook|email|slack [--webhook-url URL]
kctl-ak notifications delete-transport <id> [--force]
kctl-ak notifications mark-read <id|--all>
```

### system — System settings and administration

```bash
kctl-ak system settings                      # Show all system settings
kctl-ak system update-setting --key KEY --value VALUE
kctl-ak system license                       # Show enterprise license info
kctl-ak system version                       # Show server version
kctl-ak system impersonation [on|off]        # Toggle/show impersonation setting
kctl-ak system user-changes [--name on|off] [--email on|off] [--username on|off]
kctl-ak system token-defaults [--duration DURATION] [--length N]
kctl-ak system event-retention [DURATION]    # Set/show event retention
```

---

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
- `admin/settings/` -- System settings (GET/PUT)
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

### Apps without SSO providers
1. `kctl-ak apps audit` -- find apps missing providers
2. `kctl-ak apps orphaned` -- list apps with no provider
3. `kctl-ak setup oauth2 "AppName" "callback_url"` -- create provider + app binding

### Missing groups for role provisioning
1. `kctl-ak users roles --verify` -- check all roles' groups exist
2. `kctl-ak groups sync` -- preview group create/update/prune from structure file
3. `kctl-ak groups sync --no-dry-run` -- apply group changes
4. `kctl-ak groups sync --no-dry-run --prune` -- apply changes and delete stale ak-* groups

### Sync apps from registry
1. `kctl-ak apps sync` -- preview app create/update/prune from app-registry.yaml
2. `kctl-ak apps sync --no-dry-run` -- apply app changes
3. `kctl-ak apps sync --no-dry-run --prune` -- apply changes and delete stale managed apps
4. `kctl-ak apps set-icon <slug> ./icons/app.png` -- upload icon from local file
