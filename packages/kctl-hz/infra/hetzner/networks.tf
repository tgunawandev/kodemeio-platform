# =============================================================================
# Private Networks
# =============================================================================

resource "hcloud_network" "networks" {
  for_each = var.networks
  name     = "${var.resource_prefix}-${each.key}"
  ip_range = each.value.ip_range

  labels = {
    managed_by  = "terraform"
    environment = var.environment
    project     = var.resource_prefix
  }
}

resource "hcloud_network_subnet" "subnets" {
  for_each = {
    for item in flatten([
      for net_key, net in var.networks : [
        for idx, subnet in net.subnets : {
          key          = "${net_key}-${idx}"
          network_key  = net_key
          ip_range     = subnet.ip_range
          type         = subnet.type
          network_zone = subnet.network_zone
        }
      ]
    ]) : item.key => item
  }

  network_id   = hcloud_network.networks[each.value.network_key].id
  type         = each.value.type
  ip_range     = each.value.ip_range
  network_zone = each.value.network_zone
}
