# Cache Rules

# Cache rules via rulesets
resource "cloudflare_ruleset" "cache_rules" {
  for_each = {
    for zone_name, zone in var.zones : zone_name => zone_name
    if length([for k, v in var.cache_rules : v if v.zone_name == zone_name]) > 0
  }

  zone_id = cloudflare_zone.zones[each.key].id
  name    = "Cache rules"
  kind    = "zone"
  phase   = "http_request_cache_settings"

  dynamic "rules" {
    for_each = { for k, v in var.cache_rules : k => v if v.zone_name == each.key }
    content {
      action      = rules.value.action
      expression  = rules.value.expression
      description = rules.value.description
      enabled     = true

      action_parameters {
        cache = rules.value.action == "set_cache_settings" ? true : false

        dynamic "edge_ttl" {
          for_each = rules.value.edge_ttl != null ? [rules.value.edge_ttl] : []
          content {
            mode    = "override_origin"
            default = edge_ttl.value
          }
        }

        dynamic "browser_ttl" {
          for_each = rules.value.browser_ttl != null ? [rules.value.browser_ttl] : []
          content {
            mode    = "override_origin"
            default = browser_ttl.value
          }
        }
      }
    }
  }
}

# Page Rules (legacy, but still useful)
resource "cloudflare_page_rule" "rules" {
  for_each = var.page_rules

  zone_id  = cloudflare_zone.zones[each.value.zone_name].id
  target   = each.value.target
  priority = each.value.priority
  status   = each.value.status

  actions {
    cache_level       = lookup(each.value.actions, "cache_level", null)
    browser_cache_ttl = lookup(each.value.actions, "browser_cache_ttl", null) != null ? tonumber(each.value.actions["browser_cache_ttl"]) : null
    edge_cache_ttl    = lookup(each.value.actions, "edge_cache_ttl", null) != null ? tonumber(each.value.actions["edge_cache_ttl"]) : null
    ssl               = lookup(each.value.actions, "ssl", null)
  }
}
