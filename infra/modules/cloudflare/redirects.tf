# Redirect Rules (Bulk Redirects)

# Bulk redirect lists
resource "cloudflare_list" "redirect_lists" {
  for_each = var.redirect_lists

  account_id  = local.account_id
  name        = each.value.name
  description = each.value.description
  kind        = "redirect"

  dynamic "item" {
    for_each = each.value.items
    content {
      value {
        redirect {
          source_url            = item.value.source_url
          target_url            = item.value.target_url
          status_code           = item.value.status_code
          include_subdomains    = item.value.include_subdomains ? "enabled" : "disabled"
          subpath_matching      = item.value.subpath_matching ? "enabled" : "disabled"
          preserve_query_string = item.value.preserve_query_string ? "enabled" : "disabled"
          preserve_path_suffix  = item.value.preserve_path_suffix ? "enabled" : "disabled"
        }
      }
    }
  }
}

# Bulk redirect rules
resource "cloudflare_ruleset" "redirect_rules" {
  for_each = var.redirect_rules

  account_id = local.account_id
  name       = each.value.name
  kind       = "root"
  phase      = "http_request_redirect"

  rules {
    action      = "redirect"
    expression  = "http.request.full_uri in $${cloudflare_list.redirect_lists[each.value.list_key].id}"
    description = each.value.name
    enabled     = each.value.enabled

    action_parameters {
      from_list {
        name = cloudflare_list.redirect_lists[each.value.list_key].name
        key  = "http.request.full_uri"
      }
    }
  }
}
