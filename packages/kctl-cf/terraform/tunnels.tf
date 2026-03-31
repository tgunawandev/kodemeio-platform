# Cloudflare Tunnels (Zero Trust)

resource "cloudflare_tunnel" "tunnels" {
  for_each = var.tunnels

  account_id = local.account_id
  name       = each.key
  secret     = each.value.secret
}

resource "cloudflare_tunnel_config" "configs" {
  for_each = var.tunnels

  account_id = local.account_id
  tunnel_id  = cloudflare_tunnel.tunnels[each.key].id

  config {
    dynamic "ingress_rule" {
      for_each = each.value.config.ingress_rules
      content {
        hostname = ingress_rule.value.hostname
        path     = ingress_rule.value.path
        service  = ingress_rule.value.service
      }
    }
  }
}

# DNS CNAME records for tunnel hostnames
resource "cloudflare_record" "tunnel_cnames" {
  for_each = {
    for item in flatten([
      for tunnel_name, tunnel in var.tunnels : [
        for rule in tunnel.config.ingress_rules : {
          key         = "${tunnel_name}-${rule.hostname}"
          tunnel_name = tunnel_name
          hostname    = rule.hostname
          zone_name   = join(".", slice(split(".", rule.hostname), length(split(".", rule.hostname)) - 2, length(split(".", rule.hostname))))
        } if rule.hostname != null
      ]
    ]) : item.key => item
  }

  zone_id = cloudflare_zone.zones[each.value.zone_name].id
  name    = each.value.hostname
  type    = "CNAME"
  value   = "${cloudflare_tunnel.tunnels[each.value.tunnel_name].id}.cfargotunnel.com"
  proxied = true
}
