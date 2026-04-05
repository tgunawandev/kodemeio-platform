# kctl-mailcow

Kodemeio Mailcow CLI -- manage your Mailcow mail server via the REST API.

## Installation

```bash
uv tool install ./packages/kctl-mailcow
```

To upgrade after code changes:

```bash
uv tool install --force --reinstall ./packages/kctl-mailcow
```

With Authentik provisioning support:

```bash
uv tool install "./packages/kctl-mailcow[provision]"
```

## Quick Start

```bash
# Configure connection (interactive)
kctl-mailcow config init

# Verify connectivity
kctl-mailcow config test

# Dashboard overview
kctl-mailcow dashboard

# List all domains
kctl-mailcow domains list

# List all mailboxes
kctl-mailcow mailboxes list

# Check server health
kctl-mailcow health
```

## Command Groups

| Group               | Description                                                        |
|---------------------|--------------------------------------------------------------------|
| `domains`           | Manage mail domains (list, get, add, update, delete, dns-check)    |
| `mailboxes`         | Manage mailboxes (list, get, add, update, delete)                  |
| `aliases`           | Manage email aliases (list, get, add, update, delete)              |
| `alias-domains`     | Manage whole-domain aliases (domain-level aliasing)                |
| `dkim`              | Manage DKIM keys (list, get, generate)                             |
| `queue`             | Manage mail queue (list, flush, delete)                            |
| `quarantine`        | Manage quarantined messages                                        |
| `logs`              | View Mailcow service logs                                          |
| `status`            | Server status and health overview                                  |
| `health`            | Health checks for Mailcow services                                 |
| `dashboard`         | System overview dashboard                                          |
| `sync-jobs`         | Manage IMAP sync jobs                                              |
| `fwdhost`           | Manage forwarding hosts                                            |
| `tls`               | Manage TLS policy maps                                             |
| `resources`         | Manage Mailcow resource limits                                     |
| `ratelimits`        | Manage per-mailbox or per-domain rate limits                       |
| `identity-provider` | Manage external identity provider (OIDC SSO) for admin login       |
| `oauth2-clients`    | Manage OAuth2 clients (Mailcow as OAuth2 provider)                 |
| `provision`         | Provision mailboxes from Authentik users                           |
| `fail2ban`          | Manage fail2ban bans (list, add, delete)                           |
| `policies`          | Manage spam whitelist/blacklist policies                           |
| `app-passwords`     | Manage per-mailbox app passwords                                   |
| `password-policy`   | Manage global password policy                                      |
| `domain-admins`     | Manage domain administrators                                       |
| `filters`           | Manage per-mailbox Sieve filters                                   |
| `transports`        | Manage outbound transport maps                                     |
| `relay-hosts`       | Manage sender-dependent relay hosts                                |
| `bcc-maps`          | Manage BCC maps for compliance copies                              |
| `recipient-maps`    | Manage recipient maps (inbound address rewriting)                  |
| `rspamd`            | Manage rspamd spam filter settings                                 |
| `config`            | CLI configuration (profiles, init, test, show)                     |

## Global Options

| Option              | Short | Description                        |
|---------------------|-------|------------------------------------|
| `--json`            |       | Output as JSON                     |
| `--quiet`           | `-q`  | Suppress info messages             |
| `--profile`         | `-p`  | Config profile name                |
| `--url`             |       | API URL override (per-invocation)  |
| `--api-key`         |       | API key override (per-invocation)  |
| `--version`         | `-V`  | Show version and exit              |

## Configuration

Configuration is stored in `~/.config/kodemeio/config.yaml` under the `mailcow` service key.

### Initialize a profile

```bash
kctl-mailcow config init
```

This prompts for:
- Mailcow base URL (e.g. `https://mail.example.com`)
- API key (generate in Mailcow UI under Configuration > Access > API)

### Multiple profiles

```bash
# Add a second profile
kctl-mailcow config add --profile staging

# Switch active profile
kctl-mailcow config use staging

# List all profiles
kctl-mailcow config profiles

# Show current profile (secrets masked)
kctl-mailcow config show
```

### Environment variable override

```bash
export MAILCOW_URL=https://mail.example.com
export MAILCOW_API_KEY=your-api-key
kctl-mailcow domains list
```

Or override per-invocation:

```bash
kctl-mailcow --url https://mail.example.com --api-key <key> domains list
```

## Common Workflows

### Domain management

```bash
# List domains with alias/mailbox quotas
kctl-mailcow domains list

# Add a new domain
kctl-mailcow domains add example.com --aliases 100 --mailboxes 50 --quota 10240

# Check DNS records for a domain
kctl-mailcow domains dns-check example.com

# Deactivate a domain
kctl-mailcow domains update example.com --active 0
```

### Mailbox management

