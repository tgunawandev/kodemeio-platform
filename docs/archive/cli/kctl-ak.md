# kctl-ak

Command reference for `kctl-ak` (23 groups, ~183 commands).

> Auto-generated on 2026-04-02. Do not edit manually.
> Regenerate with: `uv run python scripts/generate-cli-docs.py`

## Global Options

| Flag | Description |
|------|-------------|
| `--json` | JSON output |
| `--quiet`, `-q` | Suppress info messages |
| `--format`, `-f` | Output format: pretty/json/csv/yaml |
| `--no-header` | Omit headers in CSV output |
| `--profile`, `-p` | Config profile name |
| `--version`, `-V` | Show version |

## Commands

### `kctl-ak apps`

Application management

| Command | Description |
|---------|-------------|
| `apps access <slug>` | Show which groups and policies can access an application. |
| `apps audit` | Show apps with missing providers, no launch URL, or no policy bindings. |
| `apps create <name> <slug> [--provider] [--launch_url] [--description]` | Create a new application. |
| `apps delete <slug> [--force]` | Delete an application. |
| `apps get <slug>` | Get application details. |
| `apps launch-urls` | List all applications with their launch URLs. |
| `apps list` | List all applications. |
| `apps orphaned` | List applications that have no active provider. |
| `apps update <slug> <field> <value>` | Update an application field. |

### `kctl-ak audit`

Event and audit log management.

| Command | Description |
|---------|-------------|
| `audit changes [--model]` | List model change events. |
| `audit delete [--event_id] [--action] [--user] [--days] [--force]` | Delete audit events by ID, action type, or user. |
| `audit delete-impersonation [--force]` | Delete all impersonation-related events. |
| `audit export [--days] [--format]` | Export audit events to JSON or CSV. |
| `audit get <event_id>` | Show details for a single event. |
| `audit list [--page] [--action] [--user] [--client_ip]` | List audit events. |
| `audit logins [--failed]` | List login events. |
| `audit stats [--days]` | Show event statistics aggregated by action type. |
| `audit suspicious [--days]` | Show suspicious events (failed logins, privilege changes, impersonation). |
| `audit tail [--interval]` | Tail new audit events (polls the API). |

### `kctl-ak blueprints`

Manage Authentik blueprints.

| Command | Description |
|---------|-------------|
| `blueprints apply <bp_id>` | Apply (or re-apply) a blueprint instance. |
| `blueprints export <flow_slug>` | Export a flow as a blueprint YAML file. |
| `blueprints get <bp_id>` | Show blueprint instance details. |
| `blueprints instances` | List all blueprint instances. |

### `kctl-ak brands`

Brand (tenant) management.

| Command | Description |
|---------|-------------|
| `brands create <domain> [--name] [--flow_authentication] [--flow_invalidation]` | Create a brand. |
| `brands current` | Show the current brand (for this domain). |
| `brands delete <id_> [--force]` | Delete a brand. |
| `brands get <id_>` | Get brand details. |
| `brands list` | List all brands. |
| `brands update <id_> [--name] [--branding_title] [--branding_logo] [--branding_favicon] [--flow_authentication] [--flow_invalidation]` | Update a brand. |

### `kctl-ak certificates`

Certificate and key pair management.

| Command | Description |
|---------|-------------|
| `certificates create <name> <cert_file> [--key_file]` | Upload a certificate (and optional key) from PEM files. |
| `certificates delete <id_> [--force]` | Delete a certificate-key pair. |
| `certificates generate <name> [--common_name] [--days]` | Generate a self-signed certificate-key pair. |
| `certificates get <id_>` | Get certificate details. |
| `certificates list` | List all certificate-key pairs. |
| `certificates used-by <id_>` | Show what uses this certificate. |
| `certificates view <id_>` | View certificate details (parsed certificate info). |

### `kctl-ak config`

Manage CLI configuration and profiles.

