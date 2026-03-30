---
name: hetzner-admin
description: >
  Hetzner Cloud infrastructure administration via kctl-hetzner CLI. MUST use for ANY server, volume, firewall, network, or Hetzner Cloud operation. Triggers on: "kctl-hetzner", "hetzner", "create server", "firewall rule", "floating IP", "volume", "snapshot", "load balancer", "server cost", "hetzner DNS", or ANY Hetzner Cloud infrastructure task.
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
- **CLI**: `kctl-hetzner` (Python, installed via `uv tool install ./cli`)
- **Config**: `~/.config/kodemeio/config.yaml` → `profiles.<profile>.hetzner`

## Commands

### Status & Health

| Command | Description |
|---------|-------------|
| `kctl-hetzner status show` | Infrastructure dashboard |
| `kctl-hetzner health check` | Cloud + DNS API check |

### Servers

| Command | Description |
|---------|-------------|
| `kctl-hetzner servers list` | All servers |
| `kctl-hetzner servers get <name>` | Server details |
| `kctl-hetzner servers create <name> --type --image --location [--ssh-key ...]` | Create server |
| `kctl-hetzner servers delete <name> [--force]` | Delete server |
| `kctl-hetzner servers reboot <name>` | Reboot server |
| `kctl-hetzner servers shutdown <name>` | Graceful shutdown |
| `kctl-hetzner servers power-off <name>` | Force power off |
| `kctl-hetzner servers reset <name> [--force]` | Hard reset server |
| `kctl-hetzner servers rebuild <name> --image [--force]` | Reinstall OS |
| `kctl-hetzner servers resize <name> --type <new-type> [--upgrade-disk] [--force]` | Resize server |
| `kctl-hetzner servers rename <name> --name <new-name>` | Rename server |
| `kctl-hetzner servers enable-rescue <name> [--ssh-key ...] [--force]` | Enable rescue mode |
| `kctl-hetzner servers disable-rescue <name>` | Disable rescue mode |
| `kctl-hetzner servers console <name>` | Get VNC console URL |
| `kctl-hetzner servers metrics <name> [--type cpu/disk/network] [--start] [--end]` | Server metrics |

### Volumes

| Command | Description |
|---------|-------------|
| `kctl-hetzner volumes list` | All volumes |
| `kctl-hetzner volumes get <id>` | Volume details |
| `kctl-hetzner volumes create <name> [--size N] [--server] [--location]` | Create volume |
| `kctl-hetzner volumes attach <id> --server <server-id>` | Attach to server |
| `kctl-hetzner volumes detach <id>` | Detach from server |
| `kctl-hetzner volumes delete <id> [--force]` | Delete volume |
| `kctl-hetzner volumes extend <id> --size <new-size>` | Extend volume size |
| `kctl-hetzner volumes protect <id> [--enable/--disable]` | Toggle delete protection |

### Firewalls

| Command | Description |
|---------|-------------|
| `kctl-hetzner firewalls list` | All firewalls |
| `kctl-hetzner firewalls get <name>` | Firewall details + rules |
| `kctl-hetzner firewalls create <name>` | Create firewall |
| `kctl-hetzner firewalls delete <id> [--force]` | Delete firewall |
| `kctl-hetzner firewalls add-rule <id> --direction <in/out> --protocol <tcp/udp/icmp> [--port] [--source-ips] [--destination-ips] [--description]` | Add firewall rule |
| `kctl-hetzner firewalls remove-rule <id> --direction --protocol [--port]` | Remove firewall rule |
| `kctl-hetzner firewalls apply <id> --server <server-id>` | Apply firewall to server |
| `kctl-hetzner firewalls remove-from <id> --server <server-id>` | Remove firewall from server |

### Networks

| Command | Description |
|---------|-------------|
| `kctl-hetzner networks list` | All networks |
| `kctl-hetzner networks get <id>` | Network details |
| `kctl-hetzner networks create <name> --ip-range <cidr>` | Create network |
| `kctl-hetzner networks delete <id> [--force]` | Delete network |
| `kctl-hetzner networks add-subnet <id> --type <cloud/vswitch/server> --ip-range <cidr> --network-zone <zone>` | Add subnet |
| `kctl-hetzner networks remove-subnet <id> --ip-range <cidr> [--force]` | Remove subnet |
| `kctl-hetzner networks attach-server <id> --server <server-id> [--ip]` | Attach server to network |
| `kctl-hetzner networks detach-server <id> --server <server-id>` | Detach server from network |
| `kctl-hetzner networks change-ip-range <id> --ip-range <cidr>` | Change network IP range |
| `kctl-hetzner networks add-route <id> --destination <cidr> --gateway <ip>` | Add static route |
| `kctl-hetzner networks remove-route <id> --destination <cidr> --gateway <ip> [--force]` | Remove static route |

