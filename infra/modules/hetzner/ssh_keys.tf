# =============================================================================
# SSH Keys
# =============================================================================

resource "hcloud_ssh_key" "keys" {
  for_each   = var.ssh_keys
  name       = "${var.resource_prefix}-${each.key}"
  public_key = each.value.public_key
}
