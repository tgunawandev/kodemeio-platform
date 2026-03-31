---
name: hetzner-admin
description: >
  Hetzner Cloud infrastructure administration via kctl-hz CLI. MUST use for ANY server, volume, firewall, network, or Hetzner Cloud operation. Triggers on: "kctl-hz", "hetzner", "create server", "firewall rule", "floating IP", "volume", "snapshot", "load balancer", "server cost", "hetzner DNS", or ANY Hetzner Cloud infrastructure task.
version: 2.0.0
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Glob
  - Grep
---

# Hetzner Cloud Administration for Kodemeio

## System Overview

- **Server**: cx42 (8 vCPU, 16 GB RAM) at fsn1
- **IP**: 168.119.233.161 (dokploy.kodeme.io)
- **APIs**: Cloud API v1 + DNS API v1 (separate tokens)
- **CLI**: `kctl-hz` (Python, installed via `uv tool install ./cli`)
- **Config**: `~/.config/kodemeio/config.yaml` → `profiles.<profile>.hetzner`

## Commands

### Status & Health

| Command | Description |
|---------|-------------|
| `kctl-hz status show` | Infrastructure dashboard |
| `kctl-hz health check` | Cloud + DNS API check |

### Servers

| Command | Description |
|---------|-------------|
| `kctl-hz servers list` | All servers |
| `kctl-hz servers get <name>` | Server details |
| `kctl-hz servers create <name> --type --image --location [--ssh-key ...]` | Create server |
| `kctl-hz servers delete <name> [--force]` | Delete server |
| `kctl-hz servers reboot <name>` | Reboot server |
| `kctl-hz servers shutdown <name>` | Graceful shutdown |
| `kctl-hz servers power-off <name>` | Force power off |
| `kctl-hz servers reset <name> [--force]` | Hard reset server |
| `kctl-hz servers rebuild <name> --image [--force]` | Reinstall OS |
| `kctl-hz servers resize <name> --type <new-type> [--upgrade-disk] [--force]` | Resize server |
| `kctl-hz servers rename <name> --name <new-name>` | Rename server |
| `kctl-hz servers enable-rescue <name> [--ssh-key ...] [--force]` | Enable rescue mode |
| `kctl-hz servers disable-rescue <name>` | Disable rescue mode |
| `kctl-hz servers console <name>` | Get VNC console URL |
| `kctl-hz servers metrics <name> [--type cpu/disk/network] [--start] [--end]` | Server metrics |

### Volumes

| Command | Description |
|---------|-------------|
| `kctl-hz volumes list` | All volumes |
| `kctl-hz volumes get <id>` | Volume details |
| `kctl-hz volumes create <name> [--size N] [--server] [--location]` | Create volume |
| `kctl-hz volumes attach <id> --server <server-id>` | Attach to server |
| `kctl-hz volumes detach <id>` | Detach from server |
| `kctl-hz volumes delete <id> [--force]` | Delete volume |
| `kctl-hz volumes extend <id> --size <new-size>` | Extend volume size |
| `kctl-hz volumes protect <id> [--enable/--disable]` | Toggle delete protection |

### Firewalls

| Command | Description |
|---------|-------------|
| `kctl-hz firewalls list` | All firewalls |
| `kctl-hz firewalls get <name>` | Firewall details + rules |
| `kctl-hz firewalls create <name>` | Create firewall |
| `kctl-hz firewalls delete <id> [--force]` | Delete firewall |
| `kctl-hz firewalls add-rule <id> --direction <in/out> --protocol <tcp/udp/icmp> [--port] [--source-ips] [--destination-ips] [--description]` | Add firewall rule |
| `kctl-hz firewalls remove-rule <id> --direction --protocol [--port]` | Remove firewall rule |
| `kctl-hz firewalls apply <id> --server <server-id>` | Apply firewall to server |
| `kctl-hz firewalls remove-from <id> --server <server-id>` | Remove firewall from server |

### Networks

