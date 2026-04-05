# kctl-cf

Kodemeio Cloudflare CLI -- manage DNS, tunnels, WAF, cache, Workers, R2, email routing, and Zero Trust Access across all zones and accounts.

## Installation

```bash
uv tool install kctl-cf
```

To upgrade after code changes:

```bash
uv tool install --force --reinstall kctl-cf
```

## Quick Start

```bash
# Configure connection (interactive)
kctl-cf config init

# Verify connectivity
kctl-cf health check

# List all zones in the account
kctl-cf zones list

# List DNS records for a zone
kctl-cf records list --zone example.com

# Purge cache for a zone
kctl-cf cache purge-all --zone example.com

# Check SSL/TLS status
kctl-cf ssl status --zone example.com

# List Cloudflare Tunnels
kctl-cf tunnels list

# Account-wide status overview
kctl-cf status overview
```

## Command Groups

| Group               | Commands | Description                                                     |
|---------------------|----------|-----------------------------------------------------------------|
| `access`            | 17       | Manage Cloudflare Zero Trust Access (apps, policies, groups)    |
| `analytics`         | 2        | Zone analytics and traffic reports                              |
| `argo`              | 3        | Manage Argo Smart Routing and Tiered Caching                    |
| `cache`             | 3        | Manage cache settings and purge                                 |
| `config`            | 10       | Manage CLI configuration and profiles                           |
| `custom-hostnames`  | 5        | Manage Custom Hostnames (Cloudflare for SaaS)                   |
| `email-routing`     | 9        | Manage Cloudflare Email Routing rules and addresses             |
| `export`            | 2        | Export and backup Cloudflare configuration                      |
| `health`            | 1        | Health checks                                                   |
| `load-balancers`    | 11       | Manage Load Balancers, pools, and monitors                      |
| `page-rules`        | 5        | Manage Cloudflare Page Rules                                    |
| `pages`             | 13       | Manage Cloudflare Pages projects and deployments                |
| `r2`                | 7        | Manage R2 object storage buckets                                |
| `records`           | 9        | Manage DNS records (CRUD, bulk create, import/export, scan)     |
| `redirects`         | 7        | Manage Cloudflare Redirect and Bulk Redirect rules              |
| `selftest`          | 1        | Run built-in test suite                                         |
| `spectrum`          | 5        | Manage Spectrum applications                                    |
| `speed`             | 7        | Manage speed optimization settings (minify, polish, mirage)     |
| `ssl`               | 7        | Manage SSL/TLS settings and certificates                        |
| `status`            | 1        | Account status dashboard                                        |
| `terraform`         | 6        | Run Terraform commands for Cloudflare infrastructure            |
| `tunnels`           | 8        | Manage Cloudflare Tunnels                                       |
| `waf`               | 12       | Manage WAF and firewall rules                                   |
| `waiting-rooms`     | 5        | Manage Waiting Rooms                                            |
| `workers`           | 17       | Manage Cloudflare Workers, routes, and KV                       |
| `zones`             | 9        | Manage DNS zones                                                |

**Total: ~195 commands across 26 groups.**

## Command Aliases

Hidden short aliases are available for common workflows:

| Alias | Expands to              |
|-------|-------------------------|
| `zl`  | `zones list`            |
| `zg`  | `zones get <zone>`      |
| `rl`  | `records list`          |
| `hc`  | `health check`          |
| `cs`  | `cache status`          |
| `cp`  | `cache purge-all`       |
| `ss`  | `ssl status`            |
| `wl`  | `workers list`          |
| `ea`  | `export all`            |
| `tl`  | `tunnels list`          |
| `st`  | `status overview`       |
| `bk`  | `export backup`         |

Example:

```bash
kctl-cf zl                         # same as: kctl-cf zones list
kctl-cf rl --zone example.com      # same as: kctl-cf records list --zone example.com
kctl-cf cp --zone example.com      # same as: kctl-cf cache purge-all --zone example.com --yes
```

## Global Options

```
--json                Output as JSON (machine-readable)
--quiet, -q           Suppress informational messages
--format, -f          Output format: pretty/json/csv/yaml (default: pretty)
--no-header           Omit header row in CSV output
--profile, -p         Use a named config profile
--api-token           API token override (skips config file)
--account-id          Account ID override (skips config file)
--version, -V         Show version and exit
```

Global options are inherited by aliases. For example:

```bash
kctl-cf --json --profile prod zl   # zones list as JSON using 'prod' profile
```

## Configuration

### Shared Config File

All kctl-* CLIs share a single config file at `~/.config/kodemeio/config.yaml`. kctl-cf uses the `cloudflare` service key for its settings.

### Profiles

kctl-cf supports named profiles for managing multiple Cloudflare accounts:

