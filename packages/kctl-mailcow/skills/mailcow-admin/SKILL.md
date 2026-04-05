---
name: mailcow-admin
description: >
  Mailcow mail server administration via kctl-mailcow CLI (32 groups, ~110 commands).
  MUST use for ANY kctl-mailcow operation.
  Triggers on: "add-blacklist", "add-whitelist", "alias-domains", "aliases", "app-passwords", "bcc-maps", "check", "compliance", "config", "current", "dashboard", "dkim", "dns-check", "domain-admins", "domains", "fail2ban", "filters", "flush", "fwdhost", "generate", "health", "identity-provider", "init", "kctl-mailcow", "logs", "mailboxes", "migrate", "oauth2-clients", "password-policy", "policies", "profile", "profiles", "provision", "quarantine", "queue", "ratelimits", "recipient-maps", "relay-hosts", "release", "remove", "resources", "rspamd", "skill", "status", "sync", "sync-jobs", "test", "tls", "transports", "unban".
  Auto-generated: 2026-04-05
  registry_hash: 6460b103d564
---

# mailcow-admin — kctl-mailcow CLI Reference

> Auto-generated from `kctl-mailcow` command registry. Do not edit manually.
> To regenerate: `kctl-mailcow skill generate`
> To add custom content: edit `SKILL.extra.md` in the same directory.

## Overview

**CLI:** `kctl-mailcow`
**Command groups:** 32
**Total commands:** ~110
**Install:** `cd cli && uv tool install --editable .`

## Global Options

| Flag | Description |
|------|-------------|
| `--json` | JSON output |
| `--quiet`, `-q` | Suppress info messages |
| `--format`, `-f` | Output format: pretty/json/csv/yaml |
| `--no-header` | Omit CSV header row |
| `--profile`, `-p` | Config profile name |
| `--version`, `-V` | Show version |

## Command Reference

### `kctl-mailcow alias-domains`

Manage domain aliases (whole-domain aliasing).

| Command | Description |
|---------|-------------|
| `alias-domains create <alias_domain> <target_domain> [--active]` | Create a domain alias. |
| `alias-domains delete <alias_domain> [--force]` | Delete a domain alias. |
| `alias-domains list` | List all domain aliases. |
| `alias-domains update <alias_domain> [--target_domain] [--active]` | Update a domain alias. |

### `kctl-mailcow aliases`

Manage email aliases.

| Command | Description |
|---------|-------------|
| `aliases add <address> <goto> [--active]` | Add a new alias. |
| `aliases delete <alias_id> [--force]` | Delete an alias. |
| `aliases get <alias_id>` | Get alias details. |
| `aliases list [--domain]` | List all aliases. |
| `aliases update <alias_id> [--address] [--goto] [--active]` | Update alias settings. |

### `kctl-mailcow app-passwords`

Manage per-mailbox app passwords.

| Command | Description |
|---------|-------------|
| `app-passwords create <mailbox> <name> <password> [--active]` | Create an app password for a mailbox. |
| `app-passwords delete <password_id> [--force]` | Delete an app password. |
| `app-passwords list [--mailbox]` | List app passwords. |

### `kctl-mailcow bcc-maps`

Manage BCC maps (compliance copies).

| Command | Description |
|---------|-------------|
| `bcc-maps create <local_dest> <bcc_dest> [--bcc_type] [--active]` | Create a BCC map. |
| `bcc-maps delete <bcc_id> [--force]` | Delete a BCC map. |
| `bcc-maps list` | List all BCC maps. |
| `bcc-maps update <bcc_id> [--local_dest] [--bcc_dest] [--bcc_type] [--active]` | Update a BCC map. |

### `kctl-mailcow config`

Manage CLI configuration and profiles.

| Command | Description |
|---------|-------------|
| `config add <name> [--url] [--api_key] [--set_default]` | Add or update a profile's Mailcow connection. |
| `config current` | Show the active profile and connection status. |
| `config init [--url] [--api_key] [--name]` | Initialize CLI configuration (interactive if no flags given). |
| `config migrate` | Migrate config from flat format to service-scoped format. |
| `config profiles` | List all profiles with Mailcow connection status. |
| `config remove <name> [--force] [--service_only]` | Remove a profile or just its Mailcow config. |
| `config set <key> <value> [--profile_arg]` | Set a configuration value for the current service. |
| `config show` | Show full configuration (API keys masked). |
| `config test` | Test API connection with current configuration. |
| `config use <name>` | Switch the default profile. |

### `kctl-mailcow dashboard`

System overview dashboard.

### `kctl-mailcow dkim`

Manage DKIM keys.

| Command | Description |
|---------|-------------|
| `dkim generate <domain> [--selector] [--length]` | Generate DKIM key for a domain. |
| `dkim get <domain>` | Get DKIM key details for a domain. |
| `dkim list` | List DKIM keys for all domains. |

