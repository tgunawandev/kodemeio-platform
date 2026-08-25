# Email Routing

# Enable email routing on zones
resource "cloudflare_email_routing_settings" "enabled" {
  for_each = var.email_routing_enabled

  zone_id = cloudflare_zone.zones[each.value].id
  enabled = true
}

# Email routing rules
resource "cloudflare_email_routing_rule" "rules" {
  for_each = var.email_routing_rules

  zone_id = cloudflare_zone.zones[each.value.zone_name].id
  name    = each.value.name
  enabled = each.value.enabled

  matcher {
    type  = each.value.match_type
    field = each.value.match_type == "literal" ? "to" : null
    value = each.value.match_value
  }

  action {
    type  = each.value.action_type
    value = each.value.action_value
  }
}

# Catch-all rules
resource "cloudflare_email_routing_catch_all" "catch_all" {
  for_each = var.email_routing_catch_all

  zone_id = cloudflare_zone.zones[each.value.zone_name].id
  name    = "Catch-all rule"
  enabled = each.value.enabled

  matcher {
    type = "all"
  }

  action {
    type  = each.value.action_type
    value = each.value.action_value
  }
}
