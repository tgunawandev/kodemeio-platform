# kctl-cf

Command reference for `kctl-cf` (38 groups, ~188 commands).

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

### `kctl-cf access`

Manage Cloudflare Zero Trust Access.

| Command | Description |
|---------|-------------|
| `access apps` | List Access applications. |
| `access create-app <name> <domain> [--app_type] [--session_duration]` | Create an Access application. |
| `access create-group <name> [--include] [--require]` | Create an Access group. |
| `access create-policy <app_id> <name> [--decision] [--include]` | Create a policy for an Access application. |
| `access create-service-token <name> [--duration]` | Create an Access service token. |
| `access delete-app <app_id> [--force]` | Delete an Access application. |
| `access delete-group <group_id> [--force]` | Delete an Access group. |
| `access delete-policy <app_id> <policy_id> [--force]` | Delete a policy for an Access application. |
| `access delete-service-token <token_id> [--force]` | Delete an Access service token. |
| `access get-app <app_id>` | Get details for an Access application. |
| `access groups` | List Access groups. |
| `access idps` | List Access identity providers. |
| `access policies <app_id>` | List policies for an Access application. |
| `access rotate-service-token <token_id>` | Rotate an Access service token (generates new secret). |
| `access service-tokens` | List Access service tokens. |
| `access update-app <app_id> [--name] [--domain] [--session_duration]` | Update an Access application (merges with existing settings). |
| `access update-policy <app_id> <policy_id> [--name] [--decision]` | Update a policy for an Access application (merges with existing). |

### `kctl-cf analytics`

Zone analytics and traffic reports.

| Command | Description |
|---------|-------------|
| `analytics dashboard [--zone] [--since]` | Show zone analytics dashboard (requests, bandwidth, threats, etc.). |
| `analytics dns [--zone] [--since]` | Show DNS analytics report. |

### `kctl-cf argo`

Manage Argo Smart Routing and Tiered Caching.

| Command | Description |
|---------|-------------|
| `argo smart-routing [--enable] [--zone]` | Get or set Argo Smart Routing. |
| `argo status [--zone]` | Show Argo Smart Routing and Tiered Caching status. |
| `argo tiered-caching [--enable] [--zone]` | Get or set Argo Tiered Caching. |

### `kctl-cf bk`

Alias: export backup

### `kctl-cf cache`

Manage cache settings and purge.

| Command | Description |
|---------|-------------|
| `cache purge <urls> [--zone]` | Purge specific URLs from the cache. |
| `cache purge-all [--zone] [--confirm]` | Purge all cached content for a zone. |
| `cache status [--zone]` | Show cache settings for a zone. |

### `kctl-cf config`

Manage CLI configuration and profiles.

| Command | Description |
|---------|-------------|
| `config init [--api_token] [--account_id] [--name]` | Initialize CLI configuration. |
| `config show` | Show configuration. |
| `config test` | Test API connection. |
| `config use <name>` | Switch default profile. |

### `kctl-cf cp`

Alias: cache purge-all

### `kctl-cf cs`

Alias: cache status

### `kctl-cf custom-hostnames`

Manage Custom Hostnames (Cloudflare for SaaS).

| Command | Description |
|---------|-------------|
| `custom-hostnames create <hostname> [--ssl_method] [--ssl_type] [--zone]` | Create a custom hostname. |
| `custom-hostnames delete <hostname_id> [--force] [--zone]` | Delete a custom hostname. |
| `custom-hostnames get <hostname_id> [--zone]` | Get details for a custom hostname. |
| `custom-hostnames list [--zone] [--hostname]` | List custom hostnames. |
| `custom-hostnames update <hostname_id> [--ssl_method] [--zone]` | Update a custom hostname. |

### `kctl-cf ea`

Alias: export all

### `kctl-cf email-routing`

Manage Cloudflare Email Routing.

| Command | Description |
|---------|-------------|
| `email-routing addresses` | List verified destination email addresses. |
| `email-routing catch-all [--zone]` | Show catch-all rule for email routing. |
| `email-routing create-rule <name> <match> [--action] [--destination] [--zone]` | Create an email routing rule. |
| `email-routing delete-rule <rule_id> [--force] [--zone]` | Delete an email routing rule. |
| `email-routing disable [--zone]` | Disable email routing for a zone. |
| `email-routing enable [--zone]` | Enable email routing for a zone. |
| `email-routing rules [--zone]` | List email routing rules. |
| `email-routing set-catch-all [--action] [--destination] [--zone]` | Set catch-all rule for email routing. |
| `email-routing status [--zone]` | Show email routing status for a zone. |

### `kctl-cf export`

Export and backup Cloudflare configuration.