### SSH Keys

| Command | Description |
|---------|-------------|
| `kctl-hetzner ssh-keys list` | SSH keys |
| `kctl-hetzner ssh-keys create <name> --public-key <key>` | Add key |
| `kctl-hetzner ssh-keys delete <id> [--force]` | Remove key |

### IPs (Floating & Primary)

| Command | Description |
|---------|-------------|
| `kctl-hetzner ips list` | All floating + primary IPs |
| `kctl-hetzner ips get <id>` | Floating IP details |
| `kctl-hetzner ips create-floating --type <ipv4/ipv6> --location <loc> [--server] [--description] [--name]` | Create floating IP |
| `kctl-hetzner ips delete-floating <id> [--force]` | Delete floating IP |
| `kctl-hetzner ips assign <id> --server <server-id>` | Assign floating IP to server |
| `kctl-hetzner ips unassign <id>` | Unassign floating IP |
| `kctl-hetzner ips get-primary <id>` | Primary IP details |
| `kctl-hetzner ips create-primary --type <ipv4/ipv6> [--assignee-type] [--assignee-id] [--datacenter] [--name] [--auto-delete/--no-auto-delete]` | Create primary IP |
| `kctl-hetzner ips update-primary <id> [--name] [--auto-delete/--no-auto-delete]` | Update primary IP |
| `kctl-hetzner ips delete-primary <id> [--force]` | Delete primary IP |

### Snapshots

| Command | Description |
|---------|-------------|
| `kctl-hetzner snapshots list` | Server snapshots |
| `kctl-hetzner snapshots get <id>` | Snapshot details |
| `kctl-hetzner snapshots create <server-id> [--description]` | Create snapshot |
| `kctl-hetzner snapshots delete <id> [--force]` | Delete snapshot |
| `kctl-hetzner snapshots restore <server-id> --image <snapshot-id> [--force]` | Restore snapshot to server |
| `kctl-hetzner snapshots update <id> [--description]` | Update snapshot metadata |

### Load Balancers

| Command | Description |
|---------|-------------|
| `kctl-hetzner load-balancers list` | All load balancers |
| `kctl-hetzner load-balancers get <name>` | Load balancer details |
| `kctl-hetzner load-balancers create <name> [--type lb11] [--location] [--algorithm] [--network]` | Create load balancer |
| `kctl-hetzner load-balancers delete <name> [--force]` | Delete load balancer |
| `kctl-hetzner load-balancers update <name> --name <new-name>` | Rename load balancer |
| `kctl-hetzner load-balancers add-target <name> --server <id> [--use-private-ip]` | Add server target |
| `kctl-hetzner load-balancers remove-target <name> --server <id>` | Remove server target |
| `kctl-hetzner load-balancers add-service <name> --protocol --listen-port --dest-port [--health-check-path]` | Add service/listener |
| `kctl-hetzner load-balancers remove-service <name> --listen-port <port>` | Remove service/listener |

### Placement Groups

| Command | Description |
|---------|-------------|
| `kctl-hetzner placement-groups list` | All placement groups |
| `kctl-hetzner placement-groups get <name>` | Placement group details |
| `kctl-hetzner placement-groups create <name> [--type spread]` | Create placement group |
| `kctl-hetzner placement-groups delete <name> [--force]` | Delete placement group |

### S3 (Hetzner Object Storage)

| Command | Description |
|---------|-------------|
| `kctl-hetzner s3 buckets` | List S3 buckets |
| `kctl-hetzner s3 ls <bucket> [--prefix]` | List objects in bucket |
| `kctl-hetzner s3 size <bucket>` | Bucket size summary |
| `kctl-hetzner s3 cp <src> <dst> [--recursive]` | Copy files (local/S3) |
| `kctl-hetzner s3 sync <src> <dst> [--delete]` | Sync files (local/S3) |
| `kctl-hetzner s3 mb <name>` | Create bucket |
| `kctl-hetzner s3 rb <name> [--force]` | Remove bucket |

### Server Types

| Command | Description |
|---------|-------------|
| `kctl-hetzner server-types list` | Available server types |
| `kctl-hetzner server-types get <id>` | Server type details |

### Locations