| Command | Description |
|---------|-------------|
| `config add <name> [--url] [--token] [--roles_dir] [--group_structure] [--set_default]` | Add or update a profile's Authentik connection. |
| `config current` | Show the active profile and connection status. |
| `config init [--url] [--token] [--name]` | Initialize CLI configuration (interactive if no flags given). |
| `config migrate` | Migrate config from flat format to service-scoped format. |
| `config profiles` | List all profiles with Authentik connection status. |
| `config remove <name> [--force] [--service_only]` | Remove a profile or just its Authentik config. |
| `config set <key> <value> [--profile_arg]` | Set a configuration value for the current service. |
| `config show` | Show full configuration (tokens masked). |
| `config test` | Test API connection with current configuration. |
| `config use <name>` | Switch the default profile. |

### `kctl-ak dashboard`

System overview dashboard.

### `kctl-ak flows`

Manage authentication flows.

| Command | Description |
|---------|-------------|
| `flows bindings <slug>` | Show flow stage bindings. |
| `flows execute <slug>` | Show the flow execution URL. |
| `flows export <slug>` | Export a flow as YAML. |
| `flows get <slug>` | Show flow details. |
| `flows list [--designation]` | List all flows. |
| `flows stages <slug>` | List stages used in a flow (via bindings). |

### `kctl-ak groups`

Group management and hierarchy.

| Command | Description |
|---------|-------------|
| `groups add-user <group> <user>` | Add a user to a group. |
| `groups create <name> [--parent] [--superuser]` | Create a new group. |
| `groups delete <identifier> [--force]` | Delete a group. |
| `groups export [--format]` | Export all groups. |
| `groups get <identifier>` | Get detailed group info. |
| `groups list [--page]` | List all groups. |
| `groups members <identifier>` | List members of a group. |
| `groups remove-user <group> <user>` | Remove a user from a group. |
| `groups sync [--dry_run] [--file]` | Sync groups from group-structure.yaml. |
| `groups tree` | Display group hierarchy as a tree. |
| `groups update <identifier> <field> <value>` | Update a group field. |

### `kctl-ak health`

Health checks and diagnostics.

### `kctl-ak mail`