### `kctl-mailcow domain-admins`

Manage domain administrators.

| Command | Description |
|---------|-------------|
| `domain-admins create <username> <password> <domains> [--active]` | Create a domain admin. |
| `domain-admins delete <username> [--force]` | Delete a domain admin. |
| `domain-admins get <username>` | Get domain admin details. |
| `domain-admins list` | List all domain admins. |
| `domain-admins update <username> [--password] [--domains] [--active]` | Update domain admin settings. |

### `kctl-mailcow domains`

Manage mail domains.

| Command | Description |
|---------|-------------|
| `domains add <domain> [--description] [--aliases] [--mailboxes] [--defquota] [--maxquota] [--quota] [--active]` | Add a new domain. |
| `domains delete <domain> [--force]` | Delete a domain. |
| `domains dns-check <domain>` | Check DNS records for a domain (MX, SPF, DKIM, DMARC, etc.). |
| `domains get <domain>` | Get domain details. |
| `domains list` | List all domains. |
| `domains update <domain> [--description] [--aliases] [--mailboxes] [--maxquota] [--quota] [--active]` | Update domain settings. |

### `kctl-mailcow fail2ban`

Manage fail2ban bans.

| Command | Description |
|---------|-------------|
| `fail2ban ban <ip>` | Ban an IP address. |
| `fail2ban status` | Show fail2ban status and banned IPs. |
| `fail2ban unban <ip>` | Unban an IP address. |

### `kctl-mailcow filters`

Manage per-mailbox Sieve filters.

| Command | Description |
|---------|-------------|
| `filters create <mailbox> <script_desc> <script_data> [--active]` | Create a Sieve filter for a mailbox. |
| `filters delete <filter_id> [--force]` | Delete a Sieve filter. |
| `filters list <mailbox>` | List Sieve filters for a mailbox. |
| `filters update <filter_id> [--script_desc] [--script_data] [--active]` | Update a Sieve filter. |

### `kctl-mailcow fwdhost`

Manage forwarding hosts.

| Command | Description |
|---------|-------------|
| `fwdhost add <hostname> [--filter_spam]` | Add a forwarding host. |
| `fwdhost delete <hostname> [--force]` | Delete a forwarding host. |
| `fwdhost list` | List all forwarding hosts. |

### `kctl-mailcow health`

Health checks.

### `kctl-mailcow identity-provider`

Manage external identity provider (OIDC SSO) for admin login.

| Command | Description |
|---------|-------------|
| `identity-provider delete [--force]` | Remove identity provider configuration. |
| `identity-provider get` | Show current identity provider configuration. |
| `identity-provider set <server_url> <client_id> <client_secret> [--redirect_url] [--authorize_url] [--token_url] [--userinfo_url] [--scopes]` | Configure external OIDC identity provider for Mailcow admin SSO. |
| `identity-provider test` | Test identity provider connectivity. |

### `kctl-mailcow logs`

View Mailcow service logs.

| Command | Description |
|---------|-------------|
| `logs list [--log_type] [--count]` | View logs for a service. |

### `kctl-mailcow mailboxes`

Manage mailboxes.

| Command | Description |
|---------|-------------|
| `mailboxes add <local_part> <domain> <password> [--name] [--quota] [--active]` | Add a new mailbox. |
| `mailboxes delete <email> [--force]` | Delete a mailbox. |
| `mailboxes get <email>` | Get mailbox details. |
| `mailboxes list [--domain]` | List all mailboxes. |
| `mailboxes update <email> [--name] [--quota] [--password] [--active]` | Update mailbox settings. |

### `kctl-mailcow oauth2-clients`

Manage OAuth2 clients (Mailcow as provider).

| Command | Description |
|---------|-------------|
| `oauth2-clients create <redirect_uri> [--scope]` | Create a new OAuth2 client. |
| `oauth2-clients delete <client_id> [--force]` | Delete an OAuth2 client. |
| `oauth2-clients get <client_id>` | Get OAuth2 client details. |
| `oauth2-clients list` | List all OAuth2 clients. |

### `kctl-mailcow password-policy`

Manage global password policy.

| Command | Description |
|---------|-------------|
| `password-policy get` | Show current password policy. |
| `password-policy set [--min_length] [--min_upper] [--min_lower] [--min_num] [--min_special]` | Set password policy rules. |

### `kctl-mailcow policies`

Manage spam whitelist/blacklist policies.

| Command | Description |
|---------|-------------|
| `policies add-blacklist <object_> <value>` | Add a blacklist entry. |
| `policies add-whitelist <object_> <value>` | Add a whitelist entry. |
| `policies delete <policy_id> [--policy_type] [--scope] [--force]` | Delete a policy entry. |
| `policies list [--domain] [--mailbox]` | List whitelist/blacklist policies. |

### `kctl-mailcow provision`

