# kctl-ak

Kodemeio Authentik CLI -- manage your Authentik identity provider from the command line.

## Install

```bash
uv pip install -e .
```

## Quick Start

```bash
kctl-ak config init
kctl-ak health
kctl-ak users list
kctl-ak users provision user@kodeme.io basic-user
```

## Global Options

These options apply to every command and subcommand:

| Option | Short | Description |
|--------|-------|-------------|
| `--json` | | Output as JSON (machine-readable) |
| `--quiet` | `-q` | Suppress informational messages |
| `--profile` | `-p` | Config profile name (default: active profile) |
| `--url` | | API URL override (bypasses config) |
| `--token` | | API token override (bypasses config) |
| `--version` | `-V` | Show version and exit |

Example using global options:

```bash
kctl-ak --profile staging users list --json
kctl-ak --url https://auth.example.com --token tk_xxx health
kctl-ak -q --json sessions list
```

## Command Groups (24)

| Group | Description |
|-------|-------------|
| `users` | User management, provisioning, bulk invite/import |
| `groups` | Group management, hierarchy, sync from YAML |
| `apps` | Application management, audit, orphaned detection |
| `providers` | OAuth2, LDAP, SAML, Proxy provider management |
| `flows` | Authentication flow management |
| `audit` | Event log, login tracking, suspicious event detection |
| `sessions` | Authenticated session management |
| `tokens` | API token management, rotation |
| `blueprints` | Blueprint management |
| `maintenance` | System maintenance and administration |
| `setup` | Setup wizards (OAuth2, Proxy, admin, recovery) |
| `health` | Health checks and diagnostics |
| `dashboard` | System overview with security view |
| `config` | CLI configuration and profiles |
| `mail` | Email operations via SMTP |
| `policies` | Policy management and testing |
| `stages` | Stage management (prompt, password, identification, etc.) |
| `property-mappings` | Property mapping management (OAuth2, SAML, LDAP, SCIM) |
| `certificates` | Certificate and key pair management |
| `outposts` | Outpost instance and service connection management |
| `brands` | Brand/tenant management |
| `notifications` | Notification rules and transports |
| `system` | System settings, impersonation, token defaults, event retention |
| `provision` | Lifecycle provisioning (onboard, offboard, sync, webhook) |

## Authentik Data Model

Authentik organises identity around five core concepts:

- **Flows** — ordered sequences of stages that execute an authentication, enrollment, or recovery journey (e.g. `default-authentication-flow`).
- **Stages** — individual steps inside a flow: identification, password check, MFA prompt, user write, etc.
- **Providers** — protocol adapters that expose an application to clients: OAuth2/OIDC, SAML, LDAP, Proxy.
- **Applications** — the logical service a user accesses (e.g. Grafana). Each application is bound to exactly one provider and can have launch URLs and icons.
- **Outposts** — lightweight reverse-proxy or LDAP agents deployed alongside applications to enforce authentication. Each outpost is tied to one or more providers and reports health back to Authentik.
- **Policies** — expression or binding-based rules attached to flows, stages, or applications to control access.
- **Property Mappings** — transform Authentik user attributes into the format expected by a provider (OAuth2 claims, SAML attributes, LDAP schema fields).

Understanding this layered model is key: `setup oauth2` wires a Provider + Application + Flow bindings in one command, while the individual `providers`, `flows`, `apps`, and `stages` groups let you inspect and manage each layer independently.

## Users

```bash
kctl-ak users list                          # List all users
kctl-ak users get <username-or-id>          # Get user detail
kctl-ak users search <query>                # Search by name/email
kctl-ak users create                        # Interactive user creation
kctl-ak users update <username-or-id>       # Update user fields
kctl-ak users password <username-or-id>     # Set password
kctl-ak users recovery <username-or-id>     # Generate recovery link
kctl-ak users activate <username-or-id>     # Re-enable user
kctl-ak users deactivate <username-or-id>   # Disable (lock) user
kctl-ak users delete <username-or-id>       # Delete user
```

## Role-Based Provisioning

```bash
kctl-ak users roles                         # List available roles
kctl-ak users roles --verify                # Check groups exist in Authentik
kctl-ak users provision user@example.com basic-user devops
```

| Role | Description |
|------|-------------|
| `admin` | Full IT admin (all apps + superuser) |
| `basic-user` | Standard employee (Mattermost) |
| `office-user` | Office worker (Mattermost + Grafana) |
| `erp-user` | ERP access (Mattermost + Odoo) |
| `devops` | DevOps engineer (Grafana admin + N8N + monitoring) |
| `mattermost-user` | Chat only |

## Group Sync

```bash
kctl-ak groups sync --dry-run               # Preview from group-structure.yaml
kctl-ak groups sync --no-dry-run            # Create missing groups
```

## Sessions

```bash
kctl-ak sessions list                       # All active sessions
kctl-ak sessions get <session-id>           # Session detail
kctl-ak sessions kill <session-id>          # Terminate a session
kctl-ak sessions kill-user <username>       # Terminate all sessions for a user
kctl-ak sessions stats                      # Session statistics
kctl-ak sessions active                     # Currently active sessions only
```

## Tokens

```bash
kctl-ak tokens list                         # List all API tokens
kctl-ak tokens get <identifier>             # Token detail
kctl-ak tokens create <identifier>          # Create a new token
kctl-ak tokens view <identifier>            # Reveal token key (masked)
kctl-ak tokens delete <identifier>          # Delete token
kctl-ak tokens rotate <identifier>          # Rotate/regenerate token key
kctl-ak tokens expire-all                   # Expire all tokens (emergency)
```

## Flows and Stages

