# Hetzner API Reference

Quick reference for the Hetzner API endpoints used by `hcloud-mgr`.

## Cloud API (api.hetzner.cloud/v1)

### Servers

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/servers` | List all servers |
| GET | `/servers?name=NAME` | Get server by name |
| POST | `/servers` | Create server |
| PUT | `/servers/{id}` | Update server (rename, labels) |
| DELETE | `/servers/{id}` | Delete server |
| POST | `/servers/{id}/actions/poweron` | Power on |
| POST | `/servers/{id}/actions/poweroff` | Power off (hard) |
| POST | `/servers/{id}/actions/shutdown` | Shutdown (graceful) |
| POST | `/servers/{id}/actions/reboot` | Reboot (soft) |
| POST | `/servers/{id}/actions/reset` | Reset (hard) |
| POST | `/servers/{id}/actions/rebuild` | Rebuild from image |
| POST | `/servers/{id}/actions/change_type` | Resize server |
| POST | `/servers/{id}/actions/enable_rescue` | Enable rescue mode |
| POST | `/servers/{id}/actions/request_console` | Request VNC console |
| POST | `/servers/{id}/actions/create_image` | Create snapshot |

### Volumes

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/volumes` | List all volumes |
| POST | `/volumes` | Create volume |
| DELETE | `/volumes/{id}` | Delete volume |
| POST | `/volumes/{id}/actions/attach` | Attach to server |
| POST | `/volumes/{id}/actions/detach` | Detach from server |
| POST | `/volumes/{id}/actions/resize` | Resize volume |

### Firewalls

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/firewalls` | List all firewalls |
| POST | `/firewalls` | Create firewall |
| DELETE | `/firewalls/{id}` | Delete firewall |
| POST | `/firewalls/{id}/actions/set_rules` | Set all rules (replace) |
| POST | `/firewalls/{id}/actions/apply_to_resources` | Apply to server |
| POST | `/firewalls/{id}/actions/remove_from_resources` | Remove from server |

### Networks

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/networks` | List all networks |
| POST | `/networks` | Create network |
| DELETE | `/networks/{id}` | Delete network |
| POST | `/networks/{id}/actions/add_subnet` | Add subnet |
| POST | `/networks/{id}/actions/delete_subnet` | Remove subnet |
| POST | `/networks/{id}/actions/add_route` | Add route |
| POST | `/networks/{id}/actions/delete_route` | Remove route |

### SSH Keys

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/ssh_keys` | List all SSH keys |
| POST | `/ssh_keys` | Create SSH key |
| PUT | `/ssh_keys/{id}` | Update SSH key |
| DELETE | `/ssh_keys/{id}` | Delete SSH key |

### Floating IPs

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/floating_ips` | List all floating IPs |
| POST | `/floating_ips` | Create floating IP |
| DELETE | `/floating_ips/{id}` | Delete floating IP |
| POST | `/floating_ips/{id}/actions/assign` | Assign to server |
| POST | `/floating_ips/{id}/actions/unassign` | Unassign from server |

### Primary IPs

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/primary_ips` | List all primary IPs |

### Load Balancers

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/load_balancers` | List all load balancers |
| POST | `/load_balancers` | Create load balancer |
| DELETE | `/load_balancers/{id}` | Delete load balancer |
| POST | `/load_balancers/{id}/actions/add_target` | Add target server |
| POST | `/load_balancers/{id}/actions/remove_target` | Remove target |
| POST | `/load_balancers/{id}/actions/add_service` | Add service |
| POST | `/load_balancers/{id}/actions/delete_service` | Remove service |

### Images / Snapshots

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/images?type=snapshot` | List all snapshots |
| GET | `/images/{id}` | Get image details |
| DELETE | `/images/{id}` | Delete snapshot |

### Placement Groups

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/placement_groups` | List all placement groups |
| POST | `/placement_groups` | Create placement group |
| DELETE | `/placement_groups/{id}` | Delete placement group |

### Actions

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/actions/{id}` | Get action status |

### Reference Data

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/locations` | List all locations |
| GET | `/server_types` | List all server types |

## DNS API (dns.hetzner.com/api/v1)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/zones` | List all DNS zones |
| GET | `/zones?name=NAME` | Get zone by name |
| GET | `/records?zone_id=ID` | List records for zone |
| GET | `/records/{id}` | Get record details |
| POST | `/records` | Create DNS record |
| PUT | `/records/{id}` | Update DNS record |
| DELETE | `/records/{id}` | Delete DNS record |

### Authentication

- Cloud API: `Authorization: Bearer {HCLOUD_TOKEN}`
- DNS API: `Auth-API-Token: {HETZNER_DNS_TOKEN}`

### Pagination

Cloud API uses `page` and `per_page` query parameters:
```
GET /servers?page=1&per_page=50
```

Response includes pagination metadata:
```json
{
  "meta": {
    "pagination": {
      "page": 1,
      "per_page": 50,
      "previous_page": null,
      "next_page": 2,
      "last_page": 3,
      "total_entries": 150
    }
  }
}
```
