# Cloudflare Workers & KV

# KV Namespaces
resource "cloudflare_workers_kv_namespace" "namespaces" {
  for_each = var.kv_namespaces

  account_id = local.account_id
  title      = each.value.title
}

# Worker Scripts
resource "cloudflare_worker_script" "workers" {
  for_each = var.workers

  account_id = local.account_id
  name       = each.key
  content    = each.value.content
  module     = each.value.module
  logpush    = each.value.logpush

  dynamic "plain_text_binding" {
    for_each = [for b in each.value.bindings : b if b.type == "plain_text"]
    content {
      name = plain_text_binding.value.name
      text = plain_text_binding.value.text
    }
  }

  dynamic "kv_namespace_binding" {
    for_each = [for b in each.value.bindings : b if b.type == "kv_namespace"]
    content {
      name         = kv_namespace_binding.value.name
      namespace_id = cloudflare_workers_kv_namespace.namespaces[kv_namespace_binding.value.text].id
    }
  }
}

# Worker Routes
resource "cloudflare_worker_route" "routes" {
  for_each = var.worker_routes

  zone_id     = cloudflare_zone.zones[each.value.zone_name].id
  pattern     = each.value.pattern
  script_name = cloudflare_worker_script.workers[each.value.worker_name].name
}