Provision mailboxes from Authentik users.

| Command | Description |
|---------|-------------|
| `provision status <group> <domain> [--ak_profile]` | Show which Authentik users have/don't have mailboxes. |
| `provision sync <group> <domain> [--quota] [--dry_run] [--ak_profile]` | Sync users from an Authentik group to Mailcow mailboxes. |

### `kctl-mailcow quarantine`

Manage quarantined messages.

| Command | Description |
|---------|-------------|
| `quarantine delete <qid> [--force]` | Delete a quarantined message. |
| `quarantine list` | List quarantined messages. |
| `quarantine release <qid>` | Release a quarantined message. |

### `kctl-mailcow queue`

Manage mail queue.

| Command | Description |
|---------|-------------|
| `queue delete <queue_id> [--force]` | Delete queued messages. |
| `queue flush [--queue_id]` | Flush (retry) queued messages. |
| `queue list` | List mail queue entries. |

### `kctl-mailcow ratelimits`

Manage rate limits.

| Command | Description |
|---------|-------------|
| `ratelimits get <mailbox>` | Get rate limit for a mailbox. |
| `ratelimits set <mailbox> <value> [--frame]` | Set rate limit for a mailbox. |

### `kctl-mailcow recipient-maps`

Manage recipient maps (inbound address rewriting).

| Command | Description |
|---------|-------------|
| `recipient-maps create <old_dest> <new_dest> [--active]` | Create a recipient map. |
| `recipient-maps delete <map_id> [--force]` | Delete a recipient map. |
| `recipient-maps list` | List all recipient maps. |

### `kctl-mailcow relay-hosts`

Manage sender-dependent relay hosts.

| Command | Description |
|---------|-------------|
| `relay-hosts create <hostname> [--username] [--password] [--active]` | Create a relay host. |
| `relay-hosts delete <relay_id> [--force]` | Delete a relay host. |
| `relay-hosts get <relay_id>` | Get relay host details. |
| `relay-hosts list` | List all relay hosts. |
| `relay-hosts update <relay_id> [--hostname] [--username] [--password] [--active]` | Update a relay host. |

### `kctl-mailcow resources`

Manage Mailcow resources.

| Command | Description |
|---------|-------------|
| `resources create <name> [--description] [--kind] [--active] [--multiple_bookings]` | Create a resource. |
| `resources delete <name> [--force]` | Delete a resource. |
| `resources list` | List all resources. |

### `kctl-mailcow rspamd`

Manage rspamd filter settings.

| Command | Description |
|---------|-------------|
| `rspamd create <desc> <content> [--active]` | Create an rspamd setting. |
| `rspamd delete <setting_id> [--force]` | Delete an rspamd setting. |
| `rspamd list` | List all rspamd settings. |
| `rspamd update <setting_id> [--desc] [--content] [--active]` | Update an rspamd setting. |

### `kctl-mailcow skill`

Claude Code skill management.

| Command | Description |
|---------|-------------|
| `skill generate [--output] [--install] [--check]` | Auto-generate SKILL.md from CLI command registry. |

**Examples:**
```bash
kctl-mailcow skill generate
kctl-mailcow skill generate --install
kctl-mailcow skill generate --check
```

### `kctl-mailcow status`

Server status and health.

### `kctl-mailcow sync-jobs`

Manage IMAP sync jobs.

| Command | Description |
|---------|-------------|
| `sync-jobs add <local_mailbox> <remote_host> <remote_user> <remote_password> [--remote_port] [--mins_interval] [--enc1] [--delete2duplicates] [--active]` | Add a new sync job. |
| `sync-jobs delete <job_id> [--force]` | Delete a sync job. |
| `sync-jobs list` | List all sync jobs. |

### `kctl-mailcow tls`

Manage TLS policy maps.

| Command | Description |
|---------|-------------|
| `tls create <domain> [--policy] [--parameters] [--active]` | Create a TLS policy map entry. |
| `tls delete <tls_id> [--force]` | Delete a TLS policy map entry. |
| `tls list` | List all TLS policy maps. |

### `kctl-mailcow transports`

Manage outbound transport maps.

| Command | Description |
|---------|-------------|
| `transports create <destination> <nexthop> [--username] [--password] [--active]` | Create a transport map. |
| `transports delete <transport_id> [--force]` | Delete a transport map. |
| `transports get <transport_id>` | Get transport map details. |
| `transports list` | List all transport maps. |
| `transports update <transport_id> [--destination] [--nexthop] [--username] [--password] [--active]` | Update a transport map. |

## Configuration

Shared config: `~/.config/kodemeio/config.yaml`

```bash
kctl-mailcow config init       # Interactive setup
kctl-mailcow config show       # Show current config
kctl-mailcow config profiles   # List profiles
kctl-mailcow config current    # Show active profile
kctl-mailcow config validate   # Verify config
```