| Command | Description |
|---------|-------------|
| `export all [--zone]` | Export all Cloudflare configuration as JSON. |
| `export backup [--zone] [--output_dir] [--upload] [--s3_remote]` | Save Cloudflare export to timestamped JSON files on disk. |

### `kctl-cf hc`

Alias: health check

### `kctl-cf health`

Health checks.

| Command | Description |
|---------|-------------|
| `health check [--watch] [--interval] [--notify]` | Run comprehensive Cloudflare health checks (6 checks, scored). |

### `kctl-cf load-balancers`

Manage Load Balancers, pools, and monitors.

| Command | Description |
|---------|-------------|
| `load-balancers create <name> <default_pools> [--fallback_pool] [--proxied] [--zone]` | Create a load balancer. |
| `load-balancers create-monitor <monitor_type> [--description] [--expected_codes]` | Create a load balancer monitor. |
| `load-balancers create-pool <name> <origins>` | Create a load balancer pool from a JSON origins file. |
| `load-balancers delete <lb_id> [--force] [--zone]` | Delete a load balancer. |
| `load-balancers delete-monitor <monitor_id> [--force]` | Delete a load balancer monitor. |
| `load-balancers delete-pool <pool_id> [--force]` | Delete a load balancer pool. |
| `load-balancers get <lb_id> [--zone]` | Get load balancer details. |
| `load-balancers list [--zone]` | List load balancers. |
| `load-balancers monitors` | List load balancer monitors. |
| `load-balancers pools` | List load balancer pools. |
| `load-balancers update <lb_id> [--name] [--enabled] [--zone]` | Update a load balancer. |

### `kctl-cf page-rules`

Manage Cloudflare Page Rules.

| Command | Description |
|---------|-------------|
| `page-rules create <target> <action> [--value] [--priority] [--status_flag] [--zone]` | Create a page rule. |
| `page-rules delete <rule_id> [--force] [--zone]` | Delete a page rule. |
| `page-rules get <rule_id> [--zone]` | Get details for a specific page rule. |
| `page-rules list [--zone]` | List page rules for a zone. |
| `page-rules update <rule_id> [--target] [--action] [--value] [--zone]` | Update a page rule. |

### `kctl-cf pages`

Manage Cloudflare Pages projects and deployments.

| Command | Description |
|---------|-------------|
| `pages add-domain <project_name> <name>` | Add a custom domain to a Pages project. |
| `pages create-deployment <project_name> [--branch]` | Create a new deployment for a Pages project. |
| `pages create-project <name> <production_branch>` | Create a new Pages project. |
| `pages delete-deployment <project_name> <deployment_id> [--force]` | Delete a deployment. |
| `pages delete-project <name> [--force]` | Delete a Pages project. |
| `pages deployments <project_name>` | List deployments for a Pages project. |
| `pages domains <project_name>` | List custom domains for a Pages project. |
| `pages get-deployment <project_name> <deployment_id>` | Get deployment details. |
| `pages get-project <name>` | Get Pages project details. |
| `pages projects` | List all Pages projects. |
| `pages remove-domain <project_name> <domain_name> [--force]` | Remove a custom domain from a Pages project. |
| `pages retry-deployment <project_name> <deployment_id>` | Retry a failed deployment. |
| `pages rollback-deployment <project_name> <deployment_id>` | Rollback to a specific deployment. |

### `kctl-cf r2`

Manage R2 object storage buckets.

| Command | Description |
|---------|-------------|
| `r2 create <name> [--location]` | Create an R2 bucket. |
| `r2 delete <name> [--force]` | Delete an R2 bucket. |
| `r2 delete-object <bucket_name> <key> [--force]` | Delete an object from an R2 bucket. |
| `r2 get <name>` | Get R2 bucket details. |
| `r2 list` | List all R2 buckets. |
| `r2 list-objects <bucket_name> [--prefix] [--limit]` | List objects in an R2 bucket. |
| `r2 usage <name>` | Show R2 bucket usage statistics. |

### `kctl-cf records`

Manage DNS records.

| Command | Description |
|---------|-------------|
| `records bulk-create <file> [--zone]` | Bulk create DNS records from a JSON file. |
| `records create <record_type> <name> <content> [--ttl] [--proxied] [--zone]` | Create a DNS record. |
| `records delete <record_id> [--force] [--zone]` | Delete a DNS record. |
| `records export [--zone] [--file]` | Export DNS records in BIND format. |
| `records get <record_id> [--zone]` | Get a single DNS record by ID. |
| `records import <file> [--zone]` | Import DNS records from a BIND zone file. |
| `records list [--zone] [--record_type]` | List DNS records. |
| `records scan [--zone]` | Scan for DNS records in a zone. |
| `records update <record_id> [--record_type] [--name] [--content] [--ttl] [--proxied] [--zone]` | Update an existing DNS record. |