Email operations (uses Authentik's built-in SMTP).

| Command | Description |
|---------|-------------|
| `mail recovery-link <identifier>` | Generate a recovery link (without sending email). |
| `mail send-password <identifier> [--new_password]` | Set a new password and also send a recovery email. |
| `mail send-recovery <identifier>` | Send a password reset email to a user. |
| `mail send-welcome <identifier>` | Send a welcome/onboarding email to a new user. |
| `mail test [--to]` | Test email configuration by checking Authentik's SMTP and email stages. |

### `kctl-ak maintenance`

System maintenance and administration.

| Command | Description |
|---------|-------------|
| `maintenance cache-clear` | Clear system caches. |
| `maintenance clean` | Clean expired sessions and models. |
| `maintenance config` | Show brands/tenant configuration. |
| `maintenance impersonation [--enable] [--require_reason]` | View or toggle user impersonation settings. |
| `maintenance outposts` | List outpost instances. |
| `maintenance run <task_name>` | Trigger a system task to run. |
| `maintenance settings [--set_key] [--value]` | View or modify Authentik system settings. |
| `maintenance status` | Show system status. |
| `maintenance tasks` | List system tasks. |
| `maintenance version` | Show Authentik version info. |
| `maintenance workers` | Show worker status via system info. |

### `kctl-ak notifications`

Manage notifications, rules, and transports.

| Command | Description |
|---------|-------------|
| `notifications create-rule <name> <group> [--severity] [--transports]` | Create a notification rule. |
| `notifications create-transport <name> [--mode] [--webhook_url] [--send_once]` | Create a notification transport. |
| `notifications delete-rule <rule_id> [--force]` | Delete a notification rule. |
| `notifications delete-transport <transport_id> [--force]` | Delete a notification transport. |
| `notifications list [--page]` | List notifications. |
| `notifications mark-read [--notification_id]` | Mark notification(s) as seen. |
| `notifications rules` | List notification rules. |
| `notifications transports` | List notification transports. |
| `notifications update-rule <rule_id> [--name] [--group] [--severity] [--transports]` | Update a notification rule. |

### `kctl-ak outposts`

Outpost instance and service connection management.

| Command | Description |
|---------|-------------|
| `outposts connections` | List all service connections. |
| `outposts create <name> [--type_] [--providers] [--service_connection]` | Create an outpost instance. |
| `outposts create-connection <name> [--type_] [--local] [--url]` | Create a service connection. |
| `outposts delete <id_> [--force]` | Delete an outpost instance. |
| `outposts delete-connection <id_> [--force]` | Delete a service connection. |
| `outposts get <id_>` | Get outpost details. |
| `outposts health <id_>` | Check outpost health. |
| `outposts list` | List all outpost instances. |
| `outposts update <id_> [--name] [--providers] [--service_connection]` | Update an outpost instance. |

### `kctl-ak policies`

Policy management (expression, password, reputation, etc.).

| Command | Description |
|---------|-------------|
| `policies bind <policy_id> <target> [--order] [--enabled] [--negate]` | Create a policy binding. |
| `policies bindings` | List all policy bindings. |
| `policies create <name> [--type_] [--expression] [--execution_logging]` | Create a policy. |
| `policies delete <id_> [--force]` | Delete a policy. |
| `policies get <id_>` | Get policy details. |
| `policies list [--type_]` | List all policies. |
| `policies test <id_> <user>` | Test a policy against a user. |
| `policies unbind <binding_id>` | Delete a policy binding. |
| `policies update <id_> [--name] [--expression] [--execution_logging]` | Update a policy. |

### `kctl-ak property-mappings`

Property mapping management (scope, SAML, LDAP, SCIM).

| Command | Description |
|---------|-------------|
| `property-mappings create-ldap <name> <object_field> <expression>` | Create an LDAP property mapping. |
| `property-mappings create-saml <name> <saml_name> <expression>` | Create a SAML property mapping. |
| `property-mappings create-scim <name> <expression>` | Create a SCIM property mapping. |
| `property-mappings create-scope <name> <scope_name> <expression>` | Create an OAuth2 scope mapping. |
| `property-mappings delete <id_> [--force]` | Delete a property mapping. |
| `property-mappings get <id_>` | Get property mapping details. |
| `property-mappings list [--type_]` | List all property mappings. |
| `property-mappings test <id_> <user>` | Test a property mapping against a user. |
| `property-mappings update <id_> [--name] [--expression]` | Update a property mapping. |

### `kctl-ak providers`

Provider management

| Command | Description |
|---------|-------------|
| `providers ldap` | LDAP providers. |
| `providers list [--type_]` | List all providers across types. |
| `providers oauth2` | OAuth2 providers. |
| `providers proxy` | Proxy providers. |
| `providers saml` | SAML providers. |

### `kctl-ak sessions`

Authenticated session management.

| Command | Description |
|---------|-------------|
| `sessions active` | List currently active sessions (most recent first). |
| `sessions get <session_id>` | Show details for a single session. |
| `sessions kill <session_id>` | Terminate a single session. |
| `sessions kill-user <user> [--force]` | Terminate all sessions for a user. |
| `sessions list [--user]` | List authenticated sessions. |
| `sessions stats` | Show session statistics aggregated by user. |

### `kctl-ak setup`

Setup wizards for providers, apps, and admin access.

| Command | Description |
|---------|-------------|
| `setup admin <username>` | Grant admin/superuser status to a user. |
| `setup app <name> <slug> [--app_type] [--redirect] [--external]` | Create an application with a provider (shortcut for oauth2/proxy commands). |
| `setup oauth2 <name> <redirect_uri> [--client_type] [--slug]` | Create an OAuth2 provider and linked application. |
| `setup proxy <name> <external_host> [--internal_host] [--slug]` | Create a proxy provider (forward auth) and linked application. |
| `setup recovery <username>` | Generate a recovery link for a user. |
| `setup status` | Show what is currently configured. |

### `kctl-ak stages`

Stage management (prompt, password, identification, consent, email, etc.).

| Command | Description |
|---------|-------------|
| `stages create-authenticator-validate <name>` | Create an authenticator validation stage. |
| `stages create-consent <name> [--mode]` | Create a consent stage. |
| `stages create-email <name> [--template]` | Create an email stage. |
| `stages create-identification <name> [--sources] [--user_fields]` | Create an identification stage. |
| `stages create-password <name>` | Create a password stage. |
| `stages create-prompt <name> [--fields]` | Create a prompt stage. |
| `stages create-user-login <name>` | Create a user login stage. |
| `stages create-user-logout <name>` | Create a user logout stage. |
| `stages delete <id_> [--force]` | Delete a stage. |
| `stages get <id_>` | Get stage details. |
| `stages list [--type_]` | List all stages. |
| `stages prompts` | List prompt fields (prompt stage field definitions). |
| `stages update <id_> [--name]` | Update a stage. |

### `kctl-ak system`

System settings, version, and license info.

| Command | Description |
|---------|-------------|
| `system event-retention [--duration]` | Set or show event retention duration. |
| `system impersonation [--state]` | Toggle or show impersonation setting. |
| `system license` | Show enterprise license information. |
| `system settings` | Show Authentik system settings. |
| `system token-defaults [--duration] [--length]` | Set or show default token parameters. |
| `system update-setting <key> <value>` | Update a system setting. |
| `system user-changes [--name] [--email] [--username]` | Toggle user self-service field change settings. |
| `system version` | Show Authentik server version. |

### `kctl-ak tokens`

API token management.

| Command | Description |
|---------|-------------|
| `tokens create <identifier> <user> [--intent] [--description]` | Create a new token and display the key. |
| `tokens delete <identifier> [--force]` | Delete a token. |
| `tokens expire-all <user> [--force]` | Delete all tokens for a user. |
| `tokens get <identifier>` | Show token details (without the key). |
| `tokens list [--user]` | List tokens. |
| `tokens rotate <identifier>` | Rotate a token (delete and recreate with same settings, show new key). |
| `tokens view <identifier>` | View the actual token key. |

### `kctl-ak users`

User management and provisioning.

| Command | Description |
|---------|-------------|
| `users activate <identifier>` | Activate a user. |
| `users bulk-import <file>` | Bulk-import users from a JSON file. |
| `users bulk-invite <file> [--send_mail]` | Bulk invite users from a JSON file. |
| `users create <email> [--name] [--username] [--password] [--groups] [--superuser]` | Create a new user. |
| `users deactivate <identifier>` | Deactivate a user. |
| `users delete <identifier> [--force]` | Delete a user. |
| `users export [--format]` | Export all users. |
| `users get <identifier>` | Get detailed user info. |
| `users groups <identifier>` | List groups for a user. |
| `users invite <email> [--name] [--groups] [--send_mail]` | Invite a user. |
| `users list [--page] [--page_size] [--active] [--inactive]` | List all users. |
| `users me` | Show the current authenticated user. |
| `users password <identifier> [--new_password]` | Set a user's password. |
| `users pending` | List users who have never logged in (invited but not activated). |
| `users provision <email> <role_names> [--name] [--username] [--send_mail]` | Provision a user with one or more roles. |
| `users re-invite <identifier>` | Re-send welcome email to an existing user. |
| `users recovery <identifier>` | Generate a recovery link for a user. |
| `users role <name> [--verify]` | Show details for a specific role. |
| `users roles [--verify]` | List available provisioning roles. |
| `users search <term>` | Search users by name, username, or email. |
| `users update <identifier> <field> <value>` | Update a user field. |
