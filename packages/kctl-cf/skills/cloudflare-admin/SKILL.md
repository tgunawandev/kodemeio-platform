---
name: cloudflare-admin
description: >
  Cloudflare infrastructure administration via kctl-cf CLI. MUST use for ANY DNS, tunnel, WAF, cache, SSL/TLS, Workers, R2, or Cloudflare operation. Triggers on: "kctl-cf", "cloudflare", "DNS record", "tunnel", "WAF rule", "page rule", "R2 bucket", "worker", "SSL certificate", "cache purge", "email routing", "kodeme.io DNS", or ANY Cloudflare resource management.
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
- **CLI**: `kctl-cf` (Python, installed via `uv tool install ./cli`)
- **IaC**: Terraform in kodemeio-infra/kodemeio-cloudflare/
- **Config**: `~/.config/kodemeio/config.yaml` → `profiles.<profile>.cloudflare`

## Commands

### Zones

| Command | Description |
|---------|-------------|
| `kctl-cf zones list` | All DNS zones |
| `kctl-cf zones get <zone>` | Zone details |

### DNS Records

| Command | Description |
|---------|-------------|
| `kctl-cf records list [--zone] [--type]` | DNS records |
| `kctl-cf records update <record-id> [--type] [--name] [--content] [--ttl] [--proxied/--no-proxied] [--zone]` | Update DNS record |
| `kctl-cf records bulk-create --file <json-file> [--zone]` | Bulk create records from JSON |
| `kctl-cf records import --file <bind-file> [--zone]` | Import BIND zone file |

### Tunnels

| Command | Description |
|---------|-------------|
| `kctl-cf tunnels list` | Cloudflare Tunnels |
| `kctl-cf tunnels get <name>` | Tunnel details |

### WAF

| Command | Description |
|---------|-------------|
| `kctl-cf waf list [--zone]` | WAF firewall rules |
| `kctl-cf waf ip-rules [--zone]` | IP access rules |
| `kctl-cf waf rate-limits [--zone]` | Rate limiting rules |

### Cache

| Command | Description |
|---------|-------------|
| `kctl-cf cache status [--zone]` | Cache settings |
| `kctl-cf cache purge-all [--zone] [--yes]` | Purge all cache |
| `kctl-cf cache purge <urls...> [--zone]` | Purge specific URLs |

### SSL/TLS

| Command | Description |
|---------|-------------|
| `kctl-cf ssl status [--zone]` | SSL/TLS mode |
| `kctl-cf ssl certificates [--zone]` | Certificate packs |
| `kctl-cf ssl origin-certs` | List origin certificates |
| `kctl-cf ssl create-origin-cert --hostname <h> [--hostname ...] [--validity 5475] [--type origin-rsa]` | Create origin certificate |
| `kctl-cf ssl delete-origin-cert <cert-id> [--force]` | Delete origin certificate |
| `kctl-cf ssl min-tls [--version 1.0/1.1/1.2/1.3] [--zone]` | Get/set minimum TLS version |
| `kctl-cf ssl always-https [--enable/--disable] [--zone]` | Get/set Always Use HTTPS |

### Workers

| Command | Description |
|---------|-------------|
| `kctl-cf workers list` | Worker scripts |
| `kctl-cf workers routes [--zone]` | Worker routes |
| `kctl-cf workers kv` | KV namespaces |
| `kctl-cf workers deploy <script-name> --file <path>` | Deploy worker script |
| `kctl-cf workers delete <script-name> [--force]` | Delete worker script |
| `kctl-cf workers env <script-name>` | List worker environment variables |
| `kctl-cf workers set-env <script-name> --key <k> --value <v>` | Set worker environment variable |
| `kctl-cf workers tail <script-name>` | Tail worker logs |
| `kctl-cf workers subdomain` | Get workers subdomain |
| `kctl-cf workers set-subdomain --name <subdomain>` | Set workers subdomain |

### R2 Storage

| Command | Description |
|---------|-------------|
| `kctl-cf r2 list` | R2 buckets |
| `kctl-cf r2 get <name>` | Bucket details |

### Email Routing

| Command | Description |
|---------|-------------|
| `kctl-cf email-routing status [--zone]` | Email routing status |
| `kctl-cf email-routing enable [--zone]` | Enable email routing |
| `kctl-cf email-routing disable [--zone]` | Disable email routing |
| `kctl-cf email-routing rules [--zone]` | List routing rules |
| `kctl-cf email-routing create-rule --name <n> --match <email> [--action forward] [--destination <email>] [--zone]` | Create routing rule |
| `kctl-cf email-routing delete-rule <rule-id> [--zone]` | Delete routing rule |
| `kctl-cf email-routing catch-all [--zone]` | Get catch-all rule |
| `kctl-cf email-routing set-catch-all [--action forward] [--destination <email>] [--zone]` | Set catch-all rule |
| `kctl-cf email-routing addresses` | List verified destination addresses |

### Page Rules

