# DNS Zone Management

resource "cloudflare_zone" "zones" {
  for_each = var.zones

  account_id = local.account_id
  zone       = each.key
  plan       = each.value.plan
  jump_start = each.value.jump_start
  paused     = each.value.paused
  type       = each.value.type
}

# Zone settings override
resource "cloudflare_zone_settings_override" "settings" {
  for_each = var.zones

  zone_id = cloudflare_zone.zones[each.key].id

  settings {
    # SSL/TLS
    ssl                      = "strict"
    always_use_https         = "on"
    min_tls_version          = "1.2"
    automatic_https_rewrites = "on"
    opportunistic_encryption = "on"

    # Security
    security_level     = "medium"
    challenge_ttl      = 1800
    browser_check      = "on"
    email_obfuscation  = "on"
    hotlink_protection = "off"

    # Performance
    minify {
      css  = "on"
      js   = "on"
      html = "on"
    }
    brotli = "on"

    # Caching
    browser_cache_ttl = 14400
    cache_level       = "aggressive"
    development_mode  = "off"

    # Other
    http3          = "on"
    early_hints    = "on"
    zero_rtt       = "on"
    websockets     = "on"
    ip_geolocation = "on"
  }
}
