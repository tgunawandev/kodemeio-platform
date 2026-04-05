# kctl-hz

Kodemeio Hetzner Cloud CLI — manage Hetzner Cloud infrastructure.

## Features

- **139 commands** across 24 groups (servers, volumes, firewalls, networks, load-balancers, IPs, DNS, S3, storage-boxes, and more)
- **Terraform IaC** — production-ready infrastructure definitions with 3 architecture options
- **Multi-API support** — Hetzner Cloud API + DNS API + Robot API + S3
- **Profile-based config** — multiple named profiles with token/credential storage
- **Multiple output formats** — pretty (Rich tables), JSON, CSV, YAML
- **Cost estimation** — monthly cost calculator for running resources
- **10 quick aliases** — `sl`, `sg`, `sc`, `hc`, `ss`, `vl`, `fl`, `nl`, `ce`, `dz`

## Install

```bash
uv tool install kctl-hz
kctl-hz config init
```

## Quick Start

```bash
# List all servers
kctl-hz servers list

# Get server details
kctl-hz servers get my-server

# Create a new server
kctl-hz servers create my-server --type cx22 --image ubuntu-24.04

# Check account health
kctl-hz health check

# Show resource status summary
kctl-hz status show

# Estimate monthly costs
kctl-hz costs estimate
```

## Global Options

All commands support these global options:

| Option | Short | Description |
|--------|-------|-------------|
| `--json` | | Output as JSON |
| `--quiet` | `-q` | Suppress info messages |
| `--format` | `-f` | Output format: `pretty`, `json`, `csv`, `yaml` (default: `pretty`) |
| `--no-header` | | Omit column headers in CSV output |
| `--profile` | `-p` | Config profile name |
| `--token` | | Hetzner Cloud API token override |
| `--dns-token` | | Hetzner DNS API token override |
| `--version` | `-V` | Show version and exit |

## Command Groups

### servers — Cloud server lifecycle management

| Command | Description |
|---------|-------------|
| `list` | List all servers |
| `get` | Get server details |
| `create` | Create a new server |
| `delete` | Delete a server |
| `reboot` | Reboot a server |
| `shutdown` | Gracefully shut down a server |
| `power-off` | Force power off a server |
| `reset` | Hard reset a server |
| `rebuild` | Rebuild a server from an image |
| `resize` | Resize a server to a different type |
| `update` | Update server metadata |
| `enable-rescue` | Enable rescue mode |
| `disable-rescue` | Disable rescue mode |
| `console` | Open server console |
| `metrics` | Show server CPU/network metrics |

### volumes — Block storage management

| Command | Description |
|---------|-------------|
| `list` | List all volumes |
| `get` | Get volume details |
| `create` | Create a new volume |
| `attach` | Attach volume to a server |
| `detach` | Detach volume from a server |
| `delete` | Delete a volume |
| `update` | Update volume metadata |
| `extend` | Extend volume size |
| `protect` | Toggle deletion protection |

### firewalls — Firewall rules management

| Command | Description |
|---------|-------------|
| `list` | List all firewalls |
| `get` | Get firewall details |
| `create` | Create a new firewall |
| `delete` | Delete a firewall |
| `update` | Update firewall metadata |
| `add-rule` | Add an inbound or outbound rule |
| `remove-rule` | Remove a firewall rule |
| `apply` | Apply firewall to a server |
| `remove-from` | Remove firewall from a server |

### networks — Private network management

| Command | Description |
|---------|-------------|
| `list` | List all networks |
| `get` | Get network details |
| `create` | Create a new private network |
| `delete` | Delete a network |
| `update` | Update network metadata |
| `add-subnet` | Add a subnet to the network |
| `remove-subnet` | Remove a subnet |
| `attach-server` | Attach a server to the network |
| `detach-server` | Detach a server from the network |
| `change-ip-range` | Change the network IP range |
| `add-route` | Add a static route |
| `remove-route` | Remove a static route |

### dns — Hetzner DNS zone and record management

| Command | Description |
|---------|-------------|
| `zones` | List all DNS zones |
| `records` | List records in a zone |
| `create-record` | Create a DNS record |
| `update-record` | Update an existing DNS record |
| `delete-record` | Delete a DNS record |

### ips — Floating and primary IP management

| Command | Description |
|---------|-------------|
| `list` | List all IPs |
| `get` | Get floating IP details |
| `create-floating` | Create a floating IP |
| `update-floating` | Update floating IP metadata |
| `delete-floating` | Delete a floating IP |
| `assign` | Assign floating IP to a server |
| `unassign` | Unassign floating IP |
| `get-primary` | Get primary IP details |
| `create-primary` | Create a primary IP |
| `update-primary` | Update primary IP metadata |
| `delete-primary` | Delete a primary IP |

### ssh-keys — SSH key management

| Command | Description |
|---------|-------------|
| `list` | List all SSH keys |
| `create` | Upload a new SSH key |
| `update` | Update SSH key name |
| `delete` | Delete an SSH key |

### snapshots — Server snapshot management

| Command | Description |
|---------|-------------|
| `list` | List all snapshots |
| `get` | Get snapshot details |
| `create` | Create a snapshot from a server |
| `delete` | Delete a snapshot |
| `restore` | Restore a server from a snapshot |
| `update` | Update snapshot metadata |

### load-balancers — Load balancer management

