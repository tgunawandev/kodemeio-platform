# DNS Record Management

resource "cloudflare_record" "records" {
  for_each = var.dns_records

  zone_id  = cloudflare_zone.zones[each.value.zone_name].id
  name     = each.value.name
  type     = each.value.type
  value    = each.value.value
  ttl      = each.value.ttl
  proxied  = each.value.proxied
  priority = each.value.priority
  comment  = each.value.comment

  lifecycle {
    prevent_destroy = false
  }
}