```bash
# List mailboxes, optionally filtered by domain
kctl-mailcow mailboxes list
kctl-mailcow mailboxes list --domain example.com

# Add a mailbox
kctl-mailcow mailboxes add user@example.com --name "Full Name" --quota 2048

# Get mailbox details
kctl-mailcow mailboxes get user@example.com

# Delete a mailbox
kctl-mailcow mailboxes delete user@example.com
```

### DKIM management

```bash
# List DKIM selectors
kctl-mailcow dkim list

# Generate DKIM key for a domain
kctl-mailcow dkim generate example.com

# Get DKIM public key (for DNS record)
kctl-mailcow dkim get example.com
```

### Authentik provisioning

Provision mailboxes automatically from Authentik group membership:

```bash
# Dry-run: preview what would be created
kctl-mailcow provision sync --group "Mail Users" --domain example.com --dry-run

# Sync users to mailboxes (creates new, skips existing)
kctl-mailcow provision sync --group "Mail Users" --domain example.com

# Check provisioning status
kctl-mailcow provision status

# Use a specific Authentik profile
kctl-mailcow provision sync --group "Mail Users" --domain example.com --ak-profile staging
```

Requires the `provision` extra: `uv tool install "./packages/kctl-mailcow[provision]"` and a configured `kctl-ak` profile.

### Mail queue

```bash
# View queued messages
kctl-mailcow queue list

# Flush (deliver) all queued messages
kctl-mailcow queue flush

# Delete all queued messages
kctl-mailcow queue delete
```

### Security & compliance

```bash
# List fail2ban bans
kctl-mailcow fail2ban list

# Unban an IP
kctl-mailcow fail2ban delete 1.2.3.4

# Add spam whitelist entry
kctl-mailcow policies add-whitelist user@trusted.com

# Add spam blacklist entry
kctl-mailcow policies add-blacklist spammer@example.com

# Manage BCC maps (compliance copies)
kctl-mailcow bcc-maps list
kctl-mailcow bcc-maps add user@example.com --bcc compliance@corp.com
```

### OIDC / OAuth2 (Authentik SSO)

```bash
# Configure external identity provider for admin login
kctl-mailcow identity-provider list
kctl-mailcow identity-provider add --provider authentik --client-id <id> --client-secret <secret>

# Manage OAuth2 clients (Mailcow as provider)
kctl-mailcow oauth2-clients list
kctl-mailcow oauth2-clients add --name "My App" --redirect-uri https://app.example.com/callback
```

### Monitoring & logs

```bash
# View service logs (all services)
kctl-mailcow logs

# View logs for a specific service
kctl-mailcow logs --service postfix

# Server status summary
kctl-mailcow status

# Health check
kctl-mailcow health

# Full dashboard
kctl-mailcow dashboard
```

## Output Formats

All commands support multiple output formats:

```bash
# Pretty table (default)
kctl-mailcow domains list

# JSON (for scripting / piping to jq)
kctl-mailcow domains list --json

# Quiet mode (suppress info messages)
kctl-mailcow mailboxes add user@example.com --name "Alice" --quota 1024 --quiet
```

## Development

```bash
# Install in development mode
cd packages/kctl-mailcow
uv sync --all-extras

# Run tests
uv run pytest tests/ -v

# Lint
uv run ruff check src/

# Type check
uv run mypy src/

# Run CLI directly (without install)
uv run kctl-mailcow --help
```

### Project structure

```
packages/kctl-mailcow/
├── src/kctl_mailcow/
│   ├── cli.py               # Main entry point, registers all command groups
│   ├── commands/            # One module per command group (31 groups)
│   │   ├── domains.py
│   │   ├── mailboxes.py
│   │   ├── aliases.py
│   │   └── ...
│   └── core/
│       ├── callbacks.py     # AppContext — profile + client init
│       ├── client.py        # Mailcow API client (extends APIClient)
│       ├── helpers.py       # Shared output helpers
│       └── provisioner.py   # Authentik → Mailcow provisioning logic
├── tests/                   # pytest test suite
└── pyproject.toml
```

### Adding a new command group

1. Create `src/kctl_mailcow/commands/my_group.py` with a `typer.Typer` app
2. Import and register it in `cli.py`:
   ```python
   from kctl_mailcow.commands.my_group import app as my_group_app
   app.add_typer(my_group_app, name="my-group")
   ```
3. Add tests in `tests/test_my_group.py`

## Dependencies

| Package      | Purpose                              |
|--------------|--------------------------------------|
| `kctl-lib`   | Shared CLI infrastructure (>=0.4.0)  |
| `typer`      | CLI framework                        |
| `rich`       | Terminal formatting                  |
| `pydantic`   | Data validation                      |
| `httpx`      | HTTP client                          |
| `pyyaml`     | YAML config parsing                  |
| `kctl-ak`    | Authentik client (provision extra)   |
