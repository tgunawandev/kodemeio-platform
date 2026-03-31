# R2 Storage

resource "cloudflare_r2_bucket" "buckets" {
  for_each = var.r2_buckets

  account_id = local.account_id
  name       = each.value.name
  location   = each.value.location
}