### `kctl-cf redirects`

Manage Cloudflare Redirect and Bulk Redirect rules.

| Command | Description |
|---------|-------------|
| `redirects create-item <list_id> <source> <target> [--status_code]` | Add a redirect item to a bulk redirect list. |
| `redirects create-list <name> [--description]` | Create a bulk redirect list. |
| `redirects delete-item <list_id> <item_id> [--force]` | Delete a redirect item from a bulk redirect list. |
| `redirects delete-list <list_id> [--force]` | Delete a bulk redirect list. |
| `redirects list-items <list_id>` | List items in a bulk redirect list. |
| `redirects lists` | List bulk redirect lists. |
| `redirects rulesets [--zone]` | List rulesets for a zone (filtered to redirect phase). |

### `kctl-cf rl`

Alias: records list

### `kctl-cf selftest`

Run built-in test suite.

| Command | Description |
|---------|-------------|
| `selftest run [--verbose] [--smoke] [--coverage]` | Run the kctl-cf test suite. |

### `kctl-cf spectrum`

Manage Spectrum applications.

| Command | Description |
|---------|-------------|
| `spectrum create <protocol> <dns_name> <origin_direct> [--dns_type] [--proxy_protocol] [--zone]` | Create a Spectrum application. |
| `spectrum delete <app_id> [--force] [--zone]` | Delete a Spectrum application. |
| `spectrum get <app_id> [--zone]` | Get Spectrum application details. |
| `spectrum list [--zone]` | List Spectrum applications. |
| `spectrum update <app_id> [--protocol] [--origin_direct] [--zone]` | Update a Spectrum application (merges with existing settings). |

### `kctl-cf speed`

Manage speed optimization settings (minify, polish, mirage, etc.).

| Command | Description |
|---------|-------------|
| `speed brotli [--zone] [--enable]` | Show or toggle Brotli compression. |
| `speed early-hints [--zone] [--enable]` | Show or toggle Early Hints (103 responses). |
| `speed minify [--zone] [--html] [--css] [--js]` | Show or set auto-minification settings. |
| `speed mirage [--zone] [--enable]` | Show or toggle Mirage (image lazy loading for mobile). |
| `speed polish [--zone] [--mode]` | Show or set Polish (image optimization) mode. |
| `speed rocket-loader [--zone] [--enable]` | Show or toggle Rocket Loader (async JS loading). |
| `speed settings [--zone]` | Show speed-related settings for a zone. |

### `kctl-cf ss`

Alias: ssl status

### `kctl-cf ssl`

Manage SSL/TLS settings and certificates.

| Command | Description |
|---------|-------------|
| `ssl always-https [--enable] [--zone]` | Show or toggle Always Use HTTPS for a zone. |
| `ssl certificates [--zone]` | List SSL certificate packs for a zone. |
| `ssl create-origin-cert <hostnames> [--validity] [--request_type]` | Create an Origin CA certificate. |
| `ssl delete-origin-cert <cert_id> [--force]` | Delete an Origin CA certificate. |
| `ssl min-tls [--version] [--zone]` | Show or set minimum TLS version for a zone. |
| `ssl origin-certs` | List Origin CA certificates. |
| `ssl status [--zone]` | Show SSL/TLS mode for a zone. |

### `kctl-cf st`

Alias: status overview

### `kctl-cf status`

Account status dashboard.

| Command | Description |
|---------|-------------|
| `status overview` | Show a comprehensive account-level dashboard. |

### `kctl-cf terraform`

Run Terraform commands for Cloudflare infrastructure.

| Command | Description |
|---------|-------------|
| `terraform apply [--auto_approve] [--notify]` | Apply Terraform changes. |
| `terraform destroy [--auto_approve] [--notify]` | Destroy Terraform-managed infrastructure. |
| `terraform init` | Initialize Terraform working directory. |
| `terraform output` | Show Terraform outputs. |
| `terraform plan` | Show Terraform execution plan. |
| `terraform validate` | Validate Terraform configuration. |

### `kctl-cf tl`

Alias: tunnels list

### `kctl-cf tunnels`

Manage Cloudflare Tunnels.