| Command | Description |
|---------|-------------|
| `list` | List all load balancers |
| `get` | Get load balancer details |
| `create` | Create a new load balancer |
| `delete` | Delete a load balancer |
| `update` | Update load balancer metadata |
| `add-target` | Add a server target |
| `remove-target` | Remove a server target |
| `add-service` | Add a service (port mapping) |
| `remove-service` | Remove a service |

### s3 — Hetzner Object Storage (S3-compatible)

| Command | Description |
|---------|-------------|
| `buckets` | List all S3 buckets |
| `ls` | List objects in a bucket |
| `size` | Show total size of a bucket |
| `cp` | Copy objects to/from a bucket |
| `sync` | Sync a local directory to/from a bucket |
| `mb` | Create a new bucket |
| `rb` | Delete a bucket |

### storage-boxes — Hetzner Robot storage box management

| Command | Description |
|---------|-------------|
| `list` | List all storage boxes |
| `get` | Get storage box details |
| `update` | Update storage box metadata |
| `snapshots` | List storage box snapshots |
| `create-snapshot` | Create a storage box snapshot |
| `delete-snapshot` | Delete a storage box snapshot |
| `reset-password` | Reset storage box password |
| `subaccounts` | List storage box subaccounts |

### placement-groups — Placement group management

| Command | Description |
|---------|-------------|
| `list` | List all placement groups |
| `get` | Get placement group details |
| `create` | Create a placement group |
| `delete` | Delete a placement group |
| `update` | Update placement group metadata |

### images — Server image management

| Command | Description |
|---------|-------------|
| `list` | List available images |
| `get` | Get image details |
| `delete` | Delete a custom image |
| `update` | Update image metadata |

### labels — Resource label management

| Command | Description |
|---------|-------------|
| `list` | List labels on a resource |
| `set` | Set a label on a resource |
| `remove` | Remove a label from a resource |

### rdns — Reverse DNS management

| Command | Description |
|---------|-------------|
| `get` | Get reverse DNS entry |
| `set` | Set a reverse DNS entry |
| `delete` | Delete a reverse DNS entry |

### server-types, locations, costs, health, status

| Group | Commands | Description |
|-------|----------|-------------|
| `server-types` | `list`, `get` | List and inspect available server types |
| `locations` | `list`, `get`, `datacenters` | Regions, cities, and datacenter details |
| `costs` | `estimate` | Estimate monthly cost for running resources |
| `health` | `check` | API connectivity and token health check |
| `status` | `show` | Summary of all active resources across the account |

### config — Profile management

| Command | Description |
|---------|-------------|
| `init` | Initialize a new profile interactively |
| `add` | Add a named profile |
| `use` | Switch active profile |
| `show` | Display current profile (secrets masked) |
| `validate` | Validate config file structure |
| `remove` | Remove a profile |
| `set` | Set a config value in the active profile |
| `profiles` | List all profiles |
| `current` | Show active profile name |

## Quick Aliases

| Alias | Expands to |
|-------|-----------|
| `sl` | `servers list` |
| `sg <name>` | `servers get <name>` |
| `sc <name>` | `servers create <name>` |
| `hc` | `health check` |
| `ss` | `status show` |
| `vl` | `volumes list` |
| `fl` | `firewalls list` |
| `nl` | `networks list` |
| `ce` | `costs estimate` |
| `dz` | `dns zones` |

## Shell Completions

```bash
# Zsh
kctl-hz --install-completion zsh

# Bash
kctl-hz --install-completion bash

# Fish
kctl-hz --install-completion fish
```

## Structure

```
kctl-hz/
├── src/kctl_hz/     # Python CLI (139 commands, 24 groups)
├── tests/           # 108+ pytest tests
├── infra/hetzner/   # Terraform IaC (13 .tf files + cloud-init templates)
├── docs/            # Deployment guide, infrastructure reference, API reference
├── skills/          # Claude Code skill definitions
└── .env.example     # Required environment variables
```

## Terraform

Three production architecture options in `infra/hetzner/`:

| Option | Servers | Cost | Use Case |
|--------|---------|------|----------|
| A — Single | 1x cx52 | ~EUR75/mo | Dev/staging |
| B — 2-Server | cx42 + cx32 | ~EUR75/mo | Production <500 users |
| C — 3-Server | cx32 + cx42 + cx42 | ~EUR100/mo | Scale-ready 500+ users |

```bash
cd infra/hetzner
terraform init
terraform plan
terraform apply
```

## Infrastructure Architecture

kctl-hz manages the Kodemeio Hetzner Cloud infrastructure, which follows a multi-server layout:

- **Servers** run Docker Compose services via Dokploy, joined to `dokploy-network` (external bridge)
- **Private networks** (10.0.0.0/8) connect servers within a project for internal DB/Redis traffic
- **Firewalls** restrict inbound to ports 80, 443, and 22 (SSH) only — all other ports are blocked
- **Floating IPs** are used for failover and point to Traefik reverse proxy on the target server
- **S3 / storage-boxes** provide object storage for backups and static assets
- **DNS** (Hetzner DNS API) manages A/AAAA/CNAME records pointing to floating or primary IPs
- All secrets (API tokens, robot credentials, S3 keys) are stored in `~/.config/kodemeio/config.yaml` under the `hz` service key

## Config File

Config is stored at `~/.config/kodemeio/config.yaml` under the `hz` service key:

```yaml
profiles:
  default:
    hz:
      token: hcloud_...
      dns_token: dns_...
      robot_user: u1234
      robot_password: "****"
      s3_endpoint: https://fsn1.your-objectstorage.com
      s3_access_key: "****"
      s3_secret_key: "****"
active_profile: default
```
