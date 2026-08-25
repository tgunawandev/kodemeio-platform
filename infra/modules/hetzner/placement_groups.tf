# =============================================================================
# Placement Groups
# =============================================================================

resource "hcloud_placement_group" "groups" {
  for_each = var.placement_groups
  name     = "${var.resource_prefix}-${each.key}"
  type     = each.value.type

  labels = merge(
    {
      managed_by  = "terraform"
      environment = var.environment
      project     = var.resource_prefix
    },
    each.value.labels
  )
}
