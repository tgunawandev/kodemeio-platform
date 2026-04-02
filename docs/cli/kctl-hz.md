# kctl-hz

Command reference for `kctl-hz` (32 groups, ~133 commands).

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

### `kctl-hz ce`

Alias: costs estimate

### `kctl-hz config`

Manage CLI configuration and profiles.

| Command | Description |
|---------|-------------|
| `config init [--cloud_token] [--dns_token] [--name]` | Initialize CLI configuration. |
| `config show` | Show configuration. |
| `config test` | Test API connection. |
| `config use <name>` | Switch default profile. |

### `kctl-hz costs`

Estimate monthly infrastructure costs.

| Command | Description |
|---------|-------------|
| `costs estimate` | Estimate monthly costs for all Hetzner resources. |

### `kctl-hz dns`

Manage Hetzner DNS zones and records.

| Command | Description |
|---------|-------------|
| `dns create-record <zone_name> <record_type> <name> <value> [--ttl]` | Create a DNS record in a zone. |
| `dns delete-record <record_id> [--force]` | Delete a DNS record. |
| `dns records <zone_name>` | List DNS records for a zone. |
| `dns update-record <record_id> <zone_name> [--record_type] [--name] [--value] [--ttl]` | Update a DNS record. |
| `dns zones` | List all DNS zones. |

### `kctl-hz dz`

Alias: dns zones

### `kctl-hz firewalls`

Manage Hetzner Cloud firewalls.

| Command | Description |
|---------|-------------|
| `firewalls add-rule <firewall_id> <direction> <protocol> [--port] [--source_ips] [--destination_ips] [--description]` | Add a rule to a firewall (appends to existing rules). |
| `firewalls apply <firewall_id> <server>` | Apply a firewall to a server. |
| `firewalls create <name>` | Create a new firewall. |
| `firewalls delete <firewall_id> [--force]` | Delete a firewall. |
| `firewalls get <name>` | Get firewall details with rules. |
| `firewalls list` | List all firewalls. |
| `firewalls remove-from <firewall_id> <server>` | Remove a firewall from a server. |
| `firewalls remove-rule <firewall_id> <direction> <protocol> [--port]` | Remove a matching rule from a firewall. |
| `firewalls update <firewall_id> [--name] [--labels]` | Update a firewall (name, labels). |

### `kctl-hz fl`

Alias: firewalls list

### `kctl-hz hc`

Alias: health check

### `kctl-hz health`

Health checks.

| Command | Description |
|---------|-------------|
| `health check` | Check Hetzner Cloud + DNS API connectivity. |

### `kctl-hz images`

Manage Hetzner Cloud images (OS, snapshots, backups).

| Command | Description |
|---------|-------------|
| `images delete <image_id> [--force]` | Delete an image (only snapshots can be deleted). |
| `images get <image_id>` | Get details of an image. |
| `images list [--image_type] [--architecture]` | List images (optionally filtered by type). |
| `images update <image_id> [--description] [--image_type] [--labels]` | Update an image (description, type, labels). |

### `kctl-hz ips`

Manage Hetzner Cloud IP addresses.

| Command | Description |
|---------|-------------|
| `ips assign <ip_id> <server>` | Assign a floating IP to a server. |
| `ips create-floating <ip_type> <location> [--server] [--description] [--name]` | Create a new floating IP. |
| `ips create-primary <ip_type> [--assignee_type] [--assignee_id] [--datacenter] [--name] [--auto_delete]` | Create a new primary IP. |
| `ips delete-floating <ip_id> [--force]` | Delete a floating IP. |
| `ips delete-primary <ip_id> [--force]` | Delete a primary IP. |
| `ips get <ip_id>` | Get details of a floating IP. |
| `ips get-primary <ip_id>` | Get details of a primary IP. |
| `ips list` | List all floating and primary IPs. |
| `ips unassign <ip_id>` | Unassign a floating IP from its server. |
| `ips update-floating <ip_id> [--name] [--description] [--labels]` | Update a floating IP (name, description, labels). |
| `ips update-primary <ip_id> [--name] [--auto_delete] [--labels]` | Update a primary IP (name, auto-delete, labels). |

### `kctl-hz labels`

Manage labels on Hetzner Cloud resources.

| Command | Description |
|---------|-------------|
| `labels list <resource_type> <resource_id>` | Show labels on a resource. |
| `labels remove <resource_type> <resource_id> <key>` | Remove a label from a resource. |
| `labels set <resource_type> <resource_id> <labels>` | Set labels on a resource (merges with existing labels). |

