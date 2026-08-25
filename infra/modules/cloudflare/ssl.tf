# SSL/TLS Configuration

# Origin CA certificates for end-to-end encryption
resource "cloudflare_origin_ca_certificate" "certs" {
  for_each = var.origin_certificates

  csr                = each.value.csr
  hostnames          = each.value.hostnames
  request_type       = each.value.request_type
  requested_validity = each.value.requested_validity

  lifecycle {
    create_before_destroy = true
  }
}

# Authenticated Origin Pulls (mTLS)
resource "cloudflare_authenticated_origin_pulls" "aop" {
  for_each = var.authenticated_origin_pulls

  zone_id = cloudflare_zone.zones[each.value].id
  enabled = true
}