| Command | Description |
|---------|-------------|
| `kctl-hz networks list` | All networks |
| `kctl-hz networks get <id>` | Network details |
| `kctl-hz networks create <name> --ip-range <cidr>` | Create network |
| `kctl-hz networks delete <id> [--force]` | Delete network |
| `kctl-hz networks add-subnet <id> --type <cloud/vswitch/server> --ip-range <cidr> --network-zone <zone>` | Add subnet |
| `kctl-hz networks remove-subnet <id> --ip-range <cidr> [--force]` | Remove subnet |
| `kctl-hz networks attach-server <id> --server <server-id> [--ip]` | Attach server to network |
| `kctl-hz networks detach-server <id> --server <server-id>` | Detach server from network |
| `kctl-hz networks change-ip-range <id> --ip-range <cidr>` | Change network IP range |
| `kctl-hz networks add-route <id> --destination <cidr> --gateway <ip>` | Add static route |
| `kctl-hz networks remove-route <id> --destination <cidr> --gateway <ip> [--force]` | Remove static route |

### SSH Keys

| Command | Description |
|---------|-------------|
| `kctl-hz ssh-keys list` | SSH keys |
| `kctl-hz ssh-keys create <name> --public-key <key>` | Add key |
| `kctl-hz ssh-keys delete <id> [--force]` | Remove key |

### IPs (Floating & Primary)

| Command | Description |
|---------|-------------|
| `kctl-hz ips list` | All floating + primary IPs |
| `kctl-hz ips get <id>` | Floating IP details |
| `kctl-hz ips create-floating --type <ipv4/ipv6> --location <loc> [--server] [--description] [--name]` | Create floating IP |
| `kctl-hz ips delete-floating <id> [--force]` | Delete floating IP |
| `kctl-hz ips assign <id> --server <server-id>` | Assign floating IP to server |
| `kctl-hz ips unassign <id>` | Unassign floating IP |
| `kctl-hz ips get-primary <id>` | Primary IP details |
| `kctl-hz ips create-primary --type <ipv4/ipv6> [--assignee-type] [--assignee-id] [--datacenter] [--name] [--auto-delete/--no-auto-delete]` | Create primary IP |
| `kctl-hz ips update-primary <id> [--name] [--auto-delete/--no-auto-delete]` | Update primary IP |
| `kctl-hz ips delete-primary <id> [--force]` | Delete primary IP |

### Snapshots

| Command | Description |
|---------|-------------|
| `kctl-hz snapshots list` | Server snapshots |
| `kctl-hz snapshots get <id>` | Snapshot details |
| `kctl-hz snapshots create <server-id> [--description]` | Create snapshot |
| `kctl-hz snapshots delete <id> [--force]` | Delete snapshot |
| `kctl-hz snapshots restore <server-id> --image <snapshot-id> [--force]` | Restore snapshot to server |
| `kctl-hz snapshots update <id> [--description]` | Update snapshot metadata |

### Load Balancers

| Command | Description |
|---------|-------------|
| `kctl-hz load-balancers list` | All load balancers |
| `kctl-hz load-balancers get <name>` | Load balancer details |
| `kctl-hz load-balancers create <name> [--type lb11] [--location] [--algorithm] [--network]` | Create load balancer |
| `kctl-hz load-balancers delete <name> [--force]` | Delete load balancer |
| `kctl-hz load-balancers update <name> --name <new-name>` | Rename load balancer |
| `kctl-hz load-balancers add-target <name> --server <id> [--use-private-ip]` | Add server target |
| `kctl-hz load-balancers remove-target <name> --server <id>` | Remove server target |
| `kctl-hz load-balancers add-service <name> --protocol --listen-port --dest-port [--health-check-path]` | Add service/listener |
| `kctl-hz load-balancers remove-service <name> --listen-port <port>` | Remove service/listener |

### Placement Groups

| Command | Description |
|---------|-------------|
| `kctl-hz placement-groups list` | All placement groups |
| `kctl-hz placement-groups get <name>` | Placement group details |
| `kctl-hz placement-groups create <name> [--type spread]` | Create placement group |
| `kctl-hz placement-groups delete <name> [--force]` | Delete placement group |

### S3 (Hetzner Object Storage)

| Command | Description |
|---------|-------------|
| `kctl-hz s3 buckets` | List S3 buckets |
| `kctl-hz s3 ls <bucket> [--prefix]` | List objects in bucket |
| `kctl-hz s3 size <bucket>` | Bucket size summary |
| `kctl-hz s3 cp <src> <dst> [--recursive]` | Copy files (local/S3) |
| `kctl-hz s3 sync <src> <dst> [--delete]` | Sync files (local/S3) |
| `kctl-hz s3 mb <name>` | Create bucket |
| `kctl-hz s3 rb <name> [--force]` | Remove bucket |

### Server Types

