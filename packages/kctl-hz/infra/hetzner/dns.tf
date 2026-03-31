# =============================================================================
# DNS Management (Hetzner DNS API)
# =============================================================================

resource "hcloud_rdns" "server_ipv4" {
  for_each   = hcloud_server.servers
  server_id  = each.value.id
  ip_address = each.value.ipv4_address
  dns_ptr    = lookup(each.value.labels, "fqdn", "${each.value.name}.kodeme.io")
}

resource "hcloud_rdns" "server_ipv6" {
  for_each   = hcloud_server.servers
  server_id  = each.value.id
  ip_address = each.value.ipv6_address
  dns_ptr    = lookup(each.value.labels, "fqdn", "${each.value.name}.kodeme.io")
}
