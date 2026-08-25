# WAF & Firewall Rules

# Custom firewall rules
resource "cloudflare_ruleset" "custom_rules" {
  for_each = {
    for zone_name, zone in var.zones : zone_name => zone_name
    if length([for k, v in var.firewall_rules : v if v.zone_name == zone_name]) > 0
  }

  zone_id = cloudflare_zone.zones[each.key].id
  name    = "Custom firewall rules"
  kind    = "zone"
  phase   = "http_request_firewall_custom"

  dynamic "rules" {
    for_each = { for k, v in var.firewall_rules : k => v if v.zone_name == each.key }
    content {
      action      = rules.value.action
      expression  = rules.value.expression
      description = rules.value.description
      enabled     = rules.value.enabled
    }
  }
}

# IP Access Rules
resource "cloudflare_access_rule" "ip_rules" {
  for_each = var.ip_access_rules

  zone_id = cloudflare_zone.zones[each.value.zone_name].id
  mode    = each.value.mode
  notes   = each.value.notes

  configuration {
    target = "ip"
    value  = each.value.ip
  }
}

# Rate Limiting
resource "cloudflare_rate_limit" "limits" {
  for_each = var.rate_limits

  zone_id   = cloudflare_zone.zones[each.value.zone_name].id
  threshold = each.value.threshold
  period    = each.value.period

  match {
    request {
      url_pattern = each.value.match_url
    }
  }

  action {
    mode = each.value.action_mode
  }

  description = each.value.description
}
