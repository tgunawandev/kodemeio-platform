# kctl-mailcow Phase 1-3: Complete API Coverage + Authentik Integration

## Goal

Bring kctl-mailcow from ~50% to ~95% Mailcow API coverage across 3 phases, plus add Authentik-to-Mailcow user provisioning.

## Architecture

All new command groups follow the existing pattern: one file per resource in `commands/`, using `mc_get/mc_add/mc_edit/mc_delete` from `MailcowClient`, output via `AppContext.output`, error handling via `handle_result()`.

The provisioning sync command (`provision sync`) is the only cross-service feature — it reads users from Authentik (via kctl-ak's client) and creates/updates mailboxes in Mailcow. It lives in `core/provisioner.py` with a thin command wrapper.

## Phase 1: Authentik Integration (3 command groups)

### 1.1 `identity-provider` — Configure external OIDC/OAuth2 for Mailcow admin SSO

Mailcow's `json_api.php` endpoint. Allows configuring Authentik as the login provider for the Mailcow admin UI.

| Command | API Call | Description |
|---------|----------|-------------|
| `identity-provider get` | `mc_get("identity-provider")` | Show current OIDC config |
| `identity-provider set` | `mc_edit("identity-provider", {...})` | Configure Authentik OIDC |
| `identity-provider delete` | `mc_delete("identity-provider", [...])` | Remove OIDC config |
| `identity-provider test` | POST to test endpoint | Test OIDC connectivity |

`set` options: `--url`, `--client-id`, `--client-secret`, `--redirect-uri`, `--authorize-url`, `--token-url`, `--userinfo-url`, `--scopes`

### 1.2 `oauth2-clients` — Manage OAuth2 clients (Mailcow as provider)

| Command | API Call | Description |
|---------|----------|-------------|
| `oauth2-clients list` | `mc_get("oauth2-client/all")` | List all OAuth2 clients |
| `oauth2-clients get <id>` | `mc_get("oauth2-client/{id}")` | Show client details |
| `oauth2-clients create` | `mc_add("oauth2-client", {...})` | Create new client |
| `oauth2-clients delete <id>` | `mc_delete("oauth2-client", [id])` | Delete client |

### 1.3 `provision` — Sync Authentik users to Mailcow mailboxes

This is the cross-service integration. Uses kctl-ak's `AuthentikClient` to read users, then kctl-mailcow's `MailcowClient` to create/update mailboxes.

| Command | Description |
|---------|-------------|
| `provision sync` | Sync users from Authentik group → Mailcow mailboxes |
| `provision sync --dry-run` | Preview what would be created/updated/skipped |
| `provision sync --group <name>` | Sync only users in this Authentik group (required) |
| `provision sync --domain <domain>` | Target Mailcow domain for mailboxes (required) |
| `provision sync --quota <mb>` | Default quota for new mailboxes (default: 3072) |
| `provision status` | Show sync status — which Authentik users have/don't have mailboxes |

**Provisioner logic** (`core/provisioner.py`):
1. Fetch all users from Authentik group (via `AuthentikClient.get_all("core/users/", params={"groups_by_name": group})`)
2. Fetch all mailboxes in target domain from Mailcow
3. For each Authentik user with an email:
   - If mailbox exists: skip (or update name if changed)
   - If mailbox missing: create with `mc_add("mailbox", {local_part, domain, name, password: random, quota, active: 1})`
4. Return `ProvisionResult` dataclass with created/updated/skipped counts

**Dependencies**: `kctl-ak` (optional dependency for provision commands only). Config reads Authentik connection from the same shared profile.

## Phase 2: Security & Compliance (6 command groups)

### 2.1 `fail2ban` — Ban/unban management

| Command | API Call |
|---------|----------|
| `fail2ban status` | `mc_get("fail2ban")` |
| `fail2ban ban <ip>` | `mc_edit("fail2ban", {ban: ip})` |
| `fail2ban unban <ip>` | `mc_edit("fail2ban", {unban: ip})` |

### 2.2 `policies` — Domain/mailbox spam whitelist/blacklist

| Command | API Call |
|---------|----------|
| `policies list --domain <d>` | `mc_get("policy_wl_domain/{d}")` + `mc_get("policy_bl_domain/{d}")` |
| `policies list --mailbox <m>` | `mc_get("policy_wl_mailbox/{m}")` + `mc_get("policy_bl_mailbox/{m}")` |
| `policies add-whitelist` | `mc_add("domain-policy", {object: ..., type: "wl"})` |
| `policies add-blacklist` | `mc_add("domain-policy", {object: ..., type: "bl"})` |
| `policies delete <id>` | `mc_delete("domain-policy", [id])` |

### 2.3 `app-passwords` — Per-mailbox app-specific passwords

| Command | API Call |
|---------|----------|
| `app-passwords list <mailbox>` | `mc_get("app-passwd/all")` filtered |
| `app-passwords create <mailbox>` | `mc_add("app-passwd", {...})` |
| `app-passwords delete <id>` | `mc_delete("app-passwd", [id])` |

### 2.4 `password-policy` — Global password rules

| Command | API Call |
|---------|----------|
| `password-policy get` | `mc_get("passwordpolicy")` |
| `password-policy set` | `mc_edit("passwordpolicy", {...})` |

### 2.5 `domain-admins` — Delegated domain management

| Command | API Call |
|---------|----------|
| `domain-admins list` | `mc_get("domain-admin/all")` |
| `domain-admins get <name>` | `mc_get("domain-admin/{name}")` |
| `domain-admins create` | `mc_add("domain-admin", {...})` |
| `domain-admins update <name>` | `mc_edit("domain-admin", {...})` |
| `domain-admins delete <name>` | `mc_delete("domain-admin", [name])` |

### 2.6 `filters` — Per-mailbox Sieve rules

| Command | API Call |
|---------|----------|
| `filters list <mailbox>` | `mc_get("filters/{mailbox}")` |
| `filters create <mailbox>` | `mc_add("filter", {...})` |
| `filters update <id>` | `mc_edit("filter", {...})` |
| `filters delete <id>` | `mc_delete("filter", [id])` |

## Phase 3: Routing & Advanced (6 command groups)

### 3.1 `transports` — Outbound mail routing

| Command | API Call |
|---------|----------|
| `transports list` | `mc_get("transport/all")` |
| `transports get <id>` | `mc_get("transport/{id}")` |
| `transports create` | `mc_add("transport", {...})` |
| `transports update <id>` | `mc_edit("transport", {...})` |
| `transports delete <id>` | `mc_delete("transport", [id])` |

### 3.2 `relay-hosts` — Sender-dependent smarthost

| Command | API Call |
|---------|----------|
| `relay-hosts list` | `mc_get("relayhost/all")` |
| `relay-hosts get <id>` | `mc_get("relayhost/{id}")` |
| `relay-hosts create` | `mc_add("relayhost", {...})` |
| `relay-hosts update <id>` | `mc_edit("relayhost", {...})` |
| `relay-hosts delete <id>` | `mc_delete("relayhost", [id])` |

### 3.3 `bcc-maps` — Compliance BCC copies

| Command | API Call |
|---------|----------|
| `bcc-maps list` | `mc_get("bcc/all")` |
| `bcc-maps create` | `mc_add("bcc", {...})` |
| `bcc-maps update <id>` | `mc_edit("bcc", {...})` |
| `bcc-maps delete <id>` | `mc_delete("bcc", [id])` |

### 3.4 `alias-domains` — Whole-domain aliasing

| Command | API Call |
|---------|----------|
| `alias-domains list` | `mc_get("alias-domain/all")` |
| `alias-domains create` | `mc_add("alias-domain", {...})` |
| `alias-domains update <id>` | `mc_edit("alias-domain", {...})` |
| `alias-domains delete <id>` | `mc_delete("alias-domain", [id])` |

### 3.5 `recipient-maps` — Inbound address rewriting

| Command | API Call |
|---------|----------|
| `recipient-maps list` | `mc_get("recipient_map/all")` |
| `recipient-maps create` | `mc_add("recipient_map", {...})` |
| `recipient-maps delete <id>` | `mc_delete("recipient_map", [id])` |

### 3.6 `rspamd` — Spam filter tuning

| Command | API Call |
|---------|----------|
| `rspamd list` | `mc_get("rsetting/all")` |
| `rspamd create` | `mc_add("rsetting", {...})` |
| `rspamd update <id>` | `mc_edit("rsetting", {...})` |
| `rspamd delete <id>` | `mc_delete("rsetting", [id])` |

## File Structure

```
packages/kctl-mailcow/src/kctl_mailcow/
├── core/
│   ├── provisioner.py          # NEW — Authentik→Mailcow sync logic
│   └── ...existing...
├── commands/
│   ├── ...existing 16 files...
│   ├── identity_provider.py    # Phase 1
│   ├── oauth2_clients.py       # Phase 1
│   ├── provision.py            # Phase 1
│   ├── fail2ban.py             # Phase 2
│   ├── policies.py             # Phase 2
│   ├── app_passwords.py        # Phase 2
│   ├── password_policy.py      # Phase 2
│   ├── domain_admins.py        # Phase 2
│   ├── filters.py              # Phase 2
│   ├── transports.py           # Phase 3
│   ├── relay_hosts.py          # Phase 3
│   ├── bcc_maps.py             # Phase 3
│   ├── alias_domains.py        # Phase 3
│   ├── recipient_maps.py       # Phase 3
│   └── rspamd.py               # Phase 3
```

## Testing Strategy

- Unit tests for `provisioner.py` (mock both Authentik and Mailcow clients)
- Smoke tests: every new command group's `--help` works
- No integration tests (require live Mailcow instance)

## Summary

| Phase | New Groups | New Commands | Key Feature |
|-------|-----------|-------------|-------------|
| 1 | 3 | ~10 | Authentik SSO + user provisioning |
| 2 | 6 | ~20 | Security, spam policies, filters |
| 3 | 6 | ~22 | Mail routing, BCC, domain aliases |
| **Total** | **15** | **~52** | **31 groups, ~112 commands total** |
