---
name: cloudflare-admin
description: >
  Cloudflare infrastructure administration via kctl-cloudflare CLI. MUST use for ANY DNS, tunnel, WAF, cache, SSL/TLS, Workers, R2, or Cloudflare operation. Triggers on: "kctl-cloudflare", "cloudflare", "DNS record", "tunnel", "WAF rule", "page rule", "R2 bucket", "worker", "SSL certificate", "cache purge", "email routing", "kodeme.io DNS", or ANY Cloudflare resource management.
version: 2.0.0
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Glob
  - Grep
---

# Cloudflare Administration for Kodemeio

## System Overview

- **Zones**: kodeme.io + 20+ subdomains
- **Architecture**: Cloudflare Edge → cloudflared tunnel → Traefik → Dokploy
- **CLI**: `kctl-cloudflare` (Python, installed via `uv tool install ./cli`)
- **IaC**: Terraform in kodemeio-infra/kodemeio-cloudflare/
- **Config**: `~/.config/kodemeio/config.yaml` → `profiles.<profile>.cloudflare`

## Commands

### Zones

| Command | Description |
|---------|-------------|
| `kctl-cloudflare zones list` | All DNS zones |
| `kctl-cloudflare zones get <zone>` | Zone details |

### DNS Records

| Command | Description |
|---------|-------------|
| `kctl-cloudflare records list [--zone] [--type]` | DNS records |
| `kctl-cloudflare records update <record-id> [--type] [--name] [--content] [--ttl] [--proxied/--no-proxied] [--zone]` | Update DNS record |
| `kctl-cloudflare records bulk-create --file <json-file> [--zone]` | Bulk create records from JSON |
| `kctl-cloudflare records import --file <bind-file> [--zone]` | Import BIND zone file |

### Tunnels

| Command | Description |
|---------|-------------|
| `kctl-cloudflare tunnels list` | Cloudflare Tunnels |
| `kctl-cloudflare tunnels get <name>` | Tunnel details |

### WAF

| Command | Description |
|---------|-------------|
| `kctl-cloudflare waf list [--zone]` | WAF firewall rules |
| `kctl-cloudflare waf ip-rules [--zone]` | IP access rules |
| `kctl-cloudflare waf rate-limits [--zone]` | Rate limiting rules |

### Cache

| Command | Description |
|---------|-------------|
| `kctl-cloudflare cache status [--zone]` | Cache settings |
| `kctl-cloudflare cache purge-all [--zone] [--yes]` | Purge all cache |
| `kctl-cloudflare cache purge <urls...> [--zone]` | Purge specific URLs |

### SSL/TLS

| Command | Description |
|---------|-------------|
| `kctl-cloudflare ssl status [--zone]` | SSL/TLS mode |
| `kctl-cloudflare ssl certificates [--zone]` | Certificate packs |
| `kctl-cloudflare ssl origin-certs` | List origin certificates |
| `kctl-cloudflare ssl create-origin-cert --hostname <h> [--hostname ...] [--validity 5475] [--type origin-rsa]` | Create origin certificate |
| `kctl-cloudflare ssl delete-origin-cert <cert-id> [--force]` | Delete origin certificate |
| `kctl-cloudflare ssl min-tls [--version 1.0/1.1/1.2/1.3] [--zone]` | Get/set minimum TLS version |
| `kctl-cloudflare ssl always-https [--enable/--disable] [--zone]` | Get/set Always Use HTTPS |

### Workers

| Command | Description |
|---------|-------------|
| `kctl-cloudflare workers list` | Worker scripts |
| `kctl-cloudflare workers routes [--zone]` | Worker routes |
| `kctl-cloudflare workers kv` | KV namespaces |
| `kctl-cloudflare workers deploy <script-name> --file <path>` | Deploy worker script |
| `kctl-cloudflare workers delete <script-name> [--force]` | Delete worker script |
| `kctl-cloudflare workers env <script-name>` | List worker environment variables |
| `kctl-cloudflare workers set-env <script-name> --key <k> --value <v>` | Set worker environment variable |
| `kctl-cloudflare workers tail <script-name>` | Tail worker logs |
| `kctl-cloudflare workers subdomain` | Get workers subdomain |
| `kctl-cloudflare workers set-subdomain --name <subdomain>` | Set workers subdomain |

### R2 Storage

| Command | Description |
|---------|-------------|
| `kctl-cloudflare r2 list` | R2 buckets |
| `kctl-cloudflare r2 get <name>` | Bucket details |

### Email Routing

| Command | Description |
|---------|-------------|
| `kctl-cloudflare email-routing status [--zone]` | Email routing status |
| `kctl-cloudflare email-routing enable [--zone]` | Enable email routing |
| `kctl-cloudflare email-routing disable [--zone]` | Disable email routing |
| `kctl-cloudflare email-routing rules [--zone]` | List routing rules |
| `kctl-cloudflare email-routing create-rule --name <n> --match <email> [--action forward] [--destination <email>] [--zone]` | Create routing rule |
| `kctl-cloudflare email-routing delete-rule <rule-id> [--zone]` | Delete routing rule |
| `kctl-cloudflare email-routing catch-all [--zone]` | Get catch-all rule |
| `kctl-cloudflare email-routing set-catch-all [--action forward] [--destination <email>] [--zone]` | Set catch-all rule |
| `kctl-cloudflare email-routing addresses` | List verified destination addresses |

### Page Rules