| Command | Description |
|---------|-------------|
| `kctl-hetzner locations list` | Available locations |
| `kctl-hetzner locations get <id>` | Location details |
| `kctl-hetzner locations datacenters` | Available datacenters |

### Images

| Command | Description |
|---------|-------------|
| `kctl-hetzner images list [--type system/snapshot/backup/app] [--architecture x86/arm]` | List images |
| `kctl-hetzner images get <id>` | Image details |
| `kctl-hetzner images delete <id> [--force]` | Delete image (snapshots only) |
| `kctl-hetzner images update <id> [--description] [--type]` | Update image metadata |

### Labels

| Command | Description |
|---------|-------------|
| `kctl-hetzner labels list <resource-type> <resource-id>` | List labels on resource |
| `kctl-hetzner labels set <resource-type> <resource-id> --labels <key=val,...>` | Set labels on resource |
| `kctl-hetzner labels remove <resource-type> <resource-id> --key <key>` | Remove label from resource |

### Reverse DNS

| Command | Description |
|---------|-------------|
| `kctl-hetzner rdns get <resource-type> <resource-id>` | Get rDNS entries |
| `kctl-hetzner rdns set <resource-type> <resource-id> --ip <ip> --dns-ptr <hostname>` | Set rDNS pointer |
| `kctl-hetzner rdns delete <resource-type> <resource-id> --ip <ip> [--force]` | Delete rDNS pointer |

### DNS (separate API, separate token)

| Command | Description |
|---------|-------------|
| `kctl-hetzner dns zones` | DNS zones |
| `kctl-hetzner dns records <zone>` | DNS records |
| `kctl-hetzner dns create-record <zone> --type --name --value [--ttl]` | Create record |
| `kctl-hetzner dns delete-record <id> [--force]` | Delete record |

### Costs

| Command | Description |
|---------|-------------|
| `kctl-hetzner costs estimate` | Monthly cost breakdown |

### Config

| Command | Description |
|---------|-------------|
| `kctl-hetzner config init` | First-time setup |
| `kctl-hetzner config show` | Show config (masked) |
| `kctl-hetzner config test` | Test connection |
| `kctl-hetzner config use <profile>` | Switch profile |

## Global Options

`--json` `--quiet` `-q` `--profile` `-p` `--token` `--dns-token` `--version` `-V`

## Server Management

```bash
kctl-hetzner servers create my-server --type cx22 --image ubuntu-24.04 --location fsn1
kctl-hetzner servers reboot my-server
kctl-hetzner servers rebuild my-server --image ubuntu-24.04
kctl-hetzner servers resize my-server --type cx32
kctl-hetzner servers metrics my-server --type cpu
```

## Firewall Management

```bash
kctl-hetzner firewalls create my-fw
kctl-hetzner firewalls add-rule 12345 --direction in --protocol tcp --port 443 --source-ips 0.0.0.0/0
kctl-hetzner firewalls apply 12345 --server 67890
```

## Network Management

```bash
kctl-hetzner networks create my-net --ip-range 10.0.0.0/16
kctl-hetzner networks add-subnet 123 --type cloud --ip-range 10.0.1.0/24 --network-zone eu-central
kctl-hetzner networks attach-server 123 --server 456
```

## Load Balancer Setup

```bash
kctl-hetzner load-balancers create my-lb --type lb11 --location fsn1
kctl-hetzner load-balancers add-target my-lb --server 12345
kctl-hetzner load-balancers add-service my-lb --protocol http --listen-port 80 --dest-port 8080
```

## S3 Object Storage

```bash
kctl-hetzner s3 buckets
kctl-hetzner s3 ls my-bucket --prefix backups/
kctl-hetzner s3 cp ./local-file s3://my-bucket/remote-file
kctl-hetzner s3 sync ./local-dir s3://my-bucket/prefix/ --delete
```

## DNS (separate API, separate token)

```bash
kctl-hetzner dns zones
kctl-hetzner dns records kodeme.io
kctl-hetzner dns create-record kodeme.io --type A --name www --value 168.119.233.161
```

## Troubleshooting

- Server unreachable: `servers get <name>` → `firewalls list` → `ips list`
- Costs: `costs estimate` → monthly breakdown by resource type
- DNS: uses separate DNS API — if using Cloudflare DNS, use kctl-cloudflare instead
- Snapshots: `snapshots list` → `snapshots restore <server-id> --image <snapshot-id>`
- Labels: `labels list server <id>` → `labels set server <id> --labels env=prod`