```bash
# Interactive setup (recommended for first time)
kctl-cf config init

# Add a profile manually
kctl-cf config add production \
  --api-token $CF_API_TOKEN \
  --account-id $CF_ACCOUNT_ID \
  --default-zone example.com

# Add a staging profile
kctl-cf config add staging \
  --api-token $CF_STAGING_TOKEN \
  --account-id $CF_STAGING_ACCOUNT_ID

# Switch default profile
kctl-cf config use production

# Use a profile for a single command
kctl-cf --profile staging zones list

# Show active profile
kctl-cf config current

# List all profiles
kctl-cf config profiles

# Show config (secrets masked)
kctl-cf config show

# Validate config
kctl-cf config validate

# Remove a profile
kctl-cf config remove staging
```

### Environment Variables

Config values can be overridden at runtime via CLI flags or environment variables:

```bash
export CF_API_TOKEN=your-token
export CF_ACCOUNT_ID=your-account-id
kctl-cf zones list
```

### Default Zone

Set a default zone in your profile to avoid passing `--zone` on every command:

```bash
kctl-cf config set default_zone example.com
```

## Common Workflows

### DNS Management

```bash
# List all A records for a zone
kctl-cf records list --zone example.com --type A

# Create a new DNS record
kctl-cf records create \
  --zone example.com \
  --type A \
  --name api.example.com \
  --content 1.2.3.4 \
  --proxied

# Update an existing record
kctl-cf records update <record-id> --content 5.6.7.8 --zone example.com

# Delete a record (requires --force)
kctl-cf records delete <record-id> --force --zone example.com

# Bulk create from JSON file
kctl-cf records bulk-create --file records.json --zone example.com

# Import BIND zone file
kctl-cf records import --file zone.txt --zone example.com

# Export records as BIND format
kctl-cf records export --zone example.com --file backup.txt
```

### Cache

```bash
# Purge all cache
kctl-cf cache purge-all --zone example.com

# Check cache status
kctl-cf cache status --zone example.com
```

### WAF & Security

```bash
# List WAF rules
kctl-cf waf list --zone example.com

# List firewall rules
kctl-cf waf firewall-list --zone example.com
```

### Tunnels

```bash
# List tunnels
kctl-cf tunnels list

# Get tunnel details
kctl-cf tunnels get <tunnel-id>

# List tunnel connectors
kctl-cf tunnels connectors <tunnel-id>
```

### Workers

```bash
# List all workers
kctl-cf workers list

# Deploy a worker script
kctl-cf workers deploy --name my-worker --file worker.js

# List KV namespaces
kctl-cf workers kv-list
```

### Export & Backup

```bash
# Export all zone config
kctl-cf export all --zone example.com

# Full account backup
kctl-cf export backup
```

## Shell Completions

```bash
# Install for your shell
kctl-cf --install-completion bash
kctl-cf --install-completion zsh
kctl-cf --install-completion fish
```

## Plugin Development

kctl-cf supports extending the CLI via Python entry points. Create a package that registers a Typer app under the `kctl_cf.plugins` entry point group:

```toml
# In your plugin's pyproject.toml
[project.entry-points."kctl_cf.plugins"]
my_plugin = "my_plugin.cli:app"
```

The plugin's `app` (a `typer.Typer` instance) will be registered as a command group automatically on startup.

## Development

### Running Tests

```bash
cd packages/kctl-cf
uv run pytest tests/ -v
```

### Linting and Formatting

```bash
cd packages/kctl-cf
uv run ruff check src/
uv run ruff format src/
```

### Type Checking

```bash
cd packages/kctl-cf
uv run mypy src/kctl_cf/
```

### Project Structure

```
packages/kctl-cf/
  src/kctl_cf/
    cli.py              Main app + command registration
    __init__.py         Version
    core/
      callbacks.py      Global option handling (AppContext)
      api_client.py     Cloudflare API client (wraps kctl-lib APIClient)
      config.py         Profile/config management
      exceptions.py     Custom exception hierarchy
      output.py         Output formatting (table, JSON, plain)
      utils.py          Zone resolution and shared helpers
    commands/
      aliases.py        Short command aliases
      access.py         Zero Trust Access
      analytics.py      Zone analytics
      argo.py           Argo Smart Routing
      cache.py          Cache management
      config_cmd.py     Config subcommands
      custom_hostnames.py  Cloudflare for SaaS
      email_routing.py  Email Routing
      export.py         Export/backup
      health.py         Health checks
      load_balancers.py Load Balancers
      page_rules.py     Page Rules
      pages.py          Cloudflare Pages
      r2.py             R2 object storage
      records.py        DNS records
      redirects.py      Redirect rules
      selftest.py       Built-in test suite
      spectrum.py       Spectrum apps
      speed.py          Speed optimization
      ssl.py            SSL/TLS settings
      status.py         Account status
      terraform.py      Terraform integration
      tunnels.py        Cloudflare Tunnels
      waf.py            WAF and firewall rules
      waiting_rooms.py  Waiting Rooms
      workers.py        Workers, routes, KV
      zones.py          DNS zones
  tests/                pytest test suite
  pyproject.toml        Package metadata and tool config
  README.md             This file
```