| Command | Description |
|---------|-------------|
| `kctl-cf page-rules list [--zone]` | List page rules |
| `kctl-cf page-rules get <rule-id> [--zone]` | Page rule details |
| `kctl-cf page-rules create --target <pattern> --action <id> [--value] [--priority] [--status] [--zone]` | Create page rule |
| `kctl-cf page-rules update <rule-id> [--target] [--action] [--value] [--zone]` | Update page rule |
| `kctl-cf page-rules delete <rule-id> [--zone]` | Delete page rule |

### Redirects (Bulk Redirects)

| Command | Description |
|---------|-------------|
| `kctl-cf redirects lists` | List redirect lists |
| `kctl-cf redirects list-items <list-id>` | List items in redirect list |
| `kctl-cf redirects create-item <list-id> --source <url> --target <url> [--status-code 301]` | Add redirect item |
| `kctl-cf redirects delete-item <list-id> <item-id>` | Delete redirect item |
| `kctl-cf redirects rulesets [--zone]` | List redirect rulesets |

### Access (Zero Trust)

| Command | Description |
|---------|-------------|
| `kctl-cf access apps` | List Access applications |
| `kctl-cf access get-app <app-id>` | Access application details |
| `kctl-cf access policies <app-id>` | List policies for application |
| `kctl-cf access groups` | List Access groups |
| `kctl-cf access create-group --name <n> --include <rules> [--require <rules>]` | Create Access group |
| `kctl-cf access idps` | List identity providers |
| `kctl-cf access service-tokens` | List service tokens |

### Speed

| Command | Description |
|---------|-------------|
| `kctl-cf speed settings [--zone]` | Speed optimization settings |
| `kctl-cf speed minify [--zone] [--html/--no-html] [--css/--no-css] [--js/--no-js]` | Get/set minification |
| `kctl-cf speed polish [--zone] [--mode off/lossless/lossy]` | Get/set image optimization |
| `kctl-cf speed mirage [--zone] [--enable/--disable]` | Get/set Mirage (image lazy-load) |
| `kctl-cf speed rocket-loader [--zone] [--enable/--disable]` | Get/set Rocket Loader |
| `kctl-cf speed early-hints [--zone] [--enable/--disable]` | Get/set Early Hints |
| `kctl-cf speed brotli [--zone] [--enable/--disable]` | Get/set Brotli compression |

### Analytics

| Command | Description |
|---------|-------------|
| `kctl-cf analytics dashboard [--zone] [--since -1440]` | Zone analytics dashboard |
| `kctl-cf analytics dns [--zone] [--since -1440]` | DNS analytics |

### Export

| Command | Description |
|---------|-------------|
| `kctl-cf export all [--zone]` | Full zone export JSON |

### Terraform

| Command | Description |
|---------|-------------|
| `kctl-cf terraform init` | Terraform init |
| `kctl-cf terraform plan` | Terraform plan |
| `kctl-cf terraform apply [--auto-approve]` | Terraform apply |
| `kctl-cf terraform destroy [--auto-approve]` | Terraform destroy |
| `kctl-cf terraform output` | Terraform output |
| `kctl-cf terraform validate` | Terraform validate |

### Health & Config

| Command | Description |
|---------|-------------|
| `kctl-cf health check` | Composite API health |
| `kctl-cf config init` | First-time setup |
| `kctl-cf config show` | Show config (masked) |
| `kctl-cf config test` | Test connection |
| `kctl-cf config use <profile>` | Switch profile |

## Global Options

`--json` `--quiet` `-q` `--profile` `-p` `--api-token` `--account-id` `--version` `-V`

## Terraform Workflow

```bash
kctl-cf terraform plan     # Review changes
kctl-cf terraform apply    # Apply changes
kctl-cf terraform output   # Check state
```

## DNS Management

```bash
kctl-cf records list --zone kodeme.io --type A
kctl-cf records update <id> --content 168.119.233.161 --zone kodeme.io
kctl-cf records bulk-create --file records.json --zone kodeme.io
kctl-cf records import --file zone.bind --zone kodeme.io
```

## SSL/TLS Management

```bash
kctl-cf ssl status --zone kodeme.io
kctl-cf ssl min-tls --version 1.2 --zone kodeme.io
kctl-cf ssl always-https --enable --zone kodeme.io
kctl-cf ssl create-origin-cert --hostname kodeme.io --hostname "*.kodeme.io"
```

## Worker Deployment

```bash
kctl-cf workers deploy my-worker --file worker.js
kctl-cf workers set-env my-worker --key API_KEY --value secret123
kctl-cf workers tail my-worker
```

## Email Routing

```bash
kctl-cf email-routing enable --zone kodeme.io
kctl-cf email-routing create-rule --name "Support" --match support@kodeme.io --action forward --destination admin@kodeme.io
kctl-cf email-routing set-catch-all --action forward --destination admin@kodeme.io
```

## Troubleshooting

- DNS not resolving: `records list --zone` → `dig +short <domain>`
- Tunnel down: `tunnels list` → `docker logs cloudflared`
- SSL issues: `ssl status --zone` → should be "strict" → `ssl min-tls --version 1.2`
- Cache stale: `cache purge-all --zone`
- Email routing: `email-routing status` → `email-routing rules`
- Access issues: `access apps` → `access policies <app-id>`
