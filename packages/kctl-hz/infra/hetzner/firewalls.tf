# =============================================================================
# Firewalls
# =============================================================================

resource "hcloud_firewall" "firewalls" {
  for_each = var.firewalls
  name     = "${var.resource_prefix}-${each.key}"

  labels = merge(
    {
      managed_by  = "terraform"
      environment = var.environment
      project     = var.resource_prefix
    },
    each.value.labels
  )

  dynamic "rule" {
    for_each = each.value.rules
    content {
      direction       = rule.value.direction
      protocol        = rule.value.protocol
      port            = rule.value.port
      description     = rule.value.description
      source_ips      = rule.value.direction == "in" ? rule.value.source_ips : null
      destination_ips = rule.value.direction == "out" ? rule.value.destination_ips : null
    }
  }
}