| Command | Description |
|---------|-------------|
| `tunnels clean-connections <tunnel_id> [--force]` | Remove inactive tunnel connections. |
| `tunnels connections <tunnel_id>` | List active tunnel connections. |
| `tunnels create <name> [--secret]` | Create a Cloudflare Tunnel. |
| `tunnels delete <tunnel_id> [--force]` | Delete a Cloudflare Tunnel. |
| `tunnels get <name>` | Get tunnel details. |
| `tunnels get-config <tunnel_id>` | Get tunnel configuration (ingress rules). |
| `tunnels list` | List all tunnels. |
| `tunnels update-config <tunnel_id> <file>` | Update tunnel configuration from a JSON file. |

### `kctl-cf waf`

Manage WAF and firewall rules.

| Command | Description |
|---------|-------------|
| `waf create <expression> [--action] [--description] [--zone]` | Create a firewall rule. |
| `waf create-ip-rule <mode> <value> [--target] [--notes] [--zone]` | Create an IP access rule. |
| `waf create-rate-limit [--url] [--threshold] [--period] [--action_mode] [--timeout] [--zone]` | Create a rate limiting rule. |
| `waf delete <rule_id> [--force] [--zone]` | Delete a firewall rule. |
| `waf delete-ip-rule <rule_id> [--force] [--zone]` | Delete an IP access rule. |
| `waf delete-rate-limit <rule_id> [--force] [--zone]` | Delete a rate limiting rule. |
| `waf ip-rules [--zone]` | List IP access rules. |
| `waf list [--zone]` | List firewall rules. |
| `waf rate-limits [--zone]` | List rate limiting rules. |
| `waf update <rule_id> [--expression] [--action] [--zone]` | Update a firewall rule. |
| `waf update-ip-rule <rule_id> [--mode] [--notes] [--zone]` | Update an IP access rule. |
| `waf update-rate-limit <rule_id> [--threshold] [--period] [--disabled] [--zone]` | Update a rate limiting rule. |

### `kctl-cf waiting-rooms`

Manage Waiting Rooms.

| Command | Description |
|---------|-------------|
| `waiting-rooms create <name> <host> <total_active_users> <new_users_per_minute> [--path] [--session_duration] [--zone]` | Create a waiting room. |
| `waiting-rooms delete <room_id> [--force] [--zone]` | Delete a waiting room. |
| `waiting-rooms get <room_id> [--zone]` | Get waiting room details. |
| `waiting-rooms list [--zone]` | List waiting rooms. |
| `waiting-rooms update <room_id> [--name] [--total_active_users] [--new_users_per_minute] [--zone]` | Update a waiting room (merges with existing settings). |

### `kctl-cf wl`

Alias: workers list

### `kctl-cf workers`

Manage Cloudflare Workers, routes, and KV.

| Command | Description |
|---------|-------------|
| `workers create-kv <title>` | Create a Workers KV namespace. |
| `workers create-route <pattern> <script> [--zone]` | Create a Workers route for a zone. |
| `workers cron-triggers <script_name>` | List cron triggers for a Worker script. |
| `workers delete <script_name> [--force]` | Delete a Worker script. |
| `workers delete-cron-triggers <script_name> [--force]` | Delete all cron triggers for a Worker script. |
| `workers delete-kv <namespace_id> [--force]` | Delete a Workers KV namespace. |
| `workers delete-route <route_id> [--force] [--zone]` | Delete a Workers route. |
| `workers deploy <script_name> <file>` | Deploy a Worker script. |
| `workers env <script_name>` | Show environment bindings for a Worker script. |
| `workers kv` | List Workers KV namespaces. |
| `workers list` | List all Workers scripts. |
| `workers routes [--zone]` | List Workers routes for a zone. |
| `workers set-cron-triggers <script_name> <crons>` | Set cron triggers for a Worker script (replaces all existing). |
| `workers set-env <script_name> <key> <value>` | Set an environment variable (plain text binding) for a Worker. |
| `workers set-subdomain <name>` | Set Workers subdomain for the account. |
| `workers subdomain` | Show Workers subdomain for the account. |
| `workers tail <script_name>` | Start a tail session for a Worker (shows recent events). |

### `kctl-cf zg`

Alias: zones get <zone>

### `kctl-cf zl`

Alias: zones list

### `kctl-cf zones`

Manage DNS zones.

| Command | Description |
|---------|-------------|
| `zones activation-check [--zone]` | Trigger an activation check for a zone. |
| `zones create <name> [--jump_start]` | Create a new DNS zone. |
| `zones delete <zone> [--force]` | Delete a DNS zone. |
| `zones edit-setting <setting> <value> [--zone]` | Edit a zone setting. |
| `zones get <zone>` | Get zone details. |
| `zones hold [--zone] [--include_subdomains]` | Place a hold on a zone. |
| `zones list` | List all zones. |
| `zones release-hold [--zone]` | Release a hold on a zone. |
| `zones settings [--zone]` | List all zone settings. |
