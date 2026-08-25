# =============================================================================
# Servers
# =============================================================================

resource "hcloud_server" "servers" {
  for_each    = var.servers
  name        = "${var.resource_prefix}-${each.key}"
  server_type = each.value.server_type
  image       = each.value.image
  location    = coalesce(each.value.location, var.location)
  ssh_keys    = [for key in each.value.ssh_keys : hcloud_ssh_key.keys[key].id]
  user_data   = each.value.user_data
  backups     = each.value.backups

  labels = merge(
    {
      managed_by  = "terraform"
      environment = var.environment
      project     = var.resource_prefix
      role        = each.key
    },
    each.value.labels
  )

  firewall_ids = [
    for fw in each.value.firewall_ids : hcloud_firewall.firewalls[fw].id
  ]

  delete_protection  = each.value.delete_protection
  rebuild_protection = each.value.delete_protection

  dynamic "network" {
    for_each = each.value.network != null ? [each.value.network] : []
    content {
      network_id = hcloud_network.networks[network.value].id
    }
  }

  lifecycle {
    ignore_changes = [
      ssh_keys,
      user_data,
    ]
  }
}

# =============================================================================
# Volumes (attached to servers)
# =============================================================================

resource "hcloud_volume" "volumes" {
  for_each = {
    for item in flatten([
      for srv_key, srv in var.servers : [
        for vol in srv.volumes : {
          key        = "${srv_key}-${vol.name}"
          name       = vol.name
          size       = vol.size
          format     = vol.format
          server_key = srv_key
          location   = coalesce(srv.location, var.location)
        }
      ]
    ]) : item.key => item
  }

  name     = "${var.resource_prefix}-${each.value.name}"
  size     = each.value.size
  format   = each.value.format
  location = each.value.location

  labels = {
    managed_by  = "terraform"
    environment = var.environment
    project     = var.resource_prefix
    server      = each.value.server_key
  }
}

resource "hcloud_volume_attachment" "attachments" {
  for_each  = hcloud_volume.volumes
  volume_id = each.value.id
  server_id = hcloud_server.servers[split("-", each.key)[0]].id
  automount = true
}