### `kctl-hz load-balancers`

Manage Hetzner Cloud load balancers.

| Command | Description |
|---------|-------------|
| `load-balancers add-service <name> <protocol> <listen_port> <dest_port> [--health_check_path]` | Add a service (listener) to a load balancer. |
| `load-balancers add-target <name> <server> [--use_private_ip]` | Add a server target to a load balancer. |
| `load-balancers create <name> [--lb_type] [--location] [--algorithm] [--network]` | Create a new load balancer. |
| `load-balancers delete <name> [--force]` | Delete a load balancer. |
| `load-balancers get <name>` | Get load balancer details. |
| `load-balancers list` | List all load balancers. |
| `load-balancers remove-service <name> <listen_port>` | Remove a service (listener) from a load balancer. |
| `load-balancers remove-target <name> <server>` | Remove a server target from a load balancer. |
| `load-balancers update <name> [--new_name] [--labels]` | Update a load balancer (name, labels). |

### `kctl-hz locations`

Browse Hetzner Cloud locations and datacenters.

| Command | Description |
|---------|-------------|
| `locations datacenters` | List all available datacenters. |
| `locations get <location_id>` | Get details of a location. |
| `locations list` | List all available locations. |

### `kctl-hz networks`

Manage Hetzner Cloud networks.

| Command | Description |
|---------|-------------|
| `networks add-route <network_id> <destination> <gateway>` | Add a static route to a network. |
| `networks add-subnet <network_id> <subnet_type> <ip_range> <network_zone>` | Add a subnet to a network. |
| `networks attach-server <network_id> <server> [--ip]` | Attach a server to a network. |
| `networks change-ip-range <network_id> <ip_range>` | Change the IP range of a network. |
| `networks create <name> <ip_range>` | Create a new network. |
| `networks delete <network_id> [--force]` | Delete a network. |
| `networks detach-server <network_id> <server>` | Detach a server from a network. |
| `networks get <network_id>` | Get network details. |
| `networks list` | List all networks. |
| `networks remove-route <network_id> <destination> <gateway> [--force]` | Remove a static route from a network. |
| `networks remove-subnet <network_id> <ip_range> [--force]` | Remove a subnet from a network. |
| `networks update <network_id> [--name] [--labels]` | Update a network (name, labels). |

### `kctl-hz nl`

Alias: networks list

### `kctl-hz placement-groups`

Manage Hetzner Cloud placement groups.

| Command | Description |
|---------|-------------|
| `placement-groups create <name> [--pg_type]` | Create a new placement group. |
| `placement-groups delete <name> [--force]` | Delete a placement group. |
| `placement-groups get <name>` | Get placement group details. |
| `placement-groups list` | List all placement groups. |
| `placement-groups update <name> [--new_name] [--labels]` | Update a placement group (name, labels). |

### `kctl-hz rdns`

Manage reverse DNS entries on Hetzner Cloud resources.

| Command | Description |
|---------|-------------|
| `rdns delete <resource_type> <resource_id> <ip> [--force]` | Delete a reverse DNS entry (set to null). |
| `rdns get <resource_type> <resource_id>` | Show reverse DNS entries for a resource. |
| `rdns set <resource_type> <resource_id> <ip> <dns_ptr>` | Set a reverse DNS entry for a resource. |

### `kctl-hz s3`

Manage Hetzner S3-compatible object storage.

| Command | Description |
|---------|-------------|
| `s3 buckets` | List all S3 buckets. |
| `s3 cp <src> <dst> [--recursive]` | Copy files to/from S3. |
| `s3 ls <bucket> [--prefix]` | List objects in an S3 bucket. |
| `s3 mb <name>` | Create a new S3 bucket. |
| `s3 rb <name> [--force]` | Remove an S3 bucket. |
| `s3 size <bucket>` | Calculate total size of an S3 bucket. |
| `s3 sync <src> <dst> [--delete]` | Sync directories to/from S3 (incremental). |

### `kctl-hz sc`

Alias: servers create <name>

### `kctl-hz self-test`

CLI self-test and smoke test.

### `kctl-hz server-types`

Browse Hetzner Cloud server types.

| Command | Description |
|---------|-------------|
| `server-types get <type_id>` | Get details of a server type. |
| `server-types list` | List all available server types. |

### `kctl-hz servers`