| Command | Description |
|---------|-------------|
| `kctl-hz server-types list` | Available server types |
| `kctl-hz server-types get <id>` | Server type details |

### Locations

| Command | Description |
|---------|-------------|
| `kctl-hz locations list` | Available locations |
| `kctl-hz locations get <id>` | Location details |
| `kctl-hz locations datacenters` | Available datacenters |

### Images

| Command | Description |
|---------|-------------|
| `kctl-hz images list [--type system/snapshot/backup/app] [--architecture x86/arm]` | List images |
| `kctl-hz images get <id>` | Image details |
| `kctl-hz images delete <id> [--force]` | Delete image (snapshots only) |
| `kctl-hz images update <id> [--description] [--type]` | Update image metadata |

### Labels

| Command | Description |
|---------|-------------|
| `kctl-hz labels list <resource-type> <resource-id>` | List labels on resource |
| `kctl-hz labels set <resource-type> <resource-id> --labels <key=val,...>` | Set labels on resource |
| `kctl-hz labels remove <resource-type> <resource-id> --key <key>` | Remove label from resource |

### Reverse DNS

| Command | Description |
|---------|-------------|
| `kctl-hz rdns get <resource-type> <resource-id>` | Get rDNS entries |
| `kctl-hz rdns set <resource-type> <resource-id> --ip <ip> --dns-ptr <hostname>` | Set rDNS pointer |
| `kctl-hz rdns delete <resource-type> <resource-id> --ip <ip> [--force]` | Delete rDNS pointer |

### DNS (separate API, separate token)

| Command | Description |
|---------|-------------|
| `kctl-hz dns zones` | DNS zones |
| `kctl-hz dns records <zone>` | DNS records |
| `kctl-hz dns create-record <zone> --type --name --value [--ttl]` | Create record |
| `kctl-hz dns delete-record <id> [--force]` | Delete record |

### Costs

| Command | Description |
|---------|-------------|
| `kctl-hz costs estimate` | Monthly cost breakdown |

### Config

| Command | Description |
|---------|-------------|
| `kctl-hz config init` | First-time setup |
| `kctl-hz config show` | Show config (masked) |
| `kctl-hz config test` | Test connection |
| `kctl-hz config use <profile>` | Switch profile |

## Global Options

`--json` `--quiet` `-q` `--profile` `-p` `--token` `--dns-token` `--version` `-V`

## Server Management

```bash
kctl-hz servers create my-server --type cx22 --image ubuntu-24.04 --location fsn1
kctl-hz servers reboot my-server
kctl-hz servers rebuild my-server --image ubuntu-24.04
kctl-hz servers resize my-server --type cx32
kctl-hz servers metrics my-server --type cpu
```

## Firewall Management

```bash
kctl-hz firewalls create my-fw
kctl-hz firewalls add-rule 12345 --direction in --protocol tcp --port 443 --source-ips 0.0.0.0/0
kctl-hz firewalls apply 12345 --server 67890
```

## Network Management

```bash
kctl-hz networks create my-net --ip-range 10.0.0.0/16
kctl-hz networks add-subnet 123 --type cloud --ip-range 10.0.1.0/24 --network-zone eu-central
kctl-hz networks attach-server 123 --server 456
```

## Load Balancer Setup

```bash
kctl-hz load-balancers create my-lb --type lb11 --location fsn1
kctl-hz load-balancers add-target my-lb --server 12345
kctl-hz load-balancers add-service my-lb --protocol http --listen-port 80 --dest-port 8080
```

## S3 Object Storage

```bash
kctl-hz s3 buckets
kctl-hz s3 ls my-bucket --prefix backups/
kctl-hz s3 cp ./local-file s3://my-bucket/remote-file
kctl-hz s3 sync ./local-dir s3://my-bucket/prefix/ --delete
```

## DNS (separate API, separate token)

```bash
kctl-hz dns zones
kctl-hz dns records kodeme.io
kctl-hz dns create-record kodeme.io --type A --name www --value 168.119.233.161
```

## Troubleshooting

- Server unreachable: `servers get <name>` → `firewalls list` → `ips list`
- Costs: `costs estimate` → monthly breakdown by resource type
- DNS: uses separate DNS API — if using Cloudflare DNS, use kctl-cloudflare instead
- Snapshots: `snapshots list` → `snapshots restore <server-id> --image <snapshot-id>`
- Labels: `labels list server <id>` → `labels set server <id> --labels env=prod`