| Command | Description |
|---------|-------------|
| `kctl-cloudflare page-rules list [--zone]` | List page rules |
| `kctl-cloudflare page-rules get <rule-id> [--zone]` | Page rule details |
| `kctl-cloudflare page-rules create --target <pattern> --action <id> [--value] [--priority] [--status] [--zone]` | Create page rule |
| `kctl-cloudflare page-rules update <rule-id> [--target] [--action] [--value] [--zone]` | Update page rule |
| `kctl-cloudflare page-rules delete <rule-id> [--zone]` | Delete page rule |

### Redirects (Bulk Redirects)

| Command | Description |
|---------|-------------|
| `kctl-cloudflare redirects lists` | List redirect lists |
| `kctl-cloudflare redirects list-items <list-id>` | List items in redirect list |
| `kctl-cloudflare redirects create-item <list-id> --source <url> --target <url> [--status-code 301]` | Add redirect item |
| `kctl-cloudflare redirects delete-item <list-id> <item-id>` | Delete redirect item |
| `kctl-cloudflare redirects rulesets [--zone]` | List redirect rulesets |

### Access (Zero Trust)

| Command | Description |
|---------|-------------|
| `kctl-cloudflare access apps` | List Access applications |
| `kctl-cloudflare access get-app <app-id>` | Access application details |
| `kctl-cloudflare access policies <app-id>` | List policies for application |
| `kctl-cloudflare access groups` | List Access groups |
| `kctl-cloudflare access create-group --name <n> --include <rules> [--require <rules>]` | Create Access group |
| `kctl-cloudflare access idps` | List identity providers |
| `kctl-cloudflare access service-tokens` | List service tokens |

### Speed

| Command | Description |
|---------|-------------|
| `kctl-cloudflare speed settings [--zone]` | Speed optimization settings |
| `kctl-cloudflare speed minify [--zone] [--html/--no-html] [--css/--no-css] [--js/--no-js]` | Get/set minification |
| `kctl-cloudflare speed polish [--zone] [--mode off/lossless/lossy]` | Get/set image optimization |
| `kctl-cloudflare speed mirage [--zone] [--enable/--disable]` | Get/set Mirage (image lazy-load) |
| `kctl-cloudflare speed rocket-loader [--zone] [--enable/--disable]` | Get/set Rocket Loader |
| `kctl-cloudflare speed early-hints [--zone] [--enable/--disable]` | Get/set Early Hints |
| `kctl-cloudflare speed brotli [--zone] [--enable/--disable]` | Get/set Brotli compression |

### Analytics

| Command | Description |
|---------|-------------|
| `kctl-cloudflare analytics dashboard [--zone] [--since -1440]` | Zone analytics dashboard |
| `kctl-cloudflare analytics dns [--zone] [--since -1440]` | DNS analytics |

### Export

| Command | Description |
|---------|-------------|
| `kctl-cloudflare export all [--zone]` | Full zone export JSON |

### Terraform

| Command | Description |
|---------|-------------|
| `kctl-cloudflare terraform init` | Terraform init |
| `kctl-cloudflare terraform plan` | Terraform plan |
| `kctl-cloudflare terraform apply [--auto-approve]` | Terraform apply |
| `kctl-cloudflare terraform destroy [--auto-approve]` | Terraform destroy |
| `kctl-cloudflare terraform output` | Terraform output |
| `kctl-cloudflare terraform validate` | Terraform validate |

### Health & Config

| Command | Description |
|---------|-------------|
| `kctl-cloudflare health check` | Composite API health |
| `kctl-cloudflare config init` | First-time setup |
| `kctl-cloudflare config show` | Show config (masked) |
| `kctl-cloudflare config test` | Test connection |
| `kctl-cloudflare config use <profile>` | Switch profile |

## Global Options

`--json` `--quiet` `-q` `--profile` `-p` `--api-token` `--account-id` `--version` `-V`

## Terraform Workflow

```bash
kctl-cloudflare terraform plan     # Review changes
kctl-cloudflare terraform apply    # Apply changes
kctl-cloudflare terraform output   # Check state
```

## DNS Management

```bash
kctl-cloudflare records list --zone kodeme.io --type A
kctl-cloudflare records update <id> --content 168.119.233.161 --zone kodeme.io
kctl-cloudflare records bulk-create --file records.json --zone kodeme.io
kctl-cloudflare records import --file zone.bind --zone kodeme.io
```

## SSL/TLS Management

```bash
kctl-cloudflare ssl status --zone kodeme.io
kctl-cloudflare ssl min-tls --version 1.2 --zone kodeme.io
kctl-cloudflare ssl always-https --enable --zone kodeme.io
kctl-cloudflare ssl create-origin-cert --hostname kodeme.io --hostname "*.kodeme.io"
```

## Worker Deployment

```bash
kctl-cloudflare workers deploy my-worker --file worker.js
kctl-cloudflare workers set-env my-worker --key API_KEY --value secret123
kctl-cloudflare workers tail my-worker
```

## Email Routing

```bash
kctl-cloudflare email-routing enable --zone kodeme.io
kctl-cloudflare email-routing create-rule --name "Support" --match support@kodeme.io --action forward --destination admin@kodeme.io
kctl-cloudflare email-routing set-catch-all --action forward --destination admin@kodeme.io
```

## Troubleshooting

- DNS not resolving: `records list --zone` → `dig +short <domain>`
- Tunnel down: `tunnels list` → `docker logs cloudflared`
- SSL issues: `ssl status --zone` → should be "strict" → `ssl min-tls --version 1.2`
- Cache stale: `cache purge-all --zone`
- Email routing: `email-routing status` → `email-routing rules`
- Access issues: `access apps` → `access policies <app-id>`