Manage Hetzner Cloud servers.

| Command | Description |
|---------|-------------|
| `servers console <name>` | Request a VNC console URL for a server. |
| `servers create <name> [--server_type] [--image] [--location] [--ssh_keys]` | Create a new server. |
| `servers delete <name> [--force]` | Delete a server. |
| `servers disable-rescue <name>` | Disable rescue mode on a server. |
| `servers enable-rescue <name> [--ssh_key] [--force]` | Enable rescue mode on a server. |
| `servers get <name>` | Get server details. |
| `servers list` | List all servers. |
| `servers metrics <name> [--metric_type] [--start] [--end]` | Fetch server metrics (cpu, disk, network). |
| `servers power-off <name>` | Force power off a server. |
| `servers reboot <name>` | Reboot a server (soft reboot). |
| `servers rebuild <name> <image> [--force]` | Rebuild a server with a new image (destroys all data). |
| `servers reset <name> [--force]` | Hard reset a server (like pulling power). |
| `servers resize <name> <server_type> [--upgrade_disk] [--force]` | Resize a server to a different type. |
| `servers shutdown <name>` | Gracefully shut down a server. |
| `servers update <name> [--new_name] [--labels]` | Update a server (name, labels). |

### `kctl-hz sg`

Alias: servers get <name>

### `kctl-hz sl`

Alias: servers list

### `kctl-hz snapshots`

Manage Hetzner Cloud snapshots.

| Command | Description |
|---------|-------------|
| `snapshots create <server_id> [--description]` | Create a snapshot from a server. |
| `snapshots delete <snapshot_id> [--force]` | Delete a snapshot. |
| `snapshots get <snapshot_id>` | Get snapshot details. |
| `snapshots list` | List all snapshots. |
| `snapshots restore <server_id> <image> [--force]` | Restore a server from a snapshot (rebuilds the server). |
| `snapshots update <snapshot_id> [--description] [--labels]` | Update a snapshot (description, labels). |

### `kctl-hz ss`

Alias: status show

### `kctl-hz ssh-keys`

Manage Hetzner Cloud SSH keys.

| Command | Description |
|---------|-------------|
| `ssh-keys create <name> <public_key>` | Create (register) a new SSH key. |
| `ssh-keys delete <key_id> [--force]` | Delete an SSH key. |
| `ssh-keys list` | List all SSH keys. |
| `ssh-keys update <key_id> [--name] [--labels]` | Update an SSH key (name, labels). |

### `kctl-hz status`

Infrastructure dashboard.

| Command | Description |
|---------|-------------|
| `status show` | Show infrastructure dashboard. |

### `kctl-hz storage-boxes`

Manage Hetzner Storage Boxes (Robot API).

| Command | Description |
|---------|-------------|
| `storage-boxes create-snapshot <storagebox_id>` | Create a snapshot of a Storage Box. |
| `storage-boxes delete-snapshot <storagebox_id> <snapshot_name> [--force]` | Delete a Storage Box snapshot. |
| `storage-boxes get <storagebox_id>` | Get Storage Box details. |
| `storage-boxes list` | List all Storage Boxes. |
| `storage-boxes reset-password <storagebox_id> [--force]` | Reset the password of a Storage Box. |
| `storage-boxes snapshots <storagebox_id>` | List snapshots of a Storage Box. |
| `storage-boxes subaccounts <storagebox_id>` | List sub-accounts of a Storage Box. |
| `storage-boxes update <storagebox_id> [--name] [--webdav] [--samba] [--ssh] [--external_reachability] [--zfs]` | Update Storage Box settings. |

### `kctl-hz vl`

Alias: volumes list

### `kctl-hz volumes`

Manage Hetzner Cloud volumes.

| Command | Description |
|---------|-------------|
| `volumes attach <volume_id> <server_id>` | Attach a volume to a server. |
| `volumes create <name> [--size] [--server] [--location]` | Create a new volume. |
| `volumes delete <volume_id> [--force]` | Delete a volume. |
| `volumes detach <volume_id>` | Detach a volume from its server. |
| `volumes extend <volume_id> <size>` | Extend (resize) a volume to a larger size. |
| `volumes get <volume_id>` | Get volume details. |
| `volumes list` | List all volumes. |
| `volumes protect <volume_id> [--enable]` | Enable or disable delete protection on a volume. |
| `volumes update <volume_id> [--name] [--labels]` | Update a volume (name, labels). |
