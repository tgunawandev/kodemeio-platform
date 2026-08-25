# infra/ — Unified Infrastructure Entry Point

This directory is the **root Terraform configuration** supporting the Kodemeio
Dokploy fleet. It aggregates locally owned Cloudflare and Hetzner modules.

```
infra/                          ← you are here (root module)
├── modules/
│   ├── cloudflare/             ← DNS, TLS, edge, and storage resources
│   └── hetzner/                ← servers, networks, firewalls, and volumes
├── main.tf                     ← wires cloudflare + hetzner modules
├── variables.tf                ← all variables for both modules
├── outputs.tf                  ← key outputs (IPs, zone IDs, network IDs)
├── backend.tf                  ← remote state config (commented out by default)
├── terraform.tfvars.example    ← copy → terraform.tfvars, fill in secrets
├── .gitignore                  ← excludes .terraform/, *.tfstate, *.tfvars
└── README.md                   ← this file

modules/cloudflare/             ← Cloudflare module (local source)
modules/hetzner/                ← Hetzner Cloud module (local source)
```

The root module references these modules with stable local paths. They were
vendored from `kodemeio-cli` commit
`7528f3e7dc8a22a08cbadd36e1d7f0ac0c0cecc1` during the Dokploy repository
consolidation. Infrastructure modules are now owned here; CLI code remains in
`kodemeio-cli`.

---

## Modules

### Cloudflare

Manages all Cloudflare resources across the platform's domains:

| Resource | Description |
|----------|-------------|
| `zones.tf` | DNS zone registration (kodeme.io, terakidz.com, ...) |
| `records.tf` | DNS A/CNAME/MX/TXT records |
| `tunnels.tf` | Cloudflare Tunnel (Argo) for zero-trust ingress |
| `ssl.tf` | Origin CA certificates, authenticated origin pulls |
| `firewall.tf` | WAF rules, IP access rules, rate limits |
| `caching.tf` | Cache rules, page rules |
| `workers.tf` | Worker scripts, routes, KV namespaces |
| `r2.tf` | R2 object storage buckets |
| `email_routing.tf` | Email routing rules and catch-all |
| `redirects.tf` | Bulk redirect lists and ruleset entries |

Provider: `cloudflare/cloudflare ~> 4.0`

### Hetzner Cloud

Manages all Hetzner Cloud compute resources:

| Resource | Description |
|----------|-------------|
| `servers.tf` | CX-series servers (dokploy app server, db server) |
| `networks.tf` | Private networks for inter-server communication |
| `firewalls.tf` | Inbound/outbound firewall rule sets |
| `ssh_keys.tf` | SSH public keys |
| `load_balancers.tf` | Optional load balancers (HA/multi-server) |
| `placement_groups.tf` | Spread placement for physical host diversity |
| `dns.tf` | Hetzner DNS records (optional, separate from Cloudflare) |
| `cloud_init.tf` | Cloud-init templates for server bootstrapping |
| `templates/` | YAML cloud-init templates |

Provider: `hetznercloud/hcloud ~> 1.49`

---

## Quick Start

### 1. Prerequisites

```bash
# Install Terraform (>= 1.5)
brew install terraform        # macOS
# or: https://developer.hashicorp.com/terraform/install

# Verify
terraform version
```

### 2. Configure Variables

```bash
cd infra/
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with real credentials
# (never commit this file — it is in .gitignore)
```

Alternatively, export credentials as environment variables:

```bash
export TF_VAR_cloudflare_api_token="cf-token..."
export TF_VAR_hcloud_token="hcloud-token..."
export TF_VAR_cloudflare_account_name="your-account"
```

### 3. Initialize

```bash
terraform init
```

This downloads the Cloudflare and Hetzner providers. The package module sources are local relative paths — no registry lookup needed for them.

### 4. Plan

Always review the plan before applying:

```bash
terraform plan -var-file="terraform.tfvars" -out=infra.tfplan
```

Review the output carefully. Pay attention to:
- Any `destroy` actions (red `-`)
- Server replacements (implies downtime)
- DNS record changes (may affect live traffic)

### 5. Apply

```bash
terraform apply infra.tfplan
```

After apply, key outputs are printed automatically. To retrieve them later:

```bash
terraform output server_ips
terraform output zone_ids
terraform output -raw tunnels    # sensitive — requires -raw flag
```

---

## State Management

By default Terraform stores state locally in `terraform.tfstate`. This is fine for solo development but unsafe for teams — concurrent applies will corrupt state.

### Remote State (Recommended for Production)

Hetzner Object Storage (S3-compatible) is the recommended backend. See `backend.tf` for the full configuration. Setup steps:

```bash
# 1. Create the state bucket (one-time)
kctl-hz storage bucket create kodemeio-terraform-state

# 2. Generate access credentials
kctl-hz storage keys create --bucket kodemeio-terraform-state

# 3. Export credentials (do not commit these)
export AWS_ACCESS_KEY_ID="<key>"
export AWS_SECRET_ACCESS_KEY="<secret>"

# 4. Uncomment the backend block in backend.tf, then re-initialize
terraform init -reconfigure
```

State locking is not available on Hetzner Object Storage (no DynamoDB equivalent). Coordinate applies manually in teams, or use Terraform Cloud for locking.

### Per-Module State (Advanced)

Each module can be operated independently with its own backend if needed. Use this approach when modules have independent release cadences (e.g., DNS changes should never require a Hetzner plan).

---

## Workflow Conventions

### Before Every Apply

```bash
terraform validate         # syntax check
terraform fmt -check       # formatting check
terraform plan             # review changes
```

### Targeted Operations

When only one module needs updating, use `-target` to limit scope:

```bash
# Only Cloudflare changes
terraform plan -target=module.cloudflare

# Only Hetzner changes
terraform plan -target=module.hetzner

# Single resource
terraform plan -target=module.hetzner.hcloud_server.servers["dokploy"]
```

### Importing Existing Resources

If resources were created outside Terraform, import them before managing:

```bash
terraform import module.hetzner.hcloud_server.servers[\"dokploy\"] <server-id>
terraform import module.cloudflare.cloudflare_zone.zones[\"kodeme.io\"] <zone-id>
```

---

## Secrets Management

Secrets follow the project's 1Password convention:

- All credentials live in 1Password under the `kodemeio-terraform` item
- Never write tokens into CLAUDE.md, README.md, or any committed file
- Use `kctl-op env export kodemeio-terraform` to populate `TF_VAR_*` env vars
- The `terraform.tfvars` file is gitignored — treat it like a `.env` file

---

## Cost Reference (Hetzner, April 2026)

| Server | Type | vCPU | RAM | Disk | Cost/mo |
|--------|------|------|-----|------|---------|
| dokploy | cx42 | 8 | 16 GB | 160 GB | ~€28 |
| db | cx32 | 4 | 8 GB | 80 GB | ~€14 |
| dokploy-data volume | — | — | — | 80 GB | ~€4 |
| pg-data volume | — | — | — | 100 GB | ~€5 |
| pg-backup volume | — | — | — | 50 GB | ~€2.50 |
| **Total** | | | | | **~€53.50/mo** |

Cloudflare free plan: $0/mo for DNS, WAF, CDN (with usage limits).
R2 storage: $0.015/GB-month after 10 GB free tier.