```bash
kctl-ak flows list                          # List all flows
kctl-ak flows get <slug>                    # Flow detail
kctl-ak flows bindings <slug>               # Stage bindings for a flow
kctl-ak flows stages <slug>                 # Stages attached to a flow
kctl-ak flows export <slug>                 # Export flow as blueprint YAML
kctl-ak flows execute <slug>                # Get flow executor URL

kctl-ak stages list                         # List all stages (all types)
kctl-ak stages get <stage-id>               # Stage detail
```

## Providers

```bash
kctl-ak providers list                      # List all providers (all types)

# OAuth2 / OIDC
kctl-ak providers oauth2 list
kctl-ak providers oauth2 get <slug>
kctl-ak providers oauth2 create <name>
kctl-ak providers oauth2 credentials <slug> # Show client ID + secret
kctl-ak providers oauth2 update <slug>
kctl-ak providers oauth2 delete <slug>

# LDAP
kctl-ak providers ldap list
kctl-ak providers ldap get <slug>
kctl-ak providers ldap create <name>
kctl-ak providers ldap delete <slug>

# SAML
kctl-ak providers saml list
kctl-ak providers saml get <slug>
kctl-ak providers saml create <name>
kctl-ak providers saml metadata <slug>      # Download SAML metadata XML
```

## Applications

```bash
kctl-ak apps list                           # List all applications
kctl-ak apps get <slug>                     # Application detail
kctl-ak apps create <name>                  # Create application
kctl-ak apps update <slug>                  # Update application
kctl-ak apps delete <slug>                  # Delete application
kctl-ak apps set-icon <slug> <url>          # Set application icon
kctl-ak apps launch-urls                    # List all application launch URLs
kctl-ak apps access <slug>                  # Show who can access this app
kctl-ak apps audit <slug>                   # Audit log for this application
kctl-ak apps orphaned                       # Applications with no provider bound
kctl-ak apps sync                           # Sync applications from config
```

## Outposts

```bash
kctl-ak outposts list                       # List all outposts
kctl-ak outposts get <outpost-id>           # Outpost detail
kctl-ak outposts create <name>              # Create outpost
kctl-ak outposts update <outpost-id>        # Update outpost
kctl-ak outposts delete <outpost-id>        # Delete outpost
kctl-ak outposts health <outpost-id>        # Health status of outpost instances
kctl-ak outposts connections                # List service connections
kctl-ak outposts create-connection          # Add a service connection
kctl-ak outposts delete-connection <id>     # Remove a service connection
```

## Certificates

```bash
kctl-ak certificates list                   # List all certificate/key pairs
kctl-ak certificates get <id>               # Certificate detail
kctl-ak certificates create                 # Upload an existing certificate
kctl-ak certificates generate <name>        # Generate a self-signed certificate
kctl-ak certificates delete <id>            # Delete certificate
kctl-ak certificates view <id>              # Show PEM certificate content
kctl-ak certificates used-by <id>           # Show providers/flows using this cert
```

## Setup Wizards

```bash
kctl-ak setup status                        # Show current setup status
kctl-ak setup oauth2 <app-name>             # Full OAuth2 app: provider + application + flow bindings
kctl-ak setup proxy <app-name>              # Proxy provider setup (forward auth)
kctl-ak setup admin <username>              # Promote user to superuser
kctl-ak setup recovery <username>           # Generate admin recovery link
kctl-ak setup app <name>                    # Scaffold a new application entry
kctl-ak setup batch                         # Batch setup from YAML config
```

## Lifecycle Provisioning

```bash
kctl-ak provision onboard <username>        # Full onboarding: create user, assign groups, send invite
kctl-ak provision offboard <username>       # Offboard: deactivate, kill sessions, revoke tokens
kctl-ak provision status <username>         # Show provisioning state for a user
kctl-ak provision sync                      # Sync provisioning state from config
kctl-ak provision setup-webhook             # Configure Authentik outbound webhook
```

## Security

```bash
kctl-ak dashboard --security               # Security-focused overview
kctl-ak audit suspicious                   # Failed logins, privilege changes
kctl-ak system impersonation off           # Disable impersonation
kctl-ak sessions kill-user <username>      # Force-logout a compromised account
kctl-ak tokens expire-all                  # Emergency: expire all API tokens
```

## Config Management

```bash
kctl-ak config init                        # Interactive profile setup
kctl-ak config add --name prod             # Add a named profile
kctl-ak config show                        # Show active profile (secrets masked)
kctl-ak config use <profile>               # Switch active profile
kctl-ak config profiles                    # List all profiles
kctl-ak config validate                    # Validate config file
kctl-ak config set <key> <value>           # Set a config key in active profile
kctl-ak config remove <profile>            # Remove a profile
kctl-ak config current                     # Print active profile name
```

Config lives at `~/.config/kodemeio/config.yaml` under the `authentik` service key, shared across all kctl-* tools.

## Shell Completions

```bash
# Zsh
kctl-ak --install-completion zsh
echo 'source ~/.zsh/completions/_kctl-ak' >> ~/.zshrc

# Bash
kctl-ak --install-completion bash
echo 'source ~/.bash_completions/kctl-ak.sh' >> ~/.bashrc

# Fish
kctl-ak --install-completion fish
```

After installing, reload your shell or open a new terminal. Tab-complete works for command groups, subcommands, and most option values.

## Development

```bash
uv sync --all-extras
uv run pytest tests/ -v                    # 166 tests
uv run ruff check src/
uv run mypy src/
```

## Dependencies

- Python >= 3.12
- `kctl-lib >= 0.4.0` (shared CLI infrastructure)
- Typer + Rich + Pydantic 2 + httpx
